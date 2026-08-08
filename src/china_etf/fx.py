"""FXSkeleton（EXECUTION_SPEC §19）。BaseCurrency=CNY；HKD mark-to-market 结构。"""

from __future__ import annotations

import pandas as pd


class FXSkeleton:
    def __init__(self, base_currency: str = "CNY") -> None:
        self.base_currency = base_currency
        # currency -> DataFrame(date, rate_to_base)
        self._series: dict[str, pd.Series] = {}

    def register(self, currency: str, rate_to_base: pd.Series) -> None:
        if currency == self.base_currency:
            raise ValueError("base currency rate not needed")
        s = rate_to_base.sort_index()
        if s.index.duplicated().any():
            s = s[~s.index.duplicated(keep="last")]
        self._series[currency] = s

    def rate(self, currency: str, asof: pd.Timestamp) -> float:
        if currency == self.base_currency:
            return 1.0
        s = self._series.get(currency)
        if s is None:
            raise KeyError(f"no FX series for {currency}")
        asof = pd.Timestamp(asof)
        valid = s[s.index <= asof]
        if valid.empty:
            raise ValueError(f"no point-in-time FX for {currency} at {asof}")
        return float(valid.iloc[-1])

    def convert(self, amount_ccy: float, currency: str, asof: pd.Timestamp) -> float:
        return amount_ccy * self.rate(currency, asof)
