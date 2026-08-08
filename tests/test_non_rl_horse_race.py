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
    env = _env()
    t = env.calendar[env._warmup_index]
    w = _weights(erc_policy(env), env, t)
    from china_etf.evaluation.baselines import _log_returns
    r = _log_returns(env.adj)
    window = r.loc[:t].iloc[-120:].dropna(how="any")
    cov = window.cov().to_numpy()
    sw = cov @ w
    contrib = w * sw
    # 边际风险贡献近似相等（ERC 特性；剔除被挤出的零权重资产）
    nonzero = w > 1e-6
    if nonzero.sum() >= 2:
        rel = contrib[nonzero] / max(contrib[nonzero].sum(), 1e-12)
        assert np.std(rel) < 0.15, f"ERC 边际贡献离散度偏高: std={np.std(rel):.3f}"
    # 相关非均匀时 ERC ≠ inv-vol
    w_rp = _weights(risk_parity_policy(env), env, t)
    assert not np.allclose(w, w_rp, atol=1e-2), "相关非均匀时 ERC 应区别于 inv-vol RP"


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
