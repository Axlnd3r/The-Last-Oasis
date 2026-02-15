from __future__ import annotations

import asyncio
import os
import tempfile
from typing import Any

from app.db import connect, init_db, insert_event, list_actions_for_tick, upsert_snapshot
from app.settings import Settings
from app.world.engine import WorldState
from app.world.snapshot import load_world, maybe_snapshot


async def run_engine_100_ticks() -> None:
    world = WorldState(size=20, tick=0)
    world.add_agent("a")
    for _ in range(100):
        world.step({"a": {"type": "rest"}})


async def run_event_sourcing_restart() -> None:
    with tempfile.TemporaryDirectory() as d:
        db_path = os.path.join(d, "test.sqlite3")
        conn = await connect(db_path)
        await init_db(conn)

        world = WorldState(size=20, tick=0)
        world.add_agent("a")
        world.add_agent("b")
        await upsert_snapshot(conn, 0, world.to_dict())

        for _ in range(25):
            target_tick = world.tick + 1
            await insert_event(conn, tick=target_tick, type="ACTION_SUBMITTED", agent_id="a", payload={"type": "rest"})
            await insert_event(conn, tick=target_tick, type="ACTION_SUBMITTED", agent_id="b", payload={"type": "rest"})
            actions: dict[str, dict[str, Any]] = {}
            for ev in await list_actions_for_tick(conn, target_tick):
                if ev.agent_id:
                    actions[ev.agent_id] = dict(ev.payload)
            world.step(actions)
            await insert_event(conn, tick=world.tick, type="TICK_RESOLVED", payload={"actions": actions})
            await maybe_snapshot(conn, world, every_ticks=10)

        reloaded = await load_world(conn, size=20)
        assert reloaded.tick == world.tick
        await conn.close()


async def main() -> None:
    await run_engine_100_ticks()
    await run_event_sourcing_restart()
    print("OK")


if __name__ == "__main__":
    asyncio.run(main())

