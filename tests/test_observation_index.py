"""GATE_4_PRECHECK — observation 索引分区证明（Reviewer §4）。

布局：[0:88] per-asset market | [88:99] actual weights | [99:104] global market。
只归一化外生 [0:88]∪[99:104]；weights [88:99] 位级不变。
"""

import numpy as np
import pandas as pd

from china_etf.environment.gym_wrapper import ChinaETFGymEnv


def _synthetic_gym():
    from china_etf.contracts import EnvironmentMode
    from china_etf.cost.mainland import MainlandETFCostModel
    from china_etf.environment.portfolio_env import ChinaETFPortfolioEnv
    from china_etf.execution.broker.mock import MockBroker
    from china_etf.execution.order_generator import OrderGenerator
    from china_etf.execution.premium import PremiumGuard
    from china_etf.execution.tradability import TradabilityMask
    from china_etf.risk.risk_overlay import RiskOverlayV0

    slots = [f"S{i}" for i in range(11)]
    n = 300
    dates = pd.bdate_range("2025-01-02", periods=n)
    rng = np.random.default_rng(5)
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
        risk_overlay=RiskOverlayV0(slots),
    )
    return ChinaETFGymEnv(env)


def test_observation_index_partition() -> None:
    gym = _synthetic_gym()
    market = gym._market_positions
    assert market == list(range(0, 88)) + list(range(99, 104))
    assert len(market) == 93
    assert list(range(88, 99)) == list(range(88, 99))  # weights 区间


def test_only_exogenous_features_are_normalized() -> None:
    gym = _synthetic_gym()
    n = 11
    # 构造可辨认的 obs：market=1.0（均值 0），weights=[0.01..0.11]，global=2.0
    obs = np.zeros(104, dtype=np.float32)
    obs[0:88] = 1.0
    obs[99:104] = 2.0
    obs[88:99] = np.arange(0.01, 0.12, 0.01)
    gym.set_market_scaler(np.zeros(93, dtype=np.float32), np.ones(93, dtype=np.float32))
    out = gym._normalize(obs)
    # 外生被标准化：(1-0)/1=1； (2-0)/1=2
    assert np.allclose(out[0:88], 1.0)
    assert np.allclose(out[99:104], 2.0)
    # weights 完全不变
    assert np.allclose(out[88:99], obs[88:99])


def test_portfolio_weight_indices_unchanged() -> None:
    gym = _synthetic_gym()
    obs = np.zeros(104, dtype=np.float32)
    obs[88:99] = np.linspace(0.05, 0.30, 11)
    gym.set_market_scaler(np.zeros(93, dtype=np.float32), np.full(93, 1e-8, dtype=np.float32))
    out = gym._normalize(obs)
    np.testing.assert_array_equal(out[88:99], obs[88:99])


def test_global_features_are_normalized() -> None:
    gym = _synthetic_gym()
    obs = np.zeros(104, dtype=np.float32)
    obs[99:104] = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float32)
    gym.set_market_scaler(np.zeros(93, dtype=np.float32), np.ones(93, dtype=np.float32))
    out = gym._normalize(obs)
    assert np.allclose(out[99:104], obs[99:104])
