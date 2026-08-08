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


def _native_rolling(series: pd.Series, w: int, fn) -> pd.Series:
    """在源原生观测日历上算 w-观测窗口特征（P1：窗口 = 最近 w 个源观测，非 China 日）。"""
    return fn(series.rolling(w))


def align_derived_to_china(derived_native: pd.Series, china_index: pd.DatetimeIndex,
                           rule: str = "asof") -> pd.Series:
    """PIT 对齐：把源原生衍生特征对齐到 China 决策日。

    P1/P2（评审 §2/§3）：derived_native 已在源日历上算好；这里只做 as-of 对齐。
    - rule="asof"：China 决策日 t 取 available ≤ t 的最新已发布值（USD/CNY/CGB/DR007/turnover）。
    - rule="strict_prev_session"：China 决策日 t 取 available < t（严格早于）——
      VIX 用前一完成 US session，same-calendar-date US close 对 China close 不可见。
    """
    s = derived_native.dropna()
    china = pd.DatetimeIndex(china_index)
    out = pd.Series(np.nan, index=china)
    if s.empty:
        # 全 NaN（如窗口不足）→ 全 NaN 输出，由下游 imputation 处理（F-A2）
        return out
    if rule == "strict_prev_session":
        for t in china:
            avail = s[s.index < t]
            if not avail.empty:
                out[t] = avail.iloc[-1]
    else:  # asof
        out = s.reindex(china, method="ffill")
    return out


def align_pit(macro_series: pd.Series, china_index: pd.DatetimeIndex) -> pd.Series:
    """strict PIT 对齐（旧 API，兼容）：对每个 China 决策日 t 取 ≤t 已发布 macro 值。

    NOTE：P1/P2 修正后，正式 F2 使用 align_derived_to_china（native-first）。本函数保留
    供简单 as-of 场景/旧测试兼容，但 VIX 必须走 strict_prev_session。
    """
    return align_derived_to_china(macro_series, china_index, rule="asof")


def _vix_percentile_native(vix: pd.Series, w: int = 252) -> pd.Series:
    """P3：VIX 分位精确公式 = (rank-1)/(N-1)，rank = 1-based average rank（ties），N=w。

    在 VIX 原生 US session 日历上滚动计算（P1）。显式 tie convention：
    ties 取平均 rank（如两个并列第 2 名 → rank 2.5）。
    """
    vals = vix.to_numpy(dtype=float)
    n = len(vals)
    out = np.full(n, np.nan)
    for i in range(w - 1, n):
        window = vals[i - w + 1: i + 1]
        # average rank, 1-based（ties → mean of ranks）
        order = np.argsort(window, kind="stable")
        ranks = np.empty(w)
        j = 0
        while j < w:
            k = j
            while k + 1 < w and window[order[k + 1]] == window[order[j]]:
                k += 1
            avg = (j + k) / 2.0 + 1.0  # 1-based average rank
            for m in range(j, k + 1):
                ranks[order[m]] = avg
            j = k + 1
        out[i] = (ranks[-1] - 1.0) / (w - 1.0)  # 当前观测 = 窗口最后一个
    return pd.Series(out, index=vix.index)


def f2_features(macro: dict[str, pd.Series], china_index: pd.DatetimeIndex) -> pd.DataFrame:
    """F2 — Macro/Forward Risk（6 特征，外部数据契约，native-calendar-first）。

    P1/P2 契约：macro 每个源 = 原生观测 Series（index=源自身观测日/available_at）。
    内部流程：源原生 Series → 在原生日历算窗口特征 → align_derived_to_china 对齐 China。

    macro keys（每值 = native Series，index 即 available 时刻）:
      vix / usd_cny / cgb10y / dr007 / a_share_turnover
    VIX 强制 strict_prev_session（前一完成 US session）；其余 asof（≤t）。
    """
    required = {"vix", "usd_cny", "cgb10y", "dr007", "a_share_turnover"}
    missing = required - set(macro.keys())
    if missing:
        raise ValueError(f"macro missing keys: {sorted(missing)}")
    idx = pd.DatetimeIndex(china_index)
    out = pd.DataFrame(index=idx)

    # --- VIX（原生 US session 日历；前一完成 session）---
    vix = macro["vix"].dropna().sort_index()
    vix_pct_native = _vix_percentile_native(vix, 252)          # (rank-1)/(N-1)，native
    vix_chg5_native = vix.pct_change(5)                         # 5 个 US session，native
    out["vix_prev_close_percentile_252"] = align_derived_to_china(
        vix_pct_native, idx, rule="strict_prev_session")
    out["vix_prev_close_change_5"] = align_derived_to_china(
        vix_chg5_native, idx, rule="strict_prev_session")

    # --- 其余源：native 窗口 → asof 对齐 ---
    usd = macro["usd_cny"].dropna().sort_index()
    cgb = macro["cgb10y"].dropna().sort_index()
    dr = macro["dr007"].dropna().sort_index()
    to = macro["a_share_turnover"].dropna().sort_index()

    usd_ret20 = usd / usd.shift(20) - 1.0                        # 20 个源观测
    out["usd_cny_return_20"] = align_derived_to_china(usd_ret20, idx, rule="asof")

    cgb_chg20 = cgb - cgb.shift(20)                              # 20 个源观测 level 差
    out["cgb10y_yield_change_20"] = align_derived_to_china(cgb_chg20, idx, rule="asof")

    dr_z = (dr - dr.rolling(60).mean()) / (dr.rolling(60).std() + EPS)
    out["dr007_zscore_60"] = align_derived_to_china(dr_z, idx, rule="asof")

    to_z = (to - to.rolling(20).mean()) / (to.rolling(20).std() + EPS)
    out["a_share_turnover_zscore_20"] = align_derived_to_china(to_z, idx, rule="asof")
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
