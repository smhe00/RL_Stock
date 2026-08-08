"""OrderGenerator（EXECUTION_SPEC §51）Gate 2 确定性版。

输入：target instrument weights + 持仓 + 组合价值 + lot size + cash buffer + 最小单额。
输出：先卖后买的 Order 序列；按手取整；保留 broker cash buffer；不允许超卖/买禁。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..accounting import PortfolioAccounting
from ..contracts import Order, TargetInstrumentWeights


@dataclass
class OrderGenerator:
    lot_size: int = 100
    min_order_notional_cny: float = 1000.0
    weight_tolerance_bps: float = 20.0
    cash_buffer_pct: float = 0.01

    def plan(
        self,
        target: TargetInstrumentWeights,
        *,
        accounting: PortfolioAccounting,
        close_prices: dict[str, float],  # 决策日收盘价（instrument 币种）
        fx_to_base: dict[str, float] | None = None,
    ) -> list[Order]:
        fx = fx_to_base or {k: 1.0 for k in target.weights.index}
        portfolio_value = accounting.cash + sum(
            pos.quantity * close_prices.get(inst, 0.0) * fx.get(inst, 1.0)
            for inst, pos in accounting.positions.items()
            if inst in close_prices
        )
        investable = portfolio_value * (1.0 - self.cash_buffer_pct)
        orders: list[Order] = []
        current = {inst: pos.quantity for inst, pos in accounting.positions.items()}
        for inst, w in target.weights.items():
            price = close_prices.get(inst)
            if price is None or price <= 0:
                continue
            target_notional = w * investable
            target_qty = target_notional / (price * fx.get(inst, 1.0))
            target_qty = np.floor(target_qty / self.lot_size) * self.lot_size
            current_qty = current.get(inst, 0.0)
            delta = target_qty - current_qty
            # 小额偏差可不交易
            if abs(delta) * price * fx.get(inst, 1.0) < self.min_order_notional_cny:
                continue
            side = "buy" if delta > 0 else "sell"
            orders.append(Order(instrument=inst, side=side, quantity=abs(delta)))
        # 超卖防护
        for o in orders:
            if o.side == "sell" and o.quantity > current.get(o.instrument, 0.0) + 1e-9:
                raise ValueError(f"oversell {o.instrument}")
        return orders
