"""EXECUTION_SPEC §28/§54.4 — 手算会计案例 + identity。"""

import pandas as pd

from china_etf.accounting import PortfolioAccounting
from china_etf.cost.mainland import MainlandETFCostModel
from china_etf.contracts import CostBreakdown, Fill


def _fill(order_id, inst, side, qty, price, cost) -> Fill:
    return Fill(
        order_id=order_id,
        instrument=inst,
        side=side,
        quantity=qty,
        price=price,
        cost=cost,
        timestamp=pd.Timestamp("2026-01-05"),
    )


def test_hand_calculated_accounting_identity() -> None:
    """手算案例：期初现金 1,000,000；买入 99,000 股 A @10（当日开盘），成本 346.5；收盘 10.5。
    V1 = 1,000,000 + 49,500(价差) - 346.5(费用) = 1,049,153.5。"""
    cost_model = MainlandETFCostModel()
    acct = PortfolioAccounting(initial_cash=1_000_000.0)
    v0 = acct.snapshot(pd.Timestamp("2026-01-02"), {}, {}).portfolio_value
    assert v0 == 1_000_000.0

    qty = 99_000
    price = 10.0
    cost = cost_model.estimate("A", "buy", qty, price)
    # 佣金 49.5 + 价差 99.0 + 滑点 198.0
    assert cost.commission == 990_000 * 0.00005
    assert cost.spread == 990_000 * 0.0001
    assert cost.slippage == 990_000 * 0.0002
    assert cost.total == 346.5

    acct.apply_fill(_fill("f1", "A", "buy", qty, price, cost), fx_to_base=1.0)
    snap = acct.snapshot(pd.Timestamp("2026-01-05"), {"A": 10.5}, {"A": 1.0})
    assert snap.cash == 1_000_000 - 990_000 - 346.5
    assert snap.portfolio_value == 9_653.5 + 99_000 * 10.5
    assert acct.verify_identity(
        v0,
        snap.portfolio_value,
        market_pnl=99_000 * 0.5,
        fx_pnl=0.0,
        fees=346.5,
    )


def test_sell_realized_pnl_and_oversell_guard() -> None:
    acct = PortfolioAccounting(initial_cash=100_000.0)
    acct.apply_fill(
        _fill("b1", "A", "buy", 1_000, 10.0, CostBreakdown(commission=0.0)),
        fx_to_base=1.0,
    )
    acct.apply_fill(
        _fill("s1", "A", "sell", 400, 12.0, CostBreakdown(commission=0.0)),
        fx_to_base=1.0,
    )
    assert acct.positions["A"].quantity == 600
    assert acct.realized_pnl == (12.0 - 10.0) * 400
    assert acct.cash == 100_000 - 10_000 + 4_800
    try:
        acct.apply_fill(
            _fill("s2", "A", "sell", 999_999, 12.0, CostBreakdown(commission=0.0)),
            fx_to_base=1.0,
        )
        raise AssertionError("oversell must raise")
    except ValueError:
        pass
