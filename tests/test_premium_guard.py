"""Reviewer §18.6 / EXECUTION_SPEC §25 — fail-closed。"""

import time

import pandas as pd

from china_etf.execution.premium import PremiumGuard


T = pd.Timestamp("2026-08-07")


def test_iopv_missing_blocks_buy() -> None:
    d = PremiumGuard().evaluate("513500.SH", T, market_price=2.695, iopv=None, now_epoch=time.time())
    assert not d.buy_allowed
    assert d.hold_allowed and d.sell_allowed
    assert d.warning_level == "block"


def test_iopv_stale_blocks_buy() -> None:
    now = time.time()
    d = PremiumGuard(max_iopv_age_seconds=60.0).evaluate(
        "513500.SH", T, market_price=2.695, iopv=2.474, iopv_ts=now - 300, now_epoch=now
    )
    assert not d.buy_allowed and d.sell_allowed and d.hold_allowed


def test_fresh_iopv_allows_buy() -> None:
    now = time.time()
    d = PremiumGuard().evaluate(
        "513500.SH", T, market_price=2.695, iopv=2.474, iopv_ts=now - 1, now_epoch=now
    )
    assert d.buy_allowed and d.sell_allowed
    assert d.premium_pct is not None and d.premium_pct > 0


def test_no_protection_required() -> None:
    guard = PremiumGuard(requires_protection=lambda inst: inst == "513500.SH")
    d = guard.evaluate("510300.SH", T, market_price=4.0, iopv=None, now_epoch=time.time())
    assert d.buy_allowed and d.warning_level == "none"
