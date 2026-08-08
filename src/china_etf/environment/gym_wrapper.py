"""SB3 兼容 Gym 包装（Gate 3/4 用）。

包装 ChinaETFPortfolioEnv 为标准 gymnasium.Env：
- action_space = Box(-1,1)^11（Reviewer BLOCKER-1）
- 数据到达末尾 = truncated（非 terminated；无 policy 终止态）
- observation 归一化 V2：仅 8N+5 维外生特征用 train-only scaler；
  末 N 维 actual portfolio weights 保持 [0,1] 原始含义（BLOCKER-B）
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
        n = len(env.slots)
        self._market_dim = 8 * n + 5
        obs_dim = self._market_dim + n
        self.observation_space = spaces.Box(-np.inf, np.inf, shape=(obs_dim,), dtype=np.float32)
        self.action_space = spaces.Box(-1.0, 1.0, shape=(env.action_dim,), dtype=np.float32)
        # obs 布局：[8N per-asset][N weights][5 global] → 外生 = [0:8N] ∪ [8N+N : 8N+N+5]
        self._market_positions = list(range(8 * n)) + list(range(8 * n + n, obs_dim))
        self._scaler_mean: np.ndarray | None = None
        self._scaler_std: np.ndarray | None = None

    def set_market_scaler(self, mean: np.ndarray, std: np.ndarray) -> None:
        self._scaler_mean = np.asarray(mean, dtype=np.float32)
        self._scaler_std = np.asarray(std, dtype=np.float32)

    def _normalize(self, obs: np.ndarray) -> np.ndarray:
        o = np.asarray(obs, dtype=np.float32).copy()
        if self._scaler_mean is not None:
            o[self._market_positions] = (
                o[self._market_positions] - self._scaler_mean
            ) / np.maximum(self._scaler_std, 1e-8)
        return o

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        return self._normalize(self._env.reset()).astype(np.float32), {}

    def step(self, action):
        obs, reward, done, info = self._env.step(np.asarray(action, dtype=np.float64).ravel())
        obs_n = self._normalize(obs).astype(np.float32)
        # 数据到达日历末尾 = truncated（gymnasium 语义）；无 policy 终止态 → terminated=False
        return obs_n, float(reward), False, bool(done), {"env_step": info.get("step"), "weights": info.get("weights")}
