"""GATE_2_CORRECTIONS — Reviewer 要求的集成测试。

覆盖：实际持仓观测、端到端 transition、隔夜持仓、执行摩擦无双算、warm-up finite、
EnvironmentMode 的 PremiumGuard 行为、费率元数据。
"""

import numpy as np
import pandas as pd
import pytest

from china_etf.contracts import (
    EnvironmentMode,
    TradabilityDecision,
)
from china_etf.cost.base import FeeRule
from china_etf.cost.mainland import MainlandETFCostModel
from china_etf.cost.southbound import SouthboundETFCostModel
from china_etf.environment.portfolio_env import ChinaETFPortfolioEnv
from china_etf.execution.broker.mock import MockBroker
from china_etf.execution.order_generator import OrderGenerator
from china_etf.execution.premium import PremiumGuard
from china_etf.risk.risk_overlay import RiskOverlayV0


class RuleMask:
    """按 instrument 规则化 tradability（用于测试 buy-disabled）。"""

    def __init__(self, buy_disabled: tuple[str, ...] = ()) -> None:
        self.buy_disabled = set(buy_disabled)

    def get(self, instrument: str, timestamp: pd.Timestamp, **kwargs):
        return TradabilityDecision(
            instrument=instrument,
            timestamp=timestamp,
            buy_allowed=instrument not in self.buy_disabled,
            sell_allowed=True,
        )


def make_env(
    slots=("A", "B", "C"),
    *,
    n=300,
    seed=3,
    buy_disabled=(),
    mode=EnvironmentMode.METHOD_RESEARCH,
    requires_premium=(),
    overlay_max=0.5,
):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2025-01-02", periods=n)
    adj = pd.DataFrame(
        {s: pd.Series(100 * np.cumprod(1 + rng.normal(0.0002, 0.01, n)), index=dates) for s in slots}
    )
    opens = {s: adj[s] * 0.999 for s in slots}
    closes = {s: adj[s] for s in slots}
    broker = MockBroker(
        tradability=RuleMask(buy_disabled=buy_disabled),
        premium_guard=PremiumGuard(requires_protection=lambda i: i in requires_premium),
        cost_model=MainlandETFCostModel(),
        open_prices=opens,
    )
    return ChinaETFPortfolioEnv(
        slots=list(slots),
        adj_close=adj,
        open_prices=opens,
        close_prices=closes,
        initial_cash=1_000_000.0,
        broker=broker,
        order_generator=OrderGenerator(),
        slot_to_instrument={s: s for s in slots},
        mode=mode,
        risk_overlay=RiskOverlayV0(list(slots), single_core_max=overlay_max),
    )


# --- 费率 ---


def test_southbound_fee_03110_reviewer_numbers() -> None:
    s = SouthboundETFCostModel()
    c = s.estimate("03110.HK", "buy", 10_000, 30.0)  # notional 300,000 HKD
    assert c.tax == 0.0  # 港股通 ETF 印花税暂免
    assert c.exchange_fee == pytest.approx(16.95 + 8.10 + 0.45 + 6.00)
    assert c.total == pytest.approx(136.50)


def test_fee_metadata_present() -> None:
    assert MainlandETFCostModel().effective_from == "2026-08-08"
    assert "broker" in MainlandETFCostModel().source.lower()
    assert MainlandETFCostModel().broker_commission_includes_exchange_fee == (
        "UNKNOWN_PENDING_BROKER_FEE_AUDIT"
    )
    s = SouthboundETFCostModel()
    assert s.effective_from == "2026-08-08" and s.source
    rule = FeeRule(
        name="AFRC", rate=0.0000015, minimum=None, maximum=None,
        currency="HKD", effective_from=pd.Timestamp("2026-08-08").date(),
        effective_to=None, source="SSE", applies_to=("southbound_etf",),
    )
    assert rule.rate == 0.0000015


# --- 实际持仓观测 ---


def test_observation_uses_actual_holdings_not_target() -> None:
    env = make_env(buy_disabled=("B",))
    env.reset()
    # action：目标 B ≈ 50%、A ≈ 50%
    raw = np.array([0.0, 0.0, -20.0])  # softmax → A≈0.5 B≈0.5 C≈0
    _, _, _, info = env.step(raw)
    step = info["step"]
    target_b = 0.5
    assert step is not None
    # B 被 buy-disabled：实际持仓必须为 0
    assert "B" not in env.accounting.positions
    obs = env._observe(env.calendar[env._i])
    w_actual_b = obs[8 * 3 + 1]  # 11×3 features 后 weights 块，B 是 slots 第 2 个
    assert w_actual_b == pytest.approx(0.0, abs=1e-9)
    assert w_actual_b != pytest.approx(target_b, abs=0.1)
    # A 实际买到
    assert "A" in env.accounting.positions


# --- 端到端 transition ---


def test_environment_end_to_end_transition() -> None:
    env = make_env(buy_disabled=("B",))
    env.reset()
    raw = np.zeros(3)
    _, reward, done, info = env.step(raw)
    step = info["step"]
    t_next = step.t_next
    marks = env._close_marks(t_next)
    snap = env.accounting.snapshot(t_next, marks, env._fx())
    # 会计 identity：V = cash + Σ position×price
    expected = snap.cash + sum(
        pos.quantity * marks.get(inst, 0.0)
        for inst, pos in env.accounting.positions.items()
    )
    assert snap.portfolio_value == pytest.approx(expected)
    # B 禁买：无持仓；A/C 正常成交且整手
    assert "B" not in env.accounting.positions
    for inst, pos in env.accounting.positions.items():
        assert pos.quantity % 100 == 0
    # 费用只按成交数量计费：fills 数量与费用一致，reject 不计费
    fills = step.fills
    assert env.broker.rejects  # B 的单被拒
    assert len(fills) == 2  # A、C 成交
    fee_from_fills = sum(f.cost.total for f in fills)
    assert env.accounting.fees_paid == pytest.approx(fee_from_fills)


# --- 隔夜持仓 ---


def test_old_positions_hold_through_overnight_gap_before_rebalance() -> None:
    # 用 permissive overlay（cap=1）保持精确权重语义，专注验证隔夜时序
    env = make_env(slots=("A", "GOLD"), seed=11, overlay_max=1.0)
    env.reset()
    wi = env._warmup_index
    cal = env.calendar
    # 控制价格：决策日 wi 收盘 10；wi+1 开盘 9（买入）；wi+1 收盘 9；wi+2 开盘 8.1（隔夜 -10%）
    for s in env.slots:
        env.adj.loc[cal[wi], s] = 10.0
        env.close_prices[s].loc[cal[wi]] = 10.0
        env.open_prices[s].loc[cal[wi + 1]] = 9.0
        env.close_prices[s].loc[cal[wi + 1]] = 9.0
        env.adj.loc[cal[wi + 1], s] = 9.0
        env.open_prices[s].loc[cal[wi + 2]] = 8.1
        env.close_prices[s].loc[cal[wi + 2]] = 8.1
        env.adj.loc[cal[wi + 2], s] = 8.1
    # step1：买入 100% A（@9.0 开盘）
    raw1 = np.array([100.0, -100.0])
    _, _, _, info1 = env.step(raw1)
    qty = env.accounting.positions["A"].quantity
    assert qty > 0 and qty % 100 == 0
    v_after_buy = info1["step"].value_after
    # step2：目标 0% A（卖出全部 @8.1 开盘）——先承受隔夜 -10%
    raw2 = np.array([-100.0, 100.0])  # A≈0 → 卖 A，买 GOLD
    _, _, _, info2 = env.step(raw2)
    st2 = info2["step"]
    sell_fill = [f for f in st2.fills if f.instrument == "A"]
    assert sell_fill and sell_fill[0].price == pytest.approx(8.1)
    assert st2.value_before == pytest.approx(v_after_buy)
    # 隔夜损失 9.0 → 8.1（-10%）在卖出前已承担：A 占组合 ~88%，净收益应显著为负
    assert st2.net_return < -0.05
    # 禁止在 t close 按 9.0 提前卖出（若提前卖出则无隔夜损失，net_return ≈ +成本影响）


# --- 执行摩擦无双算 ---


def test_no_double_count_execution_friction() -> None:
    broker = MockBroker(
        tradability=RuleMask(),
        premium_guard=PremiumGuard(),
        cost_model=MainlandETFCostModel(),
        open_prices={"A": pd.Series([10.0], index=pd.to_datetime(["2026-01-05"]))},
    )
    from china_etf.accounting import PortfolioAccounting
    from china_etf.contracts import Order

    acct = PortfolioAccounting(initial_cash=100_000.0)
    fills = broker.execute_plan(
        [Order(instrument="A", side="buy", quantity=1_000)],
        execution_date=pd.Timestamp("2026-01-05"),
        accounting=acct,
    )
    f = fills[0]
    assert f.price == 10.0  # fill 用 reference 执行价
    assert f.cost.total > 0  # 摩擦显式计入 CostBreakdown
    # 现金变化 = notional + cost.total（无隐藏滑点双算）
    assert acct.cash == pytest.approx(100_000 - 1_000 * 10.0 - f.cost.total)


# --- Warm-up / finite ---


def test_observation_is_finite_after_warmup() -> None:
    env = make_env()
    obs = env.reset()
    assert np.isfinite(obs).all()
    assert env._warmup_index >= env.min_history - 1


def test_observation_requires_full_lookback() -> None:
    with pytest.raises(ValueError):
        _short_env()


def _short_env():
    import numpy as np
    import pandas as pd

    dates = pd.bdate_range("2025-01-02", periods=100)
    adj = pd.DataFrame({s: pd.Series(np.ones(100) * 10.0, index=dates) for s in ("A", "B")})
    broker = MockBroker(
        tradability=RuleMask(),
        premium_guard=PremiumGuard(),
        cost_model=MainlandETFCostModel(),
        open_prices={s: adj[s] for s in ("A", "B")},
    )
    return ChinaETFPortfolioEnv(
        slots=["A", "B"],
        adj_close=adj,
        open_prices={s: adj[s] for s in ("A", "B")},
        close_prices={s: adj[s] for s in ("A", "B")},
        initial_cash=1_000_000.0,
        broker=broker,
        order_generator=OrderGenerator(),
        slot_to_instrument={"A": "A", "B": "B"},
    )


# --- EnvironmentMode 与 PremiumGuard ---


def test_environment_mode_research_allows_buy_without_iopv() -> None:
    env = make_env(slots=("US_BROAD", "GOLD"), requires_premium=("US_BROAD",))
    env.reset()
    _, _, _, info = env.step(np.array([10.0, -10.0]))
    assert not env.broker.premium_enforced
    assert "US_BROAD" in env.accounting.positions  # 研究模式：无 IOPV 也允许买入


def test_environment_mode_live_blocks_buy_without_iopv() -> None:
    env = make_env(
        slots=("US_BROAD", "GOLD"),
        requires_premium=("US_BROAD",),
        mode=EnvironmentMode.PAPER,
    )
    env.reset()
    _, _, _, _ = env.step(np.array([10.0, -10.0]))
    assert env.broker.premium_enforced
    assert "US_BROAD" not in env.accounting.positions  # fail-closed：无 IOPV 禁买
    assert any("premium" in r[1] for r in env.broker.rejects)
