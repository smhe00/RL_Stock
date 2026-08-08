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
    """GATE_4_PRECHECK F2 保守场景（默认 tx_date=None → 最新费率）。

    notional=300,000 HKD；佣金 万3=90（> 最低 5 HKD）；
    交易费 16.95 + SFC 8.10 + AFRC 0.45 + 股份交收费 12.6（2025-06-30 后无上下限）= 38.10；
    印花税 0；spread 30 + slippage 60 → total 218.10。
    """
    s = SouthboundETFCostModel()
    c = s.estimate("03110.HK", "buy", 10_000, 30.0)  # notional 300,000 HKD
    assert c.commission == pytest.approx(300_000 * 0.0003)
    assert c.exchange_fee == pytest.approx(
        300_000 * (0.0000565 + 0.000027 + 0.0000015 + 0.000042)
    )
    # 港股通 ETF 印花税暂免（Reviewer 核实）
    assert c.tax == 0.0
    assert c.total > c.commission + c.tax
    assert c.total == pytest.approx(218.10)


def test_southbound_historical_rate_pit() -> None:
    """GATE_4_PRECHECK F1：历史日期必须按分段费率计，生效日前不得错误用新费率。

    2022-06-01：交易费 0.005%（15.0）+ SFC 0.0027%（8.10）+ AFRC 0.00015%（0.45，2022-01-01 后）
      + 股份交收费 0.002%（6.0，min/max 钳制内）= 29.55；
    2021-06-01（AFRC 生效前）：交易费 15.0 + SFC 8.10 + AFRC 0 + 结算 6.0 = 29.10。
    """
    s = SouthboundETFCostModel()
    c22 = s.estimate("03110.HK", "buy", 10_000, 30.0, {"transaction_date": "2022-06-01"})
    assert c22.exchange_fee == pytest.approx(15.0 + 8.10 + 0.45 + 6.0)
    c21 = s.estimate("03110.HK", "buy", 10_000, 30.0, {"transaction_date": "2021-06-01"})
    assert c21.exchange_fee == pytest.approx(15.0 + 8.10 + 0.0 + 6.0)
    # 2023 交易费升档
    c23 = s.estimate("03110.HK", "buy", 10_000, 30.0, {"transaction_date": "2023-06-01"})
    assert c23.exchange_fee == pytest.approx(16.95 + 8.10 + 0.45 + 6.0)


def test_southbound_settlement_clamp_transition() -> None:
    """GATE_4_PRECHECK F1：股份交收费 2025-06-30 前 min2/max100 钳制，之后无上下限。"""
    s = SouthboundETFCostModel()
    # 旧制（2025-06-30 前）：notional 50,000 × 0.002% = 1.0 → 被 min 2.0 抬高
    # （2024-06-01 时交易费已是 0.00565%——2023-01-01 升档后）
    c_old = s.estimate("03110.HK", "buy", 1_000, 50.0, {"transaction_date": "2024-06-01"})
    s_old = c_old.exchange_fee - 1_000 * 50.0 * (0.0000565 + 0.000027 + 0.0000015)
    assert s_old == pytest.approx(2.0)  # min 钳制
    # 新制（2025-06-30 后）：notional 50,000 × 0.0042% = 2.1，无 min 抬高
    c_new = s.estimate("03110.HK", "buy", 1_000, 50.0, {"transaction_date": "2026-06-01"})
    s_new = c_new.exchange_fee - 1_000 * 50.0 * (0.0000565 + 0.000027 + 0.0000015)
    assert s_new == pytest.approx(2.1)
    assert s_new != pytest.approx(2.0)


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
