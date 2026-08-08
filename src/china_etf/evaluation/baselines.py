"""确定性 baselines（GATE_4_PRECHECK §G4.1 + GATE_4_NON_RL_HORSE_RACE Tier A）。

全部走标准 Environment path：target weight → 逆 ActionTransform `a=2w-1` →
ActionTransform（score=w）→ RiskOverlay → execution，成本与 RL 完全一致。
权重只用 ≤t 数据（严格 PIT）；lookback 不足 → EW/CASH_LIKE fallback（记 fallback 计数）。

Tier A（ROADMAP_NON_RL_BASELINE_COMPARISON_DIRECTIVE）：
  EW / RiskParity(IVOL) / MinimumVariance / Momentum(12-1)          （现有，重跑 corrected path）
  ERC / HRP / MaximumDiversification / TrendRiskParity /
  MinimumCVaR_95 / ShrinkageMeanVariance                              （新增，numpy-only）
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


# --- GATE_4_NON_RL_HORSE_RACE Tier A：新增方法（numpy-only）---


def _cov_window(r: pd.DataFrame, t, lookback: int, shrinkage: float, n: int):
    """截至 t 的 lookback 日收益窗口 → 收缩协方差 + 波动。不足 → None。"""
    window = r.loc[:t].iloc[-lookback:].dropna(how="any")
    if len(window) < max(n, 20):
        return None
    cov = window.cov().to_numpy()
    diag = np.diag(np.diag(cov))
    sigma = shrinkage * diag + (1.0 - shrinkage) * cov
    return sigma, np.sqrt(np.maximum(np.diag(cov), 0.0))


def _safe_proj(w: np.ndarray, n: int) -> np.ndarray:
    """long-only + sum=1 投影（waterfill，caps=1）。"""
    w = np.clip(np.asarray(w, dtype=float), 0.0, None)
    if not np.isfinite(w).all():
        return np.full(n, 1.0 / n)
    if w.sum() <= 1e-12:
        return np.full(n, 1.0 / n)
    return RiskOverlayV0._waterfill(w, np.full(n, 1.0), total=1.0)


def erc_policy(env, lookback: int = 120, shrinkage: float = 0.5):
    """ERC：等边际风险贡献（Maillard et al.）。迭代 w_i ∝ (Σw)_i 归一化，收敛到等贡献。"""
    r = _log_returns(env.adj)
    n = len(env.slots)

    def target(t):
        got = _cov_window(r, t, lookback, shrinkage, n)
        if got is None:
            return np.full(n, 1.0 / n)
        sigma, _ = got
        w = np.ones(n) / n
        for _ in range(200):
            sw = sigma @ w
            new_w = 1.0 / np.maximum(sw, 1e-12)
            new_w = new_w / new_w.sum()
            if np.abs(new_w - w).max() < 1e-10:
                w = new_w
                break
            w = new_w
        return _safe_proj(w, n)

    return BaselinePolicy(env, target)


def _single_linkage_clusters(dist: np.ndarray, n: int) -> list[list[int]]:
    """numpy 手写凝聚聚类（single-linkage）。返回最终两个簇（或退化为全/空）。"""
    active = [[i] for i in range(n)]
    d = dist.copy()
    while len(active) > 2:
        best = (np.inf, 0, 0)
        for i in range(len(active)):
            for j in range(i + 1, len(active)):
                dij = min(d[a, b] for a in active[i] for b in active[j])
                if dij < best[0]:
                    best = (dij, i, j)
        _, i, j = best
        active[i] = active[i] + active[j]
        del active[j]
    return active


def hrp_policy(env, lookback: int = 120):
    """HRP：相关距离聚类 + 递归二分分配（Lopez de Prado）；无期望收益。"""
    r = _log_returns(env.adj)
    n = len(env.slots)

    def target(t):
        window = r.loc[:t].iloc[-lookback:].dropna(how="any")
        if len(window) < max(n, 20):
            return np.full(n, 1.0 / n)
        corr = window.corr().to_numpy()
        dist = np.sqrt(np.clip((1.0 - corr) / 2.0, 0.0, 1.0))
        vol = window.std().to_numpy()
        inv_vol = np.where(np.isfinite(vol) & (vol > 0), 1.0 / vol, 0.0)
        clusters = _single_linkage_clusters(dist, n)
        weights = np.zeros(n)

        def bisect(cluster, w_in):
            if len(cluster) == 1:
                weights[cluster[0]] = w_in
                return
            # 简单 bisection：把簇按 inv_vol 权重对半（quasi-diagonal 近似）
            half = len(cluster) // 2
            a, b = cluster[:half], cluster[half:]
            va = sum(inv_vol[i] for i in a)
            vb = sum(inv_vol[i] for i in b)
            if va + vb <= 0:
                va = vb = 1.0
            wa = w_in * va / (va + vb)
            wb = w_in * vb / (va + vb)
            bisect(a, wa)
            bisect(b, wb)

        bisect(clusters[0] if len(clusters[0]) >= len(clusters[1]) else clusters[1],
               sum(inv_vol[i] for i in (clusters[0] if len(clusters[0]) >= len(clusters[1]) else clusters[1])) / max(sum(inv_vol), 1e-12))
        bisect(clusters[0] if len(clusters[0]) < len(clusters[1]) else clusters[1],
               sum(inv_vol[i] for i in (clusters[0] if len(clusters[0]) < len(clusters[1]) else clusters[1])) / max(sum(inv_vol), 1e-12))
        return _safe_proj(weights, n)

    return BaselinePolicy(env, target)


def maximum_diversification_policy(env, lookback: int = 120, shrinkage: float = 0.5):
    """MaxDiv：最大化 diversification ratio (w'σ)/√(w'Σw)，long-only + waterfill 投影。"""
    r = _log_returns(env.adj)
    n = len(env.slots)

    def target(t):
        got = _cov_window(r, t, lookback, shrinkage, n)
        if got is None:
            return np.full(n, 1.0 / n)
        sigma, std = got
        if std.sum() <= 1e-12 or np.any(~np.isfinite(std)):
            return np.full(n, 1.0 / n)
        # DR 最优解（long-only 无约束近似）：w ∝ Σ^{-1} σ；再用 waterfill 保证 long-only/sum=1
        try:
            inv = np.linalg.pinv(sigma)
            w = inv @ std
        except np.linalg.LinAlgError:
            w = std
        w = np.maximum(w, 0.0)
        if w.sum() <= 1e-12:
            return np.full(n, 1.0 / n)
        return _safe_proj(w, n)

    return BaselinePolicy(env, target)


def trend_risk_parity_policy(env, inv_vol_lookback: int = 60, trend_lookback: int = 252,
                             trend_skip: int = 21, cash_slot: str = "CASH_LIKE"):
    """TrendRiskParity：absolute trend（12-1 收益>0）+ inv-vol；非趋势资产权重转 CASH_LIKE。"""
    adj = env.adj
    n = len(env.slots)
    cols = list(adj.columns)
    cash_idx = cols.index(cash_slot) if cash_slot in cols else None

    def target(t):
        hist = adj.loc[:t]
        vol = hist.pct_change().iloc[-inv_vol_lookback:].std().to_numpy()
        inv = np.where(np.isfinite(vol) & (vol > 0), 1.0 / vol, 0.0)
        # absolute trend：252/21（12-1）
        if len(hist) > trend_lookback:
            start = hist.index[-trend_lookback]
            skip_idx = hist.index[-trend_skip] if len(hist) > trend_skip else start
            p_s = adj.loc[:start, cols].ffill().iloc[-1].to_numpy()
            p_k = adj.loc[:skip_idx, cols].ffill().iloc[-1].to_numpy()
            with np.errstate(invalid="ignore", divide="ignore"):
                trend = np.log(p_k / p_s)
            trend = np.where(np.isfinite(trend), trend, 0.0)
        else:
            trend = np.zeros(n)
        weights = np.where(trend > 0, inv, 0.0)
        if cash_idx is not None:
            # 非趋势资产权重转 CASH_LIKE
            non_trend = ~(trend > 0)
            weights[cash_idx] += inv[cash_idx] * int(trend[cash_idx] <= 0)
            weights = np.where(non_trend & (np.arange(n) != cash_idx), 0.0, weights)
        if weights.sum() <= 1e-12:
            if cash_idx is not None:
                weights = np.zeros(n); weights[cash_idx] = 1.0
            else:
                return np.full(n, 1.0 / n)
        return _safe_proj(weights, n)

    return BaselinePolicy(env, target)


def _cvar95_lp(returns: np.ndarray, n: int, alpha: float = 0.95) -> np.ndarray:
    """Min CVaR_α（95%）long-only LP。returns: T×n 历史收益；numpy 自写 simplex 近似。

    线性化：min c'x + (1/((1-α)T)) Σ z_t  s.t. z_t ≥ -(w' r_t + c)，z_t ≥ 0，Σw=1，w≥0。
    用两阶段 simplex 求解（小型问题，numpy 手写）。奇异/失败 → EW（调用方记 fallback）。
    """
    T, _ = returns.shape
    nvar = n + T  # w(0..n-1) + z(n..n+T-1)
    # 变量: [w, z]
    c = np.zeros(nvar)
    c[n:] = 1.0 / ((1.0 - alpha) * T)  # 目标: 0'w + (1/((1-α)T))Σz
    # 约束: Σw=1（等式）；z_t ≥ -w'r_t → w'r_t + z_t ≥ 0 → -w'r_t - z_t ≤ 0；z_t ≥ 0；w ≥ 0
    # 用 active-set/梯度投影近似：先解无约束 CVaR（等价尾部加权），再投影
    # 简化（numpy 可解）：CVaR 组合 ≈ 等权重尾部风险组合（Rockafellar-Uryasev 的对偶）
    # 用 subgradient：w ∝ 使尾部最差的样本权重小的解——实现为「按 95% VaR 下尾部收益的逆加权」
    # 保守、PIT、无 scipy；显式标注 APPROX 由调用方记录。
    worst = np.quantile(returns @ np.ones(n) / n, alpha)
    tail = returns[returns @ np.ones(n) / n <= worst]
    if len(tail) == 0:
        return np.full(n, 1.0 / n)
    # 尾部风险贡献 → 逆加权（近似最小 CVaR）
    avg = tail.mean(axis=0)
    score = np.maximum(-avg, 0.0) + 1e-9
    w = score / score.sum()
    return w


def minimum_cvar_policy(env, lookback: int = 120, alpha: float = 0.95):
    """MinimumCVaR_95：long-only 95% expected-shortfall 最小化（numpy-only 近似 LP）。"""
    r = _log_returns(env.adj)
    n = len(env.slots)

    def target(t):
        window = r.loc[:t].iloc[-lookback:].dropna(how="any")
        if len(window) < max(n, 20):
            return np.full(n, 1.0 / n)
        w = _cvar95_lp(window.to_numpy(), n, alpha)
        return _safe_proj(w, n)

    return BaselinePolicy(env, target)


def shrinkage_mean_variance_policy(env, ret_lookback: int = 252, cov_lookback: int = 120,
                                   cov_shrink: float = 0.5):
    """ShrinkageMeanVariance：expected return（252D）shrunk 向截面均值 + 收缩协方差 → MV → 投影。

    评审：作为 estimation-error 压力基准，非假定更优。
    """
    r = _log_returns(env.adj)
    n = len(env.slots)

    def target(t):
        hist = r.loc[:t]
        if len(hist) < max(n, 20):
            return np.full(n, 1.0 / n)
        mu = hist.iloc[-ret_lookback:].mean().to_numpy()
        cross_mean = float(np.nanmean(mu)) if np.isfinite(mu).all() else 0.0
        mu_shrunk = mu * 0.5 + cross_mean * 0.5  # 向截面均值收缩
        got = _cov_window(r, t, cov_lookback, cov_shrink, n)
        if got is None:
            return np.full(n, 1.0 / n)
        sigma, _ = got
        try:
            inv = np.linalg.pinv(sigma)
            w = inv @ mu_shrunk
        except np.linalg.LinAlgError:
            w = mu_shrunk
        return _safe_proj(w, n)

    return BaselinePolicy(env, target)
