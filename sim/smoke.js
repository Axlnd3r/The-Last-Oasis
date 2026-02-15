const API = process.env.API || "http://localhost:8787/api/world"

async function enter(name) {
  const res = await fetch(`${API}/enter?paid=1`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ name })
  })
  if (!res.ok) throw new Error(`enter failed: ${res.status} ${await res.text()}`)
  return res.json()
}

async function getState(token) {
  const res = await fetch(`${API}/state`, { headers: { authorization: `Bearer ${token}` } })
  if (!res.ok) throw new Error(`state failed: ${res.status} ${await res.text()}`)
  return res.json()
}

async function postAction(token, body) {
  const res = await fetch(`${API}/action`, {
    method: "POST",
    headers: { "content-type": "application/json", authorization: `Bearer ${token}` },
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(`action failed: ${res.status} ${await res.text()}`)
  return res.json()
}

async function main() {
  const { agentId, token } = await enter("smoke")
  await postAction(token, { type: "collect", resource_type: "BASIC_SUPPLIES" })
  const state = await getState(token)
  const me = state.agents[agentId]
  if (!me) throw new Error("agent missing from state")
  const candidates = [me.zoneId - 1, me.zoneId + 1]
  const aliveZoneIds = new Set((state.zones || []).filter((z) => z.alive).map((z) => z.id))
  const targetZoneId = candidates.find((z) => aliveZoneIds.has(z))
  if (typeof targetZoneId === "number") {
    await postAction(token, { type: "move", target_zone: targetZoneId })
    const state2 = await getState(token)
    const me2 = state2.agents[agentId]
    if (me2.zoneId !== targetZoneId) throw new Error(`move failed, zoneId=${me2.zoneId}`)
    console.log("OK", { agentId, zoneId: me2.zoneId })
    return
  }
  console.log("OK", { agentId, zoneId: me.zoneId, note: "no_adjacent_alive_zone_to_move" })
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
