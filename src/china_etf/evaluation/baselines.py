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


# --- GATE_4_NON_RL_HORSE_RACE Tier A：新增方法（numpy-only，canonical）---


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
    """long-only + sum=1 投影（waterfill，caps=1；无 project 约束，供非约束基线）。"""
    w = np.clip(np.asarray(w, dtype=float), 0.0, None)
    if not np.isfinite(w).all():
        return np.full(n, 1.0 / n)
    if w.sum() <= 1e-12:
        return np.full(n, 1.0 / n)
    return RiskOverlayV0._waterfill(w, np.full(n, 1.0), total=1.0)


def _project_caps(slots: list[str]) -> tuple[np.ndarray, float, tuple[int, ...]]:
    """F4：project 可行集约束 = single_slot caps(0.25) + ChinaGrowth group cap(0.50, CHINEXT+STAR)。"""
    caps = np.full(len(slots), 0.25)
    growth = tuple(i for i, s in enumerate(slots) if s in ("CHINEXT", "STAR"))
    return caps, 0.50, growth


def _proj_constrained(w: np.ndarray, slots: list[str]) -> np.ndarray:
    """投影到 project 可行集（single cap 0.25 + growth 0.50）。"""
    from .optimizers import waterfill_proj
    caps, gmax, gidx = _project_caps(slots)
    return waterfill_proj(w, len(slots), caps, gmax, gidx)


def _erc_solve(sigma: np.ndarray, n: int, max_iter: int = 500, tol: float = 1e-8) -> tuple[np.ndarray, int, bool]:
    """ERC 牛顿法（N2）：解 w_i·(Σw)_i = w_j·(Σw)_j 对所有 i,j（等边际风险贡献）。

    方程：f_i(w) = w_i(Σw)_i - w_0(Σw)_0 = 0, i=1..n-1，约束 Σw=1。
    用牛顿迭代解 n 个方程（numpy 线性系统）；数值 Jacobian eps=1e-7。
    """
    w = np.ones(n) / n
    converged = False
    # 精化循环：牛顿直到残差 < tol（F3：贡献相等 ≤1e-3）
    for it in range(max_iter):
        sw = sigma @ w
        contrib = w * sw
        F = np.concatenate([contrib[1:] - contrib[0], [w.sum() - 1.0]])
        if np.abs(F).max() < tol:
            converged = True
            break
        # 解析 Jacobian（F3）：∂(w_i(Σw)_i)/∂w_j = δ_ij(Σw)_i + w_i Σ_ij；sum 行 = 1
        J = np.zeros((n, n))
        for i in range(1, n):
            for j in range(n):
                J[i - 1, j] = (1.0 if i == j else 0.0) * sw[i] + w[i] * sigma[i, j] - (
                    (1.0 if 0 == j else 0.0) * sw[0] + w[0] * sigma[0, j])
        J[n - 1, :] = 1.0  # sum w = 1
        try:
            delta = np.linalg.solve(J, -F)
        except np.linalg.LinAlgError:
            delta = np.linalg.pinv(J) @ -F
        w_new = w + delta
        w_new = np.clip(w_new, 0.0, None)
        if w_new.sum() > 0:
            w_new = w_new / w_new.sum()
        if np.abs(w_new - w).max() < 1e-14:
            w = w_new
            break
        w = w_new
    # 收敛后残差检查（F3：如实报告 max dev）
    sw = sigma @ w
    contrib = w * sw
    rel = contrib / max(contrib.sum(), 1e-12)
    max_dev = float(np.max(np.abs(rel - np.mean(rel))) / max(np.mean(rel), 1e-12)) if len(rel) > 1 else 0.0
    if max_dev <= 1e-3:
        converged = True
    return _safe_proj(w, n), it, converged


def erc_policy(env, lookback: int = 120, shrinkage: float = 0.5):
    """ERC：等边际风险贡献（N2/F3 canonical，牛顿法，policy 同一收缩协方差；F4 投影 project 可行集）。"""
    r = _log_returns(env.adj)
    n = len(env.slots)

    def target(t):
        got = _cov_window(r, t, lookback, shrinkage, n)
        if got is None:
            return np.full(n, 1.0 / n)
        sigma, _ = got
        w, _, _ = _erc_solve(sigma, n)
        return _proj_constrained(w, list(env.slots))

    return BaselinePolicy(env, target)



def _hrp_weights(corr: np.ndarray, cov: np.ndarray, vol: np.ndarray, n: int,
                 slots: list[str] | None = None) -> np.ndarray:
    """完整 canonical HRP（N3，Lopez de Prado）：

    1. 相关距离 → 凝聚聚类（single-linkage，完整 dendrogram）
    2. quasi-diagonalization（seriation：递归左-右合并顺序）
    3. recursive bisection：沿准对角顺序二分，用 cluster variance 分配（低方差簇更多，F1）
    """
    dist = np.sqrt(np.clip((1.0 - corr) / 2.0, 0.0, 1.0))
    inv_vol = np.where(np.isfinite(vol) & (vol > 0), 1.0 / vol, 0.0)
    if inv_vol.sum() <= 1e-12:
        return np.full(n, 1.0 / n)
    # 1. single-linkage 完整聚类树：merge_history = [(left_cluster_id, right_cluster_id), ...]
    #    cluster_id < n = 叶子；≥ n = 合并节点
    active = [{"id": i, "members": [i]} for i in range(n)]
    merges = []
    next_id = n
    while len(active) > 1:
        best = (np.inf, 0, 0)
        for i in range(len(active)):
            for j in range(i + 1, len(active)):
                dij = min(dist[a, b] for a in active[i]["members"] for b in active[j]["members"])
                if dij < best[0]:
                    best = (dij, i, j)
        _, i, j = best
        merges.append((active[i]["id"], active[j]["id"]))
        active[i]["members"] = active[i]["members"] + active[j]["members"]
        active[i]["id"] = next_id
        next_id += 1
        del active[j]
    # 2. quasi-diagonal seriation：从根递归按合并顺序排列叶子（children 映射自底向上）
    children_map = {}
    for step, (l, r) in enumerate(merges):
        children_map[n + step] = (l, r)
    root = 2 * n - 2  # 最后 merge 的父 id

    def _seriate(node):
        if node < n:
            return [node]
        l, r = children_map[node]
        return _seriate(l) + _seriate(r)

    order = _seriate(root)
    # 3. recursive bisection：沿准对角顺序二分，cluster variance 分配
    weights = np.zeros(n)

    def _cluster_var(idx):
        wc = np.array([inv_vol[i] for i in idx])
        wc = wc / max(wc.sum(), 1e-12)
        full = np.zeros(n)
        for k, i in enumerate(idx):
            full[i] = wc[k]
        return float(full @ cov @ full)

    def bisect(cluster, w_in):
        if len(cluster) == 1:
            weights[cluster[0]] = w_in
            return
        half = len(cluster) // 2
        a, b = cluster[:half], cluster[half:]
        va, vb = _cluster_var(a), _cluster_var(b)
        if va + vb <= 0:
            va = vb = 1.0
        # F1（评审）：低方差簇得更多权重 → A 得 vb/(va+vb)，B 得 va/(va+vb)
        bisect(a, w_in * vb / (va + vb))
        bisect(b, w_in * va / (va + vb))

    bisect(order, 1.0)
    return _proj_constrained(weights, slots) if slots else _safe_proj(weights, n)


def hrp_policy(env, lookback: int = 120):
    """HRP（N3/F1 canonical）：完整层级聚类 + quasi-diagonal + cluster-variance recursive bisection
    （低方差簇更多权重）；投影到 project 可行集（F4）。"""
    r = _log_returns(env.adj)
    n = len(env.slots)

    def target(t):
        window = r.loc[:t].iloc[-lookback:].dropna(how="any")
        if len(window) < max(n, 20):
            return np.full(n, 1.0 / n)
        corr = window.corr().to_numpy()
        cov = window.cov().to_numpy()
        vol = window.std().to_numpy()
        return _hrp_weights(corr, cov, vol, n, slots=list(env.slots))

    return BaselinePolicy(env, target)


def _maxdiv_dr(w: np.ndarray, sigma: np.ndarray, std: np.ndarray) -> float:
    v = std @ w
    q = w @ sigma @ w
    return float(v / np.sqrt(q)) if q > 1e-12 else 1.0


def _maxdiv_coordinate(sigma: np.ndarray, std: np.ndarray, n: int, max_iter: int = 1000,
                       slots: list[str] | None = None) -> np.ndarray:
    """MaxDiv 约束 DR（N5/F4 canonical）：max (w'σ)/√(w'Σw) s.t. project 可行集。

    坐标上升：每步向 DR 梯度方向投影到 project 可行集（single caps + growth group）。
    """
    w = np.full(n, 1.0 / n)
    step = 1.0
    for _ in range(max_iter):
        q = w @ sigma @ w
        v = std @ w
        g = std / np.sqrt(q) - (v / np.sqrt(q)) * (sigma @ w) / q
        g = g / max(np.linalg.norm(g), 1e-12)
        w_new = _proj_constrained(w + step * g, slots) if slots else _safe_proj(w + step * g, n)
        if _maxdiv_dr(w_new, sigma, std) <= _maxdiv_dr(w, sigma, std) + 1e-10:
            step *= 0.5
            if step < 1e-6:
                break
        else:
            w = w_new
            step = min(step * 1.1, 2.0)
    return _proj_constrained(w, slots) if slots else w


def maximum_diversification_policy(env, lookback: int = 120, shrinkage: float = 0.5):
    """MaxDiv（N5/F4 canonical）：DR 最大化，优化迭代内投影到 project 可行集。"""
    r = _log_returns(env.adj)
    n = len(env.slots)

    def target(t):
        got = _cov_window(r, t, lookback, shrinkage, n)
        if got is None:
            return np.full(n, 1.0 / n)
        sigma, std = got
        if std.sum() <= 1e-12 or np.any(~np.isfinite(std)):
            return np.full(n, 1.0 / n)
        return _maxdiv_coordinate(sigma, std, n, slots=list(env.slots))

    return BaselinePolicy(env, target)


def trend_risk_parity_policy(env, inv_vol_lookback: int = 60, trend_lookback: int = 252,
                             trend_skip: int = 21, cash_slot: str = "CASH_LIKE"):
    """TrendRiskParity（N4 canonical）：基础 inv-vol 组合 → 非趋势 risky 预算精确转 CASH_LIKE。"""
    adj = env.adj
    n = len(env.slots)
    cols = list(adj.columns)
    cash_idx = cols.index(cash_slot) if cash_slot in cols else None

    def target(t):
        hist = adj.loc[:t]
        vol = hist.pct_change().iloc[-inv_vol_lookback:].std().to_numpy()
        inv = np.where(np.isfinite(vol) & (vol > 0), 1.0 / vol, 0.0)
        if inv.sum() <= 1e-12:
            return np.full(n, 1.0 / n)
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
        # 基础 inv-vol 组合（eligible universe）→ 归一化
        base = inv / inv.sum()
        if cash_idx is None:
            return _safe_proj(base, n)
        # N4：非趋势 risky assets 的 base 预算之和 → 精确转 CASH_LIKE；趋势 risky 保持 base
        non_trend = ~(trend > 0)
        moved = float(base[non_trend].sum())
        weights = base.copy()
        weights[non_trend] = 0.0
        weights[cash_idx] += moved
        return _safe_proj(weights, n)

    return BaselinePolicy(env, target)


def _cvar_value(w: np.ndarray, R: np.ndarray, alpha: float) -> float:
    """Empirical CVaR_α（F2 修正）：worst (1-α) 尾部的平均损失（真实 ES）。

    CVaR = (1/((1-α)T))·Σ_t max(loss_t - zeta*, 0) + zeta*，zeta*=VaR_α。
    等价于：取 loss 的 (1-α) 最差样本（含 VaR 边界），对它们求均值。
    """
    loss = -(R @ w)
    var = np.quantile(loss, alpha)  # zeta* = VaR_α（分位数）
    # R-U：zeta* + mean(max(loss - zeta*, 0))/(1-α)
    excess = np.maximum(loss - var, 0.0)
    return float(var + excess.mean() / (1.0 - alpha))


def _min_cvar_subgradient(R: np.ndarray, n: int, alpha: float = 0.95,
                          max_iter: int = 400, slots: list[str] | None = None) -> tuple[np.ndarray, int, bool]:
    """MinCVaR（N1/F2 canonical）：凸 CVaR 最小化（R-U），投影次梯度，投影到 project 可行集（F4）。

    次梯度 = -(1/((1-α)T))Σ_{tail} r_t（tail = loss ≥ VaR_α 的样本）。
    收敛：用真实 CVaR 值（_cvar_value）跟踪 best_w；非自证。
    性能：1500 迭代（1/√k 步长理论收敛；每决策日快速）。
    """
    w = np.full(n, 1.0 / n)
    best_w = w.copy()
    best_val = _cvar_value(w, R, alpha)
    converged = False
    stagnant = 0
    for it in range(max_iter):
        loss = -(R @ w)
        var = np.quantile(loss, alpha)
        tail_mask = loss >= var - 1e-9
        if tail_mask.sum() == 0:
            tail_mask = loss >= var
        g = -(R[tail_mask].mean(axis=0)) / (1.0 - alpha)
        g = g / max(np.linalg.norm(g), 1e-12)
        step = 1.0 / np.sqrt(it + 1.0)
        if slots is not None:
            w = _proj_constrained(w - step * g, slots)
        else:
            w = _safe_proj(w - step * g, n)
        val = _cvar_value(w, R, alpha)
        if val < best_val - 1e-12:
            best_w = w.copy()
            best_val = val
            stagnant = 0
        else:
            stagnant += 1
        if stagnant > 200:
            converged = True
            break
    return best_w, it, converged


def minimum_cvar_policy(env, lookback: int = 120, alpha: float = 0.95):
    """MinimumCVaR_95（N1/F2 canonical）：R-U CVaR 凸优化，投影到 project 可行集（F4）。"""
    r = _log_returns(env.adj)
    n = len(env.slots)

    def target(t):
        window = r.loc[:t].iloc[-lookback:].dropna(how="any")
        if len(window) < max(n, 20):
            return np.full(n, 1.0 / n)
        w, _, _ = _min_cvar_subgradient(window.to_numpy(), n, alpha, slots=list(env.slots))
        return w

    return BaselinePolicy(env, target)


def shrinkage_mean_variance_policy(env, ret_lookback: int = 252, cov_lookback: int = 120,
                                   cov_shrink: float = 0.5, lam: float = 0.5):
    """ShrinkageMeanVariance（N6 canonical，冻结 utility）：
    max μ'w - (λ/2) w'Σw  s.t. Σw=1, w≥0, caps；λ=0.5 冻结。
    μ = 252D 均值 shrunk 向截面均值；Σ = 120D 收缩协方差。用 qp_projected 解。
    """
    from .optimizers import qp_projected

    r = _log_returns(env.adj)
    n = len(env.slots)
    caps, gmax, gidx = _project_caps(list(env.slots))

    def target(t):
        hist = r.loc[:t]
        if len(hist) < max(n, 20):
            return np.full(n, 1.0 / n)
        mu = hist.iloc[-ret_lookback:].mean().to_numpy()
        mu = np.where(np.isfinite(mu), mu, 0.0)
        cross_mean = float(np.nanmean(mu)) if np.isfinite(mu).all() else 0.0
        mu_shrunk = mu * 0.5 + cross_mean * 0.5
        got = _cov_window(r, t, cov_lookback, cov_shrink, n)
        if got is None:
            return np.full(n, 1.0 / n)
        sigma, _ = got
        # min 0.5 λ w'Σw - μ'w → qp_projected，投影到 project 可行集（F4）
        w = qp_projected(mu_shrunk, lam * sigma, caps=caps, growth_max=gmax, growth_slots=gidx)
        return w

    return BaselinePolicy(env, target)
