"""SB3 兼容 Gym 包装（Gate 3 RL Sanity 用）。

包装 ChinaETFPortfolioEnv（plain python）为标准 gymnasium.Env。
"""

from __future__ import annotations

import numpy as np
import gymnasium as gym
from gymnasium import spaces

from .portfolio_env import ChinaETFPortfolioEnv


class ChinaETFGymEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, env: ChinaETFPortfolioEnv) -> None:
        self._env = env
        self.observation_space = spaces.Box(-np.inf, np.inf, shape=(104,), dtype=np.float32)
        self.action_space = spaces.Box(-10.0, 10.0, shape=(env.action_dim,), dtype=np.float32)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        return self._env.reset().astype(np.float32), {}

    def step(self, action):
        obs, reward, done, info = self._env.step(np.asarray(action, dtype=np.float64).ravel())
        return (
            obs.astype(np.float32),
            float(reward),
            bool(done),
            False,
            {"env_step": info.get("step")},
        )
