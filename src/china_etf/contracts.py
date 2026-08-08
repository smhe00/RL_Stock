"""Gate 2 — canonical contracts（D-005 / Reviewer §16.1）。

所有下游（Backtest / Paper / Live）只从这些对象向下转换。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import numpy as np
import pandas as pd

# --- Tradability reason codes（EXECUTION_SPEC §26）---
REASON_NOT_LISTED = "NOT_LISTED"
REASON_DELISTED = "DELISTED"
REASON_SUSPENDED = "SUSPENDED"
REASON_STOCK_CONNECT_NOT_ELIGIBLE = "STOCK_CONNECT_NOT_ELIGIBLE"
REASON_STOCK_CONNECT_SELL_ONLY = "STOCK_CONNECT_SELL_ONLY"
REASON_PREMIUM_TOO_HIGH = "PREMIUM_TOO_HIGH"
REASON_LIQUIDITY_TOO_LOW = "LIQUIDITY_TOO_LOW"
REASON_MARKET_CLOSED = "MARKET_CLOSED"
REASON_BROKER_UNSUPPORTED = "BROKER_UNSUPPORTED"
REASON_DATA_STALE = "DATA_STALE"
REASON_QUOTE_UNAVAILABLE = "QUOTE_UNAVAILABLE"


def assert_weight_invariants(weights: pd.Series, expected_sum: float = 1.0) -> None:
    """EXECUTION_SPEC §29/§54.1：finite / non-negative / sum to expected / no NaN。"""
    if weights.empty:
        raise ValueError("weights must be non-empty")
    if not np.isfinite(weights.astype(float)).all():
        raise ValueError("weights contain NaN/inf")
    if (weights < 0).any():
        raise ValueError("weights contain negative values")
    total = float(weights.sum())
    if not np.isclose(total, expected_sum, atol=1e-6):
        raise ValueError(f"weights sum to {total}, expected {expected_sum}")


def softmax_weights(raw: np.ndarray, slot_ids: list[str]) -> pd.Series:
    """simplex mapping（EXECUTION_SPEC §29）：w_i = exp(z_i)/sum(exp(z_j))。"""
    z = np.asarray(raw, dtype=float).ravel()
    z = z - z.max()  # 数值稳定
    exp = np.exp(z)
    w = exp / exp.sum()
    out = pd.Series(w, index=list(slot_ids), dtype=float)
    assert_weight_invariants(out)
    return out


@dataclass(frozen=True)
class AssetSlot:
    """经济风险槽位（EXECUTION_SPEC §5/§49）。RL 不学 ETF 代码，只学 Slot。"""

    name: str
    asset_class: str
    region: str
    style: str | None = None
    theme: str | None = None
    currency: str = "CNY"


@dataclass(frozen=True)
class TargetAssetWeights:
    """唯一 Source of Truth（D-005）。weights.index = AssetSlot ID。"""

    decision_time: pd.Timestamp
    weights: pd.Series
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        assert_weight_invariants(pd.Series(self.weights, dtype=float))


@dataclass(frozen=True)
class TargetInstrumentWeights:
    """InstrumentSelector 输出：weights.index = 具体 instrument code。"""

    decision_time: pd.Timestamp
    weights: pd.Series
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TradabilityDecision:
    instrument: str
    timestamp: pd.Timestamp
    buy_allowed: bool
    sell_allowed: bool
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class PremiumDecision:
    instrument: str
    timestamp: pd.Timestamp
    premium_pct: float | None
    iopv: float | None
    data_age_seconds: float | None
    buy_allowed: bool
    hold_allowed: bool
    sell_allowed: bool
    warning_level: str  # none | info | warning | block
    reason: str = ""


@dataclass(frozen=True)
class CostBreakdown:
    commission: float = 0.0
    exchange_fee: float = 0.0
    tax: float = 0.0
    spread: float = 0.0
    slippage: float = 0.0
    impact: float = 0.0
    fx_cost: float = 0.0

    @property
    def total(self) -> float:
        return (
            self.commission
            + self.exchange_fee
            + self.tax
            + self.spread
            + self.slippage
            + self.impact
            + self.fx_cost
        )


@dataclass(frozen=True)
class Order:
    instrument: str
    side: str  # "buy" | "sell"
    quantity: float
    limit_price: float | None = None
    order_type: str = "market"
    strategy_name: str = "china_etf"


@dataclass(frozen=True)
class Fill:
    order_id: str
    instrument: str
    side: str
    quantity: float
    price: float  # 成交价（instrument 币种）
    cost: CostBreakdown  # 总成本（base currency）
    timestamp: pd.Timestamp


@dataclass(frozen=True)
class OrderPlan:
    decision_time: pd.Timestamp
    target_asset_weights: TargetAssetWeights
    target_instrument_weights: TargetInstrumentWeights | None
    orders: tuple[Order, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
