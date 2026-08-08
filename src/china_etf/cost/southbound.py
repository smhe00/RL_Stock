"""SouthboundETFCostModel（EXECUTION_SPEC §24）骨架。

费率默认值来自 config/fees/southbound_etf.yaml（pending verification，
以港交所/结算所与券商实际结算为准）。

2026-08 官方口径（Reviewer 核实）：
  Trading Fee 0.00565%；SFC Trading Levy 0.0027%；AFRC Transaction Levy 0.00015%；
  港股通 ETF 印花税暂免（stamp=0）；投资者赔偿/特别征费暂不征收。
"""

from __future__ import annotations

from dataclasses import dataclass

from ..contracts import CostBreakdown


@dataclass
class SouthboundETFCostModel:
    broker_commission_rate: float = 0.00005
    hkex_trading_fee_rate: float = 0.0000565  # 0.00565%
    regulatory_levy_rate: float = 0.000027  # 0.0027%
    afrc_levy_rate: float = 0.0000015  # AFRC Transaction Levy 0.00015%
    stamp_duty_rate: float = 0.0  # 港股通 ETF 印花税暂免（Reviewer 核实）
    settlement_fee_rate: float = 0.00002
    settlement_fee_min_hkd: float = 2.0
    settlement_fee_max_hkd: float = 100.0
    fx_cost_bps: float = 0.0  # 换汇成本待核实
    half_spread_bps: float = 1.0
    slippage_bps: float = 2.0
    fx_to_base: float = 1.0  # CostBreakdown 一律为 base 币种（D-017）：HKD 计算后折算
    effective_from: str = "2026-08-08"
    source: str = "SSE 港股通税费说明 2026-08 + config/fees/southbound_etf.yaml (pending broker verification)"

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
        notional = quantity * reference_price  # HKD
        commission = notional * self.broker_commission_rate
        exchange_fee = notional * self.hkex_trading_fee_rate
        levy = notional * self.regulatory_levy_rate
        afrc = notional * self.afrc_levy_rate
        stamp = notional * self.stamp_duty_rate
        settlement = notional * self.settlement_fee_rate
        settlement = min(max(settlement, self.settlement_fee_min_hkd), self.settlement_fee_max_hkd)
        spread = notional * self.half_spread_bps / 10_000
        slippage = notional * self.slippage_bps / 10_000
        fx_cost = notional * self.fx_cost_bps / 10_000
        c = CostBreakdown(
            commission=commission,
            exchange_fee=exchange_fee + levy + afrc + settlement,
            tax=stamp,
            spread=spread,
            slippage=slippage,
            impact=0.0,
            fx_cost=fx_cost,
        )
        # 折算到 base 币种（D-017：CostBreakdown 全部字段 = base 币种）
        fx = self.fx_to_base
        return CostBreakdown(
            commission=c.commission * fx,
            exchange_fee=c.exchange_fee * fx,
            tax=c.tax * fx,
            spread=c.spread * fx,
            slippage=c.slippage * fx,
            impact=c.impact * fx,
            fx_cost=c.fx_cost * fx,
        )
