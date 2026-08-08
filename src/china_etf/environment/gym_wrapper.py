"""SB3 兼容 Gym 包装（Gate 3/4 用）。

包装 ChinaETFPortfolioEnv 为标准 gymnasium.Env：
- action_space = Box(-1,1)^11（Reviewer BLOCKER-1）
- 数据到达末尾 = truncated（非 terminated；无 policy 终止态）
- 可选 observation scaler（train-only fit，保存/加载随模型）
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
        obs_dim = 8 * len(env.slots) + len(env.slots) + 5
        self.observation_space = spaces.Box(-np.inf, np.inf, shape=(obs_dim,), dtype=np.float32)
        self.action_space = spaces.Box(-1.0, 1.0, shape=(env.action_dim,), dtype=np.float32)
        self._scaler_mean: np.ndarray | None = None
        self._scaler_std: np.ndarray | None = None

    def set_observation_scaler(self, mean: np.ndarray, std: np.ndarray) -> None:
        self._scaler_mean = np.asarray(mean, dtype=np.float32)
        self._scaler_std = np.asarray(std, dtype=np.float32)

    def _normalize(self, obs: np.ndarray) -> np.ndarray:
        if self._scaler_mean is None:
            return obs
        return (obs - self._scaler_mean) / np.maximum(self._scaler_std, 1e-8)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        return self._normalize(self._env.reset()).astype(np.float32), {}

    def step(self, action):
        obs, reward, done, info = self._env.step(np.asarray(action, dtype=np.float64).ravel())
        obs_n = self._normalize(obs).astype(np.float32)
        # 数据到达日历末尾 = truncated（gymnasium 语义）；无 policy 终止态 → terminated=False
        return obs_n, float(reward), False, bool(done), {"env_step": info.get("step"), "weights": info.get("weights")}
