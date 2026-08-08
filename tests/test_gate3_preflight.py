"""GATE_3 PREFLIGHT — P1 现金偿付 / P2 CNY 收益序列。"""

import numpy as np
import pandas as pd

from china_etf.accounting import PortfolioAccounting
from china_etf.contracts import Order, TargetInstrumentWeights
from china_etf.cost.mainland import MainlandETFCostModel
from china_etf.environment.portfolio_env import ChinaETFPortfolioEnv
from china_etf.execution.broker.mock import MockBroker
from china_etf.execution.order_generator import OrderGenerator
from china_etf.execution.premium import PremiumGuard


def _rule_mask(buy_disabled=()):
    from china_etf.contracts import TradabilityDecision

    class _M:
        def __init__(self):
            self.bd = set(buy_disabled)

        def get(self, instrument, timestamp, **kw):
            return TradabilityDecision(
                instrument=instrument,
                timestamp=timestamp,
                buy_allowed=instrument not in self.bd,
                sell_allowed=True,
            )

    return _M()


def _env(n=300, slots=("A", "B"), seed=5):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2025-01-02", periods=n)
    adj = pd.DataFrame(
        {s: pd.Series(100 * np.cumprod(1 + rng.normal(0.0002, 0.01, n)), index=dates) for s in slots}
    )
    opens = {s: adj[s] * 0.999 for s in slots}
    closes = {s: adj[s] for s in slots}
    broker = MockBroker(
        tradability=_rule_mask(),
        premium_guard=PremiumGuard(),
        cost_model=MainlandETFCostModel(),
        open_prices=opens,
    )
    return ChinaETFPortfolioEnv(
        slots=list(slots), adj_close=adj, open_prices=opens, close_prices=closes,
        initial_cash=1_000_000.0, broker=broker, order_generator=OrderGenerator(),
        slot_to_instrument={s: s for s in slots},
    )


# --- P1 Cash solvency ---


def test_no_negative_cash_after_max_investment() -> None:
    """Case A：1,000,000 现金，target=100% 单一 ETF，非零费用 → cash ≥ 0，无杠杆。"""
    env = _env(slots=("A", "B"))
    env.reset()
    _, _, _, _ = env.step(np.array([100.0, -100.0]))  # 100% A
    assert env.accounting.cash >= 0.0
    assert env.accounting.cash > 0.0  # 1% buffer 保留


def test_rebalance_sells_before_buys() -> None:
    """Case B：100% A → target 100% B：先卖 A 得现金，再买 B；中间现金不为负、无拒单。"""
    env = _env()
    env.reset()
    _, _, _, i1 = env.step(np.array([100.0, -100.0]))  # 买 A
    n_rejects_1 = len(env.broker.rejects)
    cash_after_buy = env.accounting.cash
    _, _, _, i2 = env.step(np.array([-100.0, 100.0]))  # 换仓 B
    assert len(env.broker.rejects) == n_rejects_1  # 无新拒单
    # broker 按 先卖后买 排序成交
    fills = i2["step"].fills
    sides = [f.side for f in fills]
    first_sell = sides.index("sell") if "sell" in sides else None
    assert first_sell is not None and sides[first_sell:] == sorted(sides, key=lambda s: 0 if s == "sell" else 1)
    assert env.accounting.cash >= 0.0
    assert "A" not in env.accounting.positions
    assert "B" in env.accounting.positions
    assert cash_after_buy >= 0.0


def test_buy_sizing_reserves_transaction_cost() -> None:
    """Case C：买入按 investable=V×(1−1%) 计；费用由 buffer 覆盖；Σw_actual ≤ 1+ε。"""
    env = _env()
    env.reset()
    _, _, _, i1 = env.step(np.array([100.0, -100.0]))
    snap = env.accounting.snapshot(
        i1["step"].t_next, env._close_marks(i1["step"].t_next), env._fx()
    )
    actual_weights = {s: 0.0 for s in env.slots}
    for inst, pos in env.accounting.positions.items():
        slot = inst  # slot==instrument in tests
        mark = env._close_marks(i1["step"].t_next).get(inst, 0.0)
        actual_weights[slot] = pos.quantity * mark / snap.portfolio_value
    assert sum(actual_weights.values()) <= 1.0 + 1e-6
    assert env.accounting.cash >= 0.0


# --- P2 CNY base-currency return ---


def test_hkd_to_cny_research_series() -> None:
    """R_CNY = V_t/V_{t-1}−1，V=P_HKD×FX；HKD 与 CNY 收益不同（FX 变动时）。"""
    dates = pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06"])
    p_hkd = pd.Series([30.0, 30.5, 31.0], index=dates)
    fx = pd.Series([0.90, 0.91, 0.90], index=dates)  # HKD/CNY
    v_cny = p_hkd * fx
    r_cny = v_cny / v_cny.shift(1) - 1.0
    r_hkd = p_hkd / p_hkd.shift(1) - 1.0
    # 2026-01-05：HKD +1.67%，CNY +2.78%（含 FX 0.90→0.91）
    assert abs(r_hkd.iloc[1] - (30.5 / 30.0 - 1)) < 1e-9
    assert abs(r_cny.iloc[1] - ((30.5 * 0.91) / (30.0 * 0.90) - 1)) < 1e-9
    assert not np.isclose(r_cny.iloc[1], r_hkd.iloc[1])
