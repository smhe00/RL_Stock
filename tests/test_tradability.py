"""EXECUTION_SPEC §54.5 — tradability 状态机。"""

import pandas as pd

from china_etf.contracts import (
    REASON_DATA_STALE,
    REASON_MARKET_CLOSED,
    REASON_NOT_LISTED,
    REASON_PREMIUM_TOO_HIGH,
    REASON_STOCK_CONNECT_SELL_ONLY,
    REASON_SUSPENDED,
)
from china_etf.execution.tradability import TradabilityMask


T = pd.Timestamp("2026-08-07")


def test_normal_tradable() -> None:
    d = TradabilityMask().get("510300.SH", T)
    assert d.buy_allowed and d.sell_allowed and not d.reason_codes


def test_not_listed_and_suspended() -> None:
    mask = TradabilityMask()
    d = mask.get("X", T, listed=False)
    assert not d.buy_allowed and not d.sell_allowed
    assert REASON_NOT_LISTED in d.reason_codes
    d2 = mask.get("X", T, suspended=True)
    assert REASON_SUSPENDED in d2.reason_codes


def test_sell_only_and_premium_block() -> None:
    mask = TradabilityMask()
    d = mask.get("03110.HK", T, stock_connect_sell_only=True)
    assert not d.buy_allowed and d.sell_allowed
    assert REASON_STOCK_CONNECT_SELL_ONLY in d.reason_codes
    d2 = mask.get("513500.SH", T, premium_ok=False)
    assert not d2.buy_allowed and d2.sell_allowed
    assert REASON_PREMIUM_TOO_HIGH in d2.reason_codes


def test_market_closed_and_stale() -> None:
    mask = TradabilityMask()
    assert REASON_MARKET_CLOSED in mask.get("A", T, market_open=False).reason_codes
    assert REASON_DATA_STALE in mask.get("A", T, data_fresh=False).reason_codes
