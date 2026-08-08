"""Reviewer §18.3/§18.4 — T 收盘决策 → T+1 开盘成交；未来数据不影响当期特征。"""

import numpy as np
import pandas as pd

from china_etf.environment.portfolio_env import ChinaETFPortfolioEnv
from china_etf.execution.broker.mock import MockBroker
from china_etf.execution.order_generator import OrderGenerator
from china_etf.execution.premium import PremiumGuard
from china_etf.execution.tradability import TradabilityMask
from china_etf.features.etf_features import per_asset_features
from china_etf.cost.mainland import MainlandETFCostModel


def _make_env(n=300, seed=7):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2026-01-02", periods=n)
    slots = ["CN_LARGE", "GOLD", "CN_DURATION", "CASH_LIKE", "CHINEXT",
             "STAR", "HK_TECH", "US_BROAD", "CN_SMALL", "CN_DIVIDEND", "HK_DIVIDEND"]
    px = {}
    for i, s in enumerate(slots):
        rets = rng.normal(0.0002, 0.01, n)
        px[s] = pd.Series(100 * np.cumprod(1 + rets), index=dates)
    adj = pd.DataFrame(px)
    open_prices = {s: adj[s] * 0.999 for s in slots}
    close_prices = {s: adj[s] for s in slots}
    broker = MockBroker(
        tradability=TradabilityMask(),
        premium_guard=PremiumGuard(),
        cost_model=MainlandETFCostModel(),
        open_prices=open_prices,
    )
    env = ChinaETFPortfolioEnv(
        slots=slots,
        adj_close=adj,
        open_prices=open_prices,
        close_prices=close_prices,
        initial_cash=1_000_000.0,
        broker=broker,
        order_generator=OrderGenerator(),
        slot_to_instrument={s: s for s in slots},
    )
    return env


def test_action_dim_and_obs_shape() -> None:
    env = _make_env()
    obs = env.reset()
    assert env.action_dim == 11
    assert obs.shape == (8 * 11 + 11 + 5,)
    assert np.isfinite(obs).all()


def test_fill_at_next_open_not_same_close() -> None:
    env = _make_env()
    env.reset()
    raw = np.zeros(11)
    obs, reward, done, info = env.step(raw)
    step = info["step"]
    i0 = env._i - 1
    assert step.t == env.calendar[i0]
    assert step.t_next == env.calendar[i0 + 1]
    # 成交价 = T+1 开盘价（open ≈ 0.999 * close），而非 T 收盘价
    for f in step.fills:
        expected_open = env.open_prices[f.instrument].iloc[i0 + 1]
        assert np.isclose(f.price, expected_open)
    # 禁止同日收盘成交：成交价必须等于 T+1 开盘价（而非 T 收盘价）
    for f in step.fills:
        close_t = env.close_prices[f.instrument].iloc[i0]
        assert not np.isclose(f.price, close_t)


def test_no_lookahead_features() -> None:
    base = pd.Series(
        np.cumprod(1 + np.random.default_rng(1).normal(0, 0.01, 120)),
        index=pd.bdate_range("2026-01-01", periods=120),
    )
    t = base.index[60]
    f_base = per_asset_features(base).loc[t]
    # 修改 t 之后的数据
    future = base.copy()
    future.iloc[61:] *= 10.0
    f_future = per_asset_features(future).loc[t]
    pd.testing.assert_series_equal(f_base, f_future)
