const WebSocket = require("ws")

const BASE = process.env.BASE || "http://localhost:8787"
const API = process.env.API || `${BASE}/api/world`

async function enter(name) {
  const res = await fetch(`${API}/enter?paid=1`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ name })
  })
  if (!res.ok) throw new Error(`enter failed: ${res.status} ${await res.text()}`)
  return res.json()
}

async function main() {
  const { token } = await enter("ws-smoke")
  const wsUrl = `${BASE.replace("http", "ws")}/ws/world-updates?token=${encodeURIComponent(token)}`

  await new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl)
    const timeout = setTimeout(() => reject(new Error("timeout_waiting_snapshot")), 5000)
    ws.on("message", (data) => {
      try {
        const msg = JSON.parse(String(data))
        if (msg.kind === "snapshot") {
          clearTimeout(timeout)
          ws.close()
          resolve()
        }
      } catch {}
    })
    ws.on("error", (e) => reject(e))
  })

  console.log("OK websocket snapshot received")
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})

