from __future__ import annotations

import asyncio
import os
import time
from typing import Any

from .agent_dqn import DQNAgent
from .sdk import LastOasisClient


def _action_from_index(idx: int) -> dict[str, Any]:
    if idx == 0:
        return {"type": "move", "dx": 0, "dy": -1}
    if idx == 1:
        return {"type": "move", "dx": 0, "dy": 1}
    if idx == 2:
        return {"type": "move", "dx": -1, "dy": 0}
    if idx == 3:
        return {"type": "move", "dx": 1, "dy": 0}
    if idx == 4:
        return {"type": "gather"}
    return {"type": "rest"}


def _reward(prev_obs: dict[str, Any], next_obs: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    prev_agent = prev_obs.get("agent", {})
    next_agent = next_obs.get("agent", {})

    prev_hp = float(prev_agent.get("hp", 0.0))
    next_hp = float(next_agent.get("hp", 0.0))
    hp_delta = next_hp - prev_hp
    damage_taken = max(0.0, prev_hp - next_hp)
    hp_recovered = max(0.0, next_hp - prev_hp)

    prev_inv = prev_agent.get("inventory", {}) or {}
    next_inv = next_agent.get("inventory", {}) or {}
    prev_res = float(prev_inv.get("resource", 0.0))
    next_res = float(next_inv.get("resource", 0.0))
    resource_collected = max(0.0, next_res - prev_res)

    eliminated = not bool(next_agent.get("alive", True))

    reward = 0.0
    reward += resource_collected * 2.0
    reward += hp_recovered * 1.0
    reward += 1.0
    reward -= damage_taken * 5.0
    reward -= 10.0 if eliminated else 0.0

    outcome = {
        "tick": int(next_obs.get("tick", 0)),
        "hp_delta": hp_delta,
        "damage_taken": damage_taken,
        "hp_recovered": hp_recovered,
        "resource_collected": resource_collected,
        "eliminated": eliminated,
    }
    return reward, outcome


async def _wait_for_tick(c: LastOasisClient, min_tick: int, timeout_s: float = 5.0) -> dict[str, Any]:
    start = time.time()
    while True:
        obs = await c.observation()
        t = int(obs.get("tick", 0))
        if t >= min_tick:
            return obs
        if time.time() - start > timeout_s:
            return obs
        await asyncio.sleep(0.05)


async def train_dqn_agent(episodes: int = 100, max_ticks_per_episode: int = 500) -> DQNAgent:
    base = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
    checkpoint_dir = os.environ.get("CHECKPOINT_DIR", "checkpoints")
    os.makedirs(checkpoint_dir, exist_ok=True)

    agent = DQNAgent()

    for ep in range(int(episodes)):
        c = LastOasisClient(base)
        confirm = await c.entry_confirm(tx_ref=f"demo_dqn_ep{ep}", name=f"agent_dqn_ep{ep}")
        c.api_key = confirm.api_key

        obs = await c.observation()
        total_reward = 0.0

        for step in range(int(max_ticks_per_episode)):
            if not bool(obs.get("agent", {}).get("alive", True)):
                break

            action_idx = agent.select_action(obs)
            await c.submit_action(_action_from_index(action_idx))

            next_obs = await _wait_for_tick(c, min_tick=int(obs.get("tick", 0)) + 1)
            reward, outcome = _reward(obs, next_obs)
            total_reward += reward

            done = bool(outcome["eliminated"])
            agent.remember(obs, action_idx, reward, next_obs, done)

            if step % 4 == 0:
                loss = agent.learn()
                if loss is not None:
                    print(f"ep={ep} tick={outcome['tick']} loss={loss:.4f} epsilon={agent.epsilon:.3f}")

            if outcome["damage_taken"] > 0:
                new_action = agent.select_action(next_obs)
                agent.track_mistake_correction(
                    tick=int(outcome["tick"]),
                    prev_action=int(action_idx),
                    consequence=float(outcome["damage_taken"]),
                    new_action=int(new_action),
                )

            if done:
                break

            obs = next_obs

        agent.update_target_network()
        agent.episode_rewards.append(total_reward)
        print(f"episode={ep} total_reward={total_reward:.2f} epsilon={agent.epsilon:.3f}")

        if ep % 10 == 0:
            agent.save_model(os.path.join(checkpoint_dir, f"dqn_ep{ep}.pt"))

        if ep % 5 == 0:
            await _report_dqn_log(base, agent)

    await _report_dqn_log(base, agent)
    return agent


async def _report_dqn_log(base_url: str, agent: DQNAgent) -> None:
    import httpx
    try:
        payload = {
            "mistakes": [m.__dict__ for m in agent.mistakes_learned[-20:]],
            "episode_rewards": list(agent.episode_rewards[-50:]),
        }
        async with httpx.AsyncClient() as c:
            await c.post(f"{base_url}/admin/dqn-log", json=payload, timeout=5.0)
    except Exception:
        pass


async def main() -> None:
    episodes = int(os.environ.get("EPISODES", "100"))
    max_ticks = int(os.environ.get("MAX_TICKS_PER_EPISODE", "500"))
    await train_dqn_agent(episodes=episodes, max_ticks_per_episode=max_ticks)


if __name__ == "__main__":
    asyncio.run(main())

