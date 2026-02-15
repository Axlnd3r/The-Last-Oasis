from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import AppState, make_router
from .db import connect, init_db, insert_event, list_agents, upsert_agent
from .settings import settings
from .world.snapshot import load_world, maybe_snapshot
from .world.engine import AgentState


def create_app() -> FastAPI:
    app = FastAPI(title="The Last Oasis", version="0.1.0")
    logger = logging.getLogger("last_oasis")

    dashboard_dir = Path(__file__).parent / "dashboard"
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = Path(__file__).resolve().parent.parent / "Assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
    app.mount("/dashboard", StaticFiles(directory=str(dashboard_dir), html=True), name="dashboard")

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = uuid.uuid4().hex
        logger.exception(
            "unhandled_exception request_id=%s method=%s path=%s",
            request_id,
            request.method,
            request.url.path,
        )
        return JSONResponse(status_code=500, content={"detail": "internal_server_error", "request_id": request_id})

    @app.get("/health")
    async def health():
        """Simple health check endpoint for Railway/deployment platforms"""
        return {"status": "ok"}

    @app.get("/")
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/dashboard/")

    @app.on_event("startup")
    async def on_startup() -> None:
        try:
            logger.info(f"🚀 Starting up... DB_PATH={settings.db_path}")
            conn = await connect(settings.db_path)
            logger.info("✅ Connected to database")

            await init_db(conn)
            logger.info("✅ Database initialized")

            world = await load_world(conn, size=settings.map_size)
            logger.info(f"✅ World loaded (tick={world.tick})")

            agents = await list_agents(conn)
            logger.info(f"✅ Found {len(agents)} agents")

            for agent_id, state in agents:
                if agent_id not in world.agents:
                    world.add_agent(agent_id)
                world.agents[agent_id] = AgentState.from_dict(state)

            app.state.app_state = AppState(
                conn=conn,
                world=world,
                world_lock=asyncio.Lock(),
                db_lock=asyncio.Lock(),
                pending_actions={},
                agent_names={},
            )
            logger.info("✅ App state created")

            app.include_router(make_router(app.state.app_state))
            logger.info("✅ Router included")

            async with app.state.app_state.db_lock:
                await insert_event(conn, tick=world.tick, type="WORLD_STARTED", payload={"tick": world.tick})

            logger.info("🎉 Startup complete!")

        except Exception as e:
            logger.error(f"❌ Startup failed: {e}", exc_info=True)
            # Don't re-raise - let the app start anyway so we can at least serve /health
            # Initialize minimal state
            import aiosqlite
            conn = await aiosqlite.connect(":memory:")
            from .world.engine import WorldState
            world = WorldState(size=settings.map_size)
            app.state.app_state = AppState(
                conn=conn,
                world=world,
                world_lock=asyncio.Lock(),
                db_lock=asyncio.Lock(),
                pending_actions={},
                agent_names={},
            )
            app.include_router(make_router(app.state.app_state))
            logger.warning("⚠️  App started with minimal state due to startup error")

        async def tick_loop() -> None:
            while True:
                await asyncio.sleep(settings.tick_interval_ms / 1000.0)
                st: AppState = app.state.app_state
                async with st.world_lock:
                    if sum(1 for a in st.world.agents.values() if a.alive) == 0 and not st.pending_actions:
                        continue
                    actions = dict(st.pending_actions)
                    st.pending_actions.clear()
                    events = st.world.step(actions)
                    tick = st.world.tick
                    agent_states: dict[str, Any] = {aid: a.to_dict() for aid, a in st.world.agents.items()}

                async with st.db_lock:
                    await insert_event(conn, tick=tick, type="TICK_RESOLVED", payload={"actions": actions, "events": events})
                    for e in events:
                        et = str(e.get("type") or "EVENT")
                        await insert_event(conn, tick=tick, type=et, agent_id=e.get("agent_id"), payload=e)

                    for agent_id, state in agent_states.items():
                        cur = await conn.execute("SELECT api_key FROM agents WHERE agent_id = ? LIMIT 1", (agent_id,))
                        row = await cur.fetchone()
                        if row is None:
                            continue
                        api_key = str(row["api_key"])
                        await upsert_agent(conn, agent_id, api_key, state)

                    await maybe_snapshot(conn, st.world, settings.snapshot_every_ticks)

                # Check for STATE_ANCHORED events and submit to chain
                for e in events:
                    if e.get("type") == "STATE_ANCHORED":
                        from app.chain.state_anchor import get_state_anchor_service
                        anchor_svc = get_state_anchor_service()
                        state_hash = e.get("state_hash", "")
                        alive_count = e.get("alive_agents", 0)
                        if state_hash:
                            asyncio.create_task(anchor_svc.anchor_state(tick, state_hash, alive_count))

        app.state.tick_task = asyncio.create_task(tick_loop())

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        task = getattr(app.state, "tick_task", None)
        if task is not None:
            task.cancel()
        st = getattr(app.state, "app_state", None)
        if st is not None:
            await st.conn.close()

    return app


app = create_app()
