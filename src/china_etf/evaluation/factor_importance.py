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
