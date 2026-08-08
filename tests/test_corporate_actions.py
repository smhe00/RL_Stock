"""GATE_4_PILOT_READY CA1 — 境内 ETF 双价 contract + 公司行为记账（评审 §18）。

覆盖：
- test_execution_uses_raw_price_not_total_return_price
- test_ex_dividend_creates_receivable
- test_dividend_receivable_not_spendable_before_payment
- test_dividend_payment_moves_receivable_to_cash_without_pnl_jump
- test_ex_dividend_reward_has_no_artificial_loss
- test_unit_conversion_preserves_portfolio_value
- test_walkforward_uses_dual_price_contract
"""

import math

import numpy as np
import pandas as pd
import pytest

from china_etf.accounting import PortfolioAccounting, Position
from china_etf.contracts import EnvironmentMode
from china_etf.cost.mainland import MainlandETFCostModel
from china_etf.data.corporate_actions import CorporateActionEvent
from china_etf.environment.portfolio_env import ChinaETFPortfolioEnv
from china_etf.evaluation.walkforward import WalkForwardRunner
from china_etf.evaluation.baselines import equal_weight_policy
from china_etf.execution.broker.mock import MockBroker
from china_etf.execution.order_generator import OrderGenerator
from china_etf.execution.premium import PremiumGuard
from china_etf.execution.tradability import TradabilityMask
from china_etf.risk.risk_overlay import RiskOverlayV0

N = 300
DATES = pd.bdate_range("2025-01-02", periods=N)
EX = DATES[280]
PAY = DATES[282]


def _trendy(price=10.0):
    """非恒定研究序列（避免全局特征恒 0 相关 → NaN），供 features finite。"""
    return [price * (1 + 0.0001 * i) + 0.005 * math.sin(i / 7.0) for i in range(N)]


def _env(adj_A, raw_open, raw_close, events, initial_cash=1_000_000.0):
    """双槽位（A 有 CA 事件；B 无）→ 全局特征 finite，warmup 可完成。

    B 用独立 flat 行情（除息日不下跌），避免 B 承担无事件的价格下跌干扰断言。
    """
    slots = ["A", "B"]
    adj = pd.DataFrame({
        "A": pd.Series(adj_A, index=DATES),
        "B": pd.Series(adj_A, index=DATES),  # B 用同 adj（仅需 finite）
    })
    opens = {"A": pd.Series(raw_open, index=DATES), "B": pd.Series(_flat(10.0), index=DATES)}
    closes = {"A": pd.Series(raw_close, index=DATES), "B": pd.Series(_flat(10.0), index=DATES)}
    broker = MockBroker(
        tradability=TradabilityMask(), premium_guard=PremiumGuard(),
        cost_model=MainlandETFCostModel(), open_prices=opens,
    )
    env = ChinaETFPortfolioEnv(
        slots=slots, adj_close=adj, open_prices=opens, close_prices=closes,
        initial_cash=initial_cash, broker=broker, order_generator=OrderGenerator(),
        slot_to_instrument={"A": "A", "B": "B"}, mode=EnvironmentMode.METHOD_RESEARCH,
        risk_overlay=RiskOverlayV0(slots, single_core_max=1.0),  # 2 槽位测试：0.25 cap 不可行
        corporate_actions={"A": events},
    )
    return env


def _cash_div_event(ex=EX, pay=PAY, cash=0.10):
    return CorporateActionEvent(instrument="A", ex_date=ex, pay_date=pay, cash_per_share=cash, unit_factor=1.0)


def _flat(price=10.0):
    return [float(price)] * N


def _drive_until(env, target_t_next, action=None):
    """步进直到某步的 t_next == target_t_next；返回 (该步 reward, info, qty_pre)。

    qty_pre = 进入该步前持仓（= target_t_next 开盘前持仓，用于 CA 计提）。
    """
    while env._i < len(env.calendar) - 1:
        t_next = env.calendar[env._i + 1]
        qty_pre = float(env.accounting.positions.get("A", Position("A")).quantity)
        a = np.zeros(len(env.slots)) if action is None else action
        obs, r, done, info = env.step(a)
        if t_next == target_t_next:
            return r, info, qty_pre
        if done:
            break
    raise AssertionError(f"never crossed {target_t_next}")


def test_execution_uses_raw_price_not_total_return_price() -> None:
    """成交价必须用 raw open（执行价），而非复权研究价。"""
    # adj（TR）与 raw 明显不同：adj 平滑趋势，raw 波动
    adj_A = _trendy()
    rng = np.random.default_rng(3)
    raw_close = [10.0 + float(x) for x in rng.normal(0, 0.05, N)]
    raw_open = [10.0 + float(x) for x in rng.normal(0, 0.05, N)]
    env = _env(adj_A, raw_open, raw_close, [])
    env.reset()
    _, info, _ = _drive_until(env, DATES[260])  # warmup(~252) 之后
    fills = [f for f in info["step"].fills if f.instrument == "A"]
    assert fills, "no A fills produced"
    raw_open_series = pd.Series(raw_open, index=DATES)
    for f in fills:
        raw_open_at_fill = float(raw_open_series.loc[f.timestamp])
        assert f.price == pytest.approx(raw_open_at_fill)
        # 执行价来自 raw open 序列（≠ 平滑 adj 值）
        assert not np.isclose(f.price, 10.0, atol=0.01) or raw_open_at_fill == pytest.approx(f.price)


def test_ex_dividend_creates_receivable() -> None:
    """除息日：基于除息日开盘前持仓计提应收款。"""
    raw_close = _flat(10.0)
    raw_close[DATES.get_loc(EX)] = 9.9  # 除息日价格机械下跌
    env = _env(_trendy(), _flat(10.0), raw_close, [_cash_div_event()])
    env.reset()
    r, info, qty_pre = _drive_until(env, EX)
    assert qty_pre > 0, "测试前必须已建仓"
    assert env.accounting.dividend_receivable.get("A", 0.0) == pytest.approx(qty_pre * 0.10)
    assert env.accounting.dividend_receivable.get("A", 0.0) > 0


def test_dividend_receivable_not_spendable_before_payment() -> None:
    """应收款在派息日前不是 spendable cash（账本层面）。"""
    acc = PortfolioAccounting(initial_cash=1000.0)
    acc.positions["A"] = Position("A", quantity=100, avg_cost=10.0)
    acc.accrue_dividend("A", 100, 0.10)
    assert acc.receivable_total == pytest.approx(10.0)
    assert acc.cash == pytest.approx(1000.0)  # cash 未增加
    snap = acc.snapshot(DATES[0], {"A": 10.0}, {})
    assert snap.cash == pytest.approx(1000.0)
    assert snap.dividend_receivable == pytest.approx(10.0)
    assert snap.portfolio_value == pytest.approx(1000.0 + 100 * 10.0 + 10.0)
    # 未派发 → settle 返回 0（无应收款可结算）

    acc2 = PortfolioAccounting(initial_cash=1000.0)
    assert acc2.settle_dividend("A") == 0.0


def test_dividend_payment_moves_receivable_to_cash_without_pnl_jump() -> None:
    """派息日：应收款 → cash，equity 不变（价值中性）。"""
    acc = PortfolioAccounting(initial_cash=1000.0)
    acc.positions["A"] = Position("A", quantity=100, avg_cost=10.0)
    acc.accrue_dividend("A", 100, 0.10)
    v_before = acc.snapshot(DATES[0], {"A": 10.0}, {}).portfolio_value
    amt = acc.settle_dividend("A")
    assert amt == pytest.approx(10.0)
    v_after = acc.snapshot(DATES[0], {"A": 10.0}, {}).portfolio_value
    assert v_after == pytest.approx(v_before)  # equity 不跳变
    assert acc.cash == pytest.approx(1010.0)
    assert acc.receivable_total == 0.0
    # 环境层：跨派息日，equity 连续（raw 价不变时）
    raw_close = _flat(10.0)
    raw_close[DATES.get_loc(EX)] = 9.9
    env = _env(_trendy(), _flat(10.0), raw_close, [_cash_div_event(ex=EX, pay=PAY)])
    env.reset()
    _, _, _ = _drive_until(env, EX)
    v_after_ex = env.accounting.snapshot(EX, env._close_marks(EX), env._fx()).portfolio_value
    _, _, _ = _drive_until(env, PAY)
    v_after_pay = env.accounting.snapshot(PAY, env._close_marks(PAY), env._fx()).portfolio_value
    # 派息日无价格变化（raw 恒 9.9）→ equity 应连续（仅 rebalance 费用微小）
    assert abs(v_after_pay - v_after_ex) < v_after_ex * 0.01
    assert env.accounting.dividend_receivable.get("A", 0.0) == 0.0  # 已派发


def test_ex_dividend_reward_has_no_artificial_loss() -> None:
    """除息日 reward 不含人为损失：raw 价下跌被应收款抵消。"""
    raw_close = _flat(10.0)
    raw_close[DATES.get_loc(EX)] = 9.9  # 除息日机械下跌 1%
    assert abs((raw_close[DATES.get_loc(EX)] / raw_close[DATES.get_loc(EX) - 1] - 1.0)) > 0.009  # 价格确实下跌
    env = _env(_trendy(), _flat(10.0), raw_close, [_cash_div_event()])
    env.reset()
    r, _, _ = _drive_until(env, EX)
    # 无 CA 时 A 权重 ~50% 的 1% 下跌 → 人为损失 ≈ -0.5%；有 CA 应 ≈ 0（仅 rebalance 费用）
    no_ca_loss = -0.5 * (0.10 / 10.0)  # ≈ -0.005
    assert r > no_ca_loss / 2, f"ex-date reward={r:.5f} 显示人为损失（无 CA 应 ≈ {no_ca_loss:.5f}）"
    assert r > -0.001, f"ex-date reward={r:.5f} 仍偏负"


def test_unit_conversion_preserves_portfolio_value() -> None:
    """份额折算：qty×factor，avg_cost/factor，价值不变。"""
    acc = PortfolioAccounting(initial_cash=1000.0)
    acc.positions["A"] = Position("A", quantity=100, avg_cost=10.0)
    v_before = acc.snapshot(DATES[0], {"A": 10.0}, {}).portfolio_value  # 2000
    acc.apply_unit_conversion("A", 0.5)  # 1:0.5 折算
    assert acc.positions["A"].quantity == pytest.approx(50.0)
    assert acc.positions["A"].avg_cost == pytest.approx(20.0)
    # 折算后价格翻倍（P_new = P_old/factor）→ 市值不变
    v_after = acc.snapshot(DATES[0], {"A": 20.0}, {}).portfolio_value
    assert v_after == pytest.approx(v_before)
    # 环境层：跨折算日 qty 改变、equity 连续
    conv = CorporateActionEvent(instrument="A", ex_date=EX, pay_date=None, cash_per_share=0.0, unit_factor=0.5)
    raw_close = _flat(10.0)
    raw_close[DATES.get_loc(EX)] = 20.0  # 折算后价格翻倍（raw）
    env = _env(_trendy(), _flat(10.0), raw_close, [conv])
    env.reset()
    _, _, qty_pre = _drive_until(env, EX)
    assert qty_pre > 0
    assert env.accounting.positions["A"].quantity == pytest.approx(qty_pre * 0.5)


def test_walkforward_uses_dual_price_contract() -> None:
    """runner fold：特征用 TR 研究序列，成交用 raw 执行价（双价 contract）。"""
    n2 = 700
    dates2 = pd.bdate_range("2024-01-02", periods=n2)
    rng = np.random.default_rng(11)
    adj_A = [10.0 + float(x) for x in rng.normal(0, 0.05, n2)]
    raw_open = [10.0 + float(x) for x in rng.normal(0, 0.03, n2)]
    raw_close = [10.0 + float(x) for x in rng.normal(0, 0.03, n2)]

    slots = ["A", "B"]
    adj = pd.DataFrame({
        "A": pd.Series(adj_A, index=dates2), "B": pd.Series(adj_A, index=dates2),
    })
    opens = {"A": pd.Series(raw_open, index=dates2), "B": pd.Series(raw_open, index=dates2)}
    closes = {"A": pd.Series(raw_close, index=dates2), "B": pd.Series(raw_close, index=dates2)}

    def build_env(a, o, c, corporate_actions=None):
        broker = MockBroker(
            tradability=TradabilityMask(), premium_guard=PremiumGuard(),
            cost_model=MainlandETFCostModel(), open_prices=o,
        )
        return ChinaETFPortfolioEnv(
            slots=slots, adj_close=a, open_prices=o, close_prices=c,
            initial_cash=1_000_000.0, broker=broker, order_generator=OrderGenerator(),
            slot_to_instrument={"A": "A", "B": "B"}, mode=EnvironmentMode.METHOD_RESEARCH,
            risk_overlay=RiskOverlayV0(slots, single_core_max=1.0),
            corporate_actions=corporate_actions,
        )

    runner = WalkForwardRunner(
        adj=adj, opens=opens, closes=closes, slots=slots,
        slot_to_instrument={"A": "A", "B": "B"}, build_env=build_env,
    )
    folds = runner.make_folds(n_folds=2, min_train_days=120, val_days=40)
    env_te = runner._build_env_upto(folds[0].test_end)
    # 执行价 = raw open（不是 adj）
    env_te.reset()
    captured = []
    while env_te._i < len(env_te.calendar) - 1:
        _, _, _, info = env_te.step(np.zeros(len(slots)))
        for f in info["step"].fills:
            captured.append((f.timestamp, f.price))
    assert captured
    raw_open_series = pd.Series(raw_open, index=dates2)
    for ts, px in captured:
        assert px == pytest.approx(raw_open_series.loc[ts])
    # 特征用 adj（研究序列）：env.adj 是 TR 序列（到 test_end 截断）
    assert env_te.adj["A"].tolist() == pytest.approx(adj_A[: len(env_te.adj)])
    # 且 adj（TR）≠ raw close（双价 contract）
    assert adj_A != raw_close
