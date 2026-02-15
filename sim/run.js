const API = process.env.API || "http://localhost:8787/api/world"
const DURATION_MS = Number(process.env.DURATION_MS ?? "") || 20_000

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms))
}

async function enter(name) {
  const res = await fetch(`${API}/enter?paid=1`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ name })
  })
  if (!res.ok) throw new Error(`enter failed: ${res.status} ${await res.text()}`)
  return res.json()
}

async function call(token, path, body) {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json", authorization: `Bearer ${token}` },
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(`call failed ${path}: ${res.status} ${await res.text()}`)
  return res.json()
}

async function getState(token) {
  const res = await fetch(`${API}/state`, { headers: { authorization: `Bearer ${token}` } })
  if (!res.ok) throw new Error(`state failed: ${res.status} ${await res.text()}`)
  return res.json()
}

function pick(arr) {
  return arr[Math.floor(Math.random() * arr.length)]
}

async function agentLoop(agent, allAgentIds) {
  const resources = ["BASIC_SUPPLIES", "SHELTER_MATERIALS", "FOOD_WATER", "CRYSTALS", "RARE_RESOURCES"]
  const endAt = Date.now() + DURATION_MS
  while (true) {
    if (Date.now() >= endAt) return
    let state
    try {
      state = await getState(agent.token)
    } catch {
      return
    }
    if (state.status !== "ACTIVE") return
    const me = state.agents[agent.agentId]
    if (!me?.alive) return

    const moveDir = Math.random() < 0.6 ? 1 : -1
    const target = Math.min(7, Math.max(1, me.zoneId + moveDir))
    const r = Math.random()
    try {
      if (r < 0.45) {
        await call(agent.token, "/action", { type: "move", target_zone: target })
      } else if (r < 0.85) {
        await call(agent.token, "/action", { type: "collect", resource_type: pick(resources) })
      } else {
        const targetAgentId = pick(allAgentIds.filter((id) => id !== agent.agentId))
        await call(agent.token, "/trade", { targetAgentId, item: pick(resources), quantity: 1 })
      }
    } catch {
      return
    }

    await sleep(700 + Math.random() * 900)
  }
}

async function main() {
  const entered = await Promise.all([
    enter("alpha"),
    enter("bravo"),
    enter("charlie"),
    enter("delta")
  ])

  const allAgentIds = entered.map((a) => a.agentId)
  await Promise.all(entered.map((a) => agentLoop(a, allAgentIds)))
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
