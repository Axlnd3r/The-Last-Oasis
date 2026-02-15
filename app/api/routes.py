from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any, Optional

import aiosqlite
from fastapi import APIRouter, Body, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from ..db import insert_entry, insert_event, list_events, upsert_agent
from ..settings import settings
from ..chain.entry_fee import verify_entry_paid
from ..world.engine import WorldState, extract_observation
from ..world.snapshot import maybe_snapshot


@dataclass
class AppState:
    conn: aiosqlite.Connection
    world: WorldState
    world_lock: asyncio.Lock
    db_lock: asyncio.Lock
    pending_actions: dict[str, dict[str, Any]]
    agent_names: dict[str, str]


class EntryQuoteOut(BaseModel):
    asset: str
    amount: str
    protocol: str = "x402"
    instructions: dict[str, Any]


class EntryConfirmIn(BaseModel):
    tx_ref: str = Field(min_length=3)
    name: Optional[str] = None
    agent_address: Optional[str] = None


class EntryConfirmOut(BaseModel):
    agent_id: str
    api_key: str


class ActionIn(BaseModel):
    type: str
    dx: Optional[int] = None
    dy: Optional[int] = None
    target: Optional[str] = None
    amount: Optional[int] = None



def make_router(app_state: AppState) -> APIRouter:
    r = APIRouter()

    async def auth(x_agent_token: Optional[str] = Header(default=None)) -> str:
        if not x_agent_token:
            raise HTTPException(status_code=401, detail="missing_x_agent_token")
        agent_id = None
        async with app_state.db_lock:
            cur = await app_state.conn.execute(
                "SELECT agent_id FROM agents WHERE api_key = ? LIMIT 1",
                (x_agent_token,),
            )
            row = await cur.fetchone()
        if row is not None:
            agent_id = str(row["agent_id"])
        if agent_id is None:
            raise HTTPException(status_code=401, detail="invalid_token")
        return agent_id

    @r.post("/entry/quote", response_model=EntryQuoteOut)
    async def entry_quote() -> EntryQuoteOut:
        return EntryQuoteOut(
            asset=settings.entry_price_asset,
            amount=settings.entry_price_amount,
            instructions={
                "demo": {
                    "confirm_endpoint": "/entry/confirm",
                    "tx_ref_format": f"{settings.entry_demo_secret}_<anything>",
                }
            },
        )

    @r.post("/entry/confirm", response_model=EntryConfirmOut)
    async def entry_confirm(body: EntryConfirmIn = Body(...)) -> EntryConfirmOut:
        chain_mode = bool(settings.chain_rpc_url and settings.entry_fee_contract_address)
        if chain_mode:
            if not body.agent_address:
                raise HTTPException(status_code=400, detail="missing_agent_address")
            try:
                paid, normalized = await verify_entry_paid(
                    rpc_url=str(settings.chain_rpc_url),
                    contract_address=str(settings.entry_fee_contract_address),
                    tx_ref=body.tx_ref,
                    agent_address=body.agent_address,
                )
            except RuntimeError as e:
                raise HTTPException(status_code=502, detail=str(e)) from e
            if not paid:
                raise HTTPException(status_code=402, detail="payment_required")
            agent_address = normalized
        else:
            if not body.tx_ref.startswith(f"{settings.entry_demo_secret}_"):
                raise HTTPException(status_code=400, detail="invalid_tx_ref")
            agent_address = None

        agent_id = str(uuid.uuid4())
        api_key = str(uuid.uuid4())

        async with app_state.world_lock:
            did_reset = sum(1 for a in app_state.world.agents.values() if a.alive) == 0
            if did_reset:
                app_state.world.reset_session()
                app_state.pending_actions.clear()
            if agent_id not in app_state.world.agents:
                app_state.world.add_agent(agent_id)
            agent_state = app_state.world.agents[agent_id].to_dict()
        if body.name:
            agent_state["name"] = body.name
            app_state.agent_names[agent_id] = body.name
        if agent_address:
            agent_state["wallet_address"] = agent_address

        async with app_state.db_lock:
            await upsert_agent(app_state.conn, agent_id, api_key, agent_state)
            await insert_entry(
                app_state.conn, body.tx_ref, agent_id, settings.entry_price_asset, settings.entry_price_amount
            )
            await insert_event(
                app_state.conn,
                tick=app_state.world.tick,
                type="AGENT_ENTERED",
                agent_id=agent_id,
                payload={"agent_id": agent_id, "name": body.name or agent_id},
            )
            if did_reset:
                await insert_event(
                    app_state.conn,
                    tick=app_state.world.tick,
                    type="WORLD_RESET_IF_EXTINCT",
                    payload={"reason": "no_alive_agents"},
                )

        return EntryConfirmOut(agent_id=agent_id, api_key=api_key)

    @r.get("/world/observation")
    async def world_observation(agent_id: str = Depends(auth)) -> dict[str, Any]:
        async with app_state.world_lock:
            obs = extract_observation(app_state.world, agent_id, settings.obs_radius)
        if obs is None:
            raise HTTPException(status_code=404, detail="agent_not_found")
        return obs

    @r.post("/world/action")
    async def world_action(body: ActionIn = Body(...), agent_id: str = Depends(auth)) -> dict[str, Any]:
        action = body.model_dump(exclude_none=True)
        async with app_state.world_lock:
            if agent_id not in app_state.world.agents:
                raise HTTPException(status_code=404, detail="agent_not_found")
            if not app_state.world.agents[agent_id].alive:
                raise HTTPException(status_code=403, detail="agent_dead")
            app_state.pending_actions[agent_id] = action
            target_tick = app_state.world.tick + 1
        async with app_state.db_lock:
            await insert_event(
                app_state.conn,
                tick=target_tick,
                type="ACTION_SUBMITTED",
                agent_id=agent_id,
                payload=action,
            )
        return {"ok": True, "queued_for_tick": target_tick}

    @r.get("/world/status")
    async def world_status() -> dict[str, Any]:
        async with app_state.world_lock:
            alive = sum(1 for a in app_state.world.agents.values() if a.alive)
            avg_deg = 0.0
            c = 0
            for row in app_state.world.grid:
                for tile in row:
                    avg_deg += float(tile["degradation"])
                    c += 1
            avg_deg = avg_deg / max(1, c)
            return {"tick": app_state.world.tick, "alive_agents": alive, "avg_degradation": avg_deg}

    @r.get("/world/leaderboard")
    async def world_leaderboard() -> dict[str, Any]:
        async with app_state.world_lock:
            items = []
            for a in app_state.world.agents.values():
                score = int(a.hp) + int(a.inventory.get("resource", 0))
                items.append({"agent_id": a.agent_id, "name": app_state.agent_names.get(a.agent_id, ""), "alive": a.alive, "hp": a.hp, "resource": a.inventory.get("resource", 0), "score": score})
            items.sort(key=lambda x: (x["alive"], x["score"]), reverse=True)
            return {"tick": app_state.world.tick, "items": items[:20]}

    @r.get("/world/agents")
    async def world_agents() -> dict[str, Any]:
        async with app_state.world_lock:
            agents_out = []
            for a in app_state.world.agents.values():
                agents_out.append({
                    "agent_id": a.agent_id,
                    "x": a.x,
                    "y": a.y,
                    "hp": a.hp,
                    "alive": a.alive,
                    "inventory": dict(a.inventory),
                })
            return {"tick": app_state.world.tick, "agents": agents_out}

    @r.get("/world/grid")
    async def world_grid() -> dict[str, Any]:
        async with app_state.world_lock:
            size = app_state.world.size
            tiles: list[dict[str, Any]] = []
            for y in range(size):
                for x in range(size):
                    t = app_state.world.grid[y][x]
                    tiles.append({
                        "x": x,
                        "y": y,
                        "degradation": round(float(t["degradation"]), 4),
                        "resource": int(t["resource"]),
                        "hazard": round(float(t["hazard"]), 4),
                    })
            agents_pos = []
            for a in app_state.world.agents.values():
                score = a.hp + a.inventory.get("resource", 0)
                agents_pos.append({
                    "agent_id": a.agent_id,
                    "name": app_state.agent_names.get(a.agent_id, ""),
                    "x": a.x,
                    "y": a.y,
                    "hp": a.hp,
                    "alive": a.alive,
                    "resource": a.inventory.get("resource", 0),
                    "score": score,
                    "trust_score": round(a.trust_score, 1),
                    "betrayals": a.betrayals,
                })
            return {"tick": app_state.world.tick, "size": size, "tiles": tiles, "agents": agents_pos}

    @r.get("/world/market")
    async def world_market() -> dict[str, Any]:
        """Get current market price and economic stats"""
        async with app_state.world_lock:
            total_resources = sum(tile["resource"] for row in app_state.world.grid for tile in row)
            total_degradation = sum(tile["degradation"] for row in app_state.world.grid for tile in row)
            avg_deg = total_degradation / (app_state.world.size * app_state.world.size)

            total_agent_resources = sum(a.inventory.get("resource", 0) for a in app_state.world.agents.values() if a.alive)

            return {
                "tick": app_state.world.tick,
                "market_price": round(app_state.world.market_price, 3),
                "total_world_resources": total_resources,
                "total_agent_resources": total_agent_resources,
                "avg_degradation": round(avg_deg, 4),
                "recent_trades_count": len(app_state.world.recent_trades),
            }

    @r.get("/world/reputation")
    async def world_reputation() -> dict[str, Any]:
        """Get reputation leaderboard"""
        async with app_state.world_lock:
            items = []
            for a in app_state.world.agents.values():
                items.append({
                    "agent_id": a.agent_id,
                    "name": app_state.agent_names.get(a.agent_id, ""),
                    "trust_score": round(a.trust_score, 1),
                    "betrayals": a.betrayals,
                    "trade_count": len(a.trade_history),
                    "alive": a.alive,
                })
            items.sort(key=lambda x: x["trust_score"], reverse=True)
            return {"tick": app_state.world.tick, "items": items}

    @r.post("/admin/dqn-log")
    async def admin_dqn_log(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
        async with app_state.db_lock:
            await insert_event(
                app_state.conn,
                tick=app_state.world.tick,
                type="DQN_LOG",
                payload={
                    "mistakes": body.get("mistakes", [])[-20:],
                    "episode_rewards": body.get("episode_rewards", [])[-50:],
                    "step_count": body.get("step_count", 0),
                    "epsilon": body.get("epsilon", 1.0),
                    "loss_history": body.get("loss_history", [])[-50:],
                    "total_reward": body.get("total_reward", 0),
                },
            )
        return {"ok": True}

    @r.post("/admin/finalize-game")
    async def admin_finalize_game(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
        survivors = body.get("survivors", [])
        async with app_state.world_lock:
            tick = app_state.world.tick
            alive_agents = [a for a in app_state.world.agents.values() if a.alive]
            if not survivors:
                survivors = [
                    {"address": "0x0000000000000000000000000000000000000000", "agent_id": a.agent_id, "ticks": tick}
                    for a in alive_agents
                ]
        async with app_state.db_lock:
            await insert_event(
                app_state.conn,
                tick=tick,
                type="GAME_FINALIZED",
                payload={"survivors": survivors, "end_tick": tick},
            )
        return {"ok": True, "tick": tick, "survivors": len(survivors)}

    @r.get("/admin/events")
    async def admin_events(limit: int = 50) -> dict[str, Any]:
        limit = max(1, min(200, int(limit)))
        async with app_state.db_lock:
            evs = await list_events(app_state.conn, limit=limit)
        return {
            "items": [
                {"id": e.id, "tick": e.tick, "type": e.type, "agent_id": e.agent_id, "payload": e.payload, "created_at": e.created_at}
                for e in evs
            ]
        }

    @r.post("/admin/tick")
    async def admin_tick() -> dict[str, Any]:
        async with app_state.world_lock:
            actions = dict(app_state.pending_actions)
            app_state.pending_actions.clear()
            events = app_state.world.step(actions)
            tick = app_state.world.tick
        async with app_state.db_lock:
            await insert_event(
                app_state.conn, tick=tick, type="TICK_RESOLVED", payload={"actions": actions, "events": events}
            )
            for e in events:
                et = str(e.get("type") or "EVENT")
                await insert_event(app_state.conn, tick=tick, type=et, agent_id=e.get("agent_id"), payload=e)
            await maybe_snapshot(app_state.conn, app_state.world, settings.snapshot_every_ticks)
        return {"ok": True, "tick": tick, "events": len(events)}

    @r.post("/admin/spawn-demo-agents")
    async def admin_spawn_demo_agents(count: int = 5) -> dict[str, Any]:
        """Spawn demo agents for judges to see activity"""
        import uuid
        spawned = []

        agent_names = ["Explorer_A", "Explorer_B", "Trader_A", "Fighter_A", "Survivor_A"]

        for i in range(min(count, 10)):  # Max 10 agents
            agent_id = f"demo_{uuid.uuid4().hex[:8]}"
            api_key = uuid.uuid4().hex
            name = agent_names[i] if i < len(agent_names) else f"Agent_{i+1}"

            # Register agent in DB
            async with app_state.db_lock:
                await upsert_agent(
                    app_state.conn,
                    agent_id=agent_id,
                    api_key=api_key,
                    state={}
                )
                await insert_entry(
                    app_state.conn,
                    f"demo_{agent_id}",  # tx_ref
                    agent_id,             # agent_id
                    "DEMO",              # paid_asset
                    "0"                  # paid_amount
                )

            # Add agent to world
            async with app_state.world_lock:
                app_state.world.add_agent(agent_id)
                app_state.agent_names[agent_id] = name
                tick = app_state.world.tick

            # Log entry event
            async with app_state.db_lock:
                await insert_event(
                    app_state.conn,
                    tick=tick,
                    type="AGENT_ENTERED",
                    agent_id=agent_id,
                    payload={"agent_id": agent_id, "name": name, "demo": True}
                )

            spawned.append({"agent_id": agent_id, "name": name})

        return {"ok": True, "spawned": len(spawned), "agents": spawned}

    @r.post("/admin/reset-world")
    async def admin_reset_world() -> dict[str, Any]:
        """Reset world to tick 0 with clean slate"""
        from ..world.engine import WorldState

        async with app_state.world_lock:
            # Create fresh world
            old_tick = app_state.world.tick
            app_state.world = WorldState(size=settings.map_size)
            app_state.pending_actions.clear()
            app_state.agent_names.clear()

        # Clear agents from DB (optional - or keep for history)
        async with app_state.db_lock:
            await app_state.conn.execute("DELETE FROM agents")
            await app_state.conn.execute("DELETE FROM entries")
            await app_state.conn.commit()

            await insert_event(
                app_state.conn,
                tick=0,
                type="WORLD_RESET",
                payload={"old_tick": old_tick, "reset_at": 0}
            )

        return {"ok": True, "old_tick": old_tick, "new_tick": 0, "message": "World reset successfully"}

    return r
