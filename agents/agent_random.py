from __future__ import annotations

import asyncio
import os
import random
import sys

from .sdk import LastOasisClient


ACTIONS = ["move", "gather", "rest", "trade", "attack"]


def pick_action(obs: dict) -> dict:
    agent = obs["agent"]
    x, y = int(agent["x"]), int(agent["y"])
    hp = int(agent["hp"])
    resource = int(agent.get("inventory", {}).get("resource", 0))
    nearby = obs.get("nearby_agents", [])

    # If low HP, rest
    if hp < 5:
        return {"type": "rest"}

    # If there is a nearby agent and we have enough HP, sometimes attack
    if nearby and hp > 8 and random.random() < 0.3:
        target = random.choice(nearby)
        # Move towards target if not adjacent
        tx, ty = int(target["x"]), int(target["y"])
        dist = abs(tx - x) + abs(ty - y)
        if dist <= 1:
            return {"type": "attack", "target": target["agent_id"]}
        else:
            dx = 1 if tx > x else (-1 if tx < x else 0)
            dy = 1 if ty > y else (-1 if ty < y else 0)
            if random.random() < 0.5 and dx != 0:
                return {"type": "move", "dx": dx, "dy": 0}
            elif dy != 0:
                return {"type": "move", "dx": 0, "dy": dy}

    # If nearby agent and we have resources, sometimes trade
    if nearby and resource > 2 and random.random() < 0.15:
        target = random.choice(nearby)
        amt = random.randint(1, min(3, resource))
        return {"type": "trade", "target": target["agent_id"], "amount": amt}

    # Check current tile for resources
    current = None
    for t in obs.get("tiles", []):
        if int(t["x"]) == x and int(t["y"]) == y:
            current = t
            break

    # Gather if on resource tile
    if current and int(current.get("resource", 0)) > 0 and random.random() < 0.6:
        return {"type": "gather"}

    # Move towards resource-rich tile
    best_tile = None
    best_res = 0
    for t in obs.get("tiles", []):
        r = int(t.get("resource", 0))
        h = float(t.get("hazard", 0))
        if r > best_res and h < 0.5:
            best_res = r
            best_tile = t
    if best_tile and best_res > 5 and random.random() < 0.5:
        tx, ty = int(best_tile["x"]), int(best_tile["y"])
        dx = 1 if tx > x else (-1 if tx < x else 0)
        dy = 1 if ty > y else (-1 if ty < y else 0)
        if dx != 0:
            return {"type": "move", "dx": dx, "dy": 0}
        if dy != 0:
            return {"type": "move", "dx": 0, "dy": dy}

    # Random move or rest
    if random.random() < 0.15:
        return {"type": "rest"}
    dx, dy = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
    return {"type": "move", "dx": dx, "dy": dy}


async def main() -> None:
    base = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
    name = os.environ.get("AGENT_NAME", f"rand_{random.randint(100,999)}")
    tx_ref = os.environ.get("TX_REF", f"demo_{name}")

    print(f"[{name}] Connecting to {base}...")
    c = LastOasisClient(base)

    try:
        confirm = await c.entry_confirm(tx_ref=tx_ref, name=name)
    except Exception as e:
        print(f"[{name}] Entry failed: {e}")
        print(f"[{name}] Make sure server is running: uvicorn app.main:app")
        print(f"[{name}] And no CHAIN_RPC_URL / ENTRY_FEE_CONTRACT_ADDRESS env vars are set")
        sys.exit(1)

    c.api_key = confirm.api_key
    print(f"[{name}] Entered world! agent_id={confirm.agent_id[:8]}...")

    step = 0
    while True:
        try:
            obs = await c.observation()
            agent = obs["agent"]
            if not agent.get("alive", True):
                print(f"[{name}] Agent died at step {step}. GG!")
                return

            action = pick_action(obs)
            result = await c.submit_action(action)
            step += 1

            if step % 20 == 0:
                print(f"[{name}] step={step} hp={agent['hp']} pos=({agent['x']},{agent['y']}) res={agent.get('inventory',{}).get('resource',0)} action={action['type']}")

        except Exception as e:
            print(f"[{name}] Error at step {step}: {e}")
            await asyncio.sleep(2)
            continue

        await asyncio.sleep(0.3)


if __name__ == "__main__":
    asyncio.run(main())
