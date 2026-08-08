"""CostModel Protocol（EXECUTION_SPEC §22）。"""

from __future__ import annotations

from typing import Protocol

from ..contracts import CostBreakdown


class CostModel(Protocol):
    def estimate(
        self,
        instrument: str,
        side: str,
        quantity: float,
        reference_price: float,
        market_state: dict | None = None,
    ) -> CostBreakdown:
        ...
