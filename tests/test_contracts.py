"""EXECUTION_SPEC §54.1 / §54.6 — weight invariants 与 action 映射。"""

import numpy as np
import pandas as pd
import pytest

from china_etf.contracts import (
    TargetAssetWeights,
    assert_weight_invariants,
    softmax_weights,
)


def test_softmax_weights_basic() -> None:
    slots = ["A", "B", "C"]
    w = softmax_weights(np.array([0.0, 0.0, 0.0]), slots)
    assert list(w.index) == slots
    assert np.allclose(w.values, 1 / 3)


def test_softmax_no_nan_inf_and_sum_one() -> None:
    raw = np.array([1e10, -1e10, 3.0, 0.5])
    w = softmax_weights(raw, ["a", "b", "c", "d"])
    assert np.isfinite(w.values).all()
    assert np.isclose(w.sum(), 1.0)
    assert (w >= 0).all()


def test_weight_invariants_rejections() -> None:
    with pytest.raises(ValueError):
        assert_weight_invariants(pd.Series([0.5, np.nan, 0.5]))
    with pytest.raises(ValueError):
        assert_weight_invariants(pd.Series([1.5, -0.5]))
    with pytest.raises(ValueError):
        assert_weight_invariants(pd.Series([0.6, 0.6]))  # sum 1.2


def test_target_asset_weights_frozen_and_validated() -> None:
    w = pd.Series([0.5, 0.5], index=["CN_LARGE", "GOLD"])
    taw = TargetAssetWeights(decision_time=pd.Timestamp("2026-08-07"), weights=w)
    assert taw.weights["GOLD"] == 0.5
    with pytest.raises(ValueError):
        TargetAssetWeights(
            decision_time=pd.Timestamp("2026-08-07"), weights=pd.Series([0.5, 0.4])
        )
