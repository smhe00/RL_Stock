"""EXECUTION_SPEC §19 — FX skeleton point-in-time。"""

import pandas as pd
import pytest

from china_etf.fx import FXSkeleton


def test_hkd_conversion_point_in_time() -> None:
    fx = FXSkeleton()
    fx.register(
        "HKD",
        pd.Series(
            [0.90, 0.91, 0.92],
            index=pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06"]),
        ),
    )
    assert fx.rate("HKD", pd.Timestamp("2026-01-02")) == 0.90
    assert fx.rate("HKD", pd.Timestamp("2026-01-03")) == 0.90  # 前向不可用
    assert fx.rate("HKD", pd.Timestamp("2026-01-06")) == 0.92
    assert fx.convert(30.0, "HKD", pd.Timestamp("2026-01-06")) == 27.6
    with pytest.raises(ValueError):
        fx.rate("HKD", pd.Timestamp("2025-12-31"))  # 无 PIT 汇率


def test_base_currency_identity() -> None:
    fx = FXSkeleton()
    assert fx.rate("CNY", pd.Timestamp("2026-01-01")) == 1.0
