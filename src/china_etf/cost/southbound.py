"""SouthboundETFCostModel（EXECUTION_SPEC §24）——GATE_4_PRECHECK F1/F2 修正。

F1 历史分段费率（官方生效日；生效日前用 pre-rate）：
  Trading Fee       0.005%  → 0.00565%（2023-01-01，HKEX 通函 086/22）
  SFC Trading Levy  0.003%  → 0.0027% （2014-11-01，SSE 港股通税费页）
  FRC/AFRC Levy     0       → 0.00015%（2022-01-01，FRC 通函 CE/SEHK/CT/086/2021）
  股份交收费(settlement) 0.002%（min 2/max 100 HKD）→ 0.0042%（无上下限，
      2025-06-30，HKSCC；2025-06-30 前保留 min/max 钳制）
  印花税            ETF 豁免（0）全程；投资者赔偿征费/特别征费暂不征收（0）

F2 港股通券商佣金（NOT ACCOUNT-VERIFIED）：
  原 placeholder 0.00005（万0.5）明显低于市场默认（多来源 2025-2026：常见万2.5~万3）。
  冻结为 conservative scenario：佣金 0.0003（万3）双边 + 单笔最低 5 HKD，
  manifest 必须标注 NOT ACCOUNT-VERIFIED。Gate 4 cost sensitivity 覆盖 1x/2x/3x。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from ..contracts import CostBreakdown

# F1：首个生效日之前的官方/市场历史费率
HKEX_TRADING_FEE_PRE_RATE = 0.00005  # 0.005%
SFC_LEVY_PRE_RATE = 0.00003  # 0.003%
AFRC_LEVY_PRE_RATE = 0.0


@dataclass
class SouthboundETFCostModel:
    broker_commission_rate: float = 0.0003  # F2 conservative 万3（NOT ACCOUNT-VERIFIED）
    broker_min_commission_hkd: float = 5.0  # F2 单笔最低（多来源：常见 5 HKD，未账户核实）
    # F1 分段费率：升序 (生效日, 费率)；生效日前用模块级 pre-rate；None → 最新费率
    hkex_trading_fee_schedule: tuple = field(
        default_factory=lambda: (("2023-01-01", 0.0000565),),  # 之前 HKEX_TRADING_FEE_PRE_RATE
    )
    regulatory_levy_schedule: tuple = field(
        default_factory=lambda: (("2014-11-01", 0.000027),),  # 之前 SFC_LEVY_PRE_RATE
    )
    afrc_levy_schedule: tuple = field(
        default_factory=lambda: (("2022-01-01", 0.0000015),),  # 之前 AFRC_LEVY_PRE_RATE
    )
    # 股份交收费：(生效日, 费率, min_hkd, max_hkd)；2025-06-30 后无上下限（None）
    settlement_fee_schedule: tuple = field(
        default_factory=lambda: (
            ("2014-01-01", 0.00002, 2.0, 100.0),
            ("2025-06-30", 0.000042, None, None),
        ),
    )
    stamp_duty_rate: float = 0.0  # 港股通 ETF 印花税暂免（Reviewer 核实）
    fx_cost_bps: float = 0.0  # 换汇成本待核实
    half_spread_bps: float = 1.0
    slippage_bps: float = 2.0
    fx_to_base: float = 1.0  # CostBreakdown 一律为 base 币种（D-017）：HKD 计算后折算
    effective_from: str = "2014-01-01"
    source: str = (
        "HKEX 通函 086/22 (2023-01-01) + SSE 港股通税费页 (2014-11-01/2022-01-01) "
        "+ HKSCC 股份交收费 (2025-06-30) + F2 conservative 万3 NOT ACCOUNT-VERIFIED"
    )

    @staticmethod
    def _rate_on(schedule: tuple, pre_rate: float, transaction_date) -> float:
        """按日期选费率；schedule=升序 [(生效日, rate), ...]；None → 最新费率。

        生效日前的日期返回 pre_rate（历史费率），而非错误沿用首个生效日的新费率。
        """
        if transaction_date is None:
            return float(schedule[-1][1])
        t = pd.Timestamp(transaction_date)
        rate = float(pre_rate)
        for entry in schedule:
            if t >= pd.Timestamp(entry[0]):
                rate = float(entry[1])
            else:
                break
        return rate

    def _settlement_on(self, transaction_date) -> tuple[float, float | None, float | None]:
        """(rate, min_hkd, max_hkd)；None → 最新档（2025-06-30 后无上下限）。"""
        entries = self.settlement_fee_schedule
        if transaction_date is None:
            eff, rate, lo, hi = entries[-1]
            return float(rate), lo, hi
        t = pd.Timestamp(transaction_date)
        eff, rate, lo, hi = entries[0]
        for e, r, l, h in entries:
            if t >= pd.Timestamp(e):
                eff, rate, lo, hi = e, r, l, h
            else:
                break
        return float(rate), lo, hi

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
        tx_date = (market_state or {}).get("transaction_date")
        notional = quantity * reference_price  # HKD
        commission = notional * self.broker_commission_rate
        if self.broker_min_commission_hkd is not None and commission > 0:
            commission = max(commission, self.broker_min_commission_hkd)
        exchange_fee = notional * self._rate_on(
            self.hkex_trading_fee_schedule, HKEX_TRADING_FEE_PRE_RATE, tx_date
        )
        levy = notional * self._rate_on(
            self.regulatory_levy_schedule, SFC_LEVY_PRE_RATE, tx_date
        )
        afrc = notional * self._rate_on(
            self.afrc_levy_schedule, AFRC_LEVY_PRE_RATE, tx_date
        )
        stamp = notional * self.stamp_duty_rate
        s_rate, s_min, s_max = self._settlement_on(tx_date)
        settlement = notional * s_rate
        if s_min is not None:
            settlement = min(max(settlement, s_min), s_max)
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
