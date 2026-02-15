let socket = null
let latestState = null

function el(id) {
  return document.getElementById(id)
}

function fmtTime(iso) {
  try {
    return new Date(iso).toLocaleTimeString()
  } catch {
    return "-"
  }
}

function renderState(state) {
  latestState = state
  el("worldStatus").textContent = state.status || "-"
  el("nextDecay").textContent = state.nextDecayAt ? fmtTime(state.nextDecayAt) : "-"

  const zones = el("zones")
  zones.innerHTML = ""
  for (const z of state.zones || []) {
    const div = document.createElement("div")
    div.className = `zone ${z.alive ? "alive" : "dead"}`
    div.innerHTML = `
      <h4>Zone ${z.id}: ${z.name}</h4>
      <small>Status: ${z.alive ? "ALIVE" : "DECAYED"}</small>
      <small>Resources: ${Object.entries(z.resources || {})
        .map(([k, v]) => `${k}:${v}`)
        .join(" ")}</small>
    `
    zones.appendChild(div)
  }

  const aliveAgents = Object.values(state.agents || {}).filter((a) => a.alive)
  el("agents").textContent = aliveAgents.length
    ? aliveAgents.map((a) => `${a.name} @ Zone ${a.zoneId}`).join(", ")
    : "-"
}

function prependFeedLine(line) {
  const feed = el("feed")
  const row = document.createElement("div")
  row.textContent = line
  feed.prepend(row)
}

function onEvent(evt) {
  const ts = evt.ts ? fmtTime(evt.ts) : "-"
  prependFeedLine(`${ts} ${evt.type} ${JSON.stringify(evt)}`)
}

function connect() {
  const token = el("token").value.trim()
  if (!token) {
    alert("Bearer token kosong.")
    return
  }

  if (socket) {
    socket.close()
    socket = null
  }

  const wsUrl = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/world-updates`
  socket = new WebSocket(`${wsUrl}?token=${encodeURIComponent(token)}`)

  socket.onmessage = (msg) => {
    try {
      const data = JSON.parse(msg.data)
      if (data.kind === "snapshot" && data.state) renderState(data.state)
      if (data.kind === "event" && data.event) onEvent(data.event)
    } catch {}
  }

  socket.onopen = () => {
    prependFeedLine(`${new Date().toLocaleTimeString()} connected`)
  }
  socket.onclose = () => {
    prependFeedLine(`${new Date().toLocaleTimeString()} disconnected`)
  }
}

el("connect").addEventListener("click", connect)
