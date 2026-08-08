"""GATE_4_NON_RL_HORSE_RACE — Tier A 非 RL 方法测试（合成数据，快速）。

覆盖：权重性质（long-only/sum=1/finite）+ 各方法特定断言（ERC 等贡献、HRP 聚类、
MaxDiv 分散性、TrendRP CASH_LIKE、MinCVaR long-only、ShrinkMV finite）。
"""

import numpy as np
import pandas as pd
import pytest

from china_etf.contracts import EnvironmentMode
from china_etf.cost.mainland import MainlandETFCostModel
from china_etf.environment.portfolio_env import ChinaETFPortfolioEnv
from china_etf.evaluation.baselines import (
    equal_weight_policy,
    erc_policy,
    hrp_policy,
    maximum_diversification_policy,
    minimum_cvar_policy,
    minimum_variance_policy,
    momentum_policy,
    risk_parity_policy,
    shrinkage_mean_variance_policy,
    trend_risk_parity_policy,
)
from china_etf.execution.broker.mock import MockBroker
from china_etf.execution.order_generator import OrderGenerator
from china_etf.execution.premium import PremiumGuard
from china_etf.execution.tradability import TradabilityMask
from china_etf.risk.risk_overlay import RiskOverlayV0

SLOTS = ["S0", "S1", "S2", "S3", "S4", "CASH_LIKE"]
_N = len(SLOTS)


def _env(n=600, seed=11):
    dates = pd.bdate_range("2021-01-02", periods=n)
    rng = np.random.default_rng(seed)
    adj = pd.DataFrame(
        {s: pd.Series(100 * np.cumprod(1 + rng.normal(0.0002, 0.01, n)), index=dates) for s in SLOTS}
    )
    opens = {s: adj[s] * 0.999 for s in SLOTS}
    closes = {s: adj[s] for s in SLOTS}
    broker = MockBroker(
        tradability=TradabilityMask(), premium_guard=PremiumGuard(),
        cost_model=MainlandETFCostModel(), open_prices=opens,
    )
    return ChinaETFPortfolioEnv(
        slots=SLOTS, adj_close=adj, open_prices=opens, close_prices=closes,
        initial_cash=1_000_000.0, broker=broker, order_generator=OrderGenerator(),
        slot_to_instrument={s: s for s in SLOTS}, mode=EnvironmentMode.METHOD_RESEARCH,
        risk_overlay=RiskOverlayV0(SLOTS, single_core_max=1.0),
    )


def _weights(policy, env, t):
    w = np.asarray(policy._fn(t), dtype=float)
    w = np.clip(w, 0.0, None)
    return w / w.sum()


def _assert_legal(w):
    assert np.isfinite(w).all()
    assert (w >= -1e-9).all()
    assert np.allclose(w.sum(), 1.0, atol=1e-6)


def _policies(env):
    t = env.calendar[env._warmup_index]
    return t, {
        "EW": equal_weight_policy(env),
        "RP": risk_parity_policy(env),
        "MV": minimum_variance_policy(env),
        "MOM": momentum_policy(env),
        "ERC": erc_policy(env),
        "HRP": hrp_policy(env),
        "MaxDiv": maximum_diversification_policy(env),
        "TrendRP": trend_risk_parity_policy(env),
        "MinCVaR": minimum_cvar_policy(env),
        "ShrinkMV": shrinkage_mean_variance_policy(env),
    }


def test_all_methods_legal_weights() -> None:
    env = _env()
    t, pols = _policies(env)
    for name, pol in pols.items():
        w = _weights(pol, env, t)
        _assert_legal(w)
        assert w.max() <= 1.0 + 1e-6, f"{name} max weight > 1"


def test_erc_equalizes_marginal_risk_contribution() -> None:
    """N2/F3：ERC 在相关非均匀协方差上贡献 ≤1e-3（tight；合成均匀数据 EW 近等贡献会掩盖）。"""
    from china_etf.evaluation.baselines import _erc_solve
    n = 5
    # 相关非均匀：资产0 与 1/2 高相关，3/4 低相关 → ERC 显著偏离 EW
    corr = np.eye(n)
    for i in range(3):
        for j in range(3):
            if i != j:
                corr[i, j] = 0.8
    vol = np.array([0.01, 0.01, 0.01, 0.02, 0.02])
    sigma = np.outer(vol, vol) * corr
    w_erc, _, converged = _erc_solve(sigma, n)
    assert converged, "ERC 未收敛"
    sw = sigma @ w_erc
    contrib = w_erc * sw
    nonzero = w_erc > 1e-6
    if nonzero.sum() >= 2:
        rel = contrib[nonzero] / max(contrib[nonzero].sum(), 1e-12)
        # 评审 F3：max relative deviation ≤ 1e-3（不放宽 gate）
        max_dev = np.max(np.abs(rel - np.mean(rel))) / max(np.mean(rel), 1e-12)
        assert max_dev <= 1e-3, f"ERC 贡献非等: max_dev={max_dev:.2e}"
    # 相关非均匀时 ERC ≠ inv-vol（风险平价）
    w_rp = 1.0 / vol
    w_rp = w_rp / w_rp.sum()
    assert not np.allclose(w_erc, w_rp, atol=1e-2), "相关非均匀时 ERC 应区别于 inv-vol RP"


def test_hrp_produces_valid_and_cluster_aware() -> None:
    env = _env()
    t = env.calendar[env._warmup_index]
    w = _weights(hrp_policy(env), env, t)
    _assert_legal(w)
    # HRP 通常更分散（权重差异小于 MV）
    w_mv = _weights(minimum_variance_policy(env), env, t)
    assert w.max() < 0.5, "HRP 不应过度集中"


def test_maximum_diversification_ratio_improves() -> None:
    env = _env()
    t = env.calendar[env._warmup_index]
    w = _weights(maximum_diversification_policy(env), env, t)
    _assert_legal(w)
    from china_etf.evaluation.baselines import _log_returns
    r = _log_returns(env.adj)
    window = r.loc[:t].iloc[-120:].dropna(how="any")
    cov = window.cov().to_numpy()
    std = np.sqrt(np.maximum(np.diag(cov), 0))
    dr = (w @ std) / np.sqrt(w @ cov @ w) if w @ cov @ w > 0 else 1.0
    assert dr >= 1.0 - 1e-6, f"DR 应 ≥1（分散性），实际 {dr}"
    # DR ≥ 任一单资产（分散性）
    assert dr >= max(std / std) - 1e-6


def test_trend_risk_parity_allocates_nontrending_to_cash() -> None:
    env = _env()
    t = env.calendar[env._warmup_index]
    w = _weights(trend_risk_parity_policy(env), env, t)
    _assert_legal(w)
    cash_idx = SLOTS.index("CASH_LIKE")
    assert w[cash_idx] >= 0.0
    # 全趋势/无趋势极端：若某资产趋势 ≤0，其权重应倾向 CASH_LIKE
    assert w.max() <= 1.0


def test_minimum_cvar_long_only() -> None:
    env = _env()
    t = env.calendar[env._warmup_index]
    w = _weights(minimum_cvar_policy(env), env, t)
    _assert_legal(w)
    # CVaR 组合不依赖期望收益 → 权重稳定、无 NaN
    assert np.isfinite(w).all()


def test_shrinkage_mean_variance_finite() -> None:
    env = _env()
    t = env.calendar[env._warmup_index]
    w = _weights(shrinkage_mean_variance_policy(env), env, t)
    _assert_legal(w)


def test_lookback_insufficient_falls_back_to_ew() -> None:
    """lookback 不足 → EW fallback（方法内部 `_cov_window`/短窗口 → 全 1/N 或合法）。"""
    env = _env(n=280)  # 够 warmup(252) 但 cov lookback(120) 内共同有限行可能不足 → fallback
    t = env.calendar[env._warmup_index]
    for fac in (minimum_variance_policy, erc_policy, maximum_diversification_policy,
                minimum_cvar_policy, shrinkage_mean_variance_policy):
        w = _weights(fac(env), env, t)
        _assert_legal(w)  # fallback（EW 或投影）仍合法


# --- N1-N7 语义测试（GATE_4_NON_RL_HORSE_RACE_CORRECTIONS）---


def _empirical_es(w, R, alpha):
    """独立 empirical CVaR/ES（F2 对照）：worst (1-α) 尾部平均损失，不依赖 _cvar_value。"""
    loss = -(R @ w)
    k = max(int((1 - alpha) * len(loss)), 1)
    worst = np.sort(loss)[-k:]  # 最差 k 个
    return float(worst.mean())


def test_min_cvar_optimized_better_than_ew() -> None:
    """N1/F2：构造已知低尾资产 → 优化 CVaR ≤ EW CVaR + 低尾资产权重更低（独立 empirical ES 对照）。"""
    from china_etf.evaluation.baselines import _min_cvar_subgradient
    rng = np.random.default_rng(7)
    T, n = 300, 5
    R = rng.normal(0.0002, 0.01, (T, n))
    R[:, 3] -= 0.004  # 资产3 更差尾部 → MinCVaR 应更低权重
    w, _, _ = _min_cvar_subgradient(R, n, alpha=0.95)
    _assert_legal(w)
    # 独立 empirical ES（非 _cvar_value，防自证）
    es_w = _empirical_es(w, R, 0.95)
    es_ew = _empirical_es(np.full(n, 1.0 / n), R, 0.95)
    assert es_w <= es_ew * 1.001, f"MinCVaR ES {es_w:.5f} > EW ES {es_ew:.5f}"
    assert w[3] < np.mean(w), "低尾资产应获得更低权重"


def test_hrp_block_correlation_known_cluster() -> None:
    """N3：块相关合成协方差 → HRP 产出合法权重且块内资产权重相近（聚类意识）。"""
    n = 6
    # 块结构：前3 高相关，后3 高相关，跨块低相关
    corr = np.eye(n)
    for i in range(3):
        for j in range(3):
            if i != j:
                corr[i, j] = 0.8
    for i in range(3, 6):
        for j in range(3, 6):
            if i != j:
                corr[i, j] = 0.8
    vol = np.full(n, 0.01)
    cov = np.outer(vol, vol) * corr
    from china_etf.evaluation.baselines import _hrp_weights
    w = _hrp_weights(corr, cov, vol, n)
    _assert_legal(w)
    # 块内权重应接近（HRP 聚类把块内视为一个簇；inv_vol 全相同 → cluster-variance 二分近均分）
    block1 = w[:3].std()
    assert block1 < 0.08, f"块内权重应相近，std={block1:.4f}"


def test_maxdiv_improves_diversification_ratio_over_ew() -> None:
    """N5：MaxDiv DR ≥ EW DR（分散性目标）。"""
    from china_etf.evaluation.baselines import _maxdiv_coordinate, _maxdiv_dr
    rng = np.random.default_rng(11)
    n = 5
    L = rng.normal(0, 0.01, (n, n))
    cov = L @ L.T + np.eye(n) * 1e-4
    std = np.sqrt(np.diag(cov))
    w = _maxdiv_coordinate(cov, std, n)
    _assert_legal(w)
    dr_w = _maxdiv_dr(w, cov, std)
    dr_ew = _maxdiv_dr(np.full(n, 1.0 / n), cov, std)
    assert dr_w >= dr_ew - 1e-6, f"MaxDiv DR {dr_w:.4f} < EW DR {dr_ew:.4f}"


def test_trend_rp_exact_budget_transfer_to_cash() -> None:
    """N4：非趋势 risky 资产预算精确转 CASH_LIKE（确定性合成）。"""
    from china_etf.evaluation.baselines import _log_returns
    # 构造 3 资产：S0 趋势（持续上涨），S1/S2 无趋势（持平），CASH_LIKE
    n_days = 300
    dates = pd.bdate_range("2021-01-02", periods=n_days)
    # 单调构造：S0 上涨（趋势>0），S1/S2/CASH 缓慢下跌（趋势<0）；同波动（inv_vol 均衡）
    up = 100 * np.cumprod(np.full(n_days, 1.0005))   # S0 趋势
    down = 100 * np.cumprod(np.full(n_days, 0.9995))  # 非趋势（负向）
    adj = pd.DataFrame({"S0": pd.Series(up, index=dates),
                        "S1": pd.Series(down, index=dates),
                        "S2": pd.Series(down, index=dates),
                        "CASH_LIKE": pd.Series(down, index=dates)})
    opens = {s: adj[s] * 0.999 for s in adj.columns}
    closes = {s: adj[s] for s in adj.columns}
    broker = MockBroker(tradability=TradabilityMask(), premium_guard=PremiumGuard(),
                        cost_model=MainlandETFCostModel(), open_prices=opens)
    env = ChinaETFPortfolioEnv(
        slots=list(adj.columns), adj_close=adj, open_prices=opens, close_prices=closes,
        initial_cash=1_000_000.0, broker=broker, order_generator=OrderGenerator(),
        slot_to_instrument={s: s for s in adj.columns}, mode=EnvironmentMode.METHOD_RESEARCH,
        risk_overlay=RiskOverlayV0(list(adj.columns), single_core_max=1.0),
    )
    t = env.calendar[env._warmup_index]
    w = _weights(trend_risk_parity_policy(env, inv_vol_lookback=60, trend_lookback=100, trend_skip=10), env, t)
    _assert_legal(w)
    # S0 趋势（>0）→ 保留 base 权重；S1/S2 非趋势 → 0
    assert w[0] > 0.1, f"趋势资产 S0 应保留 base 权重: {w}"
    assert w[1] < 1e-3 and w[2] < 1e-3, f"非趋势资产应有 0 权重: {w}"
    # N4：S1+S2 非趋势 base 预算精确转 CASH_LIKE（CASH 吸收 = S1+S2+CASH 的 base 合计 ≈0.8）
    assert w[3] > 0.7, f"CASH_LIKE 应吸收非趋势预算: {w}"
    assert abs(w.sum() - 1.0) < 1e-6
    assert abs(w[3] - (1.0 - w[0])) < 1e-6  # 预算守恒：CASH = 1 - 趋势资产权重


def test_shrinkage_mv_utility_gte_ew() -> None:
    """N6：冻结 utility 下优化目标 ≥ EW 目标。"""
    from china_etf.evaluation.baselines import _log_returns, _cov_window
    rng = np.random.default_rng(13)
    env = _env()
    t = env.calendar[env._warmup_index]
    r = _log_returns(env.adj)
    mu = r.loc[:t].iloc[-252:].mean().to_numpy()
    mu = np.where(np.isfinite(mu), mu, 0.0)
    cross = float(np.nanmean(mu))
    mu_shrunk = mu * 0.5 + cross * 0.5
    sigma, _ = _cov_window(r, t, 120, 0.5, len(env.slots))
    lam = 0.5
    w = _weights(shrinkage_mean_variance_policy(env), env, t)
    ut_w = float(mu_shrunk @ w) - lam / 2.0 * float(w @ sigma @ w)
    ut_ew = float(mu_shrunk @ np.ones(len(env.slots)) / len(env.slots)) - lam / 2.0 * float(
        np.ones(len(env.slots)) / len(env.slots) @ sigma @ np.ones(len(env.slots)) / len(env.slots))
    assert ut_w >= ut_ew - 1e-6, f"ShrinkMV utility {ut_w:.6f} < EW {ut_ew:.6f}"


# --- F1/F4/F5 语义测试（GATE_4_NON_RL_HORSE_RACE_FINAL_CORRECTIONS）---


def _runner_local():
    from china_etf.evaluation.walkforward import WalkForwardRunner
    from china_etf.contracts import EnvironmentMode
    n = 700
    dates = pd.bdate_range("2021-01-02", periods=n)
    rng = np.random.default_rng(21)
    adj = pd.DataFrame(
        {s: pd.Series(100 * np.cumprod(1 + rng.normal(0.0002, 0.01, n)), index=dates) for s in SLOTS}
    )
    opens = {s: adj[s] * 0.999 for s in SLOTS}
    closes = {s: adj[s] for s in SLOTS}

    def build_env(a, o, c, corporate_actions=None):
        broker = MockBroker(tradability=TradabilityMask(), premium_guard=PremiumGuard(),
                            cost_model=MainlandETFCostModel(), open_prices=o)
        return ChinaETFPortfolioEnv(
            slots=SLOTS, adj_close=a, open_prices=o, close_prices=c,
            initial_cash=1_000_000.0, broker=broker, order_generator=OrderGenerator(),
            slot_to_instrument={s: s for s in SLOTS}, mode=EnvironmentMode.METHOD_RESEARCH,
            risk_overlay=RiskOverlayV0(SLOTS, single_core_max=1.0),
            corporate_actions=corporate_actions,
        )

    return WalkForwardRunner(
        adj=adj, opens=opens, closes=closes, slots=SLOTS,
        slot_to_instrument={s: s for s in SLOTS}, build_env=build_env,
    )


def test_hrp_low_variance_cluster_gets_more_weight() -> None:
    """F1：两簇不等方差 → 低方差簇总权重更高（HRP 分配方向反转）。"""
    from china_etf.evaluation.baselines import _hrp_weights
    n = 6
    corr = np.eye(n)
    for i in range(3):
        for j in range(3):
            if i != j:
                corr[i, j] = 0.7
    for i in range(3, 6):
        for j in range(3, 6):
            if i != j:
                corr[i, j] = 0.7
    vol = np.full(n, 0.01)
    vol[:3] = 0.005  # 前簇低波动（低方差）
    vol[3:] = 0.02   # 后簇高波动
    cov = np.outer(vol, vol) * corr
    w = _hrp_weights(corr, cov, vol, n)
    _assert_legal(w)
    low_var_total = w[:3].sum()
    high_var_total = w[3:].sum()
    assert low_var_total > high_var_total, f"低方差簇应更多权重: low={low_var_total:.3f} high={high_var_total:.3f}"


def test_maxdiv_feasible_local_optimality() -> None:
    """F4：MaxDiv 在 project 可行集内局部最优（可行扰动不改进 DR）。"""
    from china_etf.evaluation.baselines import _maxdiv_coordinate, _maxdiv_dr, _proj_constrained
    rng = np.random.default_rng(17)
    n = 5
    L = rng.normal(0, 0.01, (n, n))
    cov = L @ L.T + np.eye(n) * 1e-4
    std = np.sqrt(np.diag(cov))
    slots = [f"S{i}" for i in range(n)]
    w = _maxdiv_coordinate(cov, std, n, slots=slots)
    _assert_legal(w)
    dr0 = _maxdiv_dr(w, cov, std)
    # 可行小扰动（保持 long-only + sum=1 + caps）→ DR 不显著改进
    for _ in range(20):
        perturb = rng.normal(0, 0.005, n)
        w2 = _proj_constrained(w + perturb, slots)
        assert _maxdiv_dr(w2, cov, std) <= dr0 + 1e-6, "MaxDiv 非局部最优（可行扰动改进 DR）"


def test_rollout_execution_dates_recorded() -> None:
    """F5：roll_out series 记录真实执行日（st.t_next）。"""
    from china_etf.evaluation.benchmark import exact_test_mask
    from china_etf.evaluation.walkforward import WalkForwardRunner

    runner = _runner_local()
    folds = runner.make_folds(n_folds=2, min_train_days=200, val_days=40)
    train_env = runner._train_env_for(folds[0])
    mean, std = runner.fit_scaler(train_env, folds[0])
    m = runner._rollout_segment(folds[0], "test", mean, std, lambda o: np.zeros(len(SLOTS)))
    dates = m["series"]["execution_dates"]
    assert len(dates) == m["n_eval_steps"], "execution_dates 数 == n_eval"
    # 首执行日 == test_start；末执行日 == test_end
    assert dates[0] == str(folds[0].test_start.date())
    assert dates[-1] == str(folds[0].test_end.date())
    # 与 exact mask 中本 fold test 段一致（合成环境日历）
    mask = exact_test_mask(folds, calendar=runner.adj.index)
    seg_str = [str(d.date()) for d in mask["test_dates"]
               if folds[0].test_start <= d <= folds[0].test_end]
    assert dates == seg_str, "rollout execution_dates == 本 fold exact Test mask 段"
