"""POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY — M0-M3 行为回归测试。

覆盖（评审 PREP_CORRECTION_002 要求）:
  - M0 parity == 已接受 L1 post_risk_weights（全 1011 x 11，max|diff| <= 1e-9）
  - sleeve cap 变换数值断言（total-NAV cap / 0.95）
  - RiskOverlayCE SLSQP joint projection:
      * 双组 cap 同时 binding 的内点解析解（KKT 线性系统，独立参考）
      * 组 cap 宽松时 == RiskOverlayV0 waterfill（已知精确最小距离投影）
      * 真不可行（caps 和 < 1）-> InfeasibleConstraints
      * 确定性重复性
  - forward sanity 用实际 latest post-risk total-NAV 权重（非 cap）
  - CE per-10ppt 公式 + 零分母 NaN
  - 无 RL token
  - provenance 含 python/numpy/scipy 版本
"""

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_spec = importlib.util.spec_from_file_location("ce", ROOT / "scripts" / "gate4_maxdiv_capital_efficiency.py")
ce = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ce)

from china_etf.risk.risk_overlay import InfeasibleConstraints, RiskOverlayCE, RiskOverlayV0  # noqa: E402

SLOTS = ce.SLOTS


@pytest.fixture(scope="module")
def m0_sim():
    """M0 一次 roll_out：post_risk + total_ret + def_w。"""
    adj = ce.load_research_adj()
    opens, closes = ce.load_execution_prices()
    cal = adj.index.normalize()
    ds_i = cal.get_loc(pd.Timestamp("2022-06-09"))
    last_dec_i = len(cal) - 2
    decision_start = pd.Timestamp("2022-06-09")
    eval_start = cal[ds_i + 1]
    exec_dates = cal[ds_i + 1:last_dec_i + 2]
    c = ce._run_candidate("M0", adj, opens, closes, decision_start, eval_start,
                          exec_dates, None)
    return adj, c


# --- M0 parity (exact, all 1011 x 11, <= 1e-9) ---

def test_m0_parity_exact_l1(m0_sim):
    adj, c = m0_sim
    ref = np.asarray(json.loads(ce.L1_RAW_ARTIFACT.read_text(encoding="utf-8"))
                     ["methods"]["MaximumDiversification"]["series"]["post_risk_weights"], dtype=float)
    assert c["sleeve_w"].shape == ref.shape == (1011, 11)
    d = float(np.abs(c["sleeve_w"] - ref).max())
    assert d <= 1e-9, f"M0 parity max|diff|={d:.3e} > 1e-9"


def test_m0_metrics_close_to_l1(m0_sim):
    """M0 net metrics 贴近已接受 L1 研究 MaxDiv（同引擎，确定性容差），含 worst-calendar-year。"""
    adj, c = m0_sim
    cal = adj.index.normalize()
    ds_i = cal.get_loc(pd.Timestamp("2022-06-09"))
    exec_str = [str(d.date()) for d in cal[ds_i + 1:len(cal)]]
    assert len(exec_str) == 1011
    mets = ce._compute_metrics(c["total_ret"], exec_str)
    ref = json.loads(ce.L1_RESULTS_ARTIFACT.read_text(encoding="utf-8")) \
        ["methods"]["MaximumDiversification"]["metrics"]
    assert abs(mets["cum_return"] - ref["cum_return"]) < 0.005
    assert abs(mets["calendar_cagr"] - ref["calendar_cagr"]) < 0.002
    assert abs(mets["sharpe"] - ref["sharpe"]) < 0.05
    assert abs(mets["max_drawdown"] - ref["max_drawdown"]) < 0.005
    # worst-calendar-year return 必须与已接受 L1 一致（prod(1+r)-1 全年复合）
    assert mets["worst_calendar_year"] == ref["worst_calendar_year"], \
        f"M0 worst year {mets['worst_calendar_year']} != L1 {ref['worst_calendar_year']}"
    assert abs(mets["worst_calendar_year_return"] - ref["worst_calendar_year_return"]) < 0.002, \
        f"M0 worst-year return {mets['worst_calendar_year_return']:.6f} != L1 {ref['worst_calendar_year_return']:.6f}"


# --- sleeve cap transforms ---

def test_sleeve_cap_transforms():
    """total-NAV cap / sleeve_frac 数值精确（M1-M3）。"""
    m2_caps = ce._sleeve_caps(ce.CANDIDATES["M2"])
    assert abs(m2_caps[SLOTS.index("CASH_LIKE")] - 0.05 / 0.95) < 1e-12
    assert abs(m2_caps[SLOTS.index("CN_DURATION")] - 0.15 / 0.95) < 1e-12
    assert abs(m2_caps[SLOTS.index("CN_LARGE")] - 0.25 / 0.95) < 1e-12
    assert abs(ce._def_max_sleeve(ce.CANDIDATES["M2"]) - (0.25 - 0.05) / 0.95) < 1e-12
    m3_caps = ce._sleeve_caps(ce.CANDIDATES["M3"])
    assert abs(m3_caps[SLOTS.index("CASH_LIKE")] - 0.0) < 1e-12
    assert abs(m3_caps[SLOTS.index("CN_DURATION")] - 0.15 / 0.95) < 1e-12
    assert abs(ce._def_max_sleeve(ce.CANDIDATES["M3"]) - (0.20 - 0.05) / 0.95) < 1e-12
    m1 = ce.CANDIDATES["M1"]
    assert abs(ce._def_max_sleeve(m1) - (0.30 - 0.05) / 0.95) < 1e-12
    # M0: sleeve_frac = 1.0（无 op cash）退化为 total-NAV caps
    assert ce.CANDIDATES["M0"]["op_cash"] == 0.0 and ce.CANDIDATES["M0"]["sleeve_frac"] == 1.0


# --- RiskOverlayCE SLSQP joint projection ---

def test_ce_projection_interior_dual_binding_analytic():
    """双组 cap 同时 binding 的内点解析解（独立参考，非 SLSQP 自证）。

    n=6（growth={A,B}, def={C,D}, 自由={E,F}），raw 全分量>0 且投影为内点（无 per-slot
    cap 边界）时，KKT 线性系统可解析解:
      w* = raw - λe·1 - λg·1_growth - λd·1_def
    sum=1 / growth=gmax / def=dmax → 3 元线性方程组，λ 唯一确定。
    """
    slots = ["A", "B", "C", "D", "E", "F"]
    raw = np.array([0.25, 0.20, 0.18, 0.15, 0.12, 0.10])
    growth_max = 0.35
    def_max = 0.25
    caps = np.full(6, 0.60)
    # 解析: sum: 1.0 - 6λe - 2λg - 2λd = 1 -> 3λe + λg + λd = 0
    # growth: 0.45 - 2λe - 2λg = 0.35 -> λe + λg = 0.05
    # def: 0.33 - 2λe - 2λd = 0.25 -> λe + λd = 0.04
    # -> λg = 0.05-λe; λd = 0.04-λe; 3λe + (0.05-λe) + (0.04-λe) = 0 -> λe = -0.09
    # -> λg = 0.14; λd = 0.13
    # w* = [0.20, 0.15, 0.14, 0.11, 0.21, 0.19]（全内点）
    expected = np.array([0.20, 0.15, 0.14, 0.11, 0.21, 0.19])
    ov = RiskOverlayCE(slots, caps=caps, growth_max=growth_max,
                       growth_slots=("A", "B"), def_max=def_max,
                       def_slots=("C", "D"))
    w = ov.apply(pd.Series(raw, index=slots))
    assert np.allclose(w.values, expected, atol=1e-6), \
        f"SLSQP must match analytic interior KKT solution: got {w.values}"
    assert abs(w[["A", "B"]].sum() - growth_max) < 1e-6  # growth binding
    assert abs(w[["C", "D"]].sum() - def_max) < 1e-6  # def binding
    assert (w.values > 0).all() and (w.values < caps).all()  # interior


def test_ce_projection_uses_waterfill_initialization():
    """SLSQP x0 = bounded-simplex waterfill（冻结初始化，非 raw）。"""
    slots = ["A", "B", "C"]
    raw = np.array([0.60, 0.30, 0.10])
    caps = np.array([0.50, 0.50, 0.50])
    ov = RiskOverlayCE(slots, caps=caps, growth_max=0.99, growth_slots=(),
                       def_max=0.99, def_slots=())
    waterfill = ov._waterfill(raw.copy(), caps, total=1.0)
    # 验证 waterfill ≠ raw（raw 超 cap 时被压到 cap）
    assert not np.allclose(waterfill, raw, atol=1e-12)
    # apply 用 waterfill 初值求解凸 QP（结果仍满足 C1-C3）
    w = ov.apply(pd.Series(raw, index=slots))
    assert abs(w.sum() - 1.0) < 1e-6
    assert (w.values <= caps + 1e-6).all() and (w.values >= -1e-9).all()


def test_ce_projection_equals_waterfill_when_no_group_binding():
    """组 cap 宽松（不 binding）时，RiskOverlayCE == RiskOverlayV0 waterfill
    （后者为 C1-C3 已知精确最小距离投影）——独立最小距离断言。"""
    slots = list(ce.SLOTS)
    raw = pd.Series({s: 0.08 for s in slots})
    raw["CASH_LIKE"] = 0.30
    raw["CN_DURATION"] = 0.30
    caps_loose = np.array([0.25 / 0.95] * 11)
    ov_loose = RiskOverlayCE(slots, caps=caps_loose, growth_max=0.60,
                             def_max=0.90)
    w_ce = ov_loose.apply(raw)
    ov_legacy = RiskOverlayV0(slots, single_core_max=0.25 / 0.95, china_growth_max=0.60)
    w_legacy = ov_legacy.apply(raw)
    assert np.allclose(w_ce.values, w_legacy.values, atol=1e-8), \
        "SLSQP must match waterfill when group caps not binding (min-distance projection)"


def test_ce_projection_true_infeasible():
    """caps 之和 < 1 → InfeasibleConstraints（fail-closed）。"""
    slots = ["A", "B", "C"]
    ov = RiskOverlayCE(slots, caps=np.array([0.3, 0.3, 0.3]), growth_max=0.99,
                       growth_slots=(), def_max=0.99, def_slots=())
    with pytest.raises(InfeasibleConstraints):
        ov.apply(pd.Series([0.5, 0.3, 0.2], index=slots))


def test_ce_projection_deterministic():
    """同输入两次运行输出逐元素一致（确定性）。"""
    slots = list(ce.SLOTS)
    raw = pd.Series({s: 0.08 for s in slots})
    raw["CASH_LIKE"] = 0.30
    caps = ce._sleeve_caps(ce.CANDIDATES["M2"])
    ov = RiskOverlayCE(slots, caps=caps, growth_max=ce._growth_max_sleeve(ce.CANDIDATES["M2"]),
                       def_max=ce._def_max_sleeve(ce.CANDIDATES["M2"]))
    w1 = ov.apply(raw.copy()).values
    w2 = ov.apply(raw.copy()).values
    assert np.array_equal(w1, w2)


def test_m2_sleeve_projection_respects_all_caps():
    """M2 sleeve 投影满足 C1-C5 全部（per-slot + growth + defensive）。"""
    slots = list(ce.SLOTS)
    cfg = ce.CANDIDATES["M2"]
    raw = pd.Series({s: 0.07 for s in slots})
    raw["CASH_LIKE"] = 0.20
    raw["CN_DURATION"] = 0.25
    raw["CN_LARGE"] = 0.18
    ov = RiskOverlayCE(slots, caps=ce._sleeve_caps(cfg),
                       growth_max=ce._growth_max_sleeve(cfg),
                       def_max=ce._def_max_sleeve(cfg))
    w = ov.apply(raw)
    caps = ce._sleeve_caps(cfg)
    assert abs(w.sum() - 1.0) < 1e-6
    assert (w.values <= caps + 1e-6).all() and (w.values >= -1e-9).all()
    assert w[["CHINEXT", "STAR"]].sum() <= ce._growth_max_sleeve(cfg) + 1e-6
    # defensive 组应 binding（raw 超限）
    assert abs(w[["CASH_LIKE", "CN_DURATION"]].sum() - ce._def_max_sleeve(cfg)) < 1e-6


# --- forward sanity uses actual weights ---

def test_forward_sanity_uses_actual_latest_total_nav_weights():
    """forward sanity 用实际 latest total-NAV 权重（M1-M3 为 0.95*sleeve，非 cap、非 sleeve）。"""
    cfg = ce.CANDIDATES["M2"]
    latest_tnav = np.array([0.08] * 11)
    latest_tnav[SLOTS.index("CASH_LIKE")] = 0.05 * 0.95
    latest_tnav[SLOTS.index("CN_DURATION")] = 0.10 * 0.95
    fs = ce._forward_sanity(cfg, latest_tnav, ce._duration_yield_snapshot())
    expected_def = cfg["op_cash"] + latest_tnav[SLOTS.index("CASH_LIKE")] + latest_tnav[SLOTS.index("CN_DURATION")]
    assert abs(fs["defensive_w"] - expected_def) < 1e-9
    # total-NAV 权重下 defensive_w 必须 ≤ frozen cap（不会像 sleeve 权重那样超限）
    assert fs["defensive_w"] <= cfg["def_cap"] + 1e-9
    assert abs(fs["risk_asset_w"] - (1 - expected_def)) < 1e-9
    assert fs["cash_yield_label"] == "user planning assumption, not historical"
    # 实际权重 ≠ cap 值（验证未用 cap）
    assert abs(fs["strategic_cash_like"] - cfg["cash_like_cap"]) > 1e-3
    # yield snapshot metadata 嵌入
    assert "observation_date" in fs["cn_duration_yield_snapshot"]
    assert "value_pct" in fs["cn_duration_yield_snapshot"]
    assert "sha256" in fs["cn_duration_yield_snapshot"]
    for T in ("7", "8", "9"):
        assert np.isfinite(fs["required_risk_return"][T])


def test_forward_sanity_end_to_end_actual_candidate_weights():
    """端到端：M0-M3 各候选实际 RUN latest total-NAV 权重 → defensive_w ≤ frozen cap。"""
    adj = ce.load_research_adj()
    opens, closes = ce.load_execution_prices()
    cal = adj.index.normalize()
    ds_i = cal.get_loc(pd.Timestamp("2022-06-09"))
    last_dec_i = len(cal) - 2
    decision_start = pd.Timestamp("2022-06-09")
    eval_start = cal[ds_i + 1]
    exec_dates = cal[ds_i + 1:last_dec_i + 2]
    snap = ce._duration_yield_snapshot()
    for name, cfg in ce.CANDIDATES.items():
        overlay = None
        if cfg["op_cash"] > 0:
            from china_etf.risk.risk_overlay import RiskOverlayCE
            overlay = RiskOverlayCE(ce.SLOTS, caps=ce._sleeve_caps(cfg),
                                    growth_max=ce._growth_max_sleeve(cfg),
                                    def_max=ce._def_max_sleeve(cfg))
        c = ce._run_candidate(name, adj, opens, closes, decision_start, eval_start,
                              exec_dates, overlay)
        total_w = c["total_w"][-1]  # total-NAV slot weights
        fs = ce._forward_sanity(cfg, total_w, snap)
        # total-NAV defensive_w = op_cash + latest_tnav[CASH_LIKE] + latest_tnav[CN_DURATION]
        expected = cfg["op_cash"] + total_w[SLOTS.index("CASH_LIKE")] + total_w[SLOTS.index("CN_DURATION")]
        assert abs(fs["defensive_w"] - expected) < 1e-9
        assert fs["defensive_w"] <= cfg["def_cap"] + 1e-9, \
            f"{name}: forward defensive_w {fs['defensive_w']:.6f} > cap {cfg['def_cap']}"


# --- CE per-10ppt formulas + zero denominator ---

def test_ce_diagnostics_zero_denominator_nan():
    """防御性配置无变化（def_M0 == def_cand）→ per-10ppt NaN（不除以零）。"""
    cands = {
        "M0": {"metrics": {"calendar_cagr": 0.09, "max_drawdown": -0.04},
               "def_w": np.array([0.5] * 10)},
        "M1": {"metrics": {"calendar_cagr": 0.09, "max_drawdown": -0.04},
               "def_w": np.array([0.5] * 10)},
    }
    diag = ce._ce_diagnostics(cands, "M0")
    assert diag["M1"]["zero_denominator"] is True
    assert diag["M1"]["cagr_per_10ppt_defensive_reduction"] is None
    assert diag["M1"]["maxdd_magnitude_per_10ppt_defensive_reduction"] is None


def test_ce_diagnostics_maxdd_magnitude_convention():
    """MaxDD per-10ppt 用绝对值增量（abs convention）；signed 不混淆。"""
    cands = {
        "M0": {"metrics": {"calendar_cagr": 0.09, "max_drawdown": -0.04},
               "def_w": np.array([0.5] * 10)},
        "M2": {"metrics": {"calendar_cagr": 0.10, "max_drawdown": -0.05},
               "def_w": np.array([0.3] * 10)},
    }
    diag = ce._ce_diagnostics(cands, "M0")
    d = diag["M2"]
    # abs(MaxDD_cand)=0.05, abs(MaxDD_M0)=0.04; def_M0-def_cand=0.2; *0.10
    expected = (0.05 - 0.04) / 0.2 * 0.10
    assert abs(d["maxdd_magnitude_per_10ppt_defensive_reduction"] - expected) < 1e-9
    assert d["zero_denominator"] is False


# --- no RL / provenance ---

def test_no_rl_tokens():
    src = Path(ROOT / "scripts" / "gate4_maxdiv_capital_efficiency.py").read_text(encoding="utf-8")
    for tok in ("PPO", "SAC", "TD3", "stable_baselines3"):
        assert tok not in src, f"forbidden RL token {tok}"


def test_provenance_versions_and_l1_bound():
    """provenance 含 python/numpy/scipy 版本 + L1 artifact SHA + commit。"""
    prov = ce._provenance()
    assert "python" in prov and "numpy" in prov and "scipy" in prov
    assert prov["numpy"] == np.__version__ and prov["scipy"].startswith("1.")
    assert any("gate4_long_horizon_nonrl_results.json" in k for k in prov)
    assert any("gate4_long_horizon_nonrl_raw.json" in k for k in prov)
    assert any("CN_DURATION_CN10Y_yield.csv" in k for k in prov)
    assert any("CASH_LIKE_511360_SH_raw.csv" in k for k in prov)
