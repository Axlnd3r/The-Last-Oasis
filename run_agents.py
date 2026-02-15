"""
Launch a diverse team of agents to populate the world.

Usage:
    python run_agents.py          # Launch default team (2 Random, 1 Belief, 1 Trader, 1 DQN-sim)
    python run_agents.py 8        # Launch 8 agents (mixed types)

Make sure the server is running first:
    uvicorn app.main:app --reload
"""
from __future__ import annotations

import asyncio
import math
import os
import random
import sys

# Force demo mode
os.environ.pop("CHAIN_RPC_URL", None)
os.environ.pop("MONAD_RPC_URL", None)
os.environ.pop("ENTRY_FEE_CONTRACT_ADDRESS", None)

from agents.sdk import LastOasisClient


# ─── Helper: move towards a target position ───

def move_towards(x: int, y: int, tx: int, ty: int) -> dict:
    dx = 1 if tx > x else (-1 if tx < x else 0)
    dy = 1 if ty > y else (-1 if ty < y else 0)
    # Prefer axis with larger distance
    dist_x = abs(tx - x)
    dist_y = abs(ty - y)
    if dist_x >= dist_y and dx != 0:
        return {"type": "move", "dx": dx, "dy": 0}
    elif dy != 0:
        return {"type": "move", "dx": 0, "dy": dy}
    elif dx != 0:
        return {"type": "move", "dx": dx, "dy": 0}
    return {"type": "rest"}


def distance(x1, y1, x2, y2):
    return abs(x1 - x2) + abs(y1 - y2)


def find_closest_agent(x, y, agents):
    if not agents:
        return None
    return min(agents, key=lambda a: distance(x, y, a["x"], a["y"]))


# ─── RANDOM AGENT: aggressive warrior, seeks combat ───

def pick_random_action(obs: dict) -> dict:
    agent = obs["agent"]
    x, y = int(agent["x"]), int(agent["y"])
    hp = int(agent["hp"])
    resource = int(agent.get("inventory", {}).get("resource", 0))
    nearby = obs.get("nearby_agents", [])
    all_agents = obs.get("all_agents", [])

    if hp < 4:
        return {"type": "rest"}

    # PRIORITY: attack adjacent agent
    for a in nearby:
        if distance(x, y, a["x"], a["y"]) <= 1 and hp > 5:
            return {"type": "attack", "target": a["agent_id"]}

    # Move towards nearest agent if visible nearby
    if nearby and hp > 8:
        target = find_closest_agent(x, y, nearby)
        return move_towards(x, y, target["x"], target["y"])

    # Move towards any known agent (from all_agents)
    if all_agents and hp > 6 and random.random() < 0.6:
        target = find_closest_agent(x, y, all_agents)
        if distance(x, y, target["x"], target["y"]) > 1:
            return move_towards(x, y, target["x"], target["y"])

    # Gather on resource tile
    current = None
    for t in obs.get("tiles", []):
        if int(t["x"]) == x and int(t["y"]) == y:
            current = t
            break
    if current and int(current.get("resource", 0)) > 0 and random.random() < 0.5:
        return {"type": "gather"}

    # Trade if have resources and nearby
    if nearby and resource > 2 and random.random() < 0.2:
        target = random.choice(nearby)
        return {"type": "trade", "target": target["agent_id"], "amount": random.randint(1, min(2, resource))}

    if hp < 10:
        return {"type": "rest"}

    dx, dy = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
    return {"type": "move", "dx": dx, "dy": dy}


# ─── BELIEF AGENT: cautious, avoids danger, seeks safe resources ───

class BeliefState:
    def __init__(self):
        self.hazard = {}
        self.degradation = {}
        self.resource = {}
    def update(self, tiles):
        for t in tiles:
            k = (int(t["x"]), int(t["y"]))
            self.hazard[k] = float(t["hazard"])
            self.degradation[k] = float(t["degradation"])
            self.resource[k] = int(t["resource"])
    def danger(self, x, y):
        return self.hazard.get((x, y), 0.2) * 2.0 + self.degradation.get((x, y), 0.2)


def pick_belief_action(obs: dict, belief: BeliefState) -> dict:
    agent = obs["agent"]
    x, y = int(agent["x"]), int(agent["y"])
    hp = int(agent["hp"])
    resource = int(agent.get("inventory", {}).get("resource", 0))
    belief.update(obs.get("tiles", []))
    nearby = obs.get("nearby_agents", [])
    all_agents = obs.get("all_agents", [])

    # Flee from nearby agents if low HP
    if hp <= 5 and nearby:
        best_dir, best_d = None, 0
        for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
            d = min((distance(x+dx, y+dy, a["x"], a["y"])) for a in nearby)
            if d > best_d:
                best_d = d
                best_dir = (dx, dy)
        if best_dir:
            return {"type": "move", "dx": best_dir[0], "dy": best_dir[1]}

    if hp <= 8:
        return {"type": "rest"}

    # Gather on current tile if safe
    cur_res = 0
    for t in obs["tiles"]:
        if int(t["x"]) == x and int(t["y"]) == y:
            cur_res = int(t["resource"])
    if cur_res > 0 and belief.danger(x, y) < 0.65:
        return {"type": "gather"}

    # Trade with nearby agents if we have excess
    if nearby and resource > 5:
        weakest = min(nearby, key=lambda a: a.get("hp", 20))
        amt = random.randint(1, min(3, resource))
        return {"type": "trade", "target": weakest["agent_id"], "amount": amt}

    # Move towards other agents to socialize (trade)
    if all_agents and resource > 3 and random.random() < 0.4:
        closest = find_closest_agent(x, y, all_agents)
        d = distance(x, y, closest["x"], closest["y"])
        if d > 1 and d < 8:
            return move_towards(x, y, closest["x"], closest["y"])

    # Seek best resource tile
    best_tile, best_score = None, -999
    for (rx, ry), res in belief.resource.items():
        if res < 5: continue
        dist = abs(rx-x)+abs(ry-y)
        if dist == 0 or dist > 3: continue
        score = res / max(1, dist) - belief.danger(rx, ry) * 10
        if score > best_score:
            best_score = score
            best_tile = (rx, ry)
    if best_tile:
        return move_towards(x, y, best_tile[0], best_tile[1])

    # Move to safest
    best_dir, best_s = (0,0), belief.danger(x, y)
    for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
        s = belief.danger(x+dx, y+dy)
        if s < best_s:
            best_s = s
            best_dir = (dx, dy)
    if best_dir != (0, 0):
        return {"type": "move", "dx": best_dir[0], "dy": best_dir[1]}
    return {"type": "rest"}


# ─── TRADER AGENT: prioritizes gathering and trading with others ───

def pick_trader_action(obs: dict) -> dict:
    agent = obs["agent"]
    x, y = int(agent["x"]), int(agent["y"])
    hp = int(agent["hp"])
    resource = int(agent.get("inventory", {}).get("resource", 0))
    nearby = obs.get("nearby_agents", [])
    all_agents = obs.get("all_agents", [])
    tiles = obs.get("tiles", [])

    # TRADE PRIORITY: always try to trade when near someone
    if nearby and resource > 1:
        target = min(nearby, key=lambda a: a.get("hp", 20))
        amt = random.randint(1, min(5, resource))
        return {"type": "trade", "target": target["agent_id"], "amount": amt}

    # Move towards other agents to trade
    if all_agents and resource > 2:
        closest = find_closest_agent(x, y, all_agents)
        d = distance(x, y, closest["x"], closest["y"])
        if d > 1:
            return move_towards(x, y, closest["x"], closest["y"])

    # Even without resources, seek other agents
    if all_agents and random.random() < 0.3:
        closest = find_closest_agent(x, y, all_agents)
        d = distance(x, y, closest["x"], closest["y"])
        if d > 2:
            return move_towards(x, y, closest["x"], closest["y"])

    cur = None
    for t in tiles:
        if int(t["x"]) == x and int(t["y"]) == y:
            cur = t
            break
    risk = float(cur["hazard"]) * 2 + float(cur["degradation"]) if cur else 1.0

    if hp <= 10 or risk > 0.9:
        best, best_s = None, 10
        for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
            for t in tiles:
                if int(t["x"])==x+dx and int(t["y"])==y+dy:
                    s = float(t["hazard"])*2+float(t["degradation"])
                    if s < best_s: best_s = s; best = (dx, dy)
        if best: return {"type": "move", "dx": best[0], "dy": best[1]}
        return {"type": "rest"}

    if hp <= 12:
        return {"type": "rest"}

    # Gather resources
    if cur and int(cur.get("resource", 0)) > 0:
        return {"type": "gather"}

    # Move to richest neighbor
    best, best_r = None, 0
    for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
        for t in tiles:
            if int(t["x"])==x+dx and int(t["y"])==y+dy:
                r = int(t.get("resource", 0))
                if r > best_r and float(t.get("hazard",0)) < 0.5:
                    best_r = r; best = (dx, dy)
    if best:
        return {"type": "move", "dx": best[0], "dy": best[1]}
    dx, dy = random.choice([(1,0),(-1,0),(0,1),(0,-1)])
    return {"type": "move", "dx": dx, "dy": dy}


# ─── DQN Learning Tracker ───

class DQNTracker:
    """Tracks DQN decision-making for the dashboard panel."""
    def __init__(self):
        self.episode_rewards: list[float] = []
        self.current_reward: float = 0.0
        self.mistakes: list[dict] = []
        self.step_count: int = 0
        self.epsilon: float = 1.0
        self.loss_history: list[float] = []

    def record_step(self, obs: dict, action: dict, scores: dict, chosen: str):
        self.step_count += 1
        agent = obs["agent"]
        hp = int(agent["hp"])
        resource = int(agent.get("inventory", {}).get("resource", 0))

        # Reward = delta HP + delta resource
        reward = 0.0
        if action["type"] == "gather":
            reward += 1.5
        elif action["type"] == "attack":
            reward += 2.0
        elif action["type"] == "trade":
            reward += 1.0
        elif action["type"] == "rest" and hp < 10:
            reward += 0.5
        elif action["type"] == "move":
            reward += 0.1

        # Penalty for bad decisions
        cur_haz = 0
        for t in obs.get("tiles", []):
            if int(t["x"]) == int(agent["x"]) and int(t["y"]) == int(agent["y"]):
                cur_haz = float(t.get("hazard", 0))
        if cur_haz > 0.5 and action["type"] != "move":
            reward -= 2.0
            self.mistakes.append({
                "tick": obs.get("tick", 0),
                "bad_action": action["type"],
                "consequence": f"stayed in hazard {cur_haz:.0%}",
                "correction": "move to safer tile",
            })
        if hp < 5 and action["type"] == "attack":
            reward -= 3.0
            self.mistakes.append({
                "tick": obs.get("tick", 0),
                "bad_action": "attack at low HP",
                "consequence": f"HP={hp}, risk of death",
                "correction": "rest to recover",
            })

        self.current_reward += reward

        # Simulated loss (decreasing over time = learning)
        base_loss = max(0.5, 10.0 - self.step_count * 0.08)
        noise = random.uniform(-1, 1)
        self.loss_history.append(base_loss + noise)

        # Epsilon decay
        self.epsilon = max(0.05, 1.0 - self.step_count * 0.015)

        # Episode boundary every 20 steps
        if self.step_count % 20 == 0:
            self.episode_rewards.append(round(self.current_reward, 2))
            self.current_reward = 0.0

    async def report(self, base_url: str):
        """Send DQN log to the server dashboard."""
        import httpx
        try:
            payload = {
                "mistakes": [m for m in self.mistakes[-20:]],
                "episode_rewards": self.episode_rewards[-50:],
                "step_count": self.step_count,
                "epsilon": round(self.epsilon, 4),
                "loss_history": [round(l, 3) for l in self.loss_history[-50:]],
                "total_reward": round(sum(self.episode_rewards) + self.current_reward, 2),
            }
            async with httpx.AsyncClient() as c:
                await c.post(f"{base_url}/admin/dqn-log", json=payload, timeout=5.0)
        except Exception:
            pass


# ─── DQN-SIM AGENT: smart scorer, hunts weak agents ───

def pick_dqn_action(obs: dict) -> tuple[dict, dict]:
    agent = obs["agent"]
    x, y = int(agent["x"]), int(agent["y"])
    hp = int(agent["hp"])
    resource = int(agent.get("inventory", {}).get("resource", 0))
    nearby = obs.get("nearby_agents", [])
    all_agents = obs.get("all_agents", [])
    tiles = obs.get("tiles", [])

    cur = None
    for t in tiles:
        if int(t["x"]) == x and int(t["y"]) == y:
            cur = t
            break

    # Score actions
    scores = {"rest": 0, "gather": -5}

    if hp < 8: scores["rest"] += 5
    if hp < 4: scores["rest"] += 10

    cur_res = int(cur.get("resource", 0)) if cur else 0
    cur_haz = float(cur.get("hazard", 0)) if cur else 1
    if cur_res > 0 and cur_haz < 0.5:
        scores["gather"] = cur_res * 0.5 + 3

    # Attack adjacent
    if nearby and hp > 6:
        for a in nearby:
            if distance(x, y, a["x"], a["y"]) <= 1:
                bonus = 10 if a.get("hp", 20) < hp else 3
                scores["attack_adj"] = max(scores.get("attack_adj", 0), bonus)

    # Hunt: move towards weakest agent
    hunt_target = None
    if all_agents and hp > 10:
        weakest = min(all_agents, key=lambda a: a.get("hp", 20))
        d = distance(x, y, weakest["x"], weakest["y"])
        if d <= 6 and weakest.get("hp", 20) < hp:
            scores["hunt"] = 7 - d + (hp - weakest.get("hp", 20)) * 0.5
            hunt_target = weakest

    # Trade if nearby and have resources
    if nearby and resource > 2:
        scores["trade"] = 4

    # Move to resource
    best_res_tile = None
    best_res_score = 0
    for t in tiles:
        r = int(t.get("resource", 0))
        h = float(t.get("hazard", 0))
        dist = abs(int(t["x"]) - x) + abs(int(t["y"]) - y)
        if dist == 0 or r < 5 or h > 0.5: continue
        s = r / max(1, dist) * (1 - h)
        if s > best_res_score:
            best_res_score = s
            best_res_tile = t
    if best_res_tile:
        scores["move_res"] = best_res_score * 0.8

    # Socialize: move toward nearest agent
    if all_agents and random.random() < 0.3:
        closest = find_closest_agent(x, y, all_agents)
        d = distance(x, y, closest["x"], closest["y"])
        if d > 1:
            scores["socialize"] = 3 - d * 0.3

    # Exploration noise
    for k in scores:
        scores[k] += random.uniform(-0.5, 0.5)

    best = max(scores, key=scores.get)

    if best == "rest":
        return {"type": "rest"}, scores
    elif best == "gather":
        return {"type": "gather"}, scores
    elif best == "attack_adj":
        adj = [a for a in nearby if distance(x, y, a["x"], a["y"]) <= 1]
        if adj:
            target = min(adj, key=lambda a: a.get("hp", 20))
            return {"type": "attack", "target": target["agent_id"]}, scores
    elif best == "hunt" and hunt_target:
        return move_towards(x, y, hunt_target["x"], hunt_target["y"]), scores
    elif best == "trade" and nearby:
        target = random.choice(nearby)
        amt = random.randint(1, min(3, resource))
        return {"type": "trade", "target": target["agent_id"], "amount": amt}, scores
    elif best == "move_res" and best_res_tile:
        return move_towards(x, y, int(best_res_tile["x"]), int(best_res_tile["y"])), scores
    elif best == "socialize" and all_agents:
        closest = find_closest_agent(x, y, all_agents)
        return move_towards(x, y, closest["x"], closest["y"]), scores

    dx, dy = random.choice([(1,0),(-1,0),(0,1),(0,-1)])
    return {"type": "move", "dx": dx, "dy": dy}, scores


# ─── Default agent roster ───

AGENT_CONFIGS = [
    {"name": "Random_A", "type": "random"},
    {"name": "Random_B", "type": "random"},
    {"name": "Belief_A", "type": "belief"},
    {"name": "Trader_A", "type": "trader"},
    {"name": "DQN_Sim",  "type": "dqn"},
]


async def run_agent(config: dict, base_url: str) -> None:
    name = config["name"]
    agent_type = config["type"]
    tx_ref = f"demo_{name.lower()}_{random.randint(1000,9999)}"
    client = LastOasisClient(base_url)

    try:
        confirm = await client.entry_confirm(tx_ref=tx_ref, name=name)
    except Exception as e:
        print(f"  [{name}] Entry FAILED: {e}")
        return

    client.api_key = confirm.api_key
    print(f"  [{name}] ({agent_type}) Entered! id={confirm.agent_id[:8]}")

    belief = BeliefState() if agent_type == "belief" else None
    dqn_tracker = DQNTracker() if agent_type == "dqn" else None
    step = 0

    while True:
        try:
            obs = await client.observation()
            agent = obs["agent"]
            if not agent.get("alive", True):
                inv = agent.get("inventory", {})
                print(f"  [{name}] DIED at step {step}. Final res={inv.get('resource',0)}")
                if dqn_tracker:
                    await dqn_tracker.report(base_url)
                return

            scores = {}
            if agent_type == "random":
                action = pick_random_action(obs)
            elif agent_type == "belief":
                action = pick_belief_action(obs, belief)
            elif agent_type == "trader":
                action = pick_trader_action(obs)
            elif agent_type == "dqn":
                action, scores = pick_dqn_action(obs)
            else:
                action = pick_random_action(obs)

            await client.submit_action(action)
            step += 1

            # Track DQN decisions
            if dqn_tracker:
                dqn_tracker.record_step(obs, action, scores, action["type"])
                # Report every 5 steps so dashboard updates frequently
                if step % 5 == 0:
                    await dqn_tracker.report(base_url)

            if step % 20 == 0:
                inv = agent.get("inventory", {})
                nearby_count = len(obs.get("nearby_agents", []))
                print(f"  [{name}] ({agent_type}) step={step} hp={agent['hp']} pos=({agent['x']},{agent['y']}) res={inv.get('resource',0)} nearby={nearby_count} act={action['type']}")

        except Exception as e:
            print(f"  [{name}] Error: {e}")
            await asyncio.sleep(2)
            continue

        await asyncio.sleep(random.uniform(0.2, 0.4))


async def main() -> None:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    base_url = os.environ.get("BASE_URL", "http://127.0.0.1:8000")

    print(f"=== THE LAST OASIS - Agent Launcher ===")
    print(f"Server: {base_url}")
    print(f"Launching {count} agents...\n")

    configs = []
    if count <= len(AGENT_CONFIGS):
        configs = AGENT_CONFIGS[:count]
    else:
        configs = list(AGENT_CONFIGS)
        types = ["random", "belief", "trader", "dqn"]
        for i in range(count - len(AGENT_CONFIGS)):
            t = types[i % len(types)]
            configs.append({"name": f"{t.capitalize()}_{chr(66 + i)}", "type": t})

    print("Agent roster:")
    for c in configs:
        print(f"  - {c['name']} ({c['type']})")
    print()

    tasks = [asyncio.create_task(run_agent(c, base_url)) for c in configs]

    try:
        await asyncio.gather(*tasks)
        print("\nAll agents have died. Game over!")
    except KeyboardInterrupt:
        print("\nStopping agents...")
        for t in tasks:
            t.cancel()


if __name__ == "__main__":
    asyncio.run(main())
