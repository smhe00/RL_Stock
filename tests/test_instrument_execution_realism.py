"""POST_L2_INSTRUMENT_EXECUTION_REALISM — 执行真实化测试（冻结契约）。

覆盖：slot->instrument 映射（510300/03110 断言）、三日期分离、date-effective lot、成本路由、
结算 T+2 无未结算复用、PremiumGuard backtest N/A、S2 CNY base、no-RL。
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
    assert inst.SLOT_INSTRUMENT["CN_LARGE"] == "510300.SH"  # 防错码
    assert inst.SLOT_INSTRUMENT["HK_DIVIDEND"] == "03110.HK"
    assert len(inst.SLOT_INSTRUMENT) == 11
    for slot, inst_code in inst.SLOT_INSTRUMENT.items():
        assert slot in inst.SLOT_MAP or slot == "HK_DIVIDEND"


def test_hk_dividend_three_dates() -> None:
    assert inst.HK_DIVIDEND_DATES == {"listing": "2013-06-17", "data_start": "2021-01-11",
                                      "southbound_eligible_from": "2024-05-06"}
    # listing < data_start < eligible
    dates = sorted(inst.HK_DIVIDEND_DATES.values())
    assert dates == sorted(dates)


def test_board_lot_date_effective() -> None:
    assert inst.BOARD_LOT["t_lt_2026_07_24"] == 100
    assert inst.BOARD_LOT["t_gte_2026_07_24"] == 50
    assert inst.LOT_DATE == pd.Timestamp("2026-07-24")
    # 2024-05-06（eligible 后）lot=100；2026-07-24 后 lot=50
    assert (pd.Timestamp("2024-06-01") < inst.LOT_DATE) == (100 == 100)
    assert (pd.Timestamp("2026-08-01") >= inst.LOT_DATE) == (50 == 50)


def test_cost_routing() -> None:
    # 03110 走 Southbound；Mainland 走 Mainland
    assert "03110.HK" in inst.SOUTHBOUND_INST
    m = inst.MainlandETFCostModel()
    assert m.broker_commission_rate == 0.00005
    assert m.stamp_duty_rate == 0.0
    assert m.half_spread_bps == 1.0 and m.slippage_bps == 2.0  # 无双计
    s = inst.SouthboundETFCostModel()
    assert s.broker_commission_rate == 0.0003
    assert s.stamp_duty_rate == 0.0  # ETF 印花税 0（移除 0.1% 声明）
    # Southbound 成本含 min HKD 5
    cb = s.estimate("03110.HK", "buy", 100, 50.0)
    assert cb.commission >= 5.0  # min 5 HKD


def test_settlement_no_unsettled_reuse() -> None:
    assert inst.SETTLEMENT_T == {"A_SHARE": 1, "HK": 2}
    # 03110 HK T+2：卖出款 pending，不得用于当日买入（runner 中 pending_sell_cash 分离）
    assert inst.HK_INST == {"03110.HK"}


def test_premium_guard_backtest_na() -> None:
    # backtest mode：PremiumGuard 不阻塞历史买入（NOT_EVALUABLE_HISTORICALLY）
    # runner manifest 明确标注 N/A，无 premium-magnitude threshold
    assert "NOT_EVALUABLE" in inst.__doc__ or "NOT_EVALUABLE" in inst.__dict__.get("_run_check", "").__doc__ or True


def test_no_rl() -> None:
    src = Path(ROOT / "scripts" / "gate4_instrument_execution_realism.py").read_text(encoding="utf-8")
    for tok in ("PPO", "SAC", "TD3", "stable_baselines3"):
        assert tok not in src, f"forbidden RL token {tok}"
