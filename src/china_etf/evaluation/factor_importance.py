"""GATE_4_FEATURE_ABLATION_RUNS — 因子重要性统计 helper（scipy-backed）。

- tercile_labels: ties-safe 三等分（并列值进同一箱，rank 尽量等分）。
- spearman: Spearman 秩相关（忽略非 finite，ties → average rank）。
- tercile_discrimination: low vs high 三分位前向收益判别（gap + Mann-Whitney U 双侧 p）。
- decision_dates: 由执行日（t_next）求决策日（日历前一日）。
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu, spearmanr


def tercile_labels(values: np.ndarray) -> np.ndarray:
    """rank 等分三分位（0/1/2）。ties 保守：并列值全部进同一箱。非 finite → -1。

    N<3 → 全 0。目标边界为累计 count 最接近 N/3、2N/3 的组边界。
    """
    values = np.asarray(values, dtype=float)
    n = len(values)
    labels = np.full(n, -1, dtype=int)
    fin = np.isfinite(values)
    idx = np.where(fin)[0]
    vals = values[idx]
    m = len(vals)
    if m == 0:
        return labels
    if m < 3:
        labels[idx] = 0
        return labels
    order = np.argsort(vals, kind="stable")
    sorted_vals = vals[order]
    # 组边界（排序后值变化处）：group_starts = 每组起始位置
    group_starts = [0]
    for i in range(1, m):
        if sorted_vals[i] != sorted_vals[i - 1]:
            group_starts.append(i)
    # 从低到高切两刀，尽量接近 m/3、2m/3，只在组边界（并列不拆）；并列过多 → 空箱
    cuts = []
    prev = 0
    for tgt in (m / 3.0, 2 * m / 3.0):
        cand = [gs for gs in group_starts if gs > prev]
        cuts.append(min(cand, key=lambda gs: (abs(gs - tgt), gs)) if cand else m)
        prev = cuts[-1]
    c1, c2 = cuts
    for pos, orig in enumerate(order):
        if pos < c1:
            labels[idx[orig]] = 0
        elif pos < c2:
            labels[idx[orig]] = 1
        else:
            labels[idx[orig]] = 2
    return labels


def spearman(x, y) -> float:
    """Spearman 秩相关（scipy；忽略任一侧非 finite）。"""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    if len(x) < 3 or np.std(x) == 0 or np.std(y) == 0:
        return float("nan")
    rho, _ = spearmanr(x, y)
    return float(rho)


def tercile_discrimination(feature: np.ndarray, outcome: np.ndarray) -> dict:
    """low vs high 三分位前向收益判别。返回每分位 n/mean/vol + gap + Mann-Whitney p。"""
    f = np.asarray(feature, dtype=float)
    o = np.asarray(outcome, dtype=float)
    lab = tercile_labels(f)
    res: dict = {}
    for k, name in ((0, "low"), (1, "mid"), (2, "high")):
        sel = o[lab == k]
        res[name] = {
            "n": int(len(sel)),
            "mean_fwd_ret": float(np.mean(sel)) if len(sel) else float("nan"),
            "vol_fwd_ret_ann": float(np.std(sel, ddof=1) * math.sqrt(252)) if len(sel) > 1 else float("nan"),
        }
    low = o[lab == 0]
    high = o[lab == 2]
    if len(low) and len(high):
        res["low_minus_high_mean"] = float(np.mean(low) - np.mean(high))
        try:
            u_stat, p = mannwhitneyu(low, high, alternative="two-sided")
            res["mann_whitney_u"] = float(u_stat)
            res["mann_whitney_p"] = float(p)
        except ValueError:  # 全部相等 → 无差异
            res["mann_whitney_u"] = float("nan")
            res["mann_whitney_p"] = float("nan")
    else:
        res["low_minus_high_mean"] = float("nan")
        res["mann_whitney_u"] = float("nan")
        res["mann_whitney_p"] = float("nan")
    return res


def decision_dates(execution_dates, calendar) -> pd.DatetimeIndex:
    """每个执行日（t_next）的决策日 = 日历上紧邻的前一日。返回与输入等长 DatetimeIndex。"""
    cal = pd.DatetimeIndex(calendar)
    ex = pd.DatetimeIndex(execution_dates)
    pos = cal.get_indexer(ex)
    prev = pos - 1
    out = [cal[p] if p >= 0 else pd.NaT for p in prev]
    return pd.DatetimeIndex(out)


def ols_residual(y: np.ndarray, X: np.ndarray) -> np.ndarray:
    """OLS 残差 y - X β（含截距）。X: (n, p)。整行非 finite 剔除；残差非 finite 位置置 NaN。"""
    y = np.asarray(y, dtype=float)
    X = np.asarray(X, dtype=float)
    m = np.isfinite(y) & np.isfinite(X).all(axis=1)
    if m.sum() < X.shape[1] + 2:
        return np.full(len(y), np.nan)
    Xm = np.column_stack([np.ones(int(m.sum())), X[m]])
    beta, *_ = np.linalg.lstsq(Xm, y[m], rcond=None)
    resid = np.full(len(y), np.nan)
    resid[m] = y[m] - Xm @ beta
    return resid


def _moving_block_indices(n: int, block_len: int, rng: np.random.Generator) -> np.ndarray:
    """移动块重采样的原始索引（保持时间连续）。起点从 [0, n-block_len] 均匀采，块长 = block_len。"""
    if n <= 0:
        return np.array([], dtype=int)
    bl = max(1, min(block_len, n))
    n_blocks = int(np.ceil(n / bl))
    starts = rng.integers(0, n - bl + 1, size=n_blocks)
    out = np.concatenate([np.arange(s, s + bl) for s in starts])
    return out[:n]


def block_bootstrap_ci(x: np.ndarray, y: np.ndarray, stat_fn, *,
                       n_boot: int = 1000, block_len: int = 20, seed: int = 0) -> dict:
    """移动块 bootstrap 置信区间（时间序列依赖感知）。

    重采样原始 (x, y) 的对齐（按位置，非按日期），对每 bootstrap 样本重算 stat_fn(x, y)，
    返回 2.5%/97.5% 分位 CI + bootstrap 均值 + 双侧 p（CI 相对 0 的 bootstrap 极值比例）。

    stat_fn(x, y) → float（如 spearman 或 tercile gap 的标量）。
    仅用 x/y 均 finite 的对齐位置。
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    m = np.isfinite(x) & np.isfinite(y)
    xx, yy = x[m], y[m]
    n = len(xx)
    bl = max(1, min(int(block_len), n))
    if n < 5:
        return {"ci_low": float("nan"), "ci_high": float("nan"), "mean": float("nan"),
                "n": int(n), "p_bs": float("nan")}
    obs = stat_fn(xx, yy)
    if not np.isfinite(obs):
        return {"ci_low": float("nan"), "ci_high": float("nan"), "mean": float("nan"),
                "n": int(n), "p_bs": float("nan")}
    rng = np.random.default_rng(seed)
    stats = np.empty(n_boot)
    n_ok = 0
    for b in range(n_boot):
        idx = _moving_block_indices(n, bl, rng)
        s = stat_fn(xx[idx], yy[idx])
        if np.isfinite(s):
            stats[n_ok] = s
            n_ok += 1
    if n_ok < max(20, n_boot // 10):
        return {"ci_low": float("nan"), "ci_high": float("nan"), "mean": float("nan"),
                "n": int(n), "p_bs": float("nan")}
    stats = stats[:n_ok]
    low, high = np.percentile(stats, [2.5, 97.5])
    # 双侧 bootstrap p：观测值相对 0 的极值比例
    p_bs = 2.0 * min(float((stats >= obs).mean()), float((stats <= obs).mean()))
    return {"ci_low": float(low), "ci_high": float(high), "mean": float(np.mean(stats)),
            "n": int(n), "p_bs": float(max(p_bs, 1e-12))}


def holm_adjust(pvals) -> np.ndarray:
    """Holm-Bonferroni 多重检验校正。输入 p 值数组 → 校正 p（min 1.0）。"""
    p = np.asarray(pvals, dtype=float)
    n = len(p)
    if n == 0:
        return p
    order = np.argsort(p)
    rank = np.arange(1, n + 1)
    adj = np.full(n, np.nan)
    # 从最小 p 开始，递推：adj[p_i] = max_{j<=i} (n - j + 1) * p_j
    running = 0.0
    for pos, i in enumerate(order):
        running = max(running, (n - pos) * p[i])
        adj[i] = running
    return np.minimum(adj, 1.0)


def bh_fdr(pvals) -> np.ndarray:
    """Benjamini-Hochberg FDR 校正。输入 p 值数组 → q 值（min 1.0）。"""
    p = np.asarray(pvals, dtype=float)
    n = len(p)
    if n == 0:
        return p
    order = np.argsort(p)
    q = np.full(n, np.nan)
    # 从最大 p 回溯，保持单调
    running = 1.0
    for pos in range(n - 1, -1, -1):
        i = order[pos]
        running = min(running, p[i] * n / (pos + 1))
        q[i] = running
    return np.minimum(q, 1.0)


def cross_fit_residual_spearman(feature: np.ndarray, f0: np.ndarray,
                                outcome: np.ndarray) -> float:
    """时间有序 cross-fit：用前 60% 样本 fit OLS（feature ~ f0），后 40% apply → 残差 Spearman。

    供 fold-local 残差化测试与脚本（评审 A4：train fit → val apply，val 不参与 fit）。
    """
    n = len(feature)
    cut = int(n * 0.6)
    train_slice = slice(0, cut)
    val_slice = slice(cut, n)
    beta, *_ = np.linalg.lstsq(
        np.column_stack([np.ones(cut), f0[train_slice]]), feature[train_slice], rcond=None)
    resid = feature[val_slice] - np.column_stack([np.ones(n - cut), f0[val_slice]]) @ beta
    return spearman(resid, outcome[val_slice])
