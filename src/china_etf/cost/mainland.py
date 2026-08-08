"""MainlandETFCostModel（EXECUTION_SPEC §20/§23）。

Gate 2 为骨架：配置化费率 + 简单 spread/slippage；market impact 默认 0。
费率默认值来自 config/fees/mainland_etf.yaml（pending verification）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..contracts import CostBreakdown


@dataclass
class MainlandETFCostModel:
    broker_commission_rate: float = 0.00005  # 单边万0.5
    broker_min_commission_cash: float | None = None  # 未确认前不得假设为 0
    # Reviewer §6：上交所基金经手费 0.004% 属于会员交交易所的费用；
    # 券商 0.00005 是否已含未确认 → 不得自动叠加（防 double count），Gate 4 前冻结。
    broker_commission_includes_exchange_fee: str = "UNKNOWN_PENDING_BROKER_FEE_AUDIT"
    exchange_fee_rate: float = 0.0  # 待核实
    stamp_duty_rate: float = 0.0  # ETF 免印花税（待核实）
    half_spread_bps: float = 1.0  # 单边半价差（bps）
    slippage_bps: float = 2.0  # 单边滑点（bps）
    impact_bps: float = 0.0  # Gate 2 不校准 market impact
    effective_from: str = "2026-08-08"
    source: str = (
        "user broker commission 万0.5 constant assumption (NOT ACCOUNT-VERIFIED for "
        "historical period) + config/fees/mainland_etf.yaml"
    )

    def estimate(
        self,
        instrument: str,
        side: str,
        quantity: float,
        reference_price: float,
        market_state: dict | None = None,
    ) -> CostBreakdown:
        if quantity <= 0 or reference_price <= 0:
            raise ValueError("quantity and reference_price must be positive")
        notional = quantity * reference_price
        commission = notional * self.broker_commission_rate
        if self.broker_min_commission_cash is not None:
            commission = max(commission, self.broker_min_commission_cash)
        exchange_fee = notional * self.exchange_fee_rate
        tax = notional * self.stamp_duty_rate
        spread = notional * self.half_spread_bps / 10_000
        slippage = notional * self.slippage_bps / 10_000
        impact = notional * self.impact_bps / 10_000
        return CostBreakdown(
            commission=commission,
            exchange_fee=exchange_fee,
            tax=tax,
            spread=spread,
            slippage=slippage,
            impact=impact,
            fx_cost=0.0,
        )
