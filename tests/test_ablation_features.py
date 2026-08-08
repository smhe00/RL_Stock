"""GATE_4_FEATURE_ABLATION_PREP — F1/F2/F3 builders + F-A1/F-A2 + 维度断言。

评审 §7 项 5-9：
- F0=104 / F1=110 / F2=110 / F3=116（维度断言）
- strict PIT 对齐测试（F2 未来值不泄漏）
- F-A1：equity_downside_semivol_60 = LPM2 around zero
- F-A2：train-only imputation 隔离 + 每 obs 全 finite
"""

import numpy as np
import pandas as pd
import pytest

from china_etf.data.loader import load_research_adj
from china_etf.features.ablation_features import (
    EXOG_DIM,
    OBS_DIM,
    align_pit,
    f1_features,
    f2_features,
    market_feature_frame,
)
from china_etf.features.preprocessor import FeaturePreprocessor


def _real_adj():
    return load_research_adj()


def _synthetic_macro(index):
    """合成 macro，索引对齐到给定 china 日历（避免 reindex NaN）。"""
    dates = pd.DatetimeIndex(index)
    n = len(dates)
    rng = np.random.default_rng(7)
    vix = pd.Series(20 + 5 * np.sin(np.arange(n) / 20) + rng.normal(0, 1, n), index=dates)
    usd = pd.Series(7.0 + 0.05 * np.arange(n) / n + rng.normal(0, 0.01, n), index=dates)
    cgb = pd.Series(0.03 + 0.002 * np.sin(np.arange(n) / 40), index=dates)
    dr = pd.Series(0.02 + 0.003 * np.sin(np.arange(n) / 25) + rng.normal(0, 0.0005, n), index=dates)
    to = pd.Series(8000 + 3000 * np.sin(np.arange(n) / 60) + rng.normal(0, 300, n), index=dates)
    return {"vix": vix, "usd_cny": usd, "cgb10y": cgb, "dr007": dr, "a_share_turnover": to}


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


# --- F2 PIT 对齐 ---


def test_f2_align_pit_no_future_leak() -> None:
    """align_pit 只取 ≤t 已发布值：未来 macro 不泄漏到更早 China 日。"""
    china = pd.DatetimeIndex(pd.bdate_range("2025-01-02", periods=10))
    macro = pd.Series(
        [10.0] * 10, index=pd.DatetimeIndex(pd.bdate_range("2025-01-02", periods=10))
    )
    macro.iloc[-1] = 999.0  # 未来（第 10 日）高值
    aligned = align_pit(macro, china)
    # 第 9 日（索引 8）只看到前 9 个值，不应含 999
    assert aligned.iloc[8] == pytest.approx(10.0)
    assert aligned.iloc[9] == pytest.approx(999.0)  # 发布日之后才可见


def test_f2_features_aligns_to_china_calendar() -> None:
    """f2_features 输出对齐 China 日历；未来 macro 不影响更早日。"""
    china = pd.DatetimeIndex(pd.bdate_range("2025-01-02", periods=400))
    macro = _synthetic_macro(china)
    # 注入未来泄漏：最后 30 日 vix 跳升
    macro["vix"].iloc[-30:] += 50
    f2 = f2_features(macro, china)
    assert f2.shape[1] == 6
    assert f2.index.equals(china)
    # 泄漏前（第 340 日）的 vix 分位不受未来跳升影响（rank 只用 ≤t 数据）
    f2_valid = f2["vix_prev_close_percentile_252"].dropna()
    d_early = f2_valid.index[len(f2_valid) // 2]  # 泄漏前的某个 finite 日
    vix_until = macro["vix"].loc[:d_early]
    # 对照：rolling(252).rank(pct=True)（与实现一致，rank 只回看 ≤t 的 252 窗口）
    expected_pct = vix_until.rolling(252).rank(pct=True).dropna().iloc[-1]
    assert np.isclose(f2.loc[d_early, "vix_prev_close_percentile_252"], expected_pct, atol=1e-10)


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
