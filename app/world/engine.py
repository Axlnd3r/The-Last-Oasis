from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Optional

from .rules import apply_world_tick, hazard_damage


def stable_unit(seed: str) -> float:
    h = hashlib.sha256(seed.encode("utf-8")).digest()
    n = int.from_bytes(h[:8], "big")
    return (n % 1_000_000) / 1_000_000.0


def make_tile(x: int, y: int) -> dict[str, Any]:
    r = stable_unit(f"resource:{x}:{y}")
    h = stable_unit(f"hazard:{x}:{y}")
    return {
        "degradation": 0.0,
        "resource": int(60 + r * 40),
        "hazard": float(0.05 + h * 0.25),
    }


@dataclass
class AgentState:
    agent_id: str
    x: int
    y: int
    hp: int
    inventory: dict[str, int]
    alive: bool
    # Reputation & Alliance Layer
    trust_score: float = 100.0  # 0-100, starts at neutral
    trade_history: list[dict[str, Any]] = None  # tracks trades with other agents
    betrayals: int = 0  # count of attacks after recent trades
    alliances: list[str] = None  # agent_ids of current allies

    def __post_init__(self):
        if self.trade_history is None:
            self.trade_history = []
        if self.alliances is None:
            self.alliances = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "x": self.x,
            "y": self.y,
            "hp": self.hp,
            "inventory": dict(self.inventory),
            "alive": self.alive,
            "trust_score": self.trust_score,
            "trade_history": list(self.trade_history),
            "betrayals": self.betrayals,
            "alliances": list(self.alliances),
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "AgentState":
        return AgentState(
            agent_id=str(d["agent_id"]),
            x=int(d["x"]),
            y=int(d["y"]),
            hp=int(d["hp"]),
            inventory={str(k): int(v) for k, v in dict(d.get("inventory", {})).items()},
            alive=bool(d.get("alive", True)),
            trust_score=float(d.get("trust_score", 100.0)),
            trade_history=list(d.get("trade_history", [])),
            betrayals=int(d.get("betrayals", 0)),
            alliances=list(d.get("alliances", [])),
        )


class WorldState:
    def __init__(self, size: int, tick: int = 0) -> None:
        self.size = size
        self.tick = tick
        self.grid: list[list[dict[str, Any]]] = [
            [make_tile(x, y) for x in range(size)] for y in range(size)
        ]
        self.agents: dict[str, AgentState] = {}
        # Dynamic Market Pricing
        self.market_price: float = 1.0  # base price per resource unit
        self.recent_trades: list[dict[str, Any]] = []  # last 20 trades for betrayal detection
        # On-chain State Anchoring
        self.last_anchor_tick: int = 0
        self.state_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "size": self.size,
            "tick": self.tick,
            "grid": self.grid,
            "agents": {k: v.to_dict() for k, v in self.agents.items()},
            "market_price": self.market_price,
            "recent_trades": self.recent_trades,
            "last_anchor_tick": self.last_anchor_tick,
            "state_hash": self.state_hash,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "WorldState":
        ws = WorldState(size=int(d["size"]), tick=int(d["tick"]))
        ws.grid = d["grid"]
        ws.agents = {k: AgentState.from_dict(v) for k, v in dict(d.get("agents", {})).items()}
        ws.market_price = float(d.get("market_price", 1.0))
        ws.recent_trades = list(d.get("recent_trades", []))
        ws.last_anchor_tick = int(d.get("last_anchor_tick", 0))
        ws.state_hash = str(d.get("state_hash", ""))
        return ws

    def add_agent(self, agent_id: str) -> AgentState:
        center_x = self.size // 2 - 1
        center_y = self.size // 2 - 1
        inner_r = 2
        outer_r = 3

        def spawn_coords(attempt: int) -> tuple[int, int]:
            sx = stable_unit(f"spawnx:{agent_id}:{attempt}")
            sy = stable_unit(f"spawny:{agent_id}:{attempt}")
            dx = int((sx - 0.5) * 2 * outer_r)
            dy = int((sy - 0.5) * 2 * outer_r)
            x = center_x + dx
            y = center_y + dy
            if x < 0:
                x = 0
            elif x >= self.size:
                x = self.size - 1
            if y < 0:
                y = 0
            elif y >= self.size:
                y = self.size - 1
            return x, y

        x, y = spawn_coords(0)
        for attempt in range(1, 8):
            dx = x - center_x
            dy = y - center_y
            dist2 = dx * dx + dy * dy
            if inner_r * inner_r <= dist2 <= outer_r * outer_r:
                break
            x, y = spawn_coords(attempt)

        a = AgentState(
            agent_id=agent_id,
            x=x,
            y=y,
            hp=20,
            inventory={"resource": 0},
            alive=True,
        )
        self.agents[agent_id] = a
        return a

    def reset_environment(self) -> None:
        self.grid = [[make_tile(x, y) for x in range(self.size)] for y in range(self.size)]

    def reset_session(self) -> None:
        self.reset_environment()
        self.agents.clear()

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.size and 0 <= y < self.size

    def tile_at(self, x: int, y: int) -> dict[str, Any]:
        return self.grid[y][x]

    def calculate_market_price(self) -> float:
        """Dynamic pricing based on scarcity and degradation"""
        # Calculate total available resources
        total_resources = sum(tile["resource"] for row in self.grid for tile in row)
        max_resources = self.size * self.size * 100  # theoretical max
        scarcity = 1.0 - (total_resources / max_resources)

        # Calculate average degradation
        total_deg = sum(tile["degradation"] for row in self.grid for tile in row)
        avg_degradation = total_deg / (self.size * self.size)

        # Price increases with scarcity and degradation
        # Base price 1.0, can go up to 5.0
        base_price = 1.0
        scarcity_multiplier = 1 + (scarcity * 2.5)  # 1.0 to 3.5
        degradation_multiplier = 1 + (avg_degradation * 1.5)  # 1.0 to 2.5

        price = base_price * scarcity_multiplier * degradation_multiplier
        return min(5.0, price)  # cap at 5.0

    def compute_state_hash(self) -> str:
        """Compute deterministic hash of world state for on-chain anchoring"""
        import json
        # Create a deterministic snapshot of critical state
        state_snapshot = {
            "tick": self.tick,
            "agents": {
                aid: {
                    "x": a.x, "y": a.y, "hp": a.hp,
                    "resources": a.inventory.get("resource", 0),
                    "alive": a.alive,
                    "trust": round(a.trust_score, 2),
                }
                for aid, a in sorted(self.agents.items())
            },
            "total_degradation": sum(tile["degradation"] for row in self.grid for tile in row),
            "total_resources": sum(tile["resource"] for row in self.grid for tile in row),
        }
        state_json = json.dumps(state_snapshot, sort_keys=True)
        return hashlib.sha256(state_json.encode()).hexdigest()

    def update_reputation(self, agent_id: str, change: float, reason: str) -> dict[str, Any]:
        """Update agent reputation and emit event"""
        agent = self.agents.get(agent_id)
        if not agent:
            return {}

        old_score = agent.trust_score
        agent.trust_score = max(0.0, min(100.0, agent.trust_score + change))

        return {
            "type": "REPUTATION_CHANGED",
            "tick": self.tick,
            "agent_id": agent_id,
            "old_score": round(old_score, 1),
            "new_score": round(agent.trust_score, 1),
            "change": round(change, 1),
            "reason": reason,
        }

    def detect_betrayal(self, attacker_id: str, victim_id: str) -> bool:
        """Check if attacker recently traded with victim (betrayal)"""
        # Check if there was a trade between these agents in last 10 ticks
        for trade in self.recent_trades:
            if self.tick - trade.get("tick", 0) > 10:
                continue
            if (trade.get("agent_id") == attacker_id and trade.get("target_id") == victim_id) or \
               (trade.get("agent_id") == victim_id and trade.get("target_id") == attacker_id):
                return True
        return False

    def step(self, actions: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        self.tick += 1
        tick = self.tick
        events: list[dict[str, Any]] = []

        # Update market price based on scarcity
        old_price = self.market_price
        self.market_price = self.calculate_market_price()
        if abs(self.market_price - old_price) > 0.05:
            events.append({
                "type": "MARKET_PRICE_UPDATED",
                "tick": tick,
                "old_price": round(old_price, 3),
                "new_price": round(self.market_price, 3),
            })

        # Apply world tick to all tiles
        for y in range(self.size):
            for x in range(self.size):
                apply_world_tick(self.grid[y][x], tick)

        # Reputation decay every 10 ticks (0.5 points toward neutral 100.0)
        if tick % 10 == 0:
            for agent in self.agents.values():
                if agent.trust_score > 100.0:
                    agent.trust_score = max(100.0, agent.trust_score - 0.5)
                elif agent.trust_score < 100.0:
                    agent.trust_score = min(100.0, agent.trust_score + 0.5)

        # Process agent actions
        for agent_id, agent in list(self.agents.items()):
            if not agent.alive:
                continue
            action = actions.get(agent_id) or {"type": "rest"}
            events.extend(self.apply_action(agent, action))

        # Apply hazard damage
        for agent_id, agent in list(self.agents.items()):
            if not agent.alive:
                continue
            t = self.tile_at(agent.x, agent.y)
            dmg = hazard_damage(float(t["hazard"]), float(t["degradation"]))
            if dmg > 0:
                agent.hp -= dmg
                events.append(
                    {"type": "AGENT_DAMAGED", "tick": tick, "agent_id": agent_id, "amount": dmg}
                )
                if agent.hp <= 0:
                    agent.hp = 0
                    agent.alive = False
                    events.append(
                        {"type": "AGENT_DIED", "tick": tick, "agent_id": agent_id, "x": agent.x, "y": agent.y}
                    )

        # Compute state hash every 50 ticks for on-chain anchoring
        if tick % 50 == 0:
            self.state_hash = self.compute_state_hash()
            self.last_anchor_tick = tick
            events.append({
                "type": "STATE_ANCHORED",
                "tick": tick,
                "state_hash": self.state_hash,
                "alive_agents": sum(1 for a in self.agents.values() if a.alive),
            })

        events.append({"type": "TICK_DONE", "tick": tick})
        return events

    def apply_action(self, agent: AgentState, action: dict[str, Any]) -> list[dict[str, Any]]:
        t = self.tick
        kind = str(action.get("type") or "rest")
        events: list[dict[str, Any]] = []

        if kind == "move":
            dx = int(action.get("dx") or 0)
            dy = int(action.get("dy") or 0)
            nx, ny = agent.x + dx, agent.y + dy
            if abs(dx) + abs(dy) != 1 or not self.in_bounds(nx, ny):
                events.append({"type": "ACTION_REJECTED", "tick": t, "agent_id": agent.agent_id, "reason": "invalid_move"})
                return events
            agent.x, agent.y = nx, ny
            events.append({"type": "AGENT_MOVED", "tick": t, "agent_id": agent.agent_id, "x": nx, "y": ny})
            return events

        if kind == "gather":
            tile = self.tile_at(agent.x, agent.y)
            available = int(tile["resource"])
            if available <= 0:
                events.append({"type": "ACTION_REJECTED", "tick": t, "agent_id": agent.agent_id, "reason": "no_resource"})
                return events
            tile["resource"] = available - 1
            agent.inventory["resource"] = int(agent.inventory.get("resource", 0)) + 1
            events.append({"type": "RESOURCE_GATHERED", "tick": t, "agent_id": agent.agent_id, "amount": 1})
            return events

        if kind == "rest":
            if agent.hp < 20:
                agent.hp = min(20, agent.hp + 1)
                events.append({"type": "AGENT_RESTED", "tick": t, "agent_id": agent.agent_id, "hp": agent.hp})
            return events

        if kind == "trade":
            target_id = str(action.get("target") or "")
            amount = max(0, int(action.get("amount") or 0))
            target = self.agents.get(target_id)
            if target is None or not target.alive:
                events.append({"type": "ACTION_REJECTED", "tick": t, "agent_id": agent.agent_id, "reason": "invalid_trade_target"})
                return events
            if amount <= 0 or int(agent.inventory.get("resource", 0)) < amount:
                events.append({"type": "ACTION_REJECTED", "tick": t, "agent_id": agent.agent_id, "reason": "insufficient_resource"})
                return events

            # Execute trade
            agent.inventory["resource"] = int(agent.inventory.get("resource", 0)) - amount
            target.inventory["resource"] = int(target.inventory.get("resource", 0)) + amount

            # Calculate trade value based on market price
            trade_value = amount * self.market_price

            # Record trade in history for both agents
            trade_record = {
                "tick": t,
                "partner": target_id,
                "amount": amount,
                "value": round(trade_value, 2),
                "role": "giver",
            }
            agent.trade_history.append(trade_record)
            if len(agent.trade_history) > 50:
                agent.trade_history = agent.trade_history[-50:]

            target.trade_history.append({
                "tick": t,
                "partner": agent.agent_id,
                "amount": amount,
                "value": round(trade_value, 2),
                "role": "receiver",
            })
            if len(target.trade_history) > 50:
                target.trade_history = target.trade_history[-50:]

            # Track in recent_trades for betrayal detection
            self.recent_trades.append({
                "tick": t,
                "agent_id": agent.agent_id,
                "target_id": target_id,
                "amount": amount,
            })
            if len(self.recent_trades) > 20:
                self.recent_trades = self.recent_trades[-20:]

            # Increase trust scores for both parties (cooperation)
            trust_gain = min(5.0, amount * 0.5)  # up to +5 per trade
            rep_event_1 = self.update_reputation(agent.agent_id, trust_gain, "successful_trade")
            rep_event_2 = self.update_reputation(target_id, trust_gain, "successful_trade")

            events.append({
                "type": "TRADE_COMPLETED",
                "tick": t,
                "agent_id": agent.agent_id,
                "target_id": target_id,
                "amount": amount,
                "market_price": round(self.market_price, 3),
                "trade_value": round(trade_value, 2),
            })
            if rep_event_1:
                events.append(rep_event_1)
            if rep_event_2:
                events.append(rep_event_2)

            return events

        if kind == "attack":
            target_id = str(action.get("target") or "")
            target = self.agents.get(target_id)
            if target is None or not target.alive:
                events.append({"type": "ACTION_REJECTED", "tick": t, "agent_id": agent.agent_id, "reason": "invalid_attack_target"})
                return events
            # Must be adjacent (Manhattan distance 1)
            dist = abs(agent.x - target.x) + abs(agent.y - target.y)
            if dist > 1:
                events.append({"type": "ACTION_REJECTED", "tick": t, "agent_id": agent.agent_id, "reason": "target_not_adjacent"})
                return events

            # Detect betrayal (attacking recent trade partner)
            is_betrayal = self.detect_betrayal(agent.agent_id, target_id)

            # Attack damage: base 3, attacker spends 1 HP as stamina cost
            atk_dmg = 3
            agent.hp = max(0, agent.hp - 1)
            target.hp -= atk_dmg
            events.append({
                "type": "COMBAT_HIT", "tick": t,
                "agent_id": agent.agent_id, "target_id": target_id,
                "damage": atk_dmg, "attacker_hp": agent.hp, "target_hp": target.hp,
                "is_betrayal": is_betrayal,
            })

            # Handle betrayal reputation penalty
            if is_betrayal:
                agent.betrayals += 1
                rep_event = self.update_reputation(agent.agent_id, -25.0, "betrayal")
                if rep_event:
                    events.append(rep_event)
                events.append({
                    "type": "BETRAYAL_DETECTED",
                    "tick": t,
                    "betrayer_id": agent.agent_id,
                    "victim_id": target_id,
                    "total_betrayals": agent.betrayals,
                })
            else:
                # Normal combat, small reputation penalty
                rep_event = self.update_reputation(agent.agent_id, -3.0, "combat")
                if rep_event:
                    events.append(rep_event)

            # Loot on kill: attacker steals half of victim's resources
            if target.hp <= 0:
                target.hp = 0
                target.alive = False
                loot = int(target.inventory.get("resource", 0)) // 2
                if loot > 0:
                    target.inventory["resource"] = int(target.inventory.get("resource", 0)) - loot
                    agent.inventory["resource"] = int(agent.inventory.get("resource", 0)) + loot
                events.append({
                    "type": "COMBAT_KILL", "tick": t,
                    "agent_id": agent.agent_id, "target_id": target_id,
                    "loot": loot,
                })
            if agent.hp <= 0:
                agent.hp = 0
                agent.alive = False
                events.append({"type": "AGENT_DIED", "tick": t, "agent_id": agent.agent_id, "x": agent.x, "y": agent.y})
            return events

        events.append({"type": "ACTION_REJECTED", "tick": t, "agent_id": agent.agent_id, "reason": "unknown_action"})
        return events


def extract_observation(world: WorldState, agent_id: str, radius: int) -> Optional[dict[str, Any]]:
    agent = world.agents.get(agent_id)
    if agent is None:
        return None
    if not agent.alive:
        return {"tick": world.tick, "agent": agent.to_dict(), "tiles": [], "radius": radius}

    tiles: list[dict[str, Any]] = []
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            x, y = agent.x + dx, agent.y + dy
            if not world.in_bounds(x, y):
                continue
            tile = world.tile_at(x, y)
            tiles.append(
                {
                    "x": x,
                    "y": y,
                    "degradation": float(tile["degradation"]),
                    "resource": int(tile["resource"]),
                    "hazard": float(tile["hazard"]),
                }
            )

    nearby_agents: list[dict[str, Any]] = []
    all_agents: list[dict[str, Any]] = []
    for other in world.agents.values():
        if other.agent_id == agent_id or not other.alive:
            continue
        agent_info = {
            "agent_id": other.agent_id,
            "x": other.x,
            "y": other.y,
            "hp": other.hp,
            "trust_score": round(other.trust_score, 1),
        }
        all_agents.append(agent_info)
        if abs(other.x - agent.x) <= radius and abs(other.y - agent.y) <= radius:
            nearby_agents.append(agent_info)

    return {
        "tick": world.tick,
        "radius": radius,
        "agent": agent.to_dict(),
        "tiles": tiles,
        "nearby_agents": nearby_agents,
        "all_agents": all_agents,
        "alive_agents": sum(1 for a in world.agents.values() if a.alive),
        "market_price": round(world.market_price, 3),
    }
