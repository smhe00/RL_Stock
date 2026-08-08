"""PremiumGuard（EXECUTION_SPEC §25 / Reviewer §16.6）。

Gate 2 只实现：接口 + 数据新鲜度 + fail-closed。
禁止用 close_to_official_nav_gap 的 P95 直接设定 Live threshold（D-011）。
"""

from __future__ import annotations

import time
from typing import Callable

import pandas as pd

from ..contracts import PremiumDecision


class PremiumGuard:
    def __init__(
        self,
        *,
        requires_protection: Callable[[str], bool] | None = None,
        max_iopv_age_seconds: float = 60.0,
    ) -> None:
        self._requires = requires_protection or (lambda inst: True)
        self.max_iopv_age_seconds = max_iopv_age_seconds

    def evaluate(
        self,
        instrument: str,
        timestamp: pd.Timestamp,
        *,
        market_price: float,
        iopv: float | None = None,
        iopv_ts: float | None = None,  # epoch seconds
        now_epoch: float | None = None,
        threshold_pct: float | None = None,  # Gate 2 不提供 → 仅新鲜度判断
    ) -> PremiumDecision:
        if not self._requires(instrument):
            return PremiumDecision(
                instrument=instrument,
                timestamp=timestamp,
                premium_pct=None,
                iopv=None,
                data_age_seconds=None,
                buy_allowed=True,
                hold_allowed=True,
                sell_allowed=True,
                warning_level="none",
                reason="not_required",
            )
        now = now_epoch if now_epoch is not None else time.time()
        if iopv is None or iopv_ts is None:
            # fail-closed：需要保护但 IOPV 缺失 → 禁买，允许持有/卖出
            return PremiumDecision(
                instrument=instrument,
                timestamp=timestamp,
                premium_pct=None,
                iopv=iopv,
                data_age_seconds=None,
                buy_allowed=False,
                hold_allowed=True,
                sell_allowed=True,
                warning_level="block",
                reason="iopv_unavailable_fail_closed",
            )
        age = max(0.0, now - iopv_ts)
        if age > self.max_iopv_age_seconds:
            return PremiumDecision(
                instrument=instrument,
                timestamp=timestamp,
                premium_pct=None,
                iopv=iopv,
                data_age_seconds=age,
                buy_allowed=False,
                hold_allowed=True,
                sell_allowed=True,
                warning_level="block",
                reason="iopv_stale_fail_closed",
            )
        premium_pct = (market_price / iopv - 1.0) * 100.0 if iopv else None
        return PremiumDecision(
            instrument=instrument,
            timestamp=timestamp,
            premium_pct=premium_pct,
            iopv=iopv,
            data_age_seconds=age,
            buy_allowed=True,
            hold_allowed=True,
            sell_allowed=True,
            warning_level="info",
            reason="fresh_iopv",
        )
