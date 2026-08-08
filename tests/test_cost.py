"""EXECUTION_SPEC §54.3 — cost tests。"""

import pytest

from china_etf.cost.mainland import MainlandETFCostModel
from china_etf.cost.southbound import SouthboundETFCostModel


def test_mainland_cost_structure_and_stress() -> None:
    m = MainlandETFCostModel()
    c = m.estimate("510300.SH", "buy", 100_000, 4.0)
    assert c.total > 0
    assert c.tax == 0.0  # ETF 免印花税（待核实）
    assert c.commission > 0
    # 2x stress（Reviewer §45）：费率 ×2 可预测
    m2 = MainlandETFCostModel(
        broker_commission_rate=0.00010,
        half_spread_bps=2.0,
        slippage_bps=4.0,
    )
    c2 = m2.estimate("510300.SH", "buy", 100_000, 4.0)
    assert c2.commission == 2 * c.commission
    assert c2.spread == 2 * c.spread
    assert c2.slippage == 2 * c.slippage


def test_mainland_cost_monotonic_in_quantity() -> None:
    m = MainlandETFCostModel()
    c_small = m.estimate("A", "buy", 1_000, 10.0).total
    c_large = m.estimate("A", "buy", 100_000, 10.0).total
    assert c_large > c_small


def test_southbound_cost_components() -> None:
    s = SouthboundETFCostModel()
    c = s.estimate("03110.HK", "buy", 10_000, 30.0)  # notional 300,000 HKD
    assert c.commission == pytest.approx(300_000 * 0.00005)
    # 交易所费 0.00565% + SFC 征费 0.0027% + AFRC 0.00015% + 股份交收费(6.0，在 min/max 内)
    assert c.exchange_fee == pytest.approx(
        300_000 * (0.0000565 + 0.000027 + 0.0000015) + 6.0
    )
    # 港股通 ETF 印花税暂免（Reviewer 核实）
    assert c.tax == 0.0
    assert c.total > c.commission + c.tax
    # Reviewer 示例：total = 16.95 + 8.10 + 0.45 + 6.00 + 15.00 + 30.00 + 60.00 = 136.50
    assert c.total == pytest.approx(136.50)


def test_southbound_cost_converts_to_base() -> None:
    s = SouthboundETFCostModel(fx_to_base=0.9)
    c_hkd = SouthboundETFCostModel(fx_to_base=1.0).estimate("03110.HK", "buy", 10_000, 30.0)
    c_cny = s.estimate("03110.HK", "buy", 10_000, 30.0)
    assert c_cny.total == pytest.approx(c_hkd.total * 0.9)


def test_cost_input_validation() -> None:
    m = MainlandETFCostModel()
    with pytest.raises(ValueError):
        m.estimate("A", "buy", 0, 10.0)
    with pytest.raises(ValueError):
        m.estimate("A", "buy", 100, 0.0)
