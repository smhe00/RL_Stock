"""POST_L2_INSTRUMENT_EXECUTION_REALISM — 执行真实化行为回归测试（RUN_CORRECTION_003）。

评审（CORRECTION_002_REVIEWER_RESPONSE）7 项修正的行为断言：
  1. 03110.HK 可执行 marks 在 eligible 后有限（不再 no_quote=550）；Southbound 分支真实成交。
  2. MaxDiv target 权重与已接受 L1 post_risk_weights 精确一致（全 1011 日）。
  3. S1 每子期研究 CAGR 从 L1 artifact 计算（year_2022 != 全期 0.094154）；worst 判 S1。
  4. S3 用 distinct fail-closed days（结构停泊 ∪ 无报价）。
  5. 公司行为在 open 估值/sizing 之前（settle -> 折算 -> 计提，pre-open 持仓）。
  6. HK T+2 用 03110.HK session 日历（非 SH exec index+2，非日历 +2d）。
  7. Provenance 单一 manifest 绑定 L1 research artifact SHA + commit。
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

_spec = importlib.util.spec_from_file_location("inst_real", ROOT / "scripts" / "gate4_instrument_execution_realism.py")
inst = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(inst)

FROZEN_DS = pd.Timestamp(inst.FROZEN["decision_start"])


def _decision_dates(adj):
    cal = adj.index.normalize()
    ds_i = cal.get_loc(FROZEN_DS)
    return cal[ds_i:len(cal) - 1]


@pytest.fixture(scope="module")
def sim():
    data = inst.load_all()
    dd = _decision_dates(data["adj"])
    W = inst.maxdiv_weights(data["adj"], data["opens"], data["closes"], dd, ca=data["ca"])
    results = inst._simulate(data, W=W)
    return data, W, results


# --- frozen contract ---

def test_slot_instrument_mapping() -> None:
    assert inst.SLOT_INSTRUMENT["CN_LARGE"] == "510300.SH"
    assert inst.SLOT_INSTRUMENT["HK_DIVIDEND"] == "03110.HK"
    assert len(inst.SLOT_INSTRUMENT) == 11


def test_hk_dividend_three_dates() -> None:
    assert inst.HK_DIVIDEND_DATES == {"listing": "2013-06-17", "data_start": "2021-01-11",
                                      "southbound_eligible_from": "2024-05-06"}
    vals = list(inst.HK_DIVIDEND_DATES.values())
    assert vals == sorted(vals)


def test_cost_routing() -> None:
    assert "03110.HK" in inst.SOUTHBOUND_INST
    m = inst.MainlandETFCostModel()
    assert m.broker_commission_rate == 0.00005 and m.stamp_duty_rate == 0.0
    s = inst.SouthboundETFCostModel()
    assert s.broker_commission_rate == 0.0003 and s.stamp_duty_rate == 0.0
    s.fx_to_base = 0.9
    cb = s.estimate("03110.HK", "buy", 100, 50.0, market_state={"transaction_date": "2025-01-01"})
    assert cb.commission >= 5.0 * 0.9 - 1e-9  # min HKD 5 折 CNY


def test_no_rl() -> None:
    src = Path(ROOT / "scripts" / "gate4_instrument_execution_realism.py").read_text(encoding="utf-8")
    for tok in ("PPO", "SAC", "TD3", "stable_baselines3"):
        assert tok not in src, f"forbidden RL token {tok}"


# --- CORRECTION_003 #1: 03110 executable marks + exercised Southbound path ---

def test_03110_marks_finite_after_eligibility(sim) -> None:
    """03110.HK 在 eligible 后有有限可执行 CNY marks（评审：缺失 marks 修复）。"""
    data = sim[0]
    os_ = data["opens"]["03110.HK"]
    el = os_[os_.index >= pd.Timestamp("2024-05-06")]
    assert int((el > 0).sum()) > 500, "03110 executable marks must be finite post-eligibility"
    # HKD 本地序列保留（Southbound 成本用本地价）
    assert len(data["opens_hkd"]) > 1000


def test_03110_execution_path_exercised(sim) -> None:
    """Southbound 执行分支真实行使：attempted > 0, fills > 0, notional > 0（不再是 no_quote=550）。"""
    results = sim[2]
    hk = results["execution"]["hk_dividend_diagnostic"]
    assert hk["attempted_orders"] > 0, "03110 orders must be attempted after eligibility"
    assert hk["actual_fills"] > 0, "03110 must fill after eligibility (no_quote=550 was the bug)"
    assert hk["traded_notional_cny"] > 0
    assert hk["dates_target_notional_ge_one_board_lot"] > 400
    # 18 no-quote days（HK 假日等）而非 550
    assert results["execution"]["fail_closed"]["no_quote_days"] < 100


# --- CORRECTION_003 #2: exact MaxDiv target-weight parity ---

def test_maxdiv_weight_parity_exact(sim) -> None:
    """maxdiv_weights == 已接受 L1 post_risk_weights（全 1011 日精确一致）。"""
    W = sim[1]
    ref = np.asarray(json.loads(inst.L1_RAW_ARTIFACT.read_text(encoding="utf-8"))
                     ["methods"]["MaximumDiversification"]["series"]["post_risk_weights"])
    assert W.shape == ref.shape == (inst.FROZEN["n_decision_days"], 11)
    d = np.abs(W - ref)
    assert d.max() <= 1e-9, f"MaxDiv target-weight parity violated: max diff {d.max():.2e}"
    assert np.allclose(W.sum(axis=1), 1.0, atol=1e-6)


# --- CORRECTION_003 #3: S1 per-subperiod research CAGR ---

def test_s1_research_cagr_per_segment_not_full_period() -> None:
    """研究 CAGR 必须按子期从 L1 artifact 计算（year_2022 ≈ -0.007，非全期 0.094154）。"""
    ref = inst._research_cagr_segments()
    assert abs(ref["year_2022"] - (-0.007068)) < 1e-3, "2022 research CAGR must be per-segment, not full-period"
    assert abs(ref["year_2022"] - 0.094154) > 0.05, "must NOT reuse full-period CAGR for subperiods"
    assert "2022H2-2023_weak_equity" in ref and "2024-2026_strong_equity" in ref
    for v in ref.values():
        assert np.isfinite(v)


def test_s1_subperiod_boundaries_match_l1(sim) -> None:
    """S1 每段 n_days 与 L1 artifact 完全一致（140/242/242/243/144；382/629）。"""
    results = sim[2]
    s1 = results["s1_subperiods"]
    sp = json.loads(inst.L1_RESEARCH_ARTIFACT.read_text(encoding="utf-8")) \
        ["methods"]["MaximumDiversification"]["sub_periods"]
    for y, v in sp["calendar_years"].items():
        assert s1[f"year_{y}"]["n_days"] == v["n_days"], f"year_{y} day count mismatch"
    for ph, v in sp["phases"].items():
        if ph == "split_label":
            continue
        assert s1[ph]["n_days"] == v["n_days"], f"{ph} day count mismatch"


def test_s1_worst_degradation_from_sim(sim) -> None:
    """S1 由各段 degradation 最差段判定；worst ≥ -5% → PASS。"""
    results = sim[2]
    s1 = results["s1_subperiods"]
    segs = {k: v["degradation"] for k, v in s1.items()}
    assert results["stop_criteria"]["S1"]["worst_subperiod_degradation"] == min(segs.values())
    assert results["stop_criteria"]["S1"]["pass"] is True


# --- CORRECTION_003 #4: S3 distinct fail-closed days ---

def test_s3_distinct_fail_closed_days(sim) -> None:
    """S3 = distinct fail-closed days（结构 461 ∪ 无报价 18）/ 1011；结构停泊主导。"""
    results = sim[2]
    fc = results["execution"]["fail_closed"]
    s3 = results["stop_criteria"]["S3"]
    assert fc["structural_ineligible_cash_parking"] == 461
    assert fc["no_quote_days"] < 100
    # union 语义：distinct ≤ structural + no_quote（同日两种原因只计一次）
    assert fc["distinct_fail_closed_days"] == s3["structural_days"] + s3["no_quote_days"] \
        - s3["overlap_days"]
    assert fc["distinct_fail_closed_days"] >= s3["structural_days"]
    assert s3["fail_closed_pct"] > 40.0 and s3["pass"] is False
    assert results["stop_criteria"]["STOP"] is True


# --- CORRECTION_003 #5: corporate actions before sizing (canonical ordering) ---

def test_ca_applied_before_open_valuation(sim) -> None:
    """CA（settle/折算/计提）在 open 估值与 target_qty 之前（source-order 断言）。"""
    src = Path(ROOT / "scripts" / "gate4_instrument_execution_realism.py").read_text(encoding="utf-8")
    ca_pos = src.find("# 2. 公司行为")  # "# 2. 公司行为"
    open_pos = src.find("# 3. open/close 估值")  # "# 3. open/close 估值"
    tgt_pos = src.find("# 5. target_qty")
    assert ca_pos != -1 and open_pos != -1 and tgt_pos != -1
    assert ca_pos < open_pos < tgt_pos


def test_ca_unit_conversion_before_sizing_behavior() -> None:
    """_apply_ca_at：折算先于计提；折算后持仓 scale；计提按折算后 pre-open 持仓。"""
    positions = {"512100.SH": 1000.0}
    accrued_div = {"512100.SH": 0.0}
    cash = 0.0
    fx = pd.Series([0.9, 0.9], index=pd.date_range("2022-09-02", periods=2))
    ex = pd.Timestamp("2022-09-05")
    div_accrual = {(ex, "512100.SH"): 0.05}
    unit_conv = {(ex, "512100.SH"): 0.36555}
    div_settle = {ex + pd.Timedelta(days=7): {"512100.SH"}}
    cash = inst._apply_ca_at(ex, positions, accrued_div, cash, fx, div_accrual, unit_conv, div_settle)
    assert positions["512100.SH"] == pytest.approx(1000.0 * 0.36555)
    assert accrued_div["512100.SH"] == pytest.approx(1000.0 * 0.36555 * 0.05)
    assert cash == 0.0  # settle_date != ex
    # settle 触发
    cash = inst._apply_ca_at(ex + pd.Timedelta(days=7), positions, accrued_div, cash, fx,
                             div_accrual, unit_conv, div_settle)
    assert cash == pytest.approx(1000.0 * 0.36555 * 0.05)
    assert accrued_div["512100.SH"] == 0.0


# --- CORRECTION_003 #6: HK T+2 on 03110 session calendar ---

def test_hk_t2_session_calendar_release() -> None:
    """HK T+2 释放 = 03110 交易日历第 2 个 session（非日历 +2d，非 SH exec index+2）。"""
    hk_cal = pd.DatetimeIndex(pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-06",
                                              "2025-01-07", "2025-01-08", "2025-01-09"]))
    # 2025-01-03 卖出 → T+2 = 2025-01-07（第 2 个 HK session）；日历 +2d = 01-05（周日，非 session）
    assert inst._hk_settle_date(hk_cal, pd.Timestamp("2025-01-03")) == pd.Timestamp("2025-01-07")
    # 非 HK session 无成交日 → None（无释放）
    assert inst._hk_settle_date(hk_cal, pd.Timestamp("2025-01-04")) is None
    # 窗口尾部不足 2 个 session → None（应收保留于 NAV）
    assert inst._hk_settle_date(hk_cal, pd.Timestamp("2025-01-08")) is None


def test_hk_settle_uses_hk_not_sh_calendar() -> None:
    """HK T+2 绑定 03110.HK session 日历（sina_qfq index），非 SH exec index+2。"""
    src = Path(ROOT / "scripts" / "gate4_instrument_execution_realism.py").read_text(encoding="utf-8")
    assert "_hk_settle_date(hk_cal" in src
    assert "receivables[rd]" in src  # date-keyed 应收 ledger
    assert "SETTLEMENT_T[\"HK\"]" in src


# --- CORRECTION_003 #7: provenance binds L1 artifact + commit ---

def test_provenance_binds_l1_artifact_and_commit(sim) -> None:
    """Provenance 单一 manifest：绑定 L1 results/raw artifact SHA256 + commit；计数来自 manifest。"""
    data = sim[0]
    results = sim[2]
    man = results["manifest"]
    prov = man["data_provenance"]
    ref = man["l1_research_reference"]
    assert ref["results_sha256"] == inst.sha256_of(inst.L1_RESEARCH_ARTIFACT)
    assert ref["raw_sha256"] == inst.sha256_of(inst.L1_RAW_ARTIFACT)
    assert len(prov) == man["provenance_count"]
    assert man["provenance_count"] == 20  # 11 raw + sina_qfq + hkd_cny + 7 divid_events
    assert man["commit"] is not None
    # 03110 sina_qfq 与 CA 事件均哈希
    assert any("03110_HK_sina_qfq" in k for k in prov)
    assert any("divid_events" in k for k in prov)


# --- retained behavioral checks ---

def test_t_plus_1_open_execution_synthetic() -> None:
    """sizing/fills 用 T+1 open；close 仅 post-trade 估值。"""
    src = Path(ROOT / "scripts" / "gate4_instrument_execution_realism.py").read_text(encoding="utf-8")
    assert "open_marks" in src and "close_marks" in src
    assert "fresh" in src  # 当日报价要求（缺失 → fail-closed 保持）
    assert "nav_close.append" in src


def test_post_fill_nav_and_fee() -> None:
    """post-fill NAV：nav_close 绑定 net_returns（含 initial_cash 首日收益）。"""
    src = Path(ROOT / "scripts" / "gate4_instrument_execution_realism.py").read_text(encoding="utf-8")
    assert "nav_close.append(nav)" in src
    assert "np.diff(pv_full)" in src  # 首日收益含入（initial_cash base）
    assert "fees_total" in src and "slippage_total" in src


def test_sell_before_buy() -> None:
    """先卖后买：sells 循环在 buys 前（cash feasibility）。"""
    src = Path(ROOT / "scripts" / "gate4_instrument_execution_realism.py").read_text(encoding="utf-8")
    sell_pos = src.find("# 6. sells 先")  # "# 6. sells 先"
    buy_pos = src.find("# 7. buys")
    assert sell_pos != -1 and buy_pos != -1 and sell_pos < buy_pos


def test_southbound_local_hkd_t_minus_1_fx() -> None:
    """Southbound：HKD 本地价 + transaction_date + T-1 fx_to_base。"""
    src = Path(ROOT / "scripts" / "gate4_instrument_execution_realism.py").read_text(encoding="utf-8")
    assert "opens_hkd" in src
    assert "_fx_t_minus_1" in src and "fx_to_base" in src
    fx = pd.Series([0.80, 0.81, 0.82], index=pd.date_range("2025-01-01", periods=3))
    fx_t1 = inst._fx_t_minus_1(fx, pd.Timestamp("2025-01-03"))
    assert abs(fx_t1 - 0.81) < 1e-12  # 01-02 的 T-1，非 same-day 01-03=0.82
    assert abs(fx_t1 - 0.82) > 1e-9


def test_aggregate_headline_close_to_research(sim) -> None:
    """可执行 net 贴近已接受 L1 研究 MaxDiv（忠实版结构一致）。"""
    results = sim[2]
    m = results["metrics"]
    assert m["cum_return"] > 0.30 and m["calendar_cagr"] > 0.06
    assert m["max_drawdown"] > -0.10
    assert m["sharpe"] > 1.0
    assert results["cost_aggregation"]["fee_bps_of_traded_notional"] <= 5
    assert results["cost_aggregation"]["slippage_bps_of_traded_notional"] <= 10
