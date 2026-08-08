"""确定性 baselines（GATE_4_PRECHECK §G4.1）。

全部走标准 Environment path：target weight → 逆 ActionTransform `a=2w-1` →
ActionTransform（score=w）→ RiskOverlay → execution，成本与 RL 完全一致。
权重只用 ≤t 数据（严格 PIT）。

- EqualWeight   : 常权重 1/N
- RiskParity    : w ∝ 1/vol_i（rolling std，lookback 默认 60）
- MinimumVariance: shrinkage(0.5)→无约束 GMV→bounded-simplex 投影（numpy only，
  无 scipy 依赖；精确 box-QP 留待 pilot 若需要）
- Momentum      : w ∝ max(r[t-lookback, t-skip], 0)（经典 12-1，默认 252/21）
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..risk.risk_overlay import RiskOverlayV0


class BaselinePolicy:
    """将目标权重函数包装为 policy(obs) → action（obs 被忽略，仅用决策日）。"""

    def __init__(self, env, target_weight_fn) -> None:
        self._env = env
        self._fn = target_weight_fn

    def __call__(self, obs: np.ndarray) -> np.ndarray:
        t = self._env.calendar[self._env._i]
        w = np.asarray(self._fn(t), dtype=float)
        w = np.clip(w, 0.0, None)
        s = float(w.sum())
        n = len(self._env.slots)
        if s <= 1e-12:
            w = np.full(n, 1.0 / n)
        else:
            w = w / s
        return (2.0 * w - 1.0).astype(np.float64)


def _log_returns(adj: pd.DataFrame) -> pd.DataFrame:
    return np.log(adj / adj.shift(1))


def equal_weight_policy(env):
    n = len(env.slots)
    w = np.full(n, 1.0 / n)

    def target(t):
        return w.copy()

    return BaselinePolicy(env, target)


def risk_parity_policy(env, lookback: int = 60):
    r = _log_returns(env.adj)

    def target(t):
        hist = r.loc[:t]
        vol = hist.iloc[-lookback:].std()
        inv = vol.rdiv(1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        return inv.to_numpy()

    return BaselinePolicy(env, target)


def minimum_variance_policy(env, lookback: int = 120, shrinkage: float = 0.5):
    r = _log_returns(env.adj)
    n = len(env.slots)

    def target(t):
        window = r.loc[:t].iloc[-lookback:].dropna(how="any")
        if len(window) < max(n, 20):  # 共同有限行不足 → EW（如上市前）
            return np.full(n, 1.0 / n)
        cov = window.cov().to_numpy()
        diag = np.diag(np.diag(cov))
        sigma = shrinkage * diag + (1.0 - shrinkage) * cov
        try:
            inv = np.linalg.pinv(sigma)
            ones = np.ones(n)
            w = inv @ ones / (ones @ inv @ ones)  # 无约束 GMV
        except np.linalg.LinAlgError:
            return np.full(n, 1.0 / n)
        w = np.clip(w, 0.0, None)
        # long-only 有界 simplex 投影（与 RiskOverlay 同一投影，保证 sum=1）
        return RiskOverlayV0._waterfill(w, np.full(n, 1.0), total=1.0)

    return BaselinePolicy(env, target)


def momentum_policy(env, lookback: int = 252, skip: int = 21):
    adj = env.adj
    n = len(env.slots)
    cols = list(adj.columns)

    def target(t):
        hist = adj.loc[:t]
        if len(hist) <= lookback:
            return np.full(n, 1.0 / n)
        start = hist.index[-lookback]
        skip_idx = hist.index[-skip] if len(hist) > skip else start
        # 锚点取 ≤start / ≤skip_idx 的最后有效价（上市前 NaN 槽位得分=0，不产生 NaN）
        p_start = adj.loc[:start, cols].ffill().iloc[-1]
        p_skip = adj.loc[:skip_idx, cols].ffill().iloc[-1]
        with np.errstate(invalid="ignore", divide="ignore"):
            score = np.log(p_skip / p_start).to_numpy()
        score = np.where(np.isfinite(score) & (score > 0.0), score, 0.0)
        s = float(score.sum())
        if s <= 1e-12:
            return np.full(n, 1.0 / n)
        return score / s

    return BaselinePolicy(env, target)
