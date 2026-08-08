"""MockBroker（EXECUTION_SPEC §50）：只读/模拟执行，不允许真实 QMT 下单。"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ...accounting import PortfolioAccounting
from ...contracts import (
    REASON_MARKET_CLOSED,
    REASON_QUOTE_UNAVAILABLE,
    CostBreakdown,
    Fill,
    Order,
)
from ..premium import PremiumGuard
from ..tradability import TradabilityMask


@dataclass
class Quote:
    instrument: str
    price: float
    timestamp: pd.Timestamp


class OrderRejected(Exception):
    def __init__(self, instrument: str, reason: str) -> None:
        self.instrument = instrument
        self.reason = reason
        super().__init__(f"{instrument}: {reason}")


class MockBroker:
    """确定性模拟成交：price= 执行日参考价（open）+ 成本模型（spread/slippage）。
    不连接 QMT；研究核心禁止 import xtquant（EXECUTION_SPEC §50）。"""

    def __init__(
        self,
        *,
        tradability: TradabilityMask,
        premium_guard: PremiumGuard,
        cost_model: object,
        open_prices: dict[str, pd.Series],  # instrument -> Series(open price by date)
        fx_rate: float = 1.0,  # 简化：Gate 2 单币种；FX skeleton 单独测试
        minimum_quote_lot: int = 100,
    ) -> None:
        self.tradability = tradability
        self.premium_guard = premium_guard
        self.cost_model = cost_model
        self.open_prices = open_prices
        self.fx_rate = fx_rate
        self.minimum_quote_lot = minimum_quote_lot
        self.premium_enforced: bool = False
        self.orders: list[Order] = []
        self.fills: list[Fill] = []
        self.rejects: list[tuple[Order, str]] = []
        self._seq = 0

    def execute_plan(
        self,
        orders: list[Order],
        *,
        execution_date: pd.Timestamp,
        accounting: PortfolioAccounting,
    ) -> list[Fill]:
        fills: list[Fill] = []
        # 先卖后买（EXECUTION_SPEC §51）
        for order in sorted(orders, key=lambda o: 0 if o.side == "sell" else 1):
            fill = self._fill(order, execution_date)
            if fill is None:
                continue
            accounting.apply_fill(fill, fx_to_base=self.fx_rate)
            self.fills.append(fill)
            fills.append(fill)
        return fills

    def _fill(self, order: Order, execution_date: pd.Timestamp) -> Fill | None:
        px = self.open_prices.get(order.instrument)
        if px is None:
            raise OrderRejected(order.instrument, "no_price_series")
        valid = px[px.index <= execution_date]
        if valid.empty:
            raise OrderRejected(order.instrument, REASON_MARKET_CLOSED)
        price = float(valid.iloc[-1])
        if price is None or price <= 0 or not np.isfinite(price):
            raise OrderRejected(order.instrument, REASON_QUOTE_UNAVAILABLE)
        td = self.tradability.get(order.instrument, execution_date)
        if order.side == "buy" and not td.buy_allowed:
            self.rejects.append((order, "|".join(td.reason_codes)))
            return None
        if order.side == "sell" and not td.sell_allowed:
            self.rejects.append((order, "|".join(td.reason_codes)))
            return None
        if order.side == "buy" and self.premium_enforced:
            pd = self.premium_guard.evaluate(
                order.instrument, execution_date, market_price=price,
                iopv=None, iopv_ts=None,
            )
            if not pd.buy_allowed:
                self.rejects.append((order, f"premium:{pd.reason}"))
                return None
        cost = self.cost_model.estimate(order.instrument, order.side, order.quantity, price)
        self._seq += 1
        return Fill(
            order_id=f"mock-{self._seq}",
            instrument=order.instrument,
            side=order.side,
            quantity=order.quantity,
            price=price,
            cost=cost,
            timestamp=execution_date,
        )
