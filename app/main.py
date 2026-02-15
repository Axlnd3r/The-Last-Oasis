from __future__ import annotations

import asyncio
import logging
import sys
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

# Configure logging IMMEDIATELY
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

print("=" * 60, flush=True)
print("🚀 THE LAST OASIS - Initializing...", flush=True)
print("=" * 60, flush=True)


def create_app() -> FastAPI:
    print("📦 Creating FastAPI app...", flush=True)
    app = FastAPI(title="The Last Oasis", version="0.1.0")
    logger = logging.getLogger("last_oasis")

    dashboard_dir = Path(__file__).parent / "dashboard"
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = Path(__file__).resolve().parent.parent / "Assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
    app.mount("/dashboard", StaticFiles(directory=str(dashboard_dir), html=True), name="dashboard")
    print("✅ Static files mounted", flush=True)

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

    print("✅ Routes registered", flush=True)

    @app.on_event("startup")
    async def on_startup() -> None:
        print("\n" + "=" * 60, flush=True)
        print("🚀 STARTUP EVENT TRIGGERED", flush=True)
        print("=" * 60, flush=True)
        print(f"📁 DB_PATH: {settings.db_path}", flush=True)
        print(f"📏 MAP_SIZE: {settings.map_size}", flush=True)
        print(f"⏱️  TICK_INTERVAL: {settings.tick_interval_ms}ms", flush=True)

        try:
            print("\n📊 Step 1: Connecting to database...", flush=True)
            conn = await connect(settings.db_path)
            print("✅ Database connection established", flush=True)

            print("\n📊 Step 2: Initializing database schema...", flush=True)
            await init_db(conn)
            print("✅ Database schema initialized", flush=True)

            print("\n📊 Step 3: Loading world state...", flush=True)
            world = await load_world(conn, size=settings.map_size)
            print(f"✅ World loaded successfully (current tick: {world.tick})", flush=True)

            print("\n📊 Step 4: Loading agents...", flush=True)
            agents = await list_agents(conn)
            print(f"✅ Found {len(agents)} existing agents", flush=True)

            for agent_id, state in agents:
                if agent_id not in world.agents:
                    world.add_agent(agent_id)
                world.agents[agent_id] = AgentState.from_dict(state)
            print("✅ Agents loaded into world", flush=True)

            print("\n📊 Step 5: Creating app state...", flush=True)
            app.state.app_state = AppState(
                conn=conn,
                world=world,
                world_lock=asyncio.Lock(),
                db_lock=asyncio.Lock(),
                pending_actions={},
                agent_names={},
            )
            print("✅ App state created", flush=True)

            print("\n📊 Step 6: Including API router...", flush=True)
            app.include_router(make_router(app.state.app_state))
            print("✅ API router included", flush=True)

            print("\n📊 Step 7: Recording startup event...", flush=True)
            async with app.state.app_state.db_lock:
                await insert_event(conn, tick=world.tick, type="WORLD_STARTED", payload={"tick": world.tick})
            print("✅ Startup event recorded", flush=True)

            print("\n📊 Step 8: Starting tick loop...", flush=True)

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
            print("✅ Tick loop started", flush=True)

            print("\n" + "=" * 60, flush=True)
            print("🎉 STARTUP COMPLETE - Server is ready!", flush=True)
            print("=" * 60 + "\n", flush=True)

        except Exception as e:
            print("\n" + "=" * 60, flush=True)
            print(f"❌ STARTUP FAILED: {type(e).__name__}: {e}", flush=True)
            print("=" * 60, flush=True)
            import traceback
            traceback.print_exc()
            print("=" * 60 + "\n", flush=True)
            raise  # Re-raise so Railway sees the error

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        print("\n🛑 Shutting down...", flush=True)
        task = getattr(app.state, "tick_task", None)
        if task is not None:
            task.cancel()
        st = getattr(app.state, "app_state", None)
        if st is not None:
            await st.conn.close()
        print("✅ Shutdown complete", flush=True)

    return app


print("📦 Creating app instance...", flush=True)
app = create_app()
print("✅ App instance created successfully", flush=True)
print("🌐 Ready to accept connections on $PORT", flush=True)
