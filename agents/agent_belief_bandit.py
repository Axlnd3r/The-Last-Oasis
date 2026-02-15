from __future__ import annotations

import asyncio
import os
import random
import sys
from dataclasses import dataclass
from typing import Any

from .sdk import LastOasisClient


@dataclass
class Belief:
    hazard: dict[tuple[int, int], float]
    degradation: dict[tuple[int, int], float]
    resource: dict[tuple[int, int], int]

    def __init__(self) -> None:
        self.hazard = {}
        self.degradation = {}
        self.resource = {}

    def update(self, tiles: list[dict[str, Any]]) -> None:
        for t in tiles:
            k = (int(t["x"]), int(t["y"]))
            self.hazard[k] = float(t["hazard"])
            self.degradation[k] = float(t["degradation"])
            self.resource[k] = int(t["resource"])

    def danger(self, x: int, y: int) -> float:
        h = self.hazard.get((x, y), 0.2)
        d = self.degradation.get((x, y), 0.2)
        return h * 2.0 + d

    def best_resource_nearby(self, x: int, y: int, radius: int = 3) -> tuple[int, int] | None:
        best = None
        best_score = -1
        for (rx, ry), res in self.resource.items():
            if res < 5:
                continue
            dist = abs(rx - x) + abs(ry - y)
            if dist > radius or dist == 0:
                continue
            danger = self.danger(rx, ry)
            score = res / max(1, dist) - danger * 10
            if score > best_score:
                best_score = score
                best = (rx, ry)
        return best


def candidate_moves() -> list[tuple[int, int]]:
    return [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)]


async def main() -> None:
    base = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
    name = os.environ.get("AGENT_NAME", f"Belief_{random.randint(10,99)}")
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

    belief = Belief()
    step = 0

    while True:
        try:
            obs = await c.observation()
            agent = obs["agent"]
            if not agent.get("alive", True):
                print(f"[{name}] Died at step {step}")
                return

            belief.update(list(obs.get("tiles", [])))
            x, y = int(agent["x"]), int(agent["y"])
            hp = int(agent["hp"])
            resource = int(agent.get("inventory", {}).get("resource", 0))
            nearby = obs.get("nearby_agents", [])

            # Low HP: rest or flee
            if hp <= 8:
                # Flee from nearby agents if any
                if nearby and hp <= 5:
                    best = (0, 0)
                    best_dist = 0
                    for dx, dy in candidate_moves():
                        if dx == 0 and dy == 0:
                            continue
                        nx, ny = x + dx, y + dy
                        min_dist = min((abs(nx - a["x"]) + abs(ny - a["y"])) for a in nearby)
                        if min_dist > best_dist:
                            best_dist = min_dist
                            best = (dx, dy)
                    if best != (0, 0):
                        await c.submit_action({"type": "move", "dx": best[0], "dy": best[1]})
                    else:
                        await c.submit_action({"type": "rest"})
                else:
                    await c.submit_action({"type": "rest"})
                step += 1
                await asyncio.sleep(0.3)
                continue

            # If at resource tile, gather
            current_resource = 0
            for t in obs["tiles"]:
                if int(t["x"]) == x and int(t["y"]) == y:
                    current_resource = int(t["resource"])
                    break

            if current_resource > 0 and belief.danger(x, y) < 0.65:
                await c.submit_action({"type": "gather"})
                step += 1
                await asyncio.sleep(0.3)
                continue

            # Seek best resource tile
            target = belief.best_resource_nearby(x, y, radius=3)
            if target:
                tx, ty = target
                dx = 1 if tx > x else (-1 if tx < x else 0)
                dy = 1 if ty > y else (-1 if ty < y else 0)
                if dx != 0:
                    await c.submit_action({"type": "move", "dx": dx, "dy": 0})
                elif dy != 0:
                    await c.submit_action({"type": "move", "dx": 0, "dy": dy})
                else:
                    await c.submit_action({"type": "rest"})
                step += 1
                await asyncio.sleep(0.3)
                continue

            # Avoid danger: move to safest neighbor
            best = (0, 0)
            best_score = belief.danger(x, y)
            for dx, dy in candidate_moves():
                nx, ny = x + dx, y + dy
                s = belief.danger(nx, ny)
                if s < best_score:
                    best_score = s
                    best = (dx, dy)

            dx, dy = best
            if dx == 0 and dy == 0:
                await c.submit_action({"type": "rest"})
            else:
                await c.submit_action({"type": "move", "dx": dx, "dy": dy})

            step += 1
            if step % 30 == 0:
                inv = agent.get("inventory", {})
                print(f"[{name}] step={step} hp={hp} pos=({x},{y}) res={inv.get('resource',0)}")

        except Exception as e:
            print(f"[{name}] Error: {e}")
            await asyncio.sleep(2)
            continue

        await asyncio.sleep(0.3)


if __name__ == "__main__":
    asyncio.run(main())
