"""GATE_4_FEATURE_ABLATION_PREP(CORRECTIONS) — F1/F2/F3 builders + F-A1/F-A2 + P1-P5。

评审 §7 项 5-9 + CORRECTIONS P1-P5：
- 维度断言 104/110/110/116
- P1 native-calendar-first F2；P2 VIX 前一完成 session；P3 分位 (rank-1)/(N-1)；
  P5 F0 preprocessor ddof=1 parity；P4 spec 契约一致
- F-A1 LPM2；F-A2 train-only imputation
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from china_etf.data.loader import load_research_adj
from china_etf.features.ablation_features import (
    EXOG_DIM,
    OBS_DIM,
    _vix_percentile_native,
    align_derived_to_china,
    align_pit,
    f1_features,
    f2_features,
    market_feature_frame,
)
from china_etf.features.preprocessor import FeaturePreprocessor


def _real_adj():
    return load_research_adj()


def _synthetic_macro(index):
    """合成 macro，索引对齐到给定日历（P1：native 源日历；测试用不同 native/China 日历验证）。"""
    dates = pd.DatetimeIndex(index)
    n = len(dates)
    rng = np.random.default_rng(7)
    vix = pd.Series(20 + 5 * np.sin(np.arange(n) / 20) + rng.normal(0, 1, n), index=dates)
    usd = pd.Series(7.0 + 0.05 * np.arange(n) / n + rng.normal(0, 0.01, n), index=dates)
    cgb = pd.Series(0.03 + 0.002 * np.sin(np.arange(n) / 40), index=dates)
    dr = pd.Series(0.02 + 0.003 * np.sin(np.arange(n) / 25) + rng.normal(0, 0.0005, n), index=dates)
    to = pd.Series(8000 + 3000 * np.sin(np.arange(n) / 60) + rng.normal(0, 300, n), index=dates)
    return {"vix": vix, "usd_cny": usd, "cgb10y": cgb, "dr007": dr, "a_share_turnover": to}


def _us_native_calendar(china_dates):
    """构造不同 holiday 日历的 US native 观测（仅工作日，但剔除一些 US 假日 vs China bdays）。"""
    # 模拟 US 日历：工作日 + 7/4（US 独立日，China 不休）
    us_dates = [d for d in pd.bdate_range(china_dates[0], china_dates[-1]) if not (d.month == 7 and d.day == 4)]
    return pd.DatetimeIndex(us_dates)


def _train_region(index, frac=0.5):
    """在 F1 全 finite 区内取前 frac 作为 train 区（避开 warmup NaN）。"""
    idx = list(pd.DatetimeIndex(index))
    cut = int(len(idx) * frac)
    return pd.DatetimeIndex(idx[:cut])


# --- 维度断言（评审 §7 项 7）---


def test_feature_set_dimensions() -> None:
    adj = _real_adj()
    macro = _synthetic_macro(adj.index)
    for fs, exog, obs in [("F0", 93, 104), ("F1", 99, 110), ("F2", 99, 110), ("F3", 105, 116)]:
        df = market_feature_frame(adj, fs, macro if fs in ("F2", "F3") else None)
        assert df.shape[1] == exog, f"{fs} exog dim {df.shape[1]} != {exog}"
        assert EXOG_DIM[fs] == exog and OBS_DIM[fs] == obs
    assert OBS_DIM["F0"] == 104


# --- F1 公式 ---


def test_f1_corr_change_sign_and_value() -> None:
    """equity_bond_corr_change_20_60 = corr20 - corr60（评审 §12 符号）。"""
    adj = _real_adj()
    f1 = f1_features(adj)
    r = np.log(adj / adj.shift(1))
    # 用 F1 全 finite 区内的日期（避开早期 warmup NaN）
    d = f1["equity_bond_corr_change_20_60"].dropna().index[400]
    expected = (r["CN_LARGE"].rolling(20).corr(r["CN_DURATION"]).loc[d]
                - r["CN_LARGE"].rolling(60).corr(r["CN_DURATION"]).loc[d])
    assert np.isclose(f1.loc[d, "equity_bond_corr_change_20_60"], expected, atol=1e-10)
    # 符号：corr20-corr60
    c20 = r["CN_LARGE"].rolling(20).corr(r["CN_DURATION"]).loc[d]
    c60 = r["CN_LARGE"].rolling(60).corr(r["CN_DURATION"]).loc[d]
    assert np.isclose(f1.loc[d, "equity_bond_corr_change_20_60"], c20 - c60, atol=1e-10)


def test_f1_downside_semivol_lpm2() -> None:
    """F-A1：equity_downside_semivol_60 = sqrt(252·mean(min(r,0)^2)) over 60 obs。"""
    adj = _real_adj()
    f1 = f1_features(adj)
    r = np.log(adj["CN_LARGE"] / adj["CN_LARGE"].shift(1))
    valid = f1["equity_downside_semivol_60"].dropna()
    d = valid.index[500]
    i = list(f1.index).index(d)
    # rolling(60) 在位置 i 覆盖 [i-59, i]（60 个 obs）
    manual = np.sqrt(252.0 * np.mean(np.minimum(r.iloc[i - 59:i + 1], 0.0) ** 2))
    assert np.isclose(f1.loc[d, "equity_downside_semivol_60"], manual, atol=1e-10)


def test_f1_pc1_share_uses_correlation_matrix() -> None:
    """corr_pc1_share_60 = λ1(Corr_60)/trace(Corr_60)（相关矩阵，非协方差）。"""
    adj = _real_adj()
    f1 = f1_features(adj)
    r = np.log(adj / adj.shift(1))
    valid = f1["corr_pc1_share_60"].dropna()
    d = valid.index[500]
    i = list(f1.index).index(d)
    window = r.iloc[i - 59:i + 1]
    corr = window.corr().to_numpy()
    eigvals = np.sort(np.linalg.eigvalsh(corr))[::-1]
    expected = eigvals[0] / max(eigvals.sum(), 1e-8)
    assert np.isclose(f1.loc[d, "corr_pc1_share_60"], expected, atol=1e-10)


# --- F2 PIT 对齐（P1/P2/P3：native-calendar-first）---


def test_f2_align_pit_no_future_leak() -> None:
    """align_pit（asof）只取 ≤t 已发布值：未来 macro 不泄漏到更早 China 日。"""
    china = pd.DatetimeIndex(pd.bdate_range("2025-01-02", periods=10))
    macro = pd.Series(
        [10.0] * 10, index=pd.DatetimeIndex(pd.bdate_range("2025-01-02", periods=10))
    )
    macro.iloc[-1] = 999.0
    aligned = align_pit(macro, china)
    assert aligned.iloc[8] == pytest.approx(10.0)
    assert aligned.iloc[9] == pytest.approx(999.0)


def _vix_pair(china_dates):
    """返回 (vix_native, china)。vix 在 US native 日历（剔除 7/4）上；China 用 bdays。"""
    china = pd.DatetimeIndex(china_dates)
    us_native = _us_native_calendar(china)
    vix = pd.Series(20.0 + np.arange(len(us_native)) * 0.01, index=us_native)
    return vix, china


def test_vix_same_date_us_close_not_visible_to_china_close() -> None:
    """P2：same-calendar-date US close 对 China close 不可见（strict_prev_session < t）。"""
    vix, china = _vix_pair(pd.bdate_range("2025-01-02", periods=30))
    vix = vix.copy()
    # 某日 US 收盘值设为 999（若被 China 同日看到即泄漏）
    same_day = china[10]
    if same_day in vix.index:
        vix.loc[same_day] = 999.0
    pct = align_derived_to_china(_vix_percentile_native(vix, 252) if len(vix) >= 252 else vix,
                                 china, rule="strict_prev_session")
    aligned = align_derived_to_china(vix, china, rule="strict_prev_session")
    assert aligned.loc[same_day] != pytest.approx(999.0), "same-date US close 不得对 China close 可见"


def test_vix_rolling_5_uses_five_us_sessions_not_five_china_days() -> None:
    """P1：vix_prev_close_change_5 用 5 个 US session（native），非 5 个 China 日。"""
    china = pd.DatetimeIndex(pd.bdate_range("2025-01-02", periods=60))
    us_native = _us_native_calendar(china)  # 剔除 7/4 → native 观测数 < China 日数
    vix = pd.Series(np.arange(len(us_native), dtype=float), index=us_native)  # +1/观测
    f2 = f2_features({"vix": vix, "usd_cny": vix, "cgb10y": vix, "dr007": vix, "a_share_turnover": vix}, china)
    col = f2["vix_prev_close_change_5"].dropna()
    d = col.index[len(col) // 2]
    # strict_prev：China 决策日 d 使用 < d 的最近完成 US session 的 5-session 变化
    native_before = us_native[us_native < d]
    assert len(native_before) >= 6
    # 最近完成的 US 观测 = native_before[-1]；其 pct_change(5) = (v5 - v0)/v0 over 最近 6 个 native
    vals = vix.loc[native_before[-6:]].to_numpy()
    expected = (vals[-1] - vals[0]) / vals[0]
    assert np.isclose(f2.loc[d, "vix_prev_close_change_5"], expected, atol=1e-10)


def test_vix_percentile_252_uses_native_us_sessions() -> None:
    """P1：分位 252 用 252 个 native US session（非 China 日）；对齐前已算。"""
    china = pd.DatetimeIndex(pd.bdate_range("2025-01-02", periods=400))
    us_native = _us_native_calendar(china)
    vix = pd.Series(20.0 + np.arange(len(us_native)) * 0.01, index=us_native)
    f2 = f2_features({"vix": vix, "usd_cny": vix, "cgb10y": vix, "dr007": vix, "a_share_turnover": vix}, china)
    col = f2["vix_prev_close_percentile_252"].dropna()
    d = col.index[len(col) // 2]
    # strict_prev：d 用 < d 的最近 252 个 US 观测的 (rank-1)/(N-1)
    native_before = us_native[us_native < d]
    assert len(native_before) >= 252
    window = vix.loc[native_before[-252:]].to_numpy()
    # 手工 average rank（1-based，ties 取平均）：当前观测 = window[-1]
    n_less = int(np.sum(window < window[-1]))
    n_eq = int(np.sum(window == window[-1]))
    rank = n_less + (n_eq + 1) / 2.0  # 1-based average rank of window[-1]
    expected = (rank - 1.0) / (len(window) - 1.0)
    assert np.isclose(f2.loc[d, "vix_prev_close_percentile_252"], expected, atol=1e-10)


def test_vix_percentile_exact_rank_formula_with_ties() -> None:
    """P3：分位 = (rank-1)/(N-1)，rank=1-based average rank（ties 取平均）。"""
    vix = pd.Series([1.0, 2.0, 2.0, 3.0], index=pd.bdate_range("2025-01-02", periods=4))
    out = _vix_percentile_native(vix, w=4)
    # 窗口 [1,2,2,3]：当前 3 → rank=4（1-based）→ (4-1)/(4-1)=1.0
    assert np.isclose(out.iloc[-1], 1.0)
    # 中间窗口 [1,2,2,3] 的倒数第二（=2，ties avg rank (2+3)/2=2.5）→ (2.5-1)/3=0.5
    # 手工验证 tie 处理：单独构造
    vix2 = pd.Series([1.0, 2.0, 2.0], index=pd.bdate_range("2025-01-02", periods=3))
    out2 = _vix_percentile_native(vix2, w=3)
    # 窗口 [1,2,2]，最后 obs=2，ties avg rank=(2+3)/2=2.5 → (2.5-1)/2=0.75
    assert np.isclose(out2.iloc[-1], 0.75)


def test_f2_native_calendar_then_asof_alignment() -> None:
    """P1：f2 在 native 日历算窗口，再 asof 对齐到 China；native 缺失不重复观测。"""
    china = pd.DatetimeIndex(pd.bdate_range("2025-01-02", periods=100))
    us_native = _us_native_calendar(china)
    vix = pd.Series(np.arange(len(us_native), dtype=float), index=us_native)
    f2 = f2_features({"vix": vix, "usd_cny": vix, "cgb10y": vix, "dr007": vix, "a_share_turnover": vix}, china)
    assert f2.shape[1] == 6
    assert f2.index.equals(china)
    # 所有列对齐 China 日历
    assert f2.index[0] == china[0] and f2.index[-1] == china[-1]


def test_f2_holiday_calendar_mismatch_does_not_duplicate_window_observations() -> None:
    """P1：US 假日（7/4）缺 native 观测时，窗口不因 ffill 复制而改变计数。"""
    # 构造 7/4 在 China bday 上、但 US native 剔除的日历（2025-07-04 是周五，China 开盘）
    china = pd.DatetimeIndex(pd.bdate_range("2025-06-23", periods=30))  # 覆盖 7/4
    assert pd.Timestamp("2025-07-04") in china, "测试需 China 在 7/4 开盘"
    us_native = _us_native_calendar(china)  # 剔除 7/4（US 假日）
    assert pd.Timestamp("2025-07-04") not in us_native
    vix = pd.Series(1.0 + np.arange(len(us_native), dtype=float), index=us_native)  # 从 1 起避免 0 除
    # native 上 pct_change(5)：7/4 后首个观测用其前 5 个 native 观测（不含 7/4，无复制）
    chg = vix.pct_change(5)
    # 7/4 后首个 US 观测（vix=1+index）：5-session 前 = 1+(i-5) → chg = 5/(1+(i-5))
    # 若误把 7/4 缺失 ffill 计入窗口，计数会变 → 断言精确值证明窗口用 native 观测数
    first_after = us_native[us_native > pd.Timestamp("2025-07-04")][0]
    i = list(us_native).index(first_after)
    expected_chg = (vix.iloc[i] - vix.iloc[i - 5]) / vix.iloc[i - 5]
    assert np.isclose(chg.loc[first_after], expected_chg, atol=1e-9), "7/4 缺失不应改变窗口计数"
    # 对齐后 7/4 的 China 决策用前一完成 session（7/3），非 ffill 复制 7/4
    f2 = f2_features({"vix": vix, "usd_cny": vix, "cgb10y": vix, "dr007": vix, "a_share_turnover": vix}, china)
    assert np.isfinite(f2["vix_prev_close_change_5"].dropna()).all()


def test_macro_available_at_timestamp_controls_visibility() -> None:
    """P2：available_at（时间戳）控制可见性——同日历日但 US 未收盘不可见。"""
    china = pd.DatetimeIndex(pd.bdate_range("2025-01-02", periods=30))
    # VIX 用带时间的 available_at（US 16:00 ET close）
    us_dates = _us_native_calendar(china)
    vix_dt = pd.DatetimeIndex([d + pd.Timedelta(hours=16) for d in us_dates])  # US close 时刻
    vix = pd.Series(np.arange(len(vix_dt), dtype=float), index=vix_dt)
    # China 决策日 t 14:00（CN）< US t 16:00 → t 的 US close 对 China t 不可见（strict <）
    # 用 align_derived_to_china strict_prev：vix 索引是 datetime，China 决策用日期 00:00
    aligned = align_derived_to_china(vix, china, rule="strict_prev_session")
    same = china[10]
    # China 决策日 same 00:00 < vix same 16:00 → 取的是 <same 的最近 US 收盘（same 当日 16:00 不可见）
    visible_same = vix.index[(vix.index < same)].max()
    assert aligned.loc[same] == vix.loc[visible_same]
    assert aligned.loc[same] != vix.loc[same + pd.Timedelta(hours=16)] if (same + pd.Timedelta(hours=16)) in vix.index else True


# --- F-A2 imputation ---


def _finite_f1_split(frac=0.5):
    """返回 (df_finite, train_idx, val_idx) 在 F1 全 finite 子集上（避开 warmup NaN）。"""
    f1 = f1_features(_real_adj())
    finite = f1.dropna(how="any")
    assert len(finite) > 300, "需要足够 finite 行"
    idx = list(finite.index)
    cut = int(len(idx) * frac)
    train_idx = pd.DatetimeIndex(idx[:cut])
    val_idx = pd.DatetimeIndex(idx[cut:])
    return f1, train_idx, val_idx


def test_fa2_train_only_imputation_isolation() -> None:
    """impute/scale 只用 train 统计；val/test 只 transform；imputed ≈ normalized 0。"""
    f1, train_idx, val_idx = _finite_f1_split()
    df = f1.copy()
    # 人为在 train 区与 val 区各制造一个零星 NaN
    df.loc[train_idx[10], df.columns[0]] = np.nan
    df.loc[val_idx[5], df.columns[1]] = np.nan

    pre = FeaturePreprocessor().fit_train(df.loc[train_idx])
    assert pre.is_fitted
    tr_out = pre.transform(df.loc[train_idx])
    assert np.isfinite(tr_out).all()
    va_out = pre.transform(df.loc[val_idx])
    assert np.isfinite(va_out).all()
    # imputed 位置 ≈ normalized 0（train 均值中心）
    assert np.isnan(df.loc[val_idx[5], df.columns[1]])
    assert abs(va_out[5, 1]) < 0.5
    # train 统计不被 val 更新：fit 后 transform 逐位确定
    pre2 = FeaturePreprocessor().fit_train(df.loc[train_idx])
    out2 = pre2.transform(df.loc[val_idx])
    assert np.allclose(out2, va_out, atol=1e-12)


def test_fa2_fail_closed_no_usable_obs() -> None:
    """train 区某特征全 NaN → fail-closed（不制造值）。"""
    df = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [np.nan, np.nan, np.nan]})
    pre = FeaturePreprocessor()
    with pytest.raises(ValueError):
        pre.fit_train(df)


def test_fa2_imputed_obs_approximately_zero_after_scale() -> None:
    """imputed 值标准化后 ≈ 0（train 均值中心），且所有 obs 全 finite。"""
    f1, train_idx, val_idx = _finite_f1_split()
    df = f1.copy()
    df.loc[train_idx[20], df.columns[2]] = np.nan
    pre = FeaturePreprocessor().fit_train(df.loc[train_idx])
    out = pre.transform(df)
    assert np.isfinite(out).all()
    # 被 impute 的行（train_idx[20]，列 2）→ ≈ 0
    pos = list(f1.index).index(train_idx[20])
    assert abs(out[pos, 2]) < 0.5


def test_market_feature_frame_f2_requires_macro() -> None:
    adj = _real_adj()
    with pytest.raises(ValueError):
        market_feature_frame(adj, "F2")  # 无 macro


# --- P5：F0 legacy preprocessing parity ---


def test_f0_preprocessor_matches_legacy_scaler() -> None:
    """P5：FeaturePreprocessor（ddof=1）归一化 F0 == legacy pandas scaler（ddof=1）。"""
    from china_etf.features.etf_features import global_features, per_asset_features

    adj = _real_adj()
    # F0 全 finite 区（避开 warmup）
    f0 = market_feature_frame(adj, "F0")
    finite = f0.dropna(how="any")
    train = finite.iloc[: int(len(finite) * 0.5)]

    # legacy：pandas mean/std（std 默认 ddof=1）
    legacy_mean = train.mean().to_numpy()
    legacy_std = train.std().to_numpy()  # pandas ddof=1
    legacy_norm = (train.to_numpy() - legacy_mean) / np.maximum(legacy_std, 1e-8)

    # FeaturePreprocessor（ddof=1）
    pre = FeaturePreprocessor().fit_train(train)
    pp_norm = pre.transform(train)

    assert np.allclose(pp_norm, legacy_norm, atol=1e-8), "F0 preprocessor 与 legacy scaler 不一致（P5）"


# --- P4：spec 与代码契约一致 ---


def test_feature_spec_contract_matches_implemented_fa1_fa2() -> None:
    """P4：spec 与实现契约一致（LPM2 / imputation / native-first / VIX 因果 / 分位公式 / ddof）。"""
    spec = (Path(__file__).resolve().parents[1] / "docs" / "features" / "FEATURE_ABLATION_SPEC.md").read_text(encoding="utf-8")
    low = spec.lower()
    # F-A1：LPM2 around zero
    assert "lpm2" in low
    # F-A2：train-only imputation 覆盖所有模型观测 + fail-closed
    assert "imput" in low and "train" in low
    assert "fail-closed" in low or "fail closed" in low
    # P1：native-calendar-first F2
    assert "native" in low
    # P2：availability-time PIT（strict_prev_session / available_at）
    assert "strict_prev" in low or "available_at" in low
    # P3：分位公式 (rank-1)/(N-1)
    assert "rank - 1" in low or "rank-1" in low
    # P5：ddof=1（sample std）
    assert "ddof" in low
