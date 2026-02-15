import crypto from "node:crypto"
import { DEFAULT_DECAY_INTERVAL_MS, ZONES } from "./constants.js"

function nowIso() {
  return new Date().toISOString()
}

function clone(obj) {
  return JSON.parse(JSON.stringify(obj))
}

export function makeDefaultWorldState() {
  return {
    version: 1,
    createdAt: nowIso(),
    updatedAt: nowIso(),
    status: "ACTIVE",
    config: {
      decayIntervalMs: DEFAULT_DECAY_INTERVAL_MS
    },
    zones: ZONES.map((z, idx) => ({
      id: z.id,
      name: z.name,
      decayOrder: idx + 1,
      alive: true,
      decayedAt: null,
      resources: clone(z.resources)
    })),
    agents: {},
    trades: {},
    events: [],
    nextDecayAt: new Date(Date.now() + DEFAULT_DECAY_INTERVAL_MS).toISOString(),
    prizePool: {
      asset: "MON",
      total: "0"
    }
  }
}

export class WorldEngine {
  constructor(state, { onPersist, onEvent } = {}) {
    this.state = state
    this.onPersist = onPersist
    this.onEvent = onEvent
    this.processing = false
    this.actionQueue = []
    this.decayTimer = null
  }

  start() {
    if (this.decayTimer) return
    this.decayTimer = setInterval(() => {
      this.enqueueSystemAction({ type: "__DECAY_TICK__" })
    }, 1_000)
  }

  stop() {
    if (this.decayTimer) clearInterval(this.decayTimer)
    this.decayTimer = null
  }

  getSnapshot() {
    return clone(this.state)
  }

  getZones() {
    return this.state.zones.map((z) => clone(z))
  }

  getAgent(agentId) {
    const a = this.state.agents[agentId]
    return a ? clone(a) : null
  }

  getAgentByToken(token) {
    const agentIds = Object.keys(this.state.agents)
    for (const id of agentIds) {
      if (this.state.agents[id].token === token) return this.state.agents[id]
    }
    return null
  }

  registerAgent({ name } = {}) {
    const id = crypto.randomUUID()
    const token = crypto.randomUUID()
    const agent = {
      id,
      name: name || `agent-${id.slice(0, 6)}`,
      token,
      zoneId: 1,
      alive: true,
      eliminatedAt: null,
      inventory: {
        BASIC_SUPPLIES: 0,
        SHELTER_MATERIALS: 0,
        FOOD_WATER: 0,
        CRYSTALS: 0,
        RARE_RESOURCES: 0
      },
      createdAt: nowIso(),
      updatedAt: nowIso()
    }
    this.state.agents[id] = agent
    this.appendEvent({
      type: "AGENT_ENTERED",
      agentId: id,
      name: agent.name,
      zoneId: agent.zoneId
    })
    this.touch()
    this.persistSoon()
    return { id, token }
  }

  enqueueAction(agentId, action) {
    this.actionQueue.push({ kind: "agent", agentId, action })
    this.processQueue()
  }

  enqueueSystemAction(action) {
    this.actionQueue.push({ kind: "system", agentId: null, action })
    this.processQueue()
  }

  async processQueue() {
    if (this.processing) return
    this.processing = true
    try {
      while (this.actionQueue.length > 0) {
        const item = this.actionQueue.shift()
        if (!item) continue
        if (this.state.status !== "ACTIVE" && item.action.type !== "__DECAY_TICK__") {
          continue
        }
        if (item.kind === "system") {
          this.applySystemAction(item.action)
        } else {
          this.applyAgentAction(item.agentId, item.action)
        }
      }
    } finally {
      this.processing = false
    }
  }

  applySystemAction(action) {
    if (action.type !== "__DECAY_TICK__") return

    const now = Date.now()
    const nextDecayAtMs = Date.parse(this.state.nextDecayAt)
    if (!Number.isFinite(nextDecayAtMs) || now < nextDecayAtMs) return

    const nextAliveZone = this.state.zones.find((z) => z.alive && z.id !== 7)
    if (!nextAliveZone) {
      this.state.status = "FINISHED"
      this.appendEvent({ type: "WORLD_FINISHED" })
      this.touch()
      this.persistSoon()
      return
    }

    nextAliveZone.alive = false
    nextAliveZone.decayedAt = nowIso()
    this.appendEvent({ type: "ZONE_DECAYED", zoneId: nextAliveZone.id, name: nextAliveZone.name })

    const agents = Object.values(this.state.agents)
    for (const a of agents) {
      if (a.alive && a.zoneId === nextAliveZone.id) {
        a.alive = false
        a.eliminatedAt = nowIso()
        a.updatedAt = nowIso()
        this.appendEvent({ type: "AGENT_ELIMINATED", agentId: a.id, zoneId: a.zoneId })
      }
    }

    const next = new Date(Date.now() + this.state.config.decayIntervalMs).toISOString()
    this.state.nextDecayAt = next
    this.touch()
    this.persistSoon()
  }

  applyAgentAction(agentId, action) {
    const agent = this.state.agents[agentId]
    if (!agent || !agent.alive) return

    switch (action.type) {
      case "move":
        this.actionMove(agent, action)
        break
      case "collect":
        this.actionCollect(agent, action)
        break
      case "trade":
        this.actionTrade(agent, action)
        break
      case "accept_trade":
        this.actionAcceptTrade(agent, action)
        break
      case "wait":
        this.appendEvent({ type: "AGENT_WAITED", agentId: agent.id, zoneId: agent.zoneId })
        agent.updatedAt = nowIso()
        this.touch()
        this.persistSoon()
        break
      default:
        this.appendEvent({ type: "ACTION_REJECTED", agentId: agent.id, reason: "unknown_action" })
    }
  }

  actionMove(agent, action) {
    const targetZoneId = Number(action.target_zone)
    if (!Number.isInteger(targetZoneId)) {
      this.appendEvent({ type: "ACTION_REJECTED", agentId: agent.id, reason: "invalid_target_zone" })
      return
    }
    if (Math.abs(targetZoneId - agent.zoneId) !== 1) {
      this.appendEvent({ type: "ACTION_REJECTED", agentId: agent.id, reason: "non_adjacent_move" })
      return
    }
    const target = this.state.zones.find((z) => z.id === targetZoneId)
    if (!target || !target.alive) {
      this.appendEvent({ type: "ACTION_REJECTED", agentId: agent.id, reason: "zone_unavailable" })
      return
    }

    if (targetZoneId === 7) {
      const hasCrystal = (agent.inventory.CRYSTALS || 0) >= 1
      const hasFood = (agent.inventory.FOOD_WATER || 0) >= 1
      if (!hasCrystal || !hasFood) {
        this.appendEvent({
          type: "ACTION_REJECTED",
          agentId: agent.id,
          reason: "oasis_requirement_not_met",
          required: ["CRYSTALS>=1", "FOOD_WATER>=1"]
        })
        return
      }
    }

    const from = agent.zoneId
    agent.zoneId = targetZoneId
    agent.updatedAt = nowIso()
    this.appendEvent({ type: "AGENT_MOVED", agentId: agent.id, fromZoneId: from, toZoneId: targetZoneId })
    this.touch()
    this.persistSoon()
  }

  actionCollect(agent, action) {
    const resource = String(action.resource_type || "").toUpperCase()
    const zone = this.state.zones.find((z) => z.id === agent.zoneId)
    if (!zone || !zone.alive) {
      this.appendEvent({ type: "ACTION_REJECTED", agentId: agent.id, reason: "zone_unavailable" })
      return
    }
    const available = Number(zone.resources?.[resource] || 0)
    if (available <= 0) {
      this.appendEvent({ type: "ACTION_REJECTED", agentId: agent.id, reason: "resource_unavailable", resource })
      return
    }
    zone.resources[resource] = available - 1
    agent.inventory[resource] = Number(agent.inventory[resource] || 0) + 1
    agent.updatedAt = nowIso()
    this.appendEvent({ type: "RESOURCE_COLLECTED", agentId: agent.id, zoneId: agent.zoneId, resource, quantity: 1 })
    this.touch()
    this.persistSoon()
  }

  actionTrade(agent, action) {
    const targetAgentId = String(action.target_agent || "")
    const item = String(action.item || "").toUpperCase()
    const quantity = Number(action.quantity || 0)
    if (!targetAgentId || !this.state.agents[targetAgentId]) {
      this.appendEvent({ type: "ACTION_REJECTED", agentId: agent.id, reason: "invalid_target_agent" })
      return
    }
    if (!Number.isFinite(quantity) || quantity <= 0) {
      this.appendEvent({ type: "ACTION_REJECTED", agentId: agent.id, reason: "invalid_quantity" })
      return
    }
    if ((agent.inventory[item] || 0) < quantity) {
      this.appendEvent({ type: "ACTION_REJECTED", agentId: agent.id, reason: "insufficient_inventory" })
      return
    }

    const tradeId = crypto.randomUUID()
    this.state.trades[tradeId] = {
      id: tradeId,
      fromAgentId: agent.id,
      toAgentId: targetAgentId,
      item,
      quantity,
      status: "PENDING",
      createdAt: nowIso(),
      updatedAt: nowIso()
    }
    this.appendEvent({
      type: "TRADE_OFFERED",
      tradeId,
      fromAgentId: agent.id,
      toAgentId: targetAgentId,
      item,
      quantity
    })
    this.touch()
    this.persistSoon()
  }

  actionAcceptTrade(agent, action) {
    const tradeId = String(action.trade_id || "")
    const trade = this.state.trades[tradeId]
    if (!trade || trade.status !== "PENDING") {
      this.appendEvent({ type: "ACTION_REJECTED", agentId: agent.id, reason: "invalid_trade" })
      return
    }
    if (trade.toAgentId !== agent.id) {
      this.appendEvent({ type: "ACTION_REJECTED", agentId: agent.id, reason: "not_trade_target" })
      return
    }
    const from = this.state.agents[trade.fromAgentId]
    if (!from || !from.alive) {
      trade.status = "CANCELLED"
      trade.updatedAt = nowIso()
      this.appendEvent({ type: "TRADE_CANCELLED", tradeId, reason: "source_unavailable" })
      this.touch()
      this.persistSoon()
      return
    }
    if ((from.inventory[trade.item] || 0) < trade.quantity) {
      trade.status = "CANCELLED"
      trade.updatedAt = nowIso()
      this.appendEvent({ type: "TRADE_CANCELLED", tradeId, reason: "insufficient_source_inventory" })
      this.touch()
      this.persistSoon()
      return
    }

    from.inventory[trade.item] -= trade.quantity
    agent.inventory[trade.item] = Number(agent.inventory[trade.item] || 0) + trade.quantity
    from.updatedAt = nowIso()
    agent.updatedAt = nowIso()

    trade.status = "ACCEPTED"
    trade.updatedAt = nowIso()
    this.appendEvent({ type: "TRADE_ACCEPTED", tradeId, fromAgentId: from.id, toAgentId: agent.id })
    this.touch()
    this.persistSoon()
  }

  appendEvent(event) {
    const enriched = { id: crypto.randomUUID(), ts: nowIso(), ...event }
    this.state.events.push(enriched)
    if (this.state.events.length > 500) this.state.events.splice(0, this.state.events.length - 500)
    if (this.onEvent) this.onEvent(enriched)
  }

  touch() {
    this.state.updatedAt = nowIso()
  }

  persistSoon() {
    if (!this.onPersist) return
    Promise.resolve()
      .then(() => this.onPersist(this.state))
      .catch(() => {})
  }
}

