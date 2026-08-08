"""Gate 2 最小特征集（EXECUTION_SPEC §30 保留克制）：每资产 8 个 + 全局 5 个。"""

from __future__ import annotations

import numpy as np
import pandas as pd


def per_asset_features(adj_close: pd.Series) -> pd.DataFrame:
    """输入：单资产复权收盘价。输出：8 个特征（无未来信息，rolling 只用 ≤t 数据）。"""
    r = np.log(adj_close / adj_close.shift(1))
    feat = pd.DataFrame(index=adj_close.index)
    for w in (5, 20, 60, 120):
        feat[f"log_return_{w}"] = r.rolling(w).sum()
    feat["realized_vol_20"] = r.rolling(20).std() * np.sqrt(252)
    feat["realized_vol_60"] = r.rolling(60).std() * np.sqrt(252)
    feat["drawdown_60"] = adj_close / adj_close.rolling(60).max() - 1.0
    feat["drawdown_250"] = adj_close / adj_close.rolling(250).max() - 1.0
    return feat


def global_features(adj: pd.DataFrame) -> pd.DataFrame:
    """adj: columns=slot。5 个全局特征。"""
    r = np.log(adj / adj.shift(1))
    out = pd.DataFrame(index=adj.index)
    out["cross_sectional_dispersion_20"] = r.rolling(20).sum().std(axis=1)
    pairs = [(a, b) for i, a in enumerate(adj.columns) for b in list(adj.columns)[i + 1:]]
    if pairs:
        pair_corrs = [
            r[a].rolling(60).corr(r[b]).rename(f"{a}|{b}") for a, b in pairs
        ]
        out["equity_average_corr_60"] = pd.concat(
            pair_corrs, axis=1
        ).mean(axis=1)
    else:
        out["equity_average_corr_60"] = float("nan")
    out["cn_large_vol_percentile_252"] = (
        r[adj.columns[0]].rolling(252).rank(pct=True)
    )
    gold = next((c for c in adj.columns if "GOLD" in c), None)
    dur = next((c for c in adj.columns if "CN_DURATION" in c), None)
    first = adj.columns[0]
    out["gold_equity_corr_60"] = r[first].rolling(60).corr(r[gold]) if gold else float("nan")
    out["bond_equity_corr_60"] = r[first].rolling(60).corr(r[dur]) if dur else float("nan")
    return out


def state_vector(adj: pd.DataFrame, weights: pd.Series, asof: pd.Timestamp) -> np.ndarray:
    """拼接 per-asset(8×N) + weights(N) + global(5)。"""
    parts: list[np.ndarray] = []
    for col in adj.columns:
        f = per_asset_features(adj[col])
        row = f.loc[:asof].iloc[-1]
        parts.append(row.values)
    g = global_features(adj).loc[:asof].iloc[-1].values
    w = weights.values
    return np.concatenate(parts + [w, g]).astype(float)
