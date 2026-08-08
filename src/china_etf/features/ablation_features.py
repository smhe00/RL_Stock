"""Feature-ablation F1/F2/F3 builders（GATE_4_FEATURE_ABLATION_PREP）。

评审冻结公式（FEATURE_ABLATION_SPEC.md）：
- F1（6 特征，全内部 11 槽位研究序列）：
  corr_pc1_share_60 = λ1(Corr_60)/trace(Corr_60)  相关矩阵 PC1 share（非协方差）
  equity_bond_corr_change_20_60 = Corr20(CN_LARGE,CN_DURATION) - Corr60(...)
  equity_gold_corr_change_20_60 = Corr20(CN_LARGE,GOLD) - Corr60(...)
  cn_us_corr_60 = Corr60(CN_LARGE, US_BROAD)
  equity_vol_ratio_20_60 = ann_vol20(CN_LARGE)/(ann_vol60(CN_LARGE)+eps)
  equity_downside_semivol_60 = sqrt(252·mean(min(r,0)^2))   LPM2 around zero（F-A1）
- F2（6 特征，外部数据契约）：
  vix_prev_close_percentile_252 / vix_prev_close_change_5 / usd_cny_return_20 /
  cgb10y_yield_change_20 / dr007_zscore_60 / a_share_turnover_zscore_20
  外部 macro 必须已按 China 交易日历对齐；strict PIT：只取 ≤t 已发布值。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .etf_features import global_features, per_asset_features

EPS = 1e-8

# FEATURE_SETS：F0（无新特征）/ F1 / F2 / F3（F1+F2）
FEATURE_SETS = {
    "F0": (),
    "F1": ("f1",),
    "F2": ("f2",),
    "F3": ("f1", "f2"),
}

# 研究外生维度（不含 11 weights）：F0=93, F1=99, F2=99, F3=105
EXOG_DIM = {"F0": 93, "F1": 99, "F2": 99, "F3": 105}
OBS_DIM = {k: v + 11 for k, v in EXOG_DIM.items()}  # + 11 actual weights


def _log_returns(adj: pd.DataFrame) -> pd.DataFrame:
    return np.log(adj / adj.shift(1))


def _rolling_corr(adj: pd.DataFrame, a: str, b: str, w: int) -> pd.Series:
    r = _log_returns(adj)
    return r[a].rolling(w).corr(r[b])


def _ann_vol(adj: pd.DataFrame, slot: str, w: int) -> pd.Series:
    return _log_returns(adj)[slot].rolling(w).std() * np.sqrt(252)


def f1_features(adj: pd.DataFrame) -> pd.DataFrame:
    """F1 — Risk/Correlation（6 特征，全内部数据）。"""
    cols = list(adj.columns)
    if not all(s in cols for s in ("CN_LARGE", "CN_DURATION", "GOLD", "US_BROAD")):
        raise ValueError("F1 requires slots CN_LARGE/CN_DURATION/GOLD/US_BROAD")
    r = _log_returns(adj)
    out = pd.DataFrame(index=adj.index)

    # corr_pc1_share_60：相关矩阵 PC1 share（λ1/trace），60 日滚动
    out["corr_pc1_share_60"] = _pc1_share(r, 60, cols)

    out["equity_bond_corr_change_20_60"] = (
        _rolling_corr(adj, "CN_LARGE", "CN_DURATION", 20)
        - _rolling_corr(adj, "CN_LARGE", "CN_DURATION", 60)
    )
    out["equity_gold_corr_change_20_60"] = (
        _rolling_corr(adj, "CN_LARGE", "GOLD", 20)
        - _rolling_corr(adj, "CN_LARGE", "GOLD", 60)
    )
    out["cn_us_corr_60"] = _rolling_corr(adj, "CN_LARGE", "US_BROAD", 60)
    out["equity_vol_ratio_20_60"] = (
        _ann_vol(adj, "CN_LARGE", 20) / (_ann_vol(adj, "CN_LARGE", 60) + EPS)
    )
    # F-A1：LPM2 around zero
    out["equity_downside_semivol_60"] = (
        r["CN_LARGE"].clip(upper=0.0) ** 2
    ).rolling(60).mean().pow(0.5) * np.sqrt(252)
    return out


def _pc1_share(r: pd.DataFrame, w: int, cols: list[str]) -> pd.Series:
    """60 日滚动相关矩阵第一主成分占比。"""
    out = pd.Series(np.nan, index=r.index)
    for t in range(max(w - 1, 0), len(r)):
        window = r[cols].iloc[t - w + 1: t + 1]
        corr = window.corr().to_numpy()
        try:
            eigvals = np.linalg.eigvalsh(corr)
            eigvals = np.sort(eigvals)[::-1]
            out.iloc[t] = eigvals[0] / max(eigvals.sum(), EPS)
        except np.linalg.LinAlgError:
            out.iloc[t] = np.nan
    return out


def align_pit(macro_series: pd.Series, china_index: pd.DatetimeIndex) -> pd.Series:
    """strict PIT 对齐：对每个 China 决策日 t，只取 ≤t 已发布的 macro 值（as-of）。

    macro_series 必须已含发布日索引；对 China t 用 asof（≤t 的最近值）。这是严格 PIT，
    无未来值泄漏（不向前填充未来发布日）。
    """
    s = macro_series.dropna()
    if s.empty:
        raise ValueError("macro series empty after dropna")
    asof = s.reindex(china_index, method="ffill")  # asof 只回溯已发布
    # 未来发布日不得填充到更早的 China 日（ffill 天然只回看 ≤t）
    return asof.reindex(china_index)


def f2_features(macro: dict[str, pd.Series], china_index: pd.DatetimeIndex) -> pd.DataFrame:
    """F2 — Macro/Forward Risk（6 特征，外部数据契约）。

    macro keys: vix / usd_cny / cgb10y / dr007 / a_share_turnover
    每序列须按发布日索引；内部经 align_pit 对齐到 China 日历（strict PIT）。
    """
    required = {"vix", "usd_cny", "cgb10y", "dr007", "a_share_turnover"}
    missing = required - set(macro.keys())
    if missing:
        raise ValueError(f"macro missing keys: {sorted(missing)}")
    idx = pd.DatetimeIndex(china_index)
    out = pd.DataFrame(index=idx)
    vix = align_pit(macro["vix"], idx)
    usd = align_pit(macro["usd_cny"], idx)
    cgb = align_pit(macro["cgb10y"], idx)
    dr = align_pit(macro["dr007"], idx)
    to = align_pit(macro["a_share_turnover"], idx)

    # VIX：前一完成 US session 收盘（align_pit 已保证 as-of）
    out["vix_prev_close_percentile_252"] = vix.rolling(252).rank(pct=True)
    out["vix_prev_close_change_5"] = vix.pct_change(5)
    # USD/CNY 直接标价：上升 = 人民币贬值 → 正
    out["usd_cny_return_20"] = usd / usd.shift(20) - 1.0
    # CGB10Y 存小数；Δ20 用水平差（百分点，0.01 单位）
    out["cgb10y_yield_change_20"] = cgb - cgb.shift(20)
    # DR007 z-score
    dr_std = dr.rolling(60).std()
    out["dr007_zscore_60"] = (dr - dr.rolling(60).mean()) / (dr_std + EPS)
    # A 股全市场成交额 z-score
    to_std = to.rolling(20).std()
    out["a_share_turnover_zscore_20"] = (to - to.rolling(20).mean()) / (to_std + EPS)
    return out


def market_feature_frame(adj: pd.DataFrame, feature_set: str, macro: dict[str, pd.Series] | None = None) -> pd.DataFrame:
    """按 feature_set 构造研究外生特征矩阵（供 train-only scaler/imputer）。

    F0: 88 per-asset + 5 global（不变，评审：不改 F0 contract）
    F1: +6 内部特征；F2: +6 外部；F3: +12
    返回列顺序：[88 per-asset][5 global][新特征...]——与 obs 布局一致。
    """
    if feature_set not in FEATURE_SETS:
        raise ValueError(f"unknown feature_set {feature_set}")
    parts = [per_asset_features(adj[s]) for s in adj.columns]
    parts.append(global_features(adj))
    for block in FEATURE_SETS[feature_set]:
        if block == "f1":
            parts.append(f1_features(adj))
        elif block == "f2":
            if macro is None:
                raise ValueError("F2 requires macro data")
            parts.append(f2_features(macro, adj.index))
    return pd.concat(parts, axis=1)
