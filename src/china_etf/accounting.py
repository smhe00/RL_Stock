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
    dividend_receivable: float = 0.0  # 已计提未派发的现金分红（base currency）


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
        self.dividend_receivable: dict[str, float] = {}  # instrument -> 应收现金（base currency）
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

    # --- corporate actions（GATE_4_PILOT_READY CA1，双价 contract 执行侧）---
    def accrue_dividend(
        self,
        instrument: str,
        quantity: float,
        cash_per_share: float,
        *,
        fx_to_base: float = 1.0,
    ) -> None:
        """除息日计提现金分红应收款（基于除息日开盘前持仓）。

        价值中性：raw 价格机械性下跌被应收款抵消，portfolio equity 不受人为损失。
        """
        if quantity <= 0 or cash_per_share <= 0:
            return
        self.dividend_receivable[instrument] = self.dividend_receivable.get(instrument, 0.0) + (
            quantity * cash_per_share * fx_to_base
        )

    def settle_dividend(self, instrument: str, *, fx_to_base: float = 1.0) -> float:
        """派息日：应收款 → 现金（价值中性，equity 不跳变）。返回结算金额。"""
        amount = self.dividend_receivable.pop(instrument, 0.0)
        if amount > 0:
            self.cash += amount
        return amount

    @property
    def receivable_total(self) -> float:
        return float(sum(self.dividend_receivable.values()))

    def apply_unit_conversion(self, instrument: str, factor: float) -> None:
        """送股/折算生效日：持仓数量 ×= factor，avg_cost /= factor，总成本不变（价值中性）。

        factor = 1 + stockBonus + stockGift（如 1:0.36555 折算 → 0.36555；1:1 送股 → 2.0）。
        """
        if factor <= 0 or not np.isfinite(factor) or abs(factor - 1.0) < 1e-12:
            return
        pos = self.positions.get(instrument)
        if pos is None or pos.quantity <= 1e-12:
            return
        pos.quantity *= factor
        pos.avg_cost /= factor

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
        recv = self.receivable_total
        return Snapshot(
            timestamp=timestamp,
            cash=self.cash,
            market_value=mv,
            fees_paid=self.fees_paid,
            realized_pnl=self.realized_pnl,
            portfolio_value=self.cash + mv + recv,
            positions={k: v.quantity for k, v in self.positions.items()},
            dividend_receivable=recv,
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
