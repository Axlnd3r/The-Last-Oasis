from __future__ import annotations

import asyncio
import os
import random
import sys
from typing import Any

from .sdk import LastOasisClient


def find_current_tile(tiles: list[dict[str, Any]], x: int, y: int) -> dict[str, Any] | None:
    for t in tiles:
        if int(t["x"]) == x and int(t["y"]) == y:
            return t
    return None


def safest_neighbor(tiles: list[dict[str, Any]], x: int, y: int) -> tuple[int, int] | None:
    best = None
    best_score = 10.0
    for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
        nx, ny = x + dx, y + dy
        for t in tiles:
            if int(t["x"]) == nx and int(t["y"]) == ny:
                score = float(t["hazard"]) * 2.0 + float(t["degradation"])
                if score < best_score:
                    best_score = score
                    best = (dx, dy)
                break
    return best


def richest_neighbor(tiles: list[dict[str, Any]], x: int, y: int) -> tuple[int, int] | None:
    best = None
    best_res = 0
    for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
        nx, ny = x + dx, y + dy
        for t in tiles:
            if int(t["x"]) == nx and int(t["y"]) == ny:
                r = int(t.get("resource", 0))
                h = float(t.get("hazard", 0))
                if r > best_res and h < 0.5:
                    best_res = r
                    best = (dx, dy)
                break
    return best


async def main() -> None:
    base = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
    name = os.environ.get("AGENT_NAME", f"Trader_{random.randint(10,99)}")
    tx_ref = os.environ.get("TX_REF", f"demo_{name.lower()}_{random.randint(1000,9999)}")

    print(f"[{name}] Connecting to {base}...")
    c = LastOasisClient(base)

    try:
        confirm = await c.entry_confirm(tx_ref=tx_ref, name=name)
    except Exception as e:
        print(f"[{name}] Entry failed: {e}")
        sys.exit(1)

    c.api_key = confirm.api_key
    print(f"[{name}] Entered! id={confirm.agent_id[:8]}")

    step = 0
    while True:
        try:
            obs = await c.observation()
            agent = obs["agent"]
            if not agent.get("alive", True):
                print(f"[{name}] Died at step {step}")
                return

            x, y = int(agent["x"]), int(agent["y"])
            hp = int(agent["hp"])
            resource = int(agent.get("inventory", {}).get("resource", 0))
            tiles = list(obs.get("tiles", []))
            nearby = obs.get("nearby_agents", [])
            cur = find_current_tile(tiles, x, y)

            if cur is None:
                await c.submit_action({"type": "rest"})
                step += 1
                await asyncio.sleep(0.3)
                continue

            risk = float(cur["hazard"]) * 2.0 + float(cur["degradation"])

            # TRADE PRIORITY: if we have resources and nearby agents, trade!
            if nearby and resource > 3 and random.random() < 0.5:
                # Find lowest-HP nearby agent to help (or random)
                target = min(nearby, key=lambda a: a.get("hp", 20))
                amt = random.randint(1, min(5, resource))
                await c.submit_action({"type": "trade", "target": target["agent_id"], "amount": amt})
                step += 1
                await asyncio.sleep(0.3)
                continue

            # Flee from danger
            if hp <= 10 or risk > 0.9:
                mv = safest_neighbor(tiles, x, y)
                if mv is None:
                    await c.submit_action({"type": "rest"})
                else:
                    dx, dy = mv
                    await c.submit_action({"type": "move", "dx": dx, "dy": dy})
                step += 1
                await asyncio.sleep(0.3)
                continue

            # Low HP: rest
            if hp <= 12:
                await c.submit_action({"type": "rest"})
                step += 1
                await asyncio.sleep(0.3)
                continue

            # Gather resources
            if int(cur["resource"]) > 0:
                await c.submit_action({"type": "gather"})
            else:
                # Move to richest neighbor
                mv = richest_neighbor(tiles, x, y)
                if mv is None:
                    mv = safest_neighbor(tiles, x, y)
                if mv is None:
                    await c.submit_action({"type": "rest"})
                else:
                    dx, dy = mv
                    await c.submit_action({"type": "move", "dx": dx, "dy": dy})

            step += 1
            if step % 30 == 0:
                inv = agent.get("inventory", {})
                print(f"[{name}] step={step} hp={hp} pos=({x},{y}) res={inv.get('resource',0)} trades_attempted")

        except Exception as e:
            print(f"[{name}] Error: {e}")
            await asyncio.sleep(2)
            continue

        await asyncio.sleep(0.3)


if __name__ == "__main__":
    asyncio.run(main())
