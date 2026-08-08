"""GATE_4_PILOT_READY FINAL_FIX — P2/P3 真实事件回归（评审 §11/§16）。

P2：513690 官方派息日（2024-12-20 / 2025-12-22）；未知 pay_date 保守 fallback 不提前结算。
P3：512100 2022-09-05 真实份额合并 UNIT_CONSOLIDATION factor=0.36555；
     数量/价值/成交价连续（真实 raw fixture，非推断）。
"""

import numpy as np
import pandas as pd
import pytest

from china_etf.contracts import EnvironmentMode
from china_etf.cost.mainland import MainlandETFCostModel
from china_etf.data.corporate_actions import CorporateActionEvent, load_corporate_actions
from china_etf.data.loader import EVENTS, RAW, _fill_gaps_after_listing, total_return_index
from china_etf.environment.portfolio_env import ChinaETFPortfolioEnv
from china_etf.execution.broker.mock import MockBroker
from china_etf.execution.order_generator import OrderGenerator
from china_etf.execution.premium import PremiumGuard
from china_etf.execution.tradability import TradabilityMask
from china_etf.risk.risk_overlay import RiskOverlayV0

REAL_512100_EX = pd.Timestamp("2022-09-05")


def _read_raw(slot_code: str) -> pd.DataFrame:
    """读 data/qmt/raw/{slot}_{code}_raw.csv → (date-indexed, close)。"""
    df = pd.read_csv(RAW / f"{slot_code}_raw.csv")
    dc = next(c for c in ("index", "time", "date") if c in df.columns)
    df = df.rename(columns={dc: "date"})
    df["date"] = pd.to_datetime(df["date"].astype(str).str.strip(), format="%Y%m%d")
    return df.sort_values("date").set_index("date")


def _build_real_env(instrument: str, events, window=(pd.Timestamp("2021-06-01"), pd.Timestamp("2022-12-30"))):
    """2 槽位 env：A = instrument 真实数据（TR+raw），B = 511360 真实 flat 参考。"""
    code_a = f"CN_SMALL_512100_SH" if instrument == "512100.SH" else instrument.replace(".", "_")
    raw_a = _read_raw(code_a)
    raw_b = _read_raw("CASH_LIKE_511360_SH")
    w = raw_a.loc[window[0]:window[1]]
    wb = raw_b.loc[window[0]:window[1]]
    # A 研究序列 = raw + 官方事件 TR；B 无事件 = raw
    ev = pd.read_csv(EVENTS / f"{instrument}.csv")
    tr_a = total_return_index(w["close"], ev)
    slots = [instrument, "511360.SH"]
    adj = _fill_gaps_after_listing(
        pd.DataFrame({instrument: tr_a, "511360.SH": wb["close"]})
    )  # 停牌/缺行 ffill，避免 obs NaN（512100 2022-09-02 无行）
    opens = {instrument: w["open"], "511360.SH": wb["open"]}
    closes = {instrument: w["close"], "511360.SH": wb["close"]}
    broker = MockBroker(
        tradability=TradabilityMask(), premium_guard=PremiumGuard(),
        cost_model=MainlandETFCostModel(), open_prices=opens,
    )
    env = ChinaETFPortfolioEnv(
        slots=slots, adj_close=adj, open_prices=opens, close_prices=closes,
        initial_cash=1_000_000.0, broker=broker, order_generator=OrderGenerator(),
        slot_to_instrument={s: s for s in slots}, mode=EnvironmentMode.METHOD_RESEARCH,
        risk_overlay=RiskOverlayV0(slots, single_core_max=1.0),
        corporate_actions={instrument: events},
    )
    return env


def _step_to(env, target_t_next):
    while env._i < len(env.calendar) - 1:
        t_next = env.calendar[env._i + 1]
        obs, r, done, info = env.step(np.zeros(len(env.slots)))
        if t_next == target_t_next:
            return r, info
        if done:
            break
    raise AssertionError(f"never crossed {target_t_next}")


# --- P2: 513690 官方派息日 ---


def test_513690_2025_official_payment_date() -> None:
    """513690 2025 分红：ex 2025-12-17 → 官方 pay 2025-12-22（非 +2T fallback）。"""
    ca = load_corporate_actions()["513690.SH"]
    ev = next(e for e in ca if e.ex_date == pd.Timestamp("2025-12-17"))
    assert ev.pay_date == pd.Timestamp("2025-12-22")
    assert ev.settle_date == pd.Timestamp("2025-12-22")
    assert ev.source == "official_fund_announcement"
    assert ev.cash_per_share == pytest.approx(0.0113)


def test_513690_2024_official_payment_date() -> None:
    """513690 2024 分红：ex 2024-12-17 → 官方 pay 2024-12-20。"""
    ca = load_corporate_actions()["513690.SH"]
    ev = next(e for e in ca if e.ex_date == pd.Timestamp("2024-12-17"))
    assert ev.pay_date == pd.Timestamp("2024-12-20")
    assert ev.settle_date == pd.Timestamp("2024-12-20")
    assert ev.cash_per_share == pytest.approx(0.0085)


def test_unknown_payment_date_never_settles_early() -> None:
    """未知 pay_date → 保守 fallback ex+5T：ex+2T 应收款不结算，ex+5T 才转现金。"""
    # 合成事件：无官方 pay_date（300 日数据保证 warmup 完成）
    dates = pd.bdate_range("2025-01-02", periods=300)
    ex = dates[280]
    late = ex + pd.offsets.BDay(5)
    ev = CorporateActionEvent(
        instrument="A", action_type="CASH_DIVIDEND", ex_date=ex, unit_factor=1.0,
        cash_per_share=0.10, pay_date=None, settle_date=late, source="CONSERVATIVE_FALLBACK",
    )
    rng = np.random.default_rng(3)
    adj = pd.DataFrame({s: pd.Series(100 * np.cumprod(1 + rng.normal(0.0002, 0.01, len(dates))), index=dates) for s in ("A", "B")})
    opens = {s: adj[s] * 0.999 for s in ("A", "B")}
    closes = {s: adj[s] for s in ("A", "B")}
    broker = MockBroker(tradability=TradabilityMask(), premium_guard=PremiumGuard(),
                        cost_model=MainlandETFCostModel(), open_prices=opens)
    env = ChinaETFPortfolioEnv(
        slots=["A", "B"], adj_close=adj, open_prices=opens, close_prices=closes,
        initial_cash=1_000_000.0, broker=broker, order_generator=OrderGenerator(),
        slot_to_instrument={"A": "A", "B": "B"}, mode=EnvironmentMode.METHOD_RESEARCH,
        risk_overlay=RiskOverlayV0(["A", "B"], single_core_max=1.0),
        corporate_actions={"A": [ev]},
    )
    env.reset()
    # 推进到 ex（计提应收款）
    while env._i < len(env.calendar) - 1:
        if env.calendar[env._i + 1] == ex:
            env.step(np.zeros(2))
            break
        env.step(np.zeros(2))
    assert "A" in env.accounting.dividend_receivable, "ex-date 应计提应收款"
    # ex+2T：应收款保留（不提前结算）
    ex_plus_2 = ex + pd.offsets.BDay(2)
    while env._i < len(env.calendar) - 1:
        if env.calendar[env._i + 1] == ex_plus_2:
            env.step(np.zeros(2))
            assert "A" in env.accounting.dividend_receivable, "未知派息日 ex+2T 不得提前结算"
            break
        env.step(np.zeros(2))
    # ex+5T（保守）：应收款转现金
    while env._i < len(env.calendar) - 1:
        if env.calendar[env._i + 1] == late:
            env.step(np.zeros(2))
            assert "A" not in env.accounting.dividend_receivable, "保守 fallback 日应收款应结算"
            break
        env.step(np.zeros(2))


# --- P3: 512100 真实份额合并 ---


def test_512100_20220902_real_unit_consolidation_factor() -> None:
    """512100 2022-09-05 事件为显式 UNIT_CONSOLIDATION factor=0.36555（非 stockBonus 推断）。"""
    ca = load_corporate_actions()["512100.SH"]
    ev = next(e for e in ca if e.ex_date == REAL_512100_EX)
    assert ev.action_type == "UNIT_CONSOLIDATION"
    assert ev.unit_factor == pytest.approx(0.36555)
    assert ev.cash_per_share == 0.0
    assert "official" in ev.source.lower()


def test_512100_20220902_quantity_changes_by_036555() -> None:
    """512100 折算日（2022-09-05）：持仓 qty ×= 0.36555（真实 raw fixture）。"""
    events = load_corporate_actions()["512100.SH"]
    env = _build_real_env("512100.SH", events)
    env.reset()
    # 折算日前（09-02 或 09-01）建仓
    while env._i < len(env.calendar) - 1:
        t_next = env.calendar[env._i + 1]
        if t_next == REAL_512100_EX:
            qty_pre = float(env.accounting.positions.get("512100.SH", None).quantity) if "512100.SH" in env.accounting.positions else 0.0
            assert qty_pre > 0, "折算日前必须已持有 512100"
            _step_to(env, REAL_512100_EX)
            qty_after = float(env.accounting.positions["512100.SH"].quantity)
            assert qty_after == pytest.approx(qty_pre * 0.36555, rel=1e-6)
            return
        env.step(np.zeros(len(env.slots)))
    raise AssertionError("512100 折算日未在决策区间内")


def test_512100_20220902_portfolio_value_continuity() -> None:
    """512100 折算日：市值连续（raw 价跳变 ×2.76 被 qty×0.36555 抵消，仅真实行情 ±1%）。"""
    events = load_corporate_actions()["512100.SH"]
    env = _build_real_env("512100.SH", events)
    env.reset()
    while env._i < len(env.calendar) - 1:
        if env.calendar[env._i + 1] == REAL_512100_EX:
            t_pre = env.calendar[env._i]  # 折算前一日决策（持仓为折算前口径）
            v_before = env.accounting.snapshot(t_pre, env._close_marks(t_pre), env._fx()).portfolio_value
            _step_to(env, REAL_512100_EX)
            v_after = env.accounting.snapshot(REAL_512100_EX, env._close_marks(REAL_512100_EX), env._fx()).portfolio_value
            # 价格 0.982→2.713 (×2.7627)，qty×0.36555 → 净值 ×2.7627×0.36555 ≈ ×1.0099（真实行情 +0.99%）
            expected = v_before * (2.7627 * 0.36555)
            assert abs(v_after - expected) < v_before * 0.005, \
                f"折算日价值不连续: v_before={v_before:.0f} v_after={v_after:.0f} expected≈{expected:.0f}"
            assert v_after > v_before * 0.9, "折算日不得造成 -10% 级伪损失"
            assert v_after < v_before * 1.2, "折算日不得造成 +20% 级伪收益"
            return
        env.step(np.zeros(len(env.slots)))
    raise AssertionError("512100 折算日未在决策区间内")


def test_512100_20220902_fill_uses_raw_post_conversion_price() -> None:
    """512100 折算后任何成交必须用 raw post-conversion 价（~2.7），而非折算前 ~1.0。

    折算日（2022-09-05）本身价值中性（qty×0.36555 与价格×2.76 抵消，EW 无需 rebalance）；
    本测试在折算**之后**强制买入 512100，验证成交价 = raw 现价（post-conversion）。
    """
    events = load_corporate_actions()["512100.SH"]
    env = _build_real_env("512100.SH", events)
    env.reset()
    raw512 = _read_raw("CN_SMALL_512100_SH")
    # 折算次日起，任一交易日强制买入 512100（action +1 → 100% 权重）
    while env._i < len(env.calendar) - 1:
        t = env.calendar[env._i]
        if t > REAL_512100_EX:
            # 买入 512100 到满仓：score=[1,0] → 权重 [100%, 0]
            a = np.array([1.0, -1.0])
            obs, r, done, info = env.step(a)
            fills = [f for f in info["step"].fills if f.instrument == "512100.SH"]
            if fills:
                for f in fills:
                    assert f.side == "buy"
                    assert f.price > 2.0, f"折算后成交价 {f.price:.4f} 应为 post-conversion ~2.7 raw"
                return
        env.step(np.zeros(len(env.slots)))
    raise AssertionError("折算后未产生 512100 买入成交")
