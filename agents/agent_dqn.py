from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Optional

import random


def _require_torch() -> Any:
    try:
        import torch
        import torch.nn as nn
    except Exception as e:
        raise RuntimeError("missing_dependency_torch") from e
    return torch, nn


def _require_numpy() -> Any:
    try:
        import numpy as np
    except Exception as e:
        raise RuntimeError("missing_dependency_numpy") from e
    return np


@dataclass(frozen=True)
class MistakeCorrection:
    tick: int
    bad_action: str
    consequence: float
    correction: str


class DQN:
    def __init__(self, state_dim: int, action_dim: int, hidden_dim: int = 128) -> None:
        torch, nn = _require_torch()
        self.torch = torch
        self.nn = nn
        self.network = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, action_dim),
        )

    def parameters(self) -> Any:
        return self.network.parameters()

    def state_dict(self) -> Any:
        return self.network.state_dict()

    def load_state_dict(self, state: Any) -> None:
        self.network.load_state_dict(state)

    def to(self, device: Any) -> "DQN":
        self.network.to(device)
        return self

    def eval(self) -> None:
        self.network.eval()

    def __call__(self, x: Any) -> Any:
        return self.network(x)


class DQNAgent:
    def __init__(
        self,
        state_dim: int = 100,
        action_dim: int = 6,
        hidden_dim: int = 128,
        lr: float = 0.001,
        memory_size: int = 10_000,
        batch_size: int = 64,
        gamma: float = 0.99,
        epsilon: float = 1.0,
        epsilon_min: float = 0.01,
        epsilon_decay: float = 0.995,
    ) -> None:
        torch, nn = _require_torch()
        self.torch = torch
        self.nn = nn

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        self.state_dim = state_dim
        self.action_dim = action_dim
        self.actions = ["move_up", "move_down", "move_left", "move_right", "gather", "rest"]

        self.policy_net = DQN(state_dim, action_dim, hidden_dim).to(self.device)
        self.target_net = DQN(state_dim, action_dim, hidden_dim).to(self.device)
        self.target_net.load_state_dict(self.policy_net.state_dict())

        self.optimizer = torch.optim.Adam(self.policy_net.parameters(), lr=lr)
        self.memory: Deque[tuple[dict[str, Any], int, float, dict[str, Any], bool]] = deque(maxlen=memory_size)
        self.batch_size = batch_size
        self.gamma = gamma

        self.epsilon = epsilon
        self.epsilon_min = epsilon_min
        self.epsilon_decay = epsilon_decay

        self.episode_rewards: list[float] = []
        self.mistakes_learned: list[MistakeCorrection] = []

    def state_to_tensor(self, observation: dict[str, Any]) -> Any:
        torch = self.torch
        features: list[float] = []

        agent = observation.get("agent", {})
        features.extend(
            [
                float(agent.get("hp", 0.0)) / 20.0,
                float(agent.get("x", 0.0)) / 20.0,
                float(agent.get("y", 0.0)) / 20.0,
                float(agent.get("inventory", {}).get("resource", 0.0)) / 50.0,
            ]
        )

        ax = int(agent.get("x", 0))
        ay = int(agent.get("y", 0))
        tile_by_xy: dict[tuple[int, int], dict[str, Any]] = {}
        for t in observation.get("tiles", []) or []:
            tile_by_xy[(int(t["x"]), int(t["y"]))] = t

        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                t = tile_by_xy.get((ax + dx, ay + dy))
                if not t:
                    features.extend([0.0, 0.0, 0.0])
                    continue
                features.extend(
                    [
                        float(t.get("degradation", 0.0)),
                        float(t.get("resource", 0.0)) / 100.0,
                        float(t.get("hazard", 0.0)),
                    ]
                )

        while len(features) < self.state_dim:
            features.append(0.0)

        arr = features[: self.state_dim]
        return torch.tensor(arr, dtype=torch.float32, device=self.device)

    def select_action(self, observation: dict[str, Any]) -> int:
        torch = self.torch
        if random.random() < self.epsilon:
            return random.randint(0, self.action_dim - 1)
        with torch.no_grad():
            state = self.state_to_tensor(observation)
            q_values = self.policy_net(state)
            return int(q_values.argmax().item())

    def remember(self, state: dict[str, Any], action: int, reward: float, next_state: dict[str, Any], done: bool) -> None:
        self.memory.append((state, action, reward, next_state, done))

    def learn(self) -> Optional[float]:
        torch = self.torch
        if len(self.memory) < self.batch_size:
            return None

        batch = random.sample(self.memory, self.batch_size)
        states, actions, rewards, next_states, dones = zip(*batch)

        state_t = torch.stack([self.state_to_tensor(s) for s in states])
        next_state_t = torch.stack([self.state_to_tensor(s) for s in next_states])
        action_t = torch.tensor(actions, dtype=torch.int64, device=self.device)
        reward_t = torch.tensor(rewards, dtype=torch.float32, device=self.device)
        done_t = torch.tensor(dones, dtype=torch.float32, device=self.device)

        current_q = self.policy_net(state_t).gather(1, action_t.unsqueeze(1)).squeeze(1)
        with torch.no_grad():
            next_q = self.target_net(next_state_t).max(1)[0]
            target_q = reward_t + (1.0 - done_t) * self.gamma * next_q

        loss = self.nn.MSELoss()(current_q, target_q)

        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay

        return float(loss.item())

    def track_mistake_correction(self, tick: int, prev_action: int, consequence: float, new_action: int) -> None:
        if consequence <= 0:
            return
        self.mistakes_learned.append(
            MistakeCorrection(
                tick=int(tick),
                bad_action=self.actions[int(prev_action)],
                consequence=float(consequence),
                correction=self.actions[int(new_action)],
            )
        )

    def update_target_network(self) -> None:
        self.target_net.load_state_dict(self.policy_net.state_dict())

    def save_model(self, path: str) -> None:
        torch = self.torch
        payload = {
            "policy_net": self.policy_net.state_dict(),
            "target_net": self.target_net.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "epsilon": float(self.epsilon),
            "episode_rewards": list(self.episode_rewards),
            "mistakes_learned": [m.__dict__ for m in self.mistakes_learned],
        }
        torch.save(payload, path)

    def load_model(self, path: str) -> None:
        torch = self.torch
        ckpt = torch.load(path, map_location=self.device)
        self.policy_net.load_state_dict(ckpt["policy_net"])
        self.target_net.load_state_dict(ckpt["target_net"])
        self.optimizer.load_state_dict(ckpt["optimizer"])
        self.epsilon = float(ckpt.get("epsilon", self.epsilon))

