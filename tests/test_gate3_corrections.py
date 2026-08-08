"""GATE_3_CORRECTIONS — ActionTransform / RiskOverlayV0 / env API / check_env。"""

import numpy as np
import pandas as pd
import pytest

from china_etf.environment.action_transform import ActionTransform
from china_etf.environment.gym_wrapper import ChinaETFGymEnv
from china_etf.risk.risk_overlay import InfeasibleConstraints, RiskOverlayV0

SLOTS = [
    "CN_LARGE", "CN_SMALL", "CN_DIVIDEND", "CHINEXT", "STAR", "HK_TECH",
    "HK_DIVIDEND", "US_BROAD", "GOLD", "CN_DURATION", "CASH_LIKE",
]
T = pd.Timestamp("2026-08-07")


# --- BLOCKER-1 ActionTransform ---


def test_action_transform_sum_to_one() -> None:
    at = ActionTransform(SLOTS)
    for _ in range(20):
        a = np.random.default_rng(0).uniform(-1, 1, len(SLOTS))
        taw = at.transform(a, T)
        assert np.isclose(taw.weights.sum(), 1.0)
        assert (taw.weights >= 0).all()


def test_action_transform_extreme_bounds() -> None:
    at = ActionTransform(SLOTS)
    a = np.full(len(SLOTS), -1.0)
    a[0] = 1.0
    w = at.transform(a, T).weights
    # V2 score transform：+1→score1，-1→score0 → raw 100% 单资产
    assert w.iloc[0] == pytest.approx(1.0, abs=1e-9)
    assert (w.iloc[1:] == 0).all()
    assert np.isclose(w.sum(), 1.0)


def test_action_transform_is_monotonic() -> None:
    at = ActionTransform(SLOTS)
    a = np.zeros(len(SLOTS))
    w0 = at.transform(a, T).weights
    a2 = a.copy()
    a2[0] = 0.5
    w1 = at.transform(a2, T).weights
    assert w1.iloc[0] > w0.iloc[0]
    assert (w1.iloc[1:] < w0.iloc[1:]).all()


def test_action_zero_maps_equal_weight() -> None:
    w = ActionTransform(SLOTS).transform(np.zeros(len(SLOTS)), T).weights
    assert np.allclose(w.values, 1.0 / len(SLOTS))


def test_action_minus_one_can_map_zero_weight() -> None:
    at = ActionTransform(SLOTS)
    a = np.full(len(SLOTS), 1.0)
    a[3] = -1.0
    w = at.transform(a, T).weights
    assert w.iloc[3] == pytest.approx(0.0, abs=1e-12)


def test_action_single_positive_can_create_sparse_raw_weight() -> None:
    at = ActionTransform(SLOTS)
    a = np.full(len(SLOTS), -1.0)
    a[0] = 1.0
    w = at.transform(a, T).weights
    assert w.max() == pytest.approx(1.0, abs=1e-9)  # sparse


def test_action_all_minus_one_fallback() -> None:
    at = ActionTransform(SLOTS)
    w = at.transform(np.full(len(SLOTS), -1.0), T).weights
    assert at.last_fallback == "DEGENERATE_ACTION_FALLBACK"
    assert np.allclose(w.values, 1.0 / len(SLOTS))
    assert np.isfinite(w.values).all()


def test_action_transform_no_nan() -> None:
    at = ActionTransform(SLOTS)
    rng = np.random.default_rng(0)
    for _ in range(100):
        w = at.transform(rng.uniform(-1, 1, len(SLOTS)), T).weights
        assert np.isfinite(w.values).all() and np.isclose(w.sum(), 1.0)


def test_action_transform_algorithm_neutral() -> None:
    at = ActionTransform(SLOTS)
    a = np.linspace(-1, 1, len(SLOTS))
    w1 = at.transform(a, T).weights
    w2 = at.transform(a.copy(), T).weights  # 同一输入 → 同一输出（与算法无关）
    pd.testing.assert_series_equal(w1, w2)


def test_action_space_is_normalized_symmetric() -> None:
    from china_etf.contracts import EnvironmentMode
    from china_etf.cost.mainland import MainlandETFCostModel
    from china_etf.environment.portfolio_env import ChinaETFPortfolioEnv
    from china_etf.execution.broker.mock import MockBroker
    from china_etf.execution.order_generator import OrderGenerator
    from china_etf.execution.premium import PremiumGuard
    from china_etf.execution.tradability import TradabilityMask
    from china_etf.risk.risk_overlay import RiskOverlayV0

    n = 300
    dates = pd.bdate_range("2025-01-02", periods=n)
    rng = np.random.default_rng(3)
    adj = pd.DataFrame({s: pd.Series(100 * np.cumprod(1 + rng.normal(0.0002, 0.01, n)), index=dates) for s in SLOTS[:3]})
    broker = MockBroker(
        tradability=TradabilityMask(), premium_guard=PremiumGuard(),
        cost_model=MainlandETFCostModel(), open_prices={s: adj[s] for s in SLOTS[:3]},
    )
    env = ChinaETFPortfolioEnv(
        slots=SLOTS[:3], adj_close=adj,
        open_prices={s: adj[s] for s in SLOTS[:3]},
        close_prices={s: adj[s] for s in SLOTS[:3]},
        initial_cash=1_000_000.0, broker=broker, order_generator=OrderGenerator(),
        slot_to_instrument={s: s for s in SLOTS[:3]},
        mode=EnvironmentMode.METHOD_RESEARCH,
        risk_overlay=RiskOverlayV0(SLOTS[:3], single_core_max=0.5),
    )
    gym = ChinaETFGymEnv(env)
    assert gym.action_space.shape == (3,)
    assert gym.observation_space.shape == (8 * 3 + 3 + 5,)
    assert np.allclose(gym.action_space.low, -1.0)
    assert np.allclose(gym.action_space.high, 1.0)


# --- BLOCKER-2 RiskOverlayV0 ---


def _overlay(**kw):
    return RiskOverlayV0(SLOTS, **kw)


def test_single_core_cap() -> None:
    raw = pd.Series(np.zeros(len(SLOTS)), index=SLOTS)
    raw["GOLD"] = 1.0
    w = _overlay().apply(raw)
    assert w.max() <= 0.25 + 1e-6


def test_china_growth_group_cap() -> None:
    raw = pd.Series(np.zeros(len(SLOTS)), index=SLOTS)
    raw["CHINEXT"] = 0.5
    raw["STAR"] = 0.5
    w = _overlay().apply(raw)
    assert w["CHINEXT"] + w["STAR"] <= 0.50 + 1e-6
    assert np.isclose(w.sum(), 1.0)


def test_projection_sum_to_one_and_caps_after_renormalization() -> None:
    rng = np.random.default_rng(7)
    for _ in range(200):
        raw = pd.Series(rng.uniform(0, 1, len(SLOTS)), index=SLOTS)
        w = _overlay().apply(raw)
        assert np.isclose(w.sum(), 1.0, atol=1e-6)
        assert (w >= 0).all() and (w <= 0.25 + 1e-6).all()
        if w["CHINEXT"] + w["STAR"] > 0.5 + 1e-6:
            raise AssertionError("growth cap violated")


def test_projection_idempotent() -> None:
    raw = pd.Series(np.random.default_rng(1).uniform(0, 1, len(SLOTS)), index=SLOTS)
    ov = _overlay()
    w1 = ov.apply(raw)
    w2 = ov.apply(w1)
    pd.testing.assert_series_equal(w1, w2, atol=1e-9)


def test_infeasible_constraints_raise() -> None:
    ov = RiskOverlayV0(["A", "B", "C", "D"], single_core_max=0.2)  # sum caps=0.8 < 1
    with pytest.raises(InfeasibleConstraints):
        ov.apply(pd.Series([0.25, 0.25, 0.25, 0.25], index=["A", "B", "C", "D"]))


def test_property_10000_random_actions() -> None:
    rng = np.random.default_rng(42)
    ov = _overlay()
    for _ in range(10_000):
        raw = pd.Series(rng.uniform(0, 1, len(SLOTS)), index=SLOTS)
        w = ov.apply(raw)
        assert w.max() <= 0.25 + 1e-6
        assert w["CHINEXT"] + w["STAR"] <= 0.50 + 1e-6
        assert np.isclose(w.sum(), 1.0, atol=1e-6)


def test_forced_risk_overlay_in_environment_transition() -> None:
    """action=[1,-1,...]：raw max≈1.0 → post-risk ≤0.25 → actual 遵守执行语义。"""
    from china_etf.contracts import EnvironmentMode
    from china_etf.cost.mainland import MainlandETFCostModel
    from china_etf.environment.portfolio_env import ChinaETFPortfolioEnv
    from china_etf.execution.broker.mock import MockBroker
    from china_etf.execution.order_generator import OrderGenerator
    from china_etf.execution.premium import PremiumGuard
    from china_etf.execution.tradability import TradabilityMask
    from china_etf.risk.risk_overlay import RiskOverlayV0

    slots = SLOTS  # 11 槽位，默认 overlay 0.25/0.50 可行
    n = 400
    dates = pd.bdate_range("2025-01-02", periods=n)
    rng = np.random.default_rng(9)
    adj = pd.DataFrame({s: pd.Series(100 * np.cumprod(1 + rng.normal(0.0002, 0.01, n)), index=dates) for s in slots})
    broker = MockBroker(
        tradability=TradabilityMask(), premium_guard=PremiumGuard(),
        cost_model=MainlandETFCostModel(), open_prices={s: adj[s] * 0.999 for s in slots},
    )
    env = ChinaETFPortfolioEnv(
        slots=slots, adj_close=adj,
        open_prices={s: adj[s] * 0.999 for s in slots},
        close_prices={s: adj[s] for s in slots},
        initial_cash=1_000_000.0, broker=broker, order_generator=OrderGenerator(),
        slot_to_instrument={s: s for s in slots},
        mode=EnvironmentMode.METHOD_RESEARCH,
        risk_overlay=RiskOverlayV0(slots),  # 默认 0.25/0.50
    )
    env.reset()
    a = np.full(len(slots), -1.0)
    a[0] = 1.0
    _, _, _, info = env.step(a)
    w = info["weights"]
    assert w["raw_policy"].iloc[0] == pytest.approx(1.0, abs=1e-6)
    assert w["post_risk"].max() <= 0.25 + 1e-6
    assert w["actual"].max() <= 0.25 + 0.02  # 执行/价格漂移容忍


# --- BLOCKER-B Observation Normalization V2 ---


def _feature_frames(n=300, seed=4):
    from china_etf.contracts import EnvironmentMode
    from china_etf.environment.portfolio_env import ChinaETFPortfolioEnv
    from china_etf.cost.mainland import MainlandETFCostModel
    from china_etf.execution.broker.mock import MockBroker
    from china_etf.execution.order_generator import OrderGenerator
    from china_etf.execution.premium import PremiumGuard
    from china_etf.execution.tradability import TradabilityMask
    from china_etf.risk.risk_overlay import RiskOverlayV0

    slots = SLOTS[:3]
    dates = pd.bdate_range("2025-01-02", periods=n)
    rng = np.random.default_rng(seed)
    adj = pd.DataFrame({s: pd.Series(100 * np.cumprod(1 + rng.normal(0.0002, 0.01, n)), index=dates) for s in slots})
    broker = MockBroker(
        tradability=TradabilityMask(), premium_guard=PremiumGuard(),
        cost_model=MainlandETFCostModel(), open_prices={s: adj[s] * 0.999 for s in slots},
    )
    env = ChinaETFPortfolioEnv(
        slots=slots, adj_close=adj,
        open_prices={s: adj[s] * 0.999 for s in slots},
        close_prices={s: adj[s] for s in slots},
        initial_cash=1_000_000.0, broker=broker, order_generator=OrderGenerator(),
        slot_to_instrument={s: s for s in slots},
        mode=EnvironmentMode.METHOD_RESEARCH,
        risk_overlay=RiskOverlayV0(slots, single_core_max=0.5),
    )
    return env


def test_scaler_fits_market_features_only_and_weights_not_normalized() -> None:
    env = _feature_frames()
    market = env.market_feature_frame()
    mdim = 8 * len(env.slots) + 5
    assert market.shape[1] == mdim
    gym = ChinaETFGymEnv(env)
    mean = market.mean().to_numpy()
    std = market.std().to_numpy().clip(min=1e-8)
    gym.set_market_scaler(mean, std)
    obs, _ = gym.reset()
    n = len(env.slots)
    weight_pos = list(range(8 * n, 8 * n + n))
    # 外生位置已标准化（无极端值）
    assert np.abs(obs[gym._market_positions]).max() < 50.0
    # portfolio weights 未归一化：初始无持仓 → 0
    assert np.allclose(obs[weight_pos], 0.0)
    # 权重维保持原始语义：跑一步后 ∈[0,1]
    obs2, _, _, _, _ = gym.step(np.zeros(len(env.slots), dtype=np.float32))
    assert ((obs2[weight_pos] >= -1e-6) & (obs2[weight_pos] <= 1.0 + 1e-6)).all()


def test_scaler_uses_train_dates_only_and_eval_not_updating() -> None:
    env = _feature_frames()
    market = env.market_feature_frame()
    # train-only：warmup 之后的前半段有效行（policy-independent、time-based）
    warm = env._warmup_index
    train_slice = market.iloc[warm : warm + (len(market) - warm) // 2]
    assert train_slice.notna().all().all()  # 全 finite
    mean = train_slice.mean().to_numpy()
    std = train_slice.std().to_numpy().clip(min=1e-8)
    gym = ChinaETFGymEnv(env)
    gym.set_market_scaler(mean, std)
    frozen = gym._scaler_mean.copy()
    env.adj.iloc[-10:] *= 2.0
    assert np.allclose(gym._scaler_mean, frozen)  # eval 不更新 scaler


def test_scaler_save_load_exact() -> None:
    env = _feature_frames()
    market = env.market_feature_frame()
    mean = market.mean().to_numpy()
    std = market.std().to_numpy().clip(min=1e-8)
    gym = ChinaETFGymEnv(env)
    gym.set_market_scaler(mean, std)
    np.testing.assert_allclose(gym._scaler_mean, mean, rtol=1e-6)
    np.testing.assert_allclose(gym._scaler_std, std, rtol=1e-6)


# --- BLOCKER-5 env API / check_env ---


def _gym_env(n=300):
    from china_etf.contracts import EnvironmentMode
    from china_etf.cost.mainland import MainlandETFCostModel
    from china_etf.environment.portfolio_env import ChinaETFPortfolioEnv
    from china_etf.execution.broker.mock import MockBroker
    from china_etf.execution.order_generator import OrderGenerator
    from china_etf.execution.premium import PremiumGuard
    from china_etf.execution.tradability import TradabilityMask
    from china_etf.risk.risk_overlay import RiskOverlayV0

    slots = SLOTS[:3]
    dates = pd.bdate_range("2025-01-02", periods=n)
    rng = np.random.default_rng(3)
    adj = pd.DataFrame({s: pd.Series(100 * np.cumprod(1 + rng.normal(0.0002, 0.01, n)), index=dates) for s in slots})
    broker = MockBroker(
        tradability=TradabilityMask(), premium_guard=PremiumGuard(),
        cost_model=MainlandETFCostModel(), open_prices={s: adj[s] * 0.999 for s in slots},
    )
    env = ChinaETFPortfolioEnv(
        slots=slots, adj_close=adj,
        open_prices={s: adj[s] * 0.999 for s in slots},
        close_prices={s: adj[s] for s in slots},
        initial_cash=1_000_000.0, broker=broker, order_generator=OrderGenerator(),
        slot_to_instrument={s: s for s in slots},
        mode=EnvironmentMode.METHOD_RESEARCH,
        risk_overlay=RiskOverlayV0(slots, single_core_max=0.5),
    )
    return ChinaETFGymEnv(env)


def test_sb3_check_env() -> None:
    from stable_baselines3.common.env_checker import check_env

    gym_env = _gym_env()
    check_env(gym_env, warn=True)  # 抛异常即失败


def test_episode_end_semantics() -> None:
    gym_env = _gym_env(n=300)
    gym_env.reset()
    terminated = truncated = False
    for _ in range(400):
        obs, reward, terminated, truncated, info = gym_env.step(np.zeros(3, dtype=np.float32))
        if terminated or truncated:
            break
    assert truncated and not terminated  # 数据到末尾 = truncated


def test_reset_returns_valid_obs() -> None:
    gym_env = _gym_env()
    obs, _ = gym_env.reset()
    assert gym_env.observation_space.contains(obs)


def test_step_after_terminal_is_defined() -> None:
    gym_env = _gym_env(n=300)
    gym_env.reset()
    last = None
    for _ in range(400):
        last = gym_env.step(np.zeros(3, dtype=np.float32))
        if last[2] or last[3]:
            break
    again = gym_env.step(np.zeros(3, dtype=np.float32))  # 已定义：持续返回 truncated=True
    assert again[3] is True
