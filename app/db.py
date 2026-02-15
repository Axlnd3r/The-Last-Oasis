from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import aiosqlite


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class DbEvent:
    id: int
    tick: int
    type: str
    agent_id: Optional[str]
    payload: dict[str, Any]
    created_at: str


async def connect(db_path: str) -> aiosqlite.Connection:
    conn = await aiosqlite.connect(db_path)
    await conn.execute("PRAGMA journal_mode=WAL;")
    await conn.execute("PRAGMA synchronous=NORMAL;")
    conn.row_factory = aiosqlite.Row
    return conn


async def init_db(conn: aiosqlite.Connection) -> None:
    await conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS agents (
          agent_id TEXT PRIMARY KEY,
          api_key TEXT NOT NULL,
          state_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS entries (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          tx_ref TEXT NOT NULL,
          agent_id TEXT NOT NULL,
          paid_asset TEXT NOT NULL,
          paid_amount TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          tick INTEGER NOT NULL,
          type TEXT NOT NULL,
          agent_id TEXT,
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS world_snapshots (
          tick INTEGER PRIMARY KEY,
          state_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        """
    )
    await conn.commit()


async def insert_event(
    conn: aiosqlite.Connection,
    tick: int,
    type: str,
    payload: dict[str, Any],
    agent_id: Optional[str] = None,
) -> int:
    cur = await conn.execute(
        "INSERT INTO events (tick, type, agent_id, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
        (tick, type, agent_id, json.dumps(payload, separators=(",", ":")), utc_now_iso()),
    )
    await conn.commit()
    return int(cur.lastrowid)


async def list_events(conn: aiosqlite.Connection, limit: int) -> list[DbEvent]:
    cur = await conn.execute(
        "SELECT id, tick, type, agent_id, payload_json, created_at FROM events ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    rows = await cur.fetchall()
    out: list[DbEvent] = []
    for r in rows:
        out.append(
            DbEvent(
                id=int(r["id"]),
                tick=int(r["tick"]),
                type=str(r["type"]),
                agent_id=str(r["agent_id"]) if r["agent_id"] is not None else None,
                payload=json.loads(r["payload_json"]),
                created_at=str(r["created_at"]),
            )
        )
    return out


async def list_actions_for_tick(conn: aiosqlite.Connection, tick: int) -> list[DbEvent]:
    cur = await conn.execute(
        "SELECT id, tick, type, agent_id, payload_json, created_at FROM events WHERE tick = ? AND type = ? ORDER BY id ASC",
        (tick, "ACTION_SUBMITTED"),
    )
    rows = await cur.fetchall()
    out: list[DbEvent] = []
    for r in rows:
        out.append(
            DbEvent(
                id=int(r["id"]),
                tick=int(r["tick"]),
                type=str(r["type"]),
                agent_id=str(r["agent_id"]) if r["agent_id"] is not None else None,
                payload=json.loads(r["payload_json"]),
                created_at=str(r["created_at"]),
            )
        )
    return out


async def get_latest_snapshot(conn: aiosqlite.Connection) -> Optional[tuple[int, dict[str, Any]]]:
    cur = await conn.execute(
        "SELECT tick, state_json FROM world_snapshots ORDER BY tick DESC LIMIT 1"
    )
    row = await cur.fetchone()
    if row is None:
        return None
    return int(row["tick"]), json.loads(row["state_json"])


async def upsert_snapshot(conn: aiosqlite.Connection, tick: int, state: dict[str, Any]) -> None:
    await conn.execute(
        "INSERT INTO world_snapshots (tick, state_json, created_at) VALUES (?, ?, ?) "
        "ON CONFLICT(tick) DO UPDATE SET state_json=excluded.state_json, created_at=excluded.created_at",
        (tick, json.dumps(state, separators=(",", ":")), utc_now_iso()),
    )
    await conn.commit()


async def get_max_resolved_tick(conn: aiosqlite.Connection) -> int:
    cur = await conn.execute("SELECT MAX(tick) AS t FROM events WHERE type = ?", ("TICK_RESOLVED",))
    row = await cur.fetchone()
    if row is None or row["t"] is None:
        return 0
    return int(row["t"])


async def upsert_agent(conn: aiosqlite.Connection, agent_id: str, api_key: str, state: dict[str, Any]) -> None:
    await conn.execute(
        "INSERT INTO agents (agent_id, api_key, state_json, created_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(agent_id) DO UPDATE SET api_key=excluded.api_key, state_json=excluded.state_json",
        (agent_id, api_key, json.dumps(state, separators=(",", ":")), utc_now_iso()),
    )
    await conn.commit()


async def get_agent_by_token(conn: aiosqlite.Connection, api_key: str) -> Optional[tuple[str, dict[str, Any]]]:
    cur = await conn.execute(
        "SELECT agent_id, state_json FROM agents WHERE api_key = ? LIMIT 1",
        (api_key,),
    )
    row = await cur.fetchone()
    if row is None:
        return None
    return str(row["agent_id"]), json.loads(row["state_json"])


async def list_agents(conn: aiosqlite.Connection) -> list[tuple[str, dict[str, Any]]]:
    cur = await conn.execute("SELECT agent_id, state_json FROM agents")
    rows = await cur.fetchall()
    out: list[tuple[str, dict[str, Any]]] = []
    for r in rows:
        out.append((str(r["agent_id"]), json.loads(r["state_json"])))
    return out


async def insert_entry(
    conn: aiosqlite.Connection, tx_ref: str, agent_id: str, paid_asset: str, paid_amount: str
) -> None:
    await conn.execute(
        "INSERT INTO entries (tx_ref, agent_id, paid_asset, paid_amount, created_at) VALUES (?, ?, ?, ?, ?)",
        (tx_ref, agent_id, paid_asset, paid_amount, utc_now_iso()),
    )
    await conn.commit()

