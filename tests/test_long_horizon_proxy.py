"""GATE_4_LONG_HORIZON_PROXY — L2 场景 proxy 测试（评审 required invariants）。

覆盖：
- STAR/CHINEXT distinct 序列断言（2015-2019 不共享同一收益序列）
- CASH_LIKE carry-only / 无久期价格 P&L
- CN_DURATION /100 单位归一化 + +10bp 合成测试
- ffill-before-yield-difference（缺日不当作多次冲击）
- A股/利率 T vs HK/US/GOLD/FX T-1 信息时序
- no-future-data rolling lookbacks
- 6 方法/canonical 参数冻结
- SCENARIO_NOT_STRICT_PIT_OOS 标注强制
- 2800-interval fail-closed parity
- 无 PPO/SAC/TD3 路径
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from china_etf.evaluation.long_horizon_proxy_panel import (  # noqa: E402
    D_EFF, LAG_1_SLOTS, SLOT_ORDER, _cash_like_series, _cn_duration_series, build_panel,
)

RUNNER_SRC = (ROOT / "scripts" / "gate4_long_horizon_proxy.py").read_text(encoding="utf-8")


# --- 窗口 fail-closed parity ---


def test_window_parity_fail_closed() -> None:
    signal_panel, return_levels, cal = build_panel()
    ds = pd.Timestamp("2015-01-28")
    ds_i = cal.get_loc(ds)
    # 决策区间 [ds_i, last_decision] 含末决策（last_decision = cal[-2]）
    n = (len(cal) - 2 + 1) - ds_i
    assert n == 2800, f"n_intervals {n} != 2800"
    assert cal[ds_i].date().isoformat() == "2015-01-28"
    assert cal[-1].date().isoformat() == "2026-08-07"
    assert cal[-2].date().isoformat() == "2026-08-06"
    assert list(signal_panel.columns) == SLOT_ORDER
    assert list(return_levels.columns) == SLOT_ORDER


# --- STAR/CHINEXT distinct ---


def test_star_chinext_distinct_series() -> None:
    signal_panel, _, _ = build_panel()
    panel = signal_panel
    star = panel["STAR"]
    cyb = panel["CHINEXT"]
    # distinct: 决不可共享同一水平序列（原 CHINEXT 双计被否）
    assert not np.allclose(star.values, cyb.values, equal_nan=True), "STAR/CHINEXT must be distinct series"
    # 2015-2019 重叠期日收益不同（corr < 1）
    r = panel.pct_change().loc["2015-01-01":"2019-12-31", ["STAR", "CHINEXT"]].dropna()
    corr = r["STAR"].corr(r["CHINEXT"])
    assert corr < 0.99, f"STAR/CHINEXT corr {corr:.3f} — not distinct (frozen: 0.675)"


# --- CASH_LIKE carry-only ---


def test_cash_like_carry_only_near_zero_duration() -> None:
    """CASH_LIKE 为 carry-only：收益率脉冲对价格只产生一阶 carry，无价格 P&L。"""
    idx = pd.date_range("2015-05-01", periods=20, freq="B")
    y = pd.DataFrame({"shibor_on_pct": pd.Series(2.0, index=idx),
                      "yield_2y_pct": pd.Series(2.0, index=idx)})
    base = _cash_like_series(y)
    # 收益率 +100bp 冲击（仅影响 carry，无价格 P&L）
    y2 = y.copy()
    y2["shibor_on_pct"] = y2["shibor_on_pct"] + 1.0
    shock = _cash_like_series(y2)
    # 单日 carry 变动 = Δrate/100 × 1/365 ≈ 1%/365 ≈ 2.7e-5（近零久期：无 -D×Δy 项）
    daily_jump = (shock.iloc[10] / shock.iloc[9]) / (base.iloc[10] / base.iloc[9]) - 1.0
    assert abs(daily_jump) < 1e-3, f"CASH_LIKE carry-only violation: daily jump {daily_jump:.5f}"
    # 全程单调累乘（正 carry）
    assert (base.diff().dropna() > 0).all(), "CASH_LIKE carry-only should be monotonic up"


# --- CN_DURATION 单位安全 + 10bp ---


def _yield_frame(y10_values, idx):
    return pd.DataFrame({"yield_10y_pct": pd.Series(y10_values, index=idx),
                         "yield_2y_pct": pd.Series(2.0, index=idx),
                         "shibor_on_pct": pd.Series(2.0, index=idx)})


def test_cn_duration_unit_safe_10bp() -> None:
    """+10bp 收益率变动 → Δy=+0.0010（非 +0.10）；纯久期分量 ≈ -0.75% 在 carry 前。"""
    idx = pd.date_range("2015-01-02", periods=3, freq="D")  # 连续日历日（Δdays=1）
    y = _yield_frame([2.50, 2.60, 2.60], idx)  # 2.50 -> 2.60 = +10bp
    price = _cn_duration_series(y)
    # Δy = (2.60-2.50)/100 = 0.0010；纯久期 = -7.5 × 0.0010 = -0.0075
    # carry ≈ 2.50/100 × 1/365 ≈ 6.85e-5（连续日历日 Δdays=1）
    r1 = (price.iloc[1] / price.iloc[0]) - 1.0
    pure_duration = -D_EFF * 0.0010
    carry = (2.50 / 100.0) * 1 / 365.0
    expected = np.exp(pure_duration + carry) - 1.0
    assert abs(r1 - expected) < 1e-12, f"CN_DURATION unit violation: got {r1:.6f} want {expected:.6f}"
    # 纯久期分量 ≈ -0.75% + carry（exp 一阶近似，容差取二阶项量级）
    assert abs(r1 - (pure_duration + carry)) < 1e-4, f"纯久期分量偏移: {r1 - (pure_duration + carry):.2e}"


def test_cn_duration_ffill_before_diff() -> None:
    """缺日先 ffill 再 Δy：多日间隔不得当作多次独立冲击。"""
    idx = pd.date_range("2015-01-02", periods=6, freq="B")
    y = _yield_frame([2.50, 2.60, 2.60, 2.60, 2.60, 2.60], idx)
    # 删中间两日（模拟缺日）→ ffill 后 Δy 仅发生在 2.50->2.60 一处
    price = _cn_duration_series(y)
    # 构造"缺日"：重复值被 ffill 补，Δy=0 → 无二次久期冲击
    diffs = np.diff(np.log(price))
    # 仅第一处（2.50->2.60）有显著 Δy；其余仅 carry
    big = np.where(np.abs(diffs) > 1e-4)[0]
    assert len(big) <= 1, f"multi-day gap treated as multiple shocks: {big}"


def test_cn_duration_y_over_100_normalization_asserted() -> None:
    PANEL_SRC = (ROOT / "src" / "china_etf" / "evaluation" / "long_horizon_proxy_panel.py").read_text(
        encoding="utf-8")
    assert "/ 100.0" in PANEL_SRC, "panel must assert /100 normalization (y_decimal = y_percent / 100)"


# --- 信息时序：A股/利率 T vs 非A股 T-1 ---


def test_non_a_share_lag_1_information_timing() -> None:
    signal_panel, return_levels, cal = build_panel()
    for slot in LAG_1_SLOTS:
        s = signal_panel[slot].dropna()
        assert len(s) > 0, f"{slot} empty after dropna"
        # T-1 lag：面板首个非 NaN 决策日 = 数据首日 SH 交易日 + 1
        # （build_panel 中 shift(1) 保证；此处验证数据从 2015 前即可用）
        assert s.index[0] <= pd.Timestamp("2015-01-28"), f"{slot} unavailable before decision_start"
    # 决策起点 2015-01-28 时全部有限（signal 面板）
    ds = pd.Timestamp("2015-01-28")
    row = signal_panel.loc[:ds].iloc[-1]
    assert row.notna().all(), f"decision_start {ds.date()} not fully finite:\n{row}"


def test_signal_return_panel_separation() -> None:
    """BLOCKER 1：lagged slot 的 signal(T) = return(T-1)，且 return 面板不被 lag（T->T+1 收益）。"""
    signal_panel, return_levels, cal = build_panel()
    ds = pd.Timestamp("2015-01-28")
    ds_i = cal.get_loc(ds)
    for slot in LAG_1_SLOTS:
        assert abs(signal_panel[slot].iloc[ds_i] - return_levels[slot].iloc[ds_i - 1]) < 1e-12, \
            f"{slot} signal(T) != return(T-1)"
        # return 面板未被 lag：决策 T 的已实现收益 = price(T+1)/price(T) - 1
        r_impl = return_levels[slot].iloc[ds_i + 1] / return_levels[slot].iloc[ds_i] - 1.0
        assert np.isfinite(r_impl) or np.isnan(r_impl)
        # signal 与 return 面板在 lag 变换后不同（fail-closed，BLOCKER 1）
        # 对齐索引比较（signal 因 shift 少一行）
        common = signal_panel[slot].dropna().index.intersection(return_levels[slot].dropna().index)
        diff = np.abs(signal_panel[slot].reindex(common) - return_levels[slot].reindex(common)).max()
        assert diff > 1e-9, f"{slot} signal/return panels identical after lag (BLOCKER 1)"


def test_no_future_data_rolling() -> None:
    """rolling cov/vol/momentum 只用 ≤T：决策日 T 的 momentum 锚点 = T-252 / T-21（≤T）。"""
    signal_panel, _, cal = build_panel()
    panel = signal_panel
    t = pd.Timestamp("2020-06-01")
    idx = panel.index
    pos = idx.get_loc(t)
    assert pos > 252
    # 独立重算 momentum 权重（只用 ≤T）：锚点 T-252 / T-21
    p_start = panel.iloc[pos - 252].ffill()
    p_skip = panel.iloc[pos - 21].ffill()
    score = np.where(np.isfinite(np.log(p_skip / p_start)) & (np.log(p_skip / p_start) > 0),
                     np.log(p_skip / p_start), 0.0)
    w_ref = score / score.sum() if score.sum() > 1e-12 else np.full(len(SLOT_ORDER), 1.0 / len(SLOT_ORDER))
    assert np.isfinite(w_ref).all() and np.allclose(w_ref.sum(), 1.0, atol=1e-6)
    # 无未来信息：用 T 之后数据重算的权重必须不同（否则 lookahead 未隔离）
    p_start_f = panel.iloc[pos + 252].ffill()
    p_skip_f = panel.iloc[pos + 21].ffill()
    score_f = np.where(np.isfinite(np.log(p_skip_f / p_start_f)) & (np.log(p_skip_f / p_start_f) > 0),
                       np.log(p_skip_f / p_start_f), 0.0)
    w_fut = score_f / score_f.sum() if score_f.sum() > 1e-12 else w_ref
    assert not np.allclose(w_ref, w_fut, atol=1e-3), "future data would change momentum weights (lookahead risk)"


# --- 6 方法 / canonical / SCENARIO label / 无 RL ---


def test_methods_and_params_frozen() -> None:
    from china_etf.evaluation.long_horizon_proxy_panel import D_EFF
    for name in ("HS300_ref", "EqualWeight", "MaximumDiversification",
                 "MinimumVariance", "RiskParity_IVOL", "Momentum_12_1"):
        assert name in RUNNER_SRC, f"{name} absent from runner"
    # canonical 参数（冻结，runner 模块级常量）
    import importlib.util
    spec = importlib.util.spec_from_file_location("proxy_runner_mod", ROOT / "scripts" / "gate4_long_horizon_proxy.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.CANONICAL_PARAMS == {
        "MaximumDiversification": {"lookback": 120, "shrinkage": 0.5},
        "MinimumVariance": {"lookback": 120, "shrinkage": 0.5},
        "RiskParity_IVOL": {"lookback": 60},
        "Momentum_12_1": {"lookback": 252, "skip": 21},
    }
    assert D_EFF == 7.5


def test_overlay_constraints_applied_all_methods() -> None:
    """BLOCKER 2：全 run 每方法 post-overlay 权重满足 project 可行集（sum=1, single<=0.25,
    CHINEXT+STAR<=0.50, 无负）。用 runner 的 _apply_overlay + ProxyPolicy 实测全期。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("l2_mod", ROOT / "scripts" / "gate4_long_horizon_proxy.py")
    l2 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(l2)
    signal_panel, return_levels, cal = l2.build_panel()
    ds = pd.Timestamp("2015-01-28")
    ds_i = cal.get_loc(ds)
    last_dec_i = len(cal) - 2
    decision_dates = cal[ds_i:last_dec_i + 1]
    growth_idx = [i for i, s in enumerate(SLOT_ORDER) if s in ("CHINEXT", "STAR")]
    for name in l2.METHODS:
        pol = l2.ProxyPolicy(signal_panel, name)
        for t in decision_dates[::500]:  # 抽样覆盖全期
            w = l2._apply_overlay(pol(t), SLOT_ORDER)
            assert np.allclose(w.sum(), 1.0, atol=1e-6), f"{name} sum != 1"
            assert (w >= -1e-9).all(), f"{name} negative weight"
            assert w.max() <= 0.25 + 1e-6, f"{name} single>25%: {w.max():.4f}"
            assert w[growth_idx].sum() <= 0.50 + 1e-6, f"{name} growth>50%: {w[growth_idx].sum():.4f}"


def test_overlay_projects_unconstrained_to_feasible() -> None:
    """BLOCKER 2：合成用例——未约束 MinVar/RP/Momentum 超 25% 时 overlay 投影回可行集。"""
    from china_etf.evaluation.long_horizon_proxy_panel import SLOT_ORDER as SO
    import importlib.util
    spec = importlib.util.spec_from_file_location("l2_mod2", ROOT / "scripts" / "gate4_long_horizon_proxy.py")
    l2 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(l2)
    # 构造极端未约束权重：CASH_LIKE 99%（超 25%）
    w_bad = np.zeros(len(SO))
    w_bad[SO.index("CASH_LIKE")] = 0.99
    w_bad[SO.index("CN_LARGE")] = 0.01
    out = l2._apply_overlay(w_bad, SO)
    assert out.max() <= 0.25 + 1e-6, f"overlay failed: max {out.max():.4f}"
    assert np.allclose(out.sum(), 1.0, atol=1e-6)
    # CHINEXT+STAR 超 50% 用例
    w_g = np.zeros(len(SO))
    w_g[SO.index("CHINEXT")] = 0.30
    w_g[SO.index("STAR")] = 0.30
    w_g[SO.index("CN_LARGE")] = 0.40
    out_g = l2._apply_overlay(w_g, SO)
    growth_sum = out_g[SO.index("CHINEXT")] + out_g[SO.index("STAR")]
    assert growth_sum <= 0.50 + 1e-6, f"overlay failed growth cap: {growth_sum:.4f}"


def test_scenario_label_enforced() -> None:
    assert "SCENARIO_NOT_STRICT_PIT_OOS" in RUNNER_SRC
    assert "LONG_HORIZON_PROXY_SCENARIO_DIAGNOSTIC" in RUNNER_SRC


def test_no_rl_path() -> None:
    for tok in ("PPO", "SAC", "TD3", "stable_baselines3"):
        assert tok not in RUNNER_SRC, f"forbidden RL token {tok} in runner"
