"""TradabilityMask（EXECUTION_SPEC §26）。纯函数式，输入显式。"""

from __future__ import annotations

import pandas as pd

from ..contracts import (
    REASON_BROKER_UNSUPPORTED,
    REASON_DATA_STALE,
    REASON_DELISTED,
    REASON_LIQUIDITY_TOO_LOW,
    REASON_MARKET_CLOSED,
    REASON_NOT_LISTED,
    REASON_PREMIUM_TOO_HIGH,
    REASON_STOCK_CONNECT_NOT_ELIGIBLE,
    REASON_STOCK_CONNECT_SELL_ONLY,
    REASON_SUSPENDED,
    TradabilityDecision,
)


class TradabilityMask:
    def get(
        self,
        instrument: str,
        timestamp: pd.Timestamp,
        *,
        listed: bool = True,
        suspended: bool = False,
        market_open: bool = True,
        data_fresh: bool = True,
        broker_supported: bool = True,
        stock_connect_eligible: bool | None = None,
        stock_connect_sell_only: bool = False,
        liquidity_ok: bool = True,
        premium_ok: bool = True,
    ) -> TradabilityDecision:
        reasons: list[str] = []
        buy, sell = True, True
        if not listed:
            buy = sell = False
            reasons.append(REASON_NOT_LISTED)
        elif suspended:
            buy = sell = False
            reasons.append(REASON_SUSPENDED)
        if not market_open:
            buy = sell = False
            reasons.append(REASON_MARKET_CLOSED)
        if not data_fresh:
            buy = sell = False
            reasons.append(REASON_DATA_STALE)
        if not broker_supported:
            buy = sell = False
            reasons.append(REASON_BROKER_UNSUPPORTED)
        if stock_connect_eligible is not None and not stock_connect_eligible:
            buy = sell = False
            reasons.append(REASON_STOCK_CONNECT_NOT_ELIGIBLE)
        if stock_connect_sell_only:
            buy = False
            reasons.append(REASON_STOCK_CONNECT_SELL_ONLY)
        if not liquidity_ok:
            buy = False
            reasons.append(REASON_LIQUIDITY_TOO_LOW)
        if not premium_ok:
            buy = False
            reasons.append(REASON_PREMIUM_TOO_HIGH)
        return TradabilityDecision(
            instrument=instrument,
            timestamp=timestamp,
            buy_allowed=buy,
            sell_allowed=sell,
            reason_codes=tuple(reasons),
        )
