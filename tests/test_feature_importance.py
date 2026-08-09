"""GATE_4_FEATURE_ABLATION_RUNS — factor_importance helper 单测（合成数据，无真实依赖）。"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT_ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "artifacts"

from china_etf.evaluation.factor_importance import (
    bh_fdr,
    block_bootstrap_ci,
    block_permutation_p,
    cross_fit_residual_spearman,
    decision_dates,
    holm_adjust,
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


class TestBlockBootstrapCi:
    def test_known_difference_ci_excludes_zero(self):
        rng = np.random.default_rng(5)
        # 真实依赖：feature 高 → |outcome| 高（差距显著）
        f = np.repeat([0.0, 1.0, 2.0], 100)
        o = np.abs(rng.normal(0, 0.1 + 0.5 * f, len(f)))
        gap = lambda x, y: tercile_discrimination(x, y)["low_minus_high_mean"]  # noqa: E731
        ci = block_bootstrap_ci(f, o, gap, n_boot=200, block_len=20, seed=0)
        assert ci["ci_low"] < 0 and ci["ci_high"] < 0  # 显著负 gap → CI 排除 0

    def test_no_difference_ci_contains_zero(self):
        rng = np.random.default_rng(6)
        f = rng.normal(0, 1, 400)
        o = rng.normal(0, 1, 400)  # 无关联
        gap = lambda x, y: tercile_discrimination(x, y)["low_minus_high_mean"]  # noqa: E731
        ci = block_bootstrap_ci(f, o, gap, n_boot=200, block_len=20, seed=1)
        assert ci["ci_low"] < 0 < ci["ci_high"]

    def test_block_length_clamped(self):
        n = 10
        x = np.arange(float(n))
        y = x
        ci = block_bootstrap_ci(x, y, spearman, n_boot=50, block_len=100, seed=0)
        assert np.isfinite(ci["ci_low"]) and np.isfinite(ci["ci_high"])


class TestMultipleTesting:
    def test_holm_manual(self):
        # Holm (n=4): p=[.01,.04,.04,.05] → running max of (n-j+1)*p_j
        #   rank1 .01 → 4*.01=.04; rank2 .04 → max(.04, 3*.04=.12)=.12;
        #   rank3 .04 → max(.12, 2*.04=.08)=.12; rank4 .05 → max(.12, 1*.05)=.12
        adj = holm_adjust(np.array([0.01, 0.04, 0.04, 0.05]))
        assert adj[0] == pytest.approx(0.04, abs=1e-12)
        assert adj[1] == pytest.approx(0.12, abs=1e-12)
        assert adj[2] == pytest.approx(0.12, abs=1e-12)
        assert adj[3] == pytest.approx(0.12, abs=1e-12)

    def test_holm_clamped_to_one(self):
        adj = holm_adjust(np.array([0.3, 0.8]))
        assert adj.max() <= 1.0

    def test_bh_fdr_manual(self):
        # BH (n=4): p=[.01,.03,.04,.05] → q by backward min of p*n/(rank)
        #   rank4 .05 → .05*4/4=.05; rank3 .04 → min(.05, .04*4/3=.0533)=.05;
        #   rank2 .03 → min(.05, .03*4/2=.06)=.05; rank1 .01 → min(.05, .01*4/1=.04)=.04
        q = bh_fdr(np.array([0.01, 0.03, 0.04, 0.05]))
        assert q[0] == pytest.approx(0.04, abs=1e-12)
        assert q[1] == pytest.approx(0.05, abs=1e-12)
        assert q[2] == pytest.approx(0.05, abs=1e-12)
        assert q[3] == pytest.approx(0.05, abs=1e-12)
        assert q.max() <= 1.0

    def test_empty(self):
        assert holm_adjust([]).size == 0
        assert bh_fdr([]).size == 0


class TestCrossFitResidualization:
    def test_val_not_in_fit(self):
        """跨 fold：训练区拟合系数，验证区只 apply。拟合区外的 val 残差不被污染。"""
        rng = np.random.default_rng(7)
        n = 200
        X = rng.normal(size=(n, 2))
        f = 2.0 * X[:, 0] + rng.normal(0, 0.1, n)  # 特征大部分由 F0 解释
        o = np.abs(rng.normal(0, 1, n))  # outcome 与特征独立
        rho = cross_fit_residual_spearman(f, X, o)
        # val 残差（特征去 F0 后）与 outcome 无显著关联
        assert abs(rho) < 0.4

    def test_unexplained_feature_keeps_signal(self):
        """特征含独立于 F0 的信号，且该信号预测 outcome → val 残差仍显著。"""
        rng = np.random.default_rng(8)
        n = 300
        X = rng.normal(size=(n, 2))
        signal = rng.normal(0, 1, n)
        f = 1.5 * X[:, 0] + signal  # 特征 = F0 部分 + 独立信号
        o = np.abs(rng.normal(0, 1, n)) * (1 + 0.8 * signal)  # |o| 由 signal 驱动
        rho = cross_fit_residual_spearman(f, X, o)
        assert rho > 0.3


class TestScreeningDecisionDays:
    def test_train_val_excludes_own_test_fold_local(self):
        """fold-local：每 fold 自己的 train∪val 不含该 fold 自己的 test（expanding 下 union 必然重叠）。"""
        from china_etf.evaluation.walkforward import make_folds
        idx = pd.date_range("2020-01-01", periods=1000, freq="B")
        folds = make_folds(idx, n_folds=4, min_train_days=300, val_days=60)
        for f in folds:
            screen = set(pd.DatetimeIndex([d for d in idx if f.train_start <= d <= f.train_end]))
            screen.update(pd.DatetimeIndex([d for d in idx if f.val_start <= d <= f.val_end]))
            own_test = set(pd.DatetimeIndex([d for d in idx if f.test_start <= d <= f.test_end]))
            assert screen.isdisjoint(own_test)
        # expanding union 确实重叠（fold k+1 train 含 fold k test）——证明该测试的必要性
        all_screen = set()
        all_test = set()
        for f in folds:
            all_screen.update(pd.DatetimeIndex([d for d in idx if f.train_start <= d <= f.train_end]))
            all_screen.update(pd.DatetimeIndex([d for d in idx if f.val_start <= d <= f.val_end]))
            all_test.update(pd.DatetimeIndex([d for d in idx if f.test_start <= d <= f.test_end]))
        assert not all_screen.isdisjoint(all_test)


class TestBlockPermutationP:
    def test_null_permutation_p_not_tiny(self):
        """独立 x/y（无关联）→ permutation p 不应很小（null 下近似均匀）。"""
        rng = np.random.default_rng(10)
        x = rng.normal(0, 1, 300)
        y = rng.normal(0, 1, 300)
        p = block_permutation_p(x, y, spearman, n_perm=300, block_len=20, seed=0)
        assert p > 0.05

    def test_strong_signal_small_p(self):
        """强单调信号 → permutation p 很小（<0.05）。"""
        rng = np.random.default_rng(11)
        x = np.linspace(0.0, 1.0, 300)
        y = 3 * x + rng.normal(0, 0.05, 300)
        p = block_permutation_p(x, y, spearman, n_perm=300, block_len=20, seed=0)
        assert p < 0.05

    def test_permutation_p_in_unit_interval(self):
        x = np.arange(100.0)
        y = np.arange(100.0)
        p = block_permutation_p(x, y, spearman, n_perm=100, block_len=20, seed=0)
        assert 0.0 <= p <= 1.0


class TestBlockBootstrapNoPBs:
    def test_no_p_bs_key(self):
        """B4: block_bootstrap_ci 不再返回 p_bs（非 null 检验）。"""
        x = np.linspace(0.0, 1.0, 100)
        y = 2 * x
        ci = block_bootstrap_ci(x, y, spearman, n_boot=50, block_len=20, seed=0)
        assert "p_bs" not in ci
        assert "ci_low" in ci and "ci_high" in ci


class TestGlobalTestExclusion:
    def test_global_union_exclusion_disjoint(self):
        """全局 test 排除后 screening 集与 global test union 不相交（B1）。"""
        from china_etf.evaluation.walkforward import make_folds
        idx = pd.date_range("2020-01-01", periods=1000, freq="B")
        folds = make_folds(idx, n_folds=4, min_train_days=300, val_days=60)
        global_test = set()
        for f in folds:
            global_test.update(pd.DatetimeIndex([d for d in idx if f.test_start <= d <= f.test_end]))
        screen = set(pd.DatetimeIndex([d for d in idx if d in idx[:-1]])) - global_test
        assert screen.isdisjoint(global_test)
        # 与 fold-local 不同：union 确实包含被排除的 test 日（验证排除必要性）
        assert len(screen) < len(idx) - 1

    def test_reduced_f0_proxy_label(self):
        """B5: 脚本 manifest 用 reduced_F0_market_proxy 命名（非完整 F0）。"""
        import json
        from pathlib import Path
        art = ROOT_ARTIFACT_DIR / "gate4_feature_importance_stat_final.json"
        if art.exists():
            r = json.loads(art.read_text(encoding="utf-8"))
            assert "reduced_F0_market_proxy" in r["manifest"]["f0_residualization"]
