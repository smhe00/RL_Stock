"""GATE_4_FEATURE_ABLATION_RUNS — factor_importance helper 单测（合成数据，无真实依赖）。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from china_etf.evaluation.factor_importance import (
    decision_dates,
    ols_residual,
    spearman,
    tercile_discrimination,
    tercile_labels,
)


class TestTercileLabels:
    def test_monotone_equal_bins(self):
        vals = np.arange(300, dtype=float)
        lab = tercile_labels(vals)
        assert lab.tolist() == sorted(lab.tolist())
        counts = [int((lab == k).sum()) for k in (0, 1, 2)]
        assert counts == [100, 100, 100]

    def test_ties_into_same_bin(self):
        # 前 150 全相同，后 150 单调 → 并列全进 low
        vals = np.concatenate([np.full(150, 1.0), np.linspace(2.0, 3.0, 150)])
        lab = tercile_labels(vals)
        assert (lab[:150] == 0).all()
        assert (lab[150:] > 0).all()

    def test_non_finite_negative(self):
        vals = np.array([1.0, 2.0, 3.0, np.nan, 4.0, 5.0, 6.0])
        lab = tercile_labels(vals)
        assert lab[3] == -1
        assert set(lab[lab != -1].tolist()) <= {0, 1, 2}

    def test_short_n_all_zero(self):
        lab = tercile_labels(np.array([1.0, 2.0]))
        assert lab.tolist() == [0, 0]


class TestSpearman:
    def test_perfect_monotone(self):
        x = np.arange(1.0, 21.0)
        y = 2 * x + 1
        assert spearman(x, y) == pytest.approx(1.0, abs=1e-9)

    def test_perfect_antitone(self):
        x = np.arange(1.0, 21.0)
        y = -3 * x
        assert spearman(x, y) == pytest.approx(-1.0, abs=1e-9)

    def test_nan_ignored(self):
        x = np.array([1.0, 2.0, np.nan, 4.0, 5.0])
        y = np.array([1.0, 4.0, 9.0, 16.0, 25.0])
        rho = spearman(x, y)
        rho_clean = spearman(np.array([1.0, 2.0, 4.0, 5.0]),
                             np.array([1.0, 4.0, 16.0, 25.0]))
        assert rho == pytest.approx(rho_clean, abs=1e-9)

    def test_constant_returns_nan(self):
        assert np.isnan(spearman(np.ones(10), np.arange(10.0)))


class TestTercileDiscrimination:
    def test_separated_groups_significant(self):
        rng = np.random.default_rng(0)
        f = np.concatenate([rng.normal(0.0, 0.3, 60), rng.normal(3.0, 0.3, 60)])  # 双峰簇
        o = np.concatenate([rng.normal(-0.01, 0.01, 60), rng.normal(0.01, 0.01, 60)])
        res = tercile_discrimination(f, o)
        assert res["low_minus_high_mean"] < 0  # low 特征 → 更低前向收益
        assert res["mann_whitney_p"] < 0.05
        assert res["low"]["n"] >= 20 and res["high"]["n"] >= 20

    def test_identical_returns_high_p(self):
        f = np.array([0.0, 0.0, 1.0, 1.0, 2.0, 2.0, 3.0, 3.0, 4.0, 4.0])
        o = np.zeros(10)
        res = tercile_discrimination(f, o)
        assert res["low_minus_high_mean"] == pytest.approx(0.0, abs=1e-12)


class TestDecisionDates:
    def test_prior_calendar_day(self):
        cal = pd.date_range("2024-01-01", periods=10, freq="D")
        ex = pd.DatetimeIndex(["2024-01-03", "2024-01-08"])
        d = decision_dates(ex, cal)
        assert d[0] == pd.Timestamp("2024-01-02")
        assert d[1] == pd.Timestamp("2024-01-07")

    def test_string_input(self):
        cal = pd.date_range("2024-01-01", periods=10, freq="B")  # business days
        d = decision_dates(["2024-01-03", "2024-01-05"], cal)
        assert d[0] == cal[cal.get_indexer([pd.Timestamp("2024-01-03")])[0] - 1]


class TestOlsResidual:
    def test_exact_linear_removed(self):
        rng = np.random.default_rng(1)
        X = rng.normal(size=(200, 3))
        y = 2.0 * X[:, 0] - 1.5 * X[:, 1] + 0.5  # 精确线性
        resid = ols_residual(y, X)
        assert np.nanmax(np.abs(resid)) < 1e-8

    def test_residual_uncorrelated_with_predictors(self):
        rng = np.random.default_rng(2)
        X = rng.normal(size=(300, 2))
        y = X[:, 0] + rng.normal(0, 1, 300)
        resid = ols_residual(y, X)
        for j in range(2):
            rho = spearman(resid, X[:, j])
            assert abs(rho) < 0.2

    def test_non_finite_rows_dropped(self):
        X = np.random.default_rng(3).normal(size=(100, 2))
        y = X[:, 0]
        X[5, 1] = np.nan
        resid = ols_residual(y, X)
        assert np.isnan(resid[5])
        assert np.isfinite(resid[~np.isnan(resid)]).all()


class TestKnownMonotoneSignal:
    def test_feature_predicts_forward_risk(self):
        """已知单调关系：特征高 → 前向 |收益|（风险）高 → 正向风险 Spearman + 显著判别。"""
        rng = np.random.default_rng(4)
        f = np.linspace(0.0, 1.0, 240)
        # 前向风险随 f 单调上升：|r| = 0.002 + 0.01*f + noise
        risk = 0.002 + 0.01 * f + rng.normal(0, 0.001, len(f))
        fwd = rng.normal(0, 1, len(f)) * risk  # |fwd| ∝ risk
        assert spearman(f, np.abs(fwd)) > 0.5
        res = tercile_discrimination(f, np.abs(fwd))
        assert res["high"]["mean_fwd_ret"] > res["low"]["mean_fwd_ret"]
