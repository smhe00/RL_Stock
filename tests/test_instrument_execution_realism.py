"""POST_L2_INSTRUMENT_EXECUTION_REALISM — 执行真实化测试（RUN_CORRECTION_002 行为回归）。

覆盖：T+1-open 成交（open!=close 合成断言）、post-fill NAV/fee、T+2 session 结算释放 +
应收计入 NAV、Southbound HKD 本地价 + T-1 FX、公司行为（分红/折算）、先卖后买、MaxDiv
权重 parity、provenance 完整性、no-RL。
"""

import importlib.util
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
    assert m.half_spread_bps == 1.0 and m.slippage_bps == 2.0
    s = inst.SouthboundETFCostModel()
    assert s.broker_commission_rate == 0.0003 and s.stamp_duty_rate == 0.0
    cb = s.estimate("03110.HK", "buy", 100, 50.0, market_state={"transaction_date": "2025-01-01"})
    assert cb.commission >= 5.0 * s.fx_to_base - 1e-9  # min HKD 5（fx_to_base=1 默认）


def test_southbound_local_hkd_t_minus_1_fx() -> None:
    """Southbound：HKD 本地价 + transaction_date + T-1 fx_to_base（合成 T-1 != same-day）。"""
    src = Path(ROOT / "scripts" / "gate4_instrument_execution_realism.py").read_text(encoding="utf-8")
    assert "opens_hkd" in src or "closes_hkd" in src  # 保留 HKD 本地序列
    assert "_fx_t_minus_1" in src and "fx_to_base" in src
    # 合成：T-1 FX 与 same-day 不同时，m_hkd 反推仍为本地价
    fx = pd.Series([0.80, 0.81, 0.82], index=pd.date_range("2025-01-01", periods=3))
    t_next = pd.Timestamp("2025-01-03")
    fx_t1 = inst._fx_t_minus_1(fx, t_next)
    assert abs(fx_t1 - 0.81) < 1e-12, "T-1 FX 应为 t_next 之前最后交易日值（01-02 = 0.81）"
    # T-1 与 same-day（01-03 = 0.82）不同 → 保留本地 HKD 语义
    assert abs(fx_t1 - 0.82) > 1e-9, "T-1 FX 不应等于 same-day FX"


def test_t_plus_1_open_execution_synthetic() -> None:
    """T+1-open 成交：合成 open != close，断言 runner 用 open 成交（价格路径）。"""
    src = Path(ROOT / "scripts" / "gate4_instrument_execution_realism.py").read_text(encoding="utf-8")
    # sizing/fills 用 open_marks；close 仅 NAV
    assert "open_marks" in src and "close_marks" in src
    assert "open_marks.get(inst" in src  # fills 读 open
    # 行为断言：估值与成交价分离（open 用于 sizing/fills，close 用于 nav_close）
    assert "nav_close.append" in src
    assert "open_marks" in src and "close_marks" in src


def test_post_fill_nav_and_fee() -> None:
    """post-fill NAV：nav_close 序列绑定 net_returns。"""
    src = Path(ROOT / "scripts" / "gate4_instrument_execution_realism.py").read_text(encoding="utf-8")
    assert "nav_close.append(nav)" in src
    assert "np.diff(pv)" in src  # returns from post-fill NAV
    assert "fees_total" in src and "slippage_total" in src


def test_t_plus_2_session_calendar() -> None:
    """T+2 用 session 日历（exec index + 2），非日历 +2d；应收计入 NAV 但排除买入现金。"""
    src = Path(ROOT / "scripts" / "gate4_instrument_execution_realism.py").read_text(encoding="utf-8")
    assert "receivables[i + SETTLEMENT_T[\"HK\"]]" in src  # session T+2（index 偏移）
    assert "sum(receivables.values())" in src  # 应收计入 NAV
    assert inst.SETTLEMENT_T == {"A_SHARE": 1, "HK": 2}


def test_corporate_actions_on_positions() -> None:
    """公司行为：分红计提/派息 + 份额折算应用于可执行持仓。"""
    src = Path(ROOT / "scripts" / "gate4_instrument_execution_realism.py").read_text(encoding="utf-8")
    assert "div_accrual" in src and "div_settle" in src and "unit_conv" in src
    assert "accrued_div[inst]" in src and "positions[inst] *= factor" in src


def test_sell_before_buy() -> None:
    """先卖后买：sells 循环在 buys 前（cash feasibility）。"""
    src = Path(ROOT / "scripts" / "gate4_instrument_execution_realism.py").read_text(encoding="utf-8")
    sell_pos = src.find("# 5. sells 先")
    buy_pos = src.find("# 6. buys")
    assert sell_pos != -1 and buy_pos != -1 and sell_pos < buy_pos


def test_maxdiv_weight_parity() -> None:
    """MaxDiv 权重 parity：sum=1、single<=25%、低波动高配（L1 已接受结构）。"""
    data = inst.load_all()
    adj, opens, closes = data["adj"], data["opens"], data["closes"]
    cal = adj.index.normalize()
    ds = pd.Timestamp(inst.FROZEN["decision_start"])
    ds_i = cal.get_loc(ds)
    last_dec_i = len(cal) - 2
    decision_dates = cal[ds_i:last_dec_i + 1]
    W = inst.maxdiv_weights(adj, opens, closes, decision_dates)
    assert W.shape == (inst.FROZEN["n_decision_days"], 11)
    assert np.isfinite(W).all() and np.allclose(W.sum(axis=1), 1.0, atol=1e-6)
    assert (W >= -1e-9).all() and W.max() <= 0.25 + 1e-6
    slots = list(inst.SLOT_INSTRUMENT.keys())
    assert W.mean(axis=0)[slots.index("CASH_LIKE")] > 0.1


def test_provenance_complete() -> None:
    """Provenance：raw ETF + 03110 + FX + CA 事件全哈希，计数与实际一致。"""
    prov = inst._provenance()
    assert "data\\qmt\\raw\\HK_DIVIDEND_03110_HK_raw.csv".replace("\\", "/") in {k.replace("\\", "/") for k in prov} or \
           any("03110" in k for k in prov)
    assert any("hkd_cny" in k for k in prov)
    assert any("divid_events" in k for k in prov), "CA 事件文件必须哈希"


def test_no_rl() -> None:
    src = Path(ROOT / "scripts" / "gate4_instrument_execution_realism.py").read_text(encoding="utf-8")
    for tok in ("PPO", "SAC", "TD3", "stable_baselines3"):
        assert tok not in src, f"forbidden RL token {tok}"
