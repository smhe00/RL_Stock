"""CostModel Protocol（EXECUTION_SPEC §22）与费率规则元数据（Reviewer §5）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
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


@dataclass(frozen=True)
class FeeRule:
    """单条费率规则（带生效期与来源，避免历史回测被当前费率污染）。"""

    name: str
    rate: float | None
    minimum: float | None
    maximum: float | None
    currency: str
    effective_from: date
    effective_to: date | None
    source: str
    applies_to: tuple[str, ...]
