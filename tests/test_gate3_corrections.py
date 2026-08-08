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
    # 1 vs 10: e^1/(e^1+10e^-1) = e^2/(e^2+10) ≈ 0.4251
    assert w.iloc[0] == pytest.approx(np.e ** 2 / (np.e ** 2 + 10), abs=1e-4)
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
