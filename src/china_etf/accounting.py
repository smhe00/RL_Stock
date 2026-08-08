"""Gate 2 — Portfolio Accounting（EXECUTION_SPEC §28）。

账本状态：cash（base currency）、positions（instrument 数量）、累计 fees / realized PnL。
identity：V_{t+1} = V_t + MarketPnL + FXPnL - Fees（无外部现金流）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .contracts import CostBreakdown, Fill


@dataclass
class Position:
    instrument: str
    currency: str = "CNY"
    quantity: float = 0.0
    avg_cost: float = 0.0  # instrument 币种，含已付费用的摊薄


@dataclass
class Snapshot:
    timestamp: pd.Timestamp
    cash: float
    market_value: float
    fees_paid: float
    realized_pnl: float
    portfolio_value: float
    positions: dict[str, float]


class PortfolioAccounting:
    """单币种账本（base currency）；FX 转换由外部提供。"""

    def __init__(self, initial_cash: float, base_currency: str = "CNY") -> None:
        if initial_cash < 0:
            raise ValueError("initial_cash must be >= 0")
        self.base_currency = base_currency
        self.cash = float(initial_cash)
        self.positions: dict[str, Position] = {}
        self.fees_paid = 0.0
        self.realized_pnl = 0.0
        self._order_seq = 0

    # --- fills ---
    def apply_fill(
        self,
        fill: Fill,
        *,
        fx_to_base: float,
    ) -> None:
        """按 fill 更新账本。fill.price 为 instrument 币种成交价；fx_to_base 转换到 base。
        成本 CostBreakdown 已按 base 币种计价（由 CostModel 折算）。"""
        if fill.quantity <= 0:
            raise ValueError("fill quantity must be positive")
        if not np.isfinite(fill.price) or fill.price <= 0:
            raise ValueError("fill price must be positive and finite")
        if not np.isfinite(fx_to_base) or fx_to_base <= 0:
            raise ValueError("fx_to_base must be positive and finite")
        notional_base = fill.quantity * fill.price * fx_to_base
        fee_base = float(fill.cost.total)
        pos = self.positions.setdefault(fill.instrument, Position(fill.instrument))
        if fill.side == "buy":
            total_cost = pos.avg_cost * pos.quantity + notional_base + fee_base
            pos.quantity += fill.quantity
            pos.avg_cost = total_cost / pos.quantity
            self.cash -= notional_base + fee_base
        elif fill.side == "sell":
            if fill.quantity > pos.quantity + 1e-9:
                raise ValueError(f"oversell {fill.instrument}: {fill.quantity} > {pos.quantity}")
            realized = (fill.price - pos.avg_cost) * fill.quantity * fx_to_base
            pos.quantity -= fill.quantity
            self.cash += notional_base - fee_base
            self.realized_pnl += realized
        else:
            raise ValueError(f"unknown side: {fill.side}")
        self.fees_paid += fee_base
        if pos.quantity <= 1e-12:
            del self.positions[fill.instrument]

    # --- marking ---
    def market_value(
        self,
        prices: dict[str, float],
        fx_to_base: dict[str, float],
    ) -> float:
        """按给定价格（instrument 币种）与汇率 mark 持仓。"""
        total = 0.0
        for inst, pos in self.positions.items():
            p = prices.get(inst)
            fx = fx_to_base.get(inst, 1.0)
            if p is None or not np.isfinite(p):
                raise ValueError(f"marking price missing for {inst}")
            total += pos.quantity * p * fx
        return float(total)

    def snapshot(
        self,
        timestamp: pd.Timestamp,
        prices: dict[str, float],
        fx_to_base: dict[str, float],
    ) -> Snapshot:
        mv = self.market_value(prices, fx_to_base)
        return Snapshot(
            timestamp=timestamp,
            cash=self.cash,
            market_value=mv,
            fees_paid=self.fees_paid,
            realized_pnl=self.realized_pnl,
            portfolio_value=self.cash + mv,
            positions={k: v.quantity for k, v in self.positions.items()},
        )

    def verify_identity(
        self,
        v_prev: float,
        v_curr: float,
        *,
        market_pnl: float,
        fx_pnl: float,
        fees: float,
        tol: float = 1e-8,
    ) -> bool:
        """V_curr == V_prev + market_pnl + fx_pnl - fees（无外部现金流）。"""
        return abs(v_curr - (v_prev + market_pnl + fx_pnl - fees)) <= tol * max(1.0, abs(v_curr))
