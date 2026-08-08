"""EXECUTION_SPEC §51 — lot rounding / cash buffer / sells-first / oversell guard。"""

import pandas as pd

from china_etf.accounting import PortfolioAccounting
from china_etf.contracts import CostBreakdown, Fill, TargetInstrumentWeights
from china_etf.execution.order_generator import OrderGenerator


def test_lot_rounding_and_cash_buffer() -> None:
    acct = PortfolioAccounting(initial_cash=1_000_000.0)
    target = TargetInstrumentWeights(
        decision_time=pd.Timestamp("2026-01-02"),
        weights=pd.Series({"A": 1.0}),
    )
    orders = OrderGenerator().plan(
        target, accounting=acct, close_prices={"A": 10.0}
    )
    assert len(orders) == 1 and orders[0].side == "buy"
    # investable = 1,000,000 * 0.99 = 990,000 → 99,000 股（整手）
    assert orders[0].quantity == 99_000
    assert orders[0].quantity % 100 == 0


def test_sell_orders_first_and_oversell_guard() -> None:
    acct = PortfolioAccounting(initial_cash=1_000_000.0)
    acct.apply_fill(
        Fill(
            order_id="x", instrument="A", side="buy", quantity=50_000,
            price=10.0, cost=CostBreakdown(),
            timestamp=pd.Timestamp("2026-01-01"),
        ),
        fx_to_base=1.0,
    )
    target = TargetInstrumentWeights(
        decision_time=pd.Timestamp("2026-01-02"),
        weights=pd.Series({"A": 0.0}),
    )
    orders = OrderGenerator().plan(target, accounting=acct, close_prices={"A": 10.0})
    assert orders and all(o.side == "sell" for o in orders)
    assert orders[0].quantity == 50_000  # 全卖（不超卖）
