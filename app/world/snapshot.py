from __future__ import annotations

from typing import Any, Optional

import aiosqlite

from ..db import get_latest_snapshot, get_max_resolved_tick, list_actions_for_tick, upsert_snapshot
from .engine import WorldState


async def load_world(conn: aiosqlite.Connection, size: int) -> WorldState:
    latest = await get_latest_snapshot(conn)
    if latest is None:
        world = WorldState(size=size, tick=0)
        await upsert_snapshot(conn, 0, world.to_dict())
        return world

    snap_tick, snap_state = latest
    world = WorldState.from_dict(snap_state)

    max_resolved = await get_max_resolved_tick(conn)
    if max_resolved <= snap_tick:
        return world

    for t in range(snap_tick + 1, max_resolved + 1):
        action_events = await list_actions_for_tick(conn, t)
        actions: dict[str, dict[str, Any]] = {}
        for ev in action_events:
            if ev.agent_id is None:
                continue
            actions[ev.agent_id] = dict(ev.payload)
        world.step(actions)

    return world


async def maybe_snapshot(conn: aiosqlite.Connection, world: WorldState, every_ticks: int) -> Optional[int]:
    if every_ticks <= 0:
        return None
    if world.tick % every_ticks != 0:
        return None
    await upsert_snapshot(conn, world.tick, world.to_dict())
    return world.tick

