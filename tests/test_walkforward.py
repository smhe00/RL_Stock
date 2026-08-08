"""GATE_4_PILOT_READY — WalkForwardRunner / baselines / rollout 归一化（合成数据，快速）。"""

import numpy as np
import pandas as pd
import pytest

from china_etf.contracts import EnvironmentMode
from china_etf.cost.mainland import MainlandETFCostModel
from china_etf.environment.action_transform import ActionTransform
from china_etf.environment.gym_wrapper import ChinaETFGymEnv
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


def _synthetic(n=1000, seed=7, late_listing=None):
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

    def build_env(a, o, c, corporate_actions=None):
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
            corporate_actions=corporate_actions,
        )

    return adj, opens, closes, build_env


def _runner(n=1000, seed=7):
    adj, opens, closes, build_env = _synthetic(n=n, seed=seed)
    return WalkForwardRunner(
        adj=adj, opens=opens, closes=closes, slots=SLOTS,
        slot_to_instrument={s: s for s in SLOTS}, build_env=build_env,
    )


def _gym_for(env, mean, std):
    gym = ChinaETFGymEnv(env)
    gym.set_market_scaler(np.asarray(mean, dtype=np.float32), np.asarray(std, dtype=np.float32))
    return gym


# --- make_folds ---


def test_make_folds_partition_non_overlapping_expanding() -> None:
    runner = _runner()
    folds = runner.make_folds(n_folds=2, min_train_days=200, val_days=40)
    assert len(folds) == 2
    f1, f2 = folds
    # train → val → test 严格顺序，无重叠
    assert f1.train_end < f1.val_start < f1.val_end < f1.test_start
    assert f2.train_end < f2.val_start < f2.val_end < f2.test_start
    # fold 间无重叠
    assert f1.test_end < f2.test_start
    # expanding：train/val 终点递增
    assert f1.train_end < f2.train_end
    assert f1.val_end < f2.val_end
    # 覆盖决策区间末尾
    decision = runner.adj.index[runner.adj.index >= runner.decision_start]
    assert f2.test_end == decision[-1]
    assert f1.train_start == decision[0]


def test_make_folds_insufficient_region_raises() -> None:
    runner = _runner(n=400)
    with pytest.raises(ValueError):
        runner.make_folds(n_folds=4, min_train_days=200, val_days=40)


# --- scaler fold isolation ---


def test_fold_scaler_fit_train_only() -> None:
    """scaler 只 fit 于 fold train 决策区间；val/test 数据不进入统计。"""
    runner = _runner()
    folds = runner.make_folds(n_folds=2, min_train_days=200, val_days=40)
    f1 = folds[0]
    train_env = runner._train_env_for(f1)
    mean, std = runner.fit_scaler(train_env, f1)
    assert mean.shape == (MARKET_DIM,)
    market = train_env.market_feature_frame()
    region = market.index[(market.index >= f1.train_start) & (market.index <= f1.train_end)]
    assert np.allclose(mean, market.loc[region].mean().to_numpy(), atol=1e-12)
    # 含 val 的更宽统计必须 ≠ train-only（证明 val 行被排除）
    broad = runner._build_env_upto(f1.val_end).market_feature_frame()
    broad_region = broad.index[(broad.index >= f1.train_start) & (broad.index <= f1.val_end)]
    assert not np.allclose(mean, broad.loc[broad_region].mean().to_numpy(), atol=1e-6)


# --- rollout 归一化 ---


def test_rollout_policy_sees_normalized_obs() -> None:
    """policy 输入必须是归一化 obs（修复 gate3 sanity 直接喂 raw 的问题）。"""
    runner = _runner()
    folds = runner.make_folds(n_folds=2, min_train_days=200, val_days=40)
    f1 = folds[0]
    env_te = runner._build_env_upto(f1.test_end)
    gym_te = _gym_for(env_te, np.full(MARKET_DIM, 1000.0), np.ones(MARKET_DIM))
    seen = []

    def spy(obs):
        seen.append(obs.copy())
        raw_now = env_te._observe(env_te.calendar[env_te._i])
        assert np.allclose(obs[MARKET_POS], raw_now[MARKET_POS] - 1000.0, atol=1e-2)
        assert np.allclose(obs[W_POS], raw_now[W_POS], atol=1e-9)  # weights 不归一化
        return np.zeros(len(SLOTS))

    roll_out(env_te, gym_te, spy, f1.test_start, SLOTS)
    assert len(seen) > 0


def test_training_and_evaluation_share_same_observation_transform() -> None:
    """train 与 eval 用同一 normalize 变换：同一 raw obs → 相同归一化输出。"""
    runner = _runner()
    folds = runner.make_folds(n_folds=2, min_train_days=200, val_days=40)
    f1 = folds[0]
    train_env = runner._train_env_for(f1)
    mean, std = runner.fit_scaler(train_env, f1)
    gym_tr = _gym_for(train_env, mean, std)
    # val env 用同一 train scaler → 对 train 区间内同一天 raw obs 输出必须逐位一致
    val_env = runner._build_env_upto(f1.val_end)
    gym_va = _gym_for(val_env, mean, std)
    d = f1.val_start
    raw = val_env._observe(d)
    assert np.array_equal(gym_va._normalize(raw), gym_tr._normalize(raw))


# --- runner baseline smoke ---


def test_runner_ew_smoke_synthetic() -> None:
    runner = _runner()
    folds = runner.make_folds(n_folds=2, min_train_days=200, val_days=40)
    m = runner.run_fold_baseline(folds[1], equal_weight_policy)
    assert m["test"]["n_eval_steps"] > 0
    assert m["test"]["nan_obs_or_reward"] == 0
    assert np.isfinite(m["test"]["oos_cum_return"])
    assert m["fold"] == "F2"
    assert m["kind"] == "baseline"


# --- baselines 权重性质 ---


def test_inverse_action_transform_recovers_target() -> None:
    """a = 2w - 1 → ActionTransform(score=w) → 目标权重（含 0 权重可表达）。"""
    runner = _runner()
    folds = runner.make_folds(n_folds=2, min_train_days=200, val_days=40)
    env = runner._build_env_upto(folds[0].val_end)
    tr = ActionTransform(SLOTS)
    w = np.array([0.0, 0.2, 0.3, 0.0, 0.5])
    t = env.calendar[env._i]
    out = tr.transform(2.0 * w - 1.0, t).weights.to_numpy()
    assert np.allclose(out, w, atol=1e-9)


def test_baseline_target_action_roundtrip() -> None:
    """评审 §26：baseline target weight → 逆 ActionTransform → ActionTransform → 同权重。"""
    runner = _runner()
    folds = runner.make_folds(n_folds=2, min_train_days=200, val_days=40)
    env = runner._build_env_upto(folds[1].val_end)
    tr = ActionTransform(SLOTS)
    for fac in (equal_weight_policy, risk_parity_policy, minimum_variance_policy, momentum_policy):
        pol = fac(env)
        t = env.calendar[env._warmup_index]  # warmup 后有效决策日（特征全 finite）
        w = np.asarray(pol._fn(t), dtype=float)
        assert np.isfinite(w).all(), f"{fac.__name__} weights not finite"
        w = np.clip(w, 0.0, None)
        w = w / w.sum()
        out = tr.transform(2.0 * w - 1.0, t).weights.to_numpy()
        assert np.allclose(out, w, atol=1e-6), f"{fac.__name__} roundtrip failed"


def test_baseline_risk_parity_weights_sum_to_one() -> None:
    runner = _runner()
    folds = runner.make_folds(n_folds=2, min_train_days=200, val_days=40)
    env_te = runner._build_env_upto(folds[1].test_end)
    gym_te = _gym_for(env_te, np.zeros(MARKET_DIM), np.ones(MARKET_DIM))
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
    folds = runner.make_folds(n_folds=2, min_train_days=200, val_days=40)
    env_te = runner._build_env_upto(folds[1].test_end)
    gym_te = _gym_for(env_te, np.zeros(MARKET_DIM), np.ones(MARKET_DIM))
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
    folds = runner.make_folds(n_folds=2, min_train_days=200, val_days=40)
    f1 = folds[0]
    env_te = runner._build_env_upto(f1.val_end)
    pol = momentum_policy(env_te)
    t = env_te.calendar[env_te._i]
    w_before = pol._fn(t).copy()
    future = env_te.adj.index[env_te.adj.index > t]
    env_te.adj.loc[future] = 0.0
    w_after = pol._fn(t)
    assert np.allclose(w_before, w_after)


# --- t→t+1 边界（WF2）---


def test_train_last_decision_does_not_use_validation_price() -> None:
    """train env 数据止于 train_end（val_start 前一交易日）；末决策执行不到 val 首日。"""
    runner = _runner()
    folds = runner.make_folds(n_folds=2, min_train_days=200, val_days=40)
    f1 = folds[0]
    train_env = runner._train_env_for(f1)
    assert train_env.calendar[-1] < f1.val_start  # train env 不含任何 val 行
    # 末决策 = len-2 行，执行于 len-1（train_end），不是 val_start
    assert train_env.calendar[-1] == f1.train_end
    assert f1.train_end < f1.val_start


def test_validation_last_decision_does_not_use_test_price() -> None:
    """val env 数据止于 val_end（test_start 前一交易日）；末决策执行不到 test 首日。"""
    runner = _runner()
    folds = runner.make_folds(n_folds=2, min_train_days=200, val_days=40)
    f1 = folds[0]
    val_env = runner._build_env_upto(f1.val_end)
    assert val_env.calendar[-1] == f1.val_end
    assert f1.val_end < f1.test_start


def test_test_decision_count_equals_calendar_rows_minus_one() -> None:
    """test 段决策数 = 日历行数 - 1（末行 = terminal mark，非决策）。"""
    runner = _runner()
    folds = runner.make_folds(n_folds=2, min_train_days=200, val_days=40)
    f1 = folds[0]
    test_env = runner._build_env_upto(f1.test_end)
    cal = pd.DatetimeIndex(test_env.calendar)
    decision_rows = cal[cal >= f1.test_start]
    # 决策步数 = 测试区行数 - 1（最后一行为 mark）
    m = runner._rollout_segment(
        f1, "test", np.zeros(MARKET_DIM), np.ones(MARKET_DIM),
        equal_weight_policy(test_env),
    )
    assert m["n_eval_steps"] == len(decision_rows) - 1


def test_fold_segment_terminal_mark_semantics() -> None:
    """末行是 terminal mark：val/test 末决策的执行日 < 下段首日，且 test_end 是 mark。"""
    runner = _runner()
    folds = runner.make_folds(n_folds=2, min_train_days=200, val_days=40)
    f1 = folds[0]
    test_env = runner._build_env_upto(f1.test_end)
    # test env 的最后一行 test_end 是 mark；若继续 step 应返回 done=True
    env = test_env
    env.reset()
    done = False
    while not done:
        _, _, done, _ = env.step(np.zeros(len(SLOTS)))
    assert done
    # 最后一步决策时间 < test_end（决策于 test_end 前一日）
    assert env._i == len(env.calendar) - 1
