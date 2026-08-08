"""GATE_4_PRECHECK — WalkForwardRunner / baselines / rollout 归一化（合成数据，快速）。"""

import numpy as np
import pandas as pd
import pytest

from china_etf.contracts import EnvironmentMode
from china_etf.cost.mainland import MainlandETFCostModel
from china_etf.environment.action_transform import ActionTransform
from china_etf.environment.portfolio_env import ChinaETFPortfolioEnv
from china_etf.evaluation.baselines import (
    equal_weight_policy,
    minimum_variance_policy,
    momentum_policy,
    risk_parity_policy,
)
from china_etf.evaluation.rollout import roll_out
from china_etf.evaluation.walkforward import WalkForwardRunner, make_folds
from china_etf.execution.broker.mock import MockBroker
from china_etf.execution.order_generator import OrderGenerator
from china_etf.execution.premium import PremiumGuard
from china_etf.execution.tradability import TradabilityMask

SLOTS = ["S0", "S1", "S2", "S3", "S4"]
_N = len(SLOTS)
MARKET_POS = list(range(8 * _N)) + list(range(8 * _N + _N, 8 * _N + _N + 5))  # [0:40]∪[45:50]
W_POS = list(range(8 * _N, 8 * _N + _N))  # [40:45]
MARKET_DIM = len(MARKET_POS)  # 8N+5 = 45


def _synthetic(n=600, seed=7, late_listing=None):
    dates = pd.bdate_range("2021-01-02", periods=n)
    rng = np.random.default_rng(seed)
    adj = pd.DataFrame(
        {s: pd.Series(100 * np.cumprod(1 + rng.normal(0.0002, 0.01, n)), index=dates) for s in SLOTS}
    )
    if late_listing:  # 例如 {"S2": "2021-06-01"}：该槽位上市前 NaN
        for s, first in late_listing.items():
            adj.loc[adj.index < pd.Timestamp(first), s] = np.nan
    opens = {s: adj[s] * 0.999 for s in SLOTS}
    closes = {s: adj[s] for s in SLOTS}

    def build_env(a, o, c):
        broker = MockBroker(
            tradability=TradabilityMask(),
            premium_guard=PremiumGuard(),
            cost_model=MainlandETFCostModel(),
            open_prices=o,
        )
        return ChinaETFPortfolioEnv(
            slots=SLOTS, adj_close=a, open_prices=o, close_prices=c,
            initial_cash=1_000_000.0, broker=broker, order_generator=OrderGenerator(),
            slot_to_instrument={s: s for s in SLOTS}, mode=EnvironmentMode.METHOD_RESEARCH,
        )

    return adj, opens, closes, build_env


def _runner(n=600, seed=7):
    adj, opens, closes, build_env = _synthetic(n=n, seed=seed)
    return WalkForwardRunner(
        adj=adj, opens=opens, closes=closes, slots=SLOTS,
        slot_to_instrument={s: s for s in SLOTS}, build_env=build_env,
    )


# --- make_folds ---


def test_make_folds_partition_non_overlapping_expanding() -> None:
    runner = _runner()
    folds = runner.make_folds(n_folds=2, min_train_days=200, test_days=70)
    assert len(folds) == 2
    f1, f2 = folds
    # 严格无重叠：train 区到 train_end，test 区从 test_start 开始，train_end < test_start
    assert f1.train_end < f1.test_start
    assert f2.train_end < f2.test_start
    assert f1.test_end < f2.test_start  # fold 间测试区也不重叠
    # expanding：train_end 递增
    assert f1.train_end < f2.train_end
    # 覆盖决策区间末尾
    decision = runner.adj.index[runner.adj.index >= runner.decision_start]
    assert f2.test_end == decision[-1]
    assert f1.train_start == decision[0]


def test_make_folds_insufficient_region_raises() -> None:
    runner = _runner(n=300)
    with pytest.raises(ValueError):
        runner.make_folds(n_folds=4, min_train_days=300)


# --- scaler fold isolation ---


def test_fold_scaler_fit_train_only() -> None:
    """scaler 只 fit 于 fold train 决策区间；test 区间数据不进入统计。"""
    runner = _runner()
    folds = runner.make_folds(n_folds=2, min_train_days=200, test_days=70)
    f1 = folds[0]
    train_env = runner._train_env_for(f1)
    mean, std = runner.fit_scaler(train_env, f1)
    assert mean.shape == (MARKET_DIM,)
    # train 区外生特征手工均值 == fit 结果
    market = train_env.market_feature_frame()
    region = market.index[(market.index >= f1.train_start) & (market.index <= f1.train_end)]
    assert np.allclose(mean, market.loc[region].mean().to_numpy(), atol=1e-12)
    assert np.allclose(std, market.loc[region].std().to_numpy().clip(min=1e-8), atol=1e-8)
    # 包含 test 数据的更宽统计必须 ≠ train-only（证明 test 行被排除）
    test_env = runner._test_env_for(f1, mean, std)[0]
    broad = test_env.market_feature_frame()
    broad_region = broad.index[(broad.index >= f1.train_start) & (broad.index <= f1.test_end)]
    broad_mean = broad.loc[broad_region].mean().to_numpy()
    assert not np.allclose(mean, broad_mean, atol=1e-6)


# --- rollout 归一化 ---


def test_rollout_policy_sees_normalized_obs() -> None:
    """policy 输入必须是归一化 obs（修复 gate3 sanity 直接喂 raw 的问题）。"""
    from china_etf.environment.gym_wrapper import ChinaETFGymEnv

    runner = _runner()
    folds = runner.make_folds(n_folds=2, min_train_days=200, test_days=70)
    f1 = folds[0]
    env_te, gym_te = runner._test_env_for(
        f1, np.full(MARKET_DIM, 1000.0), np.ones(MARKET_DIM, dtype=np.float64)
    )
    seen = []

    def spy(obs):
        seen.append(obs.copy())
        raw_now = env_te._observe(env_te.calendar[env_te._i])
        assert np.allclose(obs[MARKET_POS], raw_now[MARKET_POS] - 1000.0, atol=1e-2)
        assert np.allclose(obs[W_POS], raw_now[W_POS], atol=1e-9)  # weights 不归一化
        return np.zeros(len(SLOTS))

    roll_out(env_te, gym_te, spy, f1.test_start, SLOTS)
    assert len(seen) > 0


# --- runner baseline smoke ---


def test_runner_ew_smoke_synthetic() -> None:
    runner = _runner()
    folds = runner.make_folds(n_folds=2, min_train_days=200, test_days=70)
    m = runner.run_fold_baseline(folds[1], equal_weight_policy)
    assert m["n_eval_steps"] > 0
    assert m["nan_obs_or_reward"] == 0
    assert np.isfinite(m["oos_cum_return"])
    assert m["fold"] == "F2"


# --- baselines 权重性质 ---


def test_inverse_action_transform_recovers_target() -> None:
    """a = 2w - 1 → ActionTransform(score=w) → 目标权重（含 0 权重可表达）。"""
    env = _runner()._test_env_for(
        _runner().make_folds(n_folds=2, min_train_days=200, test_days=70)[0],
        np.zeros(MARKET_DIM), np.ones(MARKET_DIM),
    )[0]
    tr = ActionTransform(SLOTS)
    w = np.array([0.0, 0.2, 0.3, 0.0, 0.5])
    t = env.calendar[env._i]
    out = tr.transform(2.0 * w - 1.0, t).weights.to_numpy()
    assert np.allclose(out, w, atol=1e-9)


def test_baseline_risk_parity_weights_sum_to_one() -> None:
    runner = _runner()
    folds = runner.make_folds(n_folds=2, min_train_days=200, test_days=70)
    env_te, gym_te = runner._test_env_for(folds[1], np.zeros(MARKET_DIM), np.ones(MARKET_DIM))
    pol = risk_parity_policy(env_te)
    env_te.reset()
    obs0 = gym_te._normalize(env_te._observe(env_te.calendar[env_te._i]))
    a = pol(obs0)
    tr = ActionTransform(SLOTS)
    w = tr.transform(a, env_te.calendar[env_te._i]).weights.to_numpy()
    assert np.allclose(w.sum(), 1.0, atol=1e-6)
    assert np.isfinite(w).all()


def test_baseline_minimum_variance_long_only() -> None:
    runner = _runner()
    folds = runner.make_folds(n_folds=2, min_train_days=200, test_days=70)
    env_te, gym_te = runner._test_env_for(folds[1], np.zeros(MARKET_DIM), np.ones(MARKET_DIM))
    pol = minimum_variance_policy(env_te)
    env_te.reset()
    obs0 = gym_te._normalize(env_te._observe(env_te.calendar[env_te._i]))
    a = pol(obs0)
    tr = ActionTransform(SLOTS)
    w = tr.transform(a, env_te.calendar[env_te._i]).weights.to_numpy()
    assert np.isfinite(w).all()
    assert (w >= -1e-9).all()  # long-only
    assert np.allclose(w.sum(), 1.0, atol=1e-6)


def test_baseline_momentum_no_lookahead() -> None:
    """momentum 只用 ≤t 数据：追加未来数据不改变 t 时刻权重（严格 PIT）。"""
    runner = _runner()
    folds = runner.make_folds(n_folds=2, min_train_days=200, test_days=70)
    f1 = folds[0]
    env_te, gym_te = runner._test_env_for(f1, np.zeros(MARKET_DIM), np.ones(MARKET_DIM))
    pol = momentum_policy(env_te)
    t = env_te.calendar[env_te._i]
    w_before = pol._fn(t).copy()
    # 篡改未来：t 之后全部归零（若 PIT，t 时刻权重必须不变）
    future = env_te.adj.index[env_te.adj.index > t]
    env_te.adj.loc[future] = 0.0
    w_after = pol._fn(t)
    assert np.allclose(w_before, w_after)
