import http from "node:http"
import path from "node:path"
import express from "express"
import { WebSocketServer } from "ws"
import { API_PREFIX, DEMO_ENTRY_FEE, WORLD_STATE_FILE } from "./constants.js"
import { makeAuthMiddleware } from "./auth.js"
import { loadJsonState, saveJsonState } from "./persistence.js"
import { makeDefaultWorldState, WorldEngine } from "./worldEngine.js"

const PORT = Number(process.env.PORT ?? "") || 8787

const app = express()
app.use(express.json({ limit: "256kb" }))

const state = await loadJsonState(WORLD_STATE_FILE, makeDefaultWorldState)

let wss = null
const world = new WorldEngine(state, {
  onPersist: async (nextState) => {
    await saveJsonState(WORLD_STATE_FILE, nextState)
  },
  onEvent: (event) => {
    if (!wss) return
    const payload = JSON.stringify({ kind: "event", event })
    for (const client of wss.clients) {
      if (client.readyState === 1) client.send(payload)
    }
  }
})

world.start()

app.get("/health", (req, res) => {
  res.json({ ok: true, status: world.state.status, updatedAt: world.state.updatedAt })
})

app.post(`${API_PREFIX}/enter`, (req, res) => {
  const paid = String(req.headers["x-mock-paid"] || "") === "true" || String(req.query.paid || "") === "1"
  if (!paid) {
    res
      .status(402)
      .set("X-Payment-Protocol", "x402")
      .json({
        error: "payment_required",
        protocol: "x402",
        entry_fee: DEMO_ENTRY_FEE,
        how_to_demo: "Retry the same request with header 'X-Mock-Paid: true' or query '?paid=1'."
      })
    return
  }

  const name = typeof req.body?.name === "string" ? req.body.name : undefined
  const { id, token } = world.registerAgent({ name })
  res.json({ agentId: id, token })
})

const requireAuth = makeAuthMiddleware(world)

app.get(`${API_PREFIX}/state`, requireAuth, (req, res) => {
  res.json(world.getSnapshot())
})

app.get(`${API_PREFIX}/zones`, requireAuth, (req, res) => {
  res.json({ zones: world.getZones(), nextDecayAt: world.state.nextDecayAt, status: world.state.status })
})

app.get(`${API_PREFIX}/state/agent/:id`, requireAuth, (req, res) => {
  const targetId = req.params.id
  if (targetId !== req.agent.id) {
    res.status(403).json({ error: "forbidden" })
    return
  }
  res.json({ agent: world.getAgent(targetId) })
})

app.post(`${API_PREFIX}/action`, requireAuth, (req, res) => {
  const action = req.body || {}
  if (!action || typeof action.type !== "string") {
    res.status(400).json({ error: "invalid_action" })
    return
  }
  world.enqueueAction(req.agent.id, action)
  res.json({ ok: true })
})

app.post(`${API_PREFIX}/trade`, requireAuth, (req, res) => {
  const { targetAgentId, item, quantity } = req.body || {}
  world.enqueueAction(req.agent.id, {
    type: "trade",
    target_agent: targetAgentId,
    item,
    quantity
  })
  res.json({ ok: true })
})

app.post(`${API_PREFIX}/claim-reward`, requireAuth, (req, res) => {
  if (world.state.status !== "FINISHED") {
    res.status(409).json({ error: "world_not_finished" })
    return
  }
  const aliveAgents = Object.values(world.state.agents).filter((a) => a.alive)
  const isSurvivor = aliveAgents.some((a) => a.id === req.agent.id)
  if (!isSurvivor) {
    res.status(403).json({ error: "not_a_survivor" })
    return
  }
  const share = 1 / Math.max(1, aliveAgents.length)
  res.json({ ok: true, message: "stub_claim", share })
})

app.use("/", express.static(path.resolve("public")))

const server = http.createServer(app)

wss = new WebSocketServer({ server, path: "/ws/world-updates" })

wss.on("connection", (ws, req) => {
  const url = new URL(req.url || "", `http://${req.headers.host}`)
  const tokenFromQuery = url.searchParams.get("token")
  const auth = req.headers.authorization || ""
  const tokenFromHeader = auth.startsWith("Bearer ") ? auth.slice("Bearer ".length) : null
  const token = tokenFromQuery || tokenFromHeader
  const agent = token ? world.getAgentByToken(token) : null
  if (!agent) {
    ws.close(1008, "missing_or_invalid_token")
    return
  }

  ws.send(JSON.stringify({ kind: "snapshot", state: world.getSnapshot() }))
})

server.listen(PORT, () => {
  // no-op
})
