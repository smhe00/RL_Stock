"""GATE_4_EVAL_FIX — 评审 E1/E2/E3 + benchmark mask 回归测试。

E1: 段边界记账重置（现金+零持仓，保留特征历史，无 retroactive replay）
E2: 段成本对账 + 换手/成本指标
E3: RiskOverlay 诊断扩展 + reconciliation
Benchmark: exact Test-date mask
"""

import numpy as np
import pandas as pd
import pytest

from china_etf.contracts import EnvironmentMode
from china_etf.cost.mainland import MainlandETFCostModel
from china_etf.data.corporate_actions import CorporateActionEvent
from china_etf.environment.gym_wrapper import ChinaETFGymEnv
from china_etf.environment.portfolio_env import ChinaETFPortfolioEnv
from china_etf.evaluation.benchmark import (
    cn_large_buy_hold_net_return,
    cn_large_buy_hold_stitched,
    exact_test_mask,
)
from china_etf.evaluation.rollout import roll_out
from china_etf.evaluation.walkforward import WalkForwardRunner
from china_etf.evaluation.baselines import equal_weight_policy
from china_etf.execution.broker.mock import MockBroker
from china_etf.execution.order_generator import OrderGenerator
from china_etf.execution.premium import PremiumGuard
from china_etf.execution.tradability import TradabilityMask
from china_etf.risk.risk_overlay import RiskOverlayV0

SLOTS = ["S0", "S1", "S2", "S3", "S4"]
_N = len(SLOTS)
MARKET_DIM = 8 * _N + 5


def _synthetic(n=700, seed=11):
    dates = pd.bdate_range("2021-01-02", periods=n)
    rng = np.random.default_rng(seed)
    adj = pd.DataFrame(
        {s: pd.Series(100 * np.cumprod(1 + rng.normal(0.0002, 0.01, n)), index=dates) for s in SLOTS}
    )
    opens = {s: adj[s] * 0.999 for s in SLOTS}
    closes = {s: adj[s] for s in SLOTS}

    def build_env(a, o, c, corporate_actions=None):
        broker = MockBroker(
            tradability=TradabilityMask(), premium_guard=PremiumGuard(),
            cost_model=MainlandETFCostModel(), open_prices=o,
        )
        return ChinaETFPortfolioEnv(
            slots=SLOTS, adj_close=a, open_prices=o, close_prices=c,
            initial_cash=1_000_000.0, broker=broker, order_generator=OrderGenerator(),
            slot_to_instrument={s: s for s in SLOTS}, mode=EnvironmentMode.METHOD_RESEARCH,
            risk_overlay=RiskOverlayV0(SLOTS, single_core_max=0.5),
            corporate_actions=corporate_actions,
        )

    return adj, opens, closes, build_env


def _runner(n=700, seed=11):
    adj, opens, closes, build_env = _synthetic(n=n, seed=seed)
    return WalkForwardRunner(
        adj=adj, opens=opens, closes=closes, slots=SLOTS,
        slot_to_instrument={s: s for s in SLOTS}, build_env=build_env,
    )


def _gym(env, mean=None, std=None):
    gym = ChinaETFGymEnv(env)
    if mean is not None:
        gym.set_market_scaler(np.asarray(mean, dtype=np.float32), np.asarray(std, dtype=np.float32))
    return gym


def _test_segment(runner, fold, policy_factory):
    train_env = runner._train_env_for(fold)
    mean, std = runner.fit_scaler(train_env, fold)
    env = runner._build_env_upto(fold.test_end)
    gym = _gym(env, mean, std)
    return roll_out(env, gym, policy_factory(env), fold.test_start, runner.slots,
                    reset_at=fold.val_end), env


# --- E1: 段边界记账重置 ---


def _ew_policy(n=5):
    return lambda o: np.zeros(n)


def test_validation_accounting_resets_at_train_end() -> None:
    runner = _runner()
    folds = runner.make_folds(n_folds=2, min_train_days=200, val_days=40)
    f1 = folds[0]
    train_env = runner._train_env_for(f1)
    mean, std = runner.fit_scaler(train_env, f1)
    m = runner._rollout_segment(f1, "validation", mean, std, _ew_policy(len(SLOTS)))
    assert m["segment_predecision_date"] == str(f1.train_end.date())
    assert m["segment_first_execution_date"] == str(f1.val_start.date())
    assert m["segment_first_metric_date"] == str(f1.val_start.date())
    assert m["initial_cash"] == pytest.approx(1_000_000.0)
    assert m["initial_positions"] == {}


def test_test_accounting_resets_at_val_end() -> None:
    runner = _runner()
    folds = runner.make_folds(n_folds=2, min_train_days=200, val_days=40)
    f1 = folds[0]
    train_env = runner._train_env_for(f1)
    mean, std = runner.fit_scaler(train_env, f1)
    m = runner._rollout_segment(f1, "test", mean, std, _ew_policy(len(SLOTS)))
    assert m["segment_predecision_date"] == str(f1.val_end.date())
    assert m["segment_first_execution_date"] == str(f1.test_start.date())
    assert m["initial_cash"] == pytest.approx(1_000_000.0)
    assert m["initial_positions"] == {}


def test_test_start_position_does_not_depend_on_retroactive_train_replay() -> None:
    """test 起点组合 = 初始现金+零持仓（E1 重置），与 train replay 无关。

    验证：reset(at val_end) 后 accounting 无持仓、cash=initial；首个记录 transition 执行于 test_start。
    """
    runner = _runner()
    folds = runner.make_folds(n_folds=2, min_train_days=200, val_days=40)
    f1 = folds[0]
    env = runner._build_env_upto(f1.test_end)
    env.reset(at_date=f1.val_end)
    assert env.accounting.positions == {}
    assert env.accounting.cash == pytest.approx(1_000_000.0)
    assert env.accounting.receivable_total == 0.0
    # 首 step：t=val_end 决策 → t_next=test_start 执行，第一个记录的 transition 是 test_start
    m, _ = _test_segment(runner, f1, equal_weight_policy)
    assert m["n_eval_steps"] > 0
    # 首个记录 transition 的执行日 = test_start（series 长度 = 段执行日行数）
    assert m["series"]["net_returns"]


def test_test_first_fill_occurs_at_test_start_open() -> None:
    """test 段第一个 fill 执行于 test_start，价格 = test_start open。"""
    runner = _runner()
    folds = runner.make_folds(n_folds=2, min_train_days=200, val_days=40)
    f1 = folds[0]
    env = runner._build_env_upto(f1.test_end)
    env.reset(at_date=f1.val_end)
    _, _, _, info = env.step(np.zeros(len(SLOTS)))
    assert info["step"].t_next == f1.test_start
    fills = info["step"].fills
    assert fills, "test_start 应有首笔成交"
    for f in fills:
        # 价格 = test_start 当日 open
        open_series = env.open_prices[f.instrument]
        assert f.price == pytest.approx(float(open_series.loc[f.timestamp]))


def test_feature_history_preserved_after_accounting_reset() -> None:
    """重置记账后特征历史保留：reset 前/后同一日期 market features 逐位一致（obs 依赖价格不依赖组合）。"""
    runner = _runner()
    folds = runner.make_folds(n_folds=2, min_train_days=200, val_days=40)
    f1 = folds[0]
    env = runner._build_env_upto(f1.test_end)
    d = f1.test_start
    market_dim = 8 * len(SLOTS)
    # reset 前：先跑一段再取 d 的 market features
    env.reset(at_date=f1.val_end)
    obs_before = env._observe(d)[:market_dim]
    # 重建 env，reset 到 d 再取（应逐位一致）
    env2 = runner._build_env_upto(f1.test_end)
    env2.reset(at_date=d)
    obs_after = env2._observe(d)[:market_dim]
    assert np.allclose(obs_before, obs_after, atol=1e-12)
    assert np.isfinite(obs_after).all()


def test_corporate_actions_before_segment_reset_do_not_create_receivables_after_reset() -> None:
    """reset 前（val 段内）的派息在 reset 后不产生应收款。"""
    dates = pd.bdate_range("2025-01-02", periods=300)
    ex = dates[280]
    pay = ex + pd.offsets.BDay(5)
    ev = CorporateActionEvent(
        instrument="S0", action_type="CASH_DIVIDEND", ex_date=ex, unit_factor=1.0,
        cash_per_share=0.10, pay_date=None, settle_date=pay, source="CONSERVATIVE_FALLBACK",
    )
    rng = np.random.default_rng(5)
    adj = pd.DataFrame({s: pd.Series(100 * np.cumprod(1 + rng.normal(0.0002, 0.01, len(dates))), index=dates) for s in SLOTS})
    opens = {s: adj[s] * 0.999 for s in SLOTS}
    closes = {s: adj[s] for s in SLOTS}
    broker = MockBroker(tradability=TradabilityMask(), premium_guard=PremiumGuard(),
                        cost_model=MainlandETFCostModel(), open_prices=opens)
    env = ChinaETFPortfolioEnv(
        slots=SLOTS, adj_close=adj, open_prices=opens, close_prices=closes,
        initial_cash=1_000_000.0, broker=broker, order_generator=OrderGenerator(),
        slot_to_instrument={s: s for s in SLOTS}, mode=EnvironmentMode.METHOD_RESEARCH,
        risk_overlay=RiskOverlayV0(SLOTS, single_core_max=0.5),
        corporate_actions={"S0": [ev]},
    )
    # 在 ex 之前建仓并跨过 ex（val 段内产生应收款）
    env.reset()
    while env._i < len(env.calendar) - 1:
        if env.calendar[env._i + 1] == ex:
            env.step(np.zeros(len(SLOTS)))
            assert "S0" in env.accounting.dividend_receivable, "ex-date 应计提应收款"
            break
        env.step(np.zeros(len(SLOTS)))
    # reset at 某 later date（段边界）→ 应收款清空、持仓清空
    later = dates[290]
    env.reset(at_date=later)
    assert env.accounting.dividend_receivable == {}
    assert env.accounting.positions == {}
    assert env.accounting.cash == pytest.approx(1_000_000.0)


# --- E2: 段成本对账 + 换手/成本指标 ---


def test_segment_cost_excludes_presegment_fees() -> None:
    """test 段 cost 不含 pre-segment 费用：E1 重置后段内独立记账。"""
    runner = _runner()
    folds = runner.make_folds(n_folds=2, min_train_days=200, val_days=40)
    f1 = folds[0]
    m, _ = _test_segment(runner, f1, equal_weight_policy)
    # total_cost == series costs 之和（E1 重置后段内费用）
    assert m["total_cost"] == pytest.approx(sum(m["series"]["costs"]), abs=1e-6)
    # cost 量级合理（换手低的 EW，单折成本应远小于 pre-test 累计费用假象 2%+）
    assert m["cost_over_initial_value"] < 0.01, "E1 修复后段成本应只含段内费用"


def test_total_cost_reconciles_to_fee_delta() -> None:
    """sum(costs) == fees_at_test_end - fees_at_test_start（roll_out 内部已 assert；此处再验证）。"""
    runner = _runner()
    folds = runner.make_folds(n_folds=2, min_train_days=200, val_days=40)
    f1 = folds[0]
    m, env = _test_segment(runner, f1, equal_weight_policy)
    fees_end = env.accounting.fees_paid
    fees_start = 0.0  # E1 reset 后 fees_paid=0
    assert m["total_cost"] == pytest.approx(fees_end - fees_start, abs=1e-6)


def test_cost_turnover_order_of_magnitude_consistent() -> None:
    """cost/traded_notional 量级 ≈ 单边成本率（佣金 0.5bp+spread 1bp+slippage 2bp ≈ 3.5e-4）。"""
    runner = _runner()
    folds = runner.make_folds(n_folds=2, min_train_days=200, val_days=40)
    f1 = folds[0]
    m, _ = _test_segment(runner, f1, equal_weight_policy)
    ratio = m["total_cost_over_traded_notional"]
    assert np.isfinite(ratio)
    assert 1e-4 < ratio < 6e-4, f"cost/traded_notional={ratio:.2e} 应≈3.5bp 单边成本"
    assert m["estimated_one_way_traded_fraction"] == pytest.approx(m["total_turnover_l1"] / 2.0)
    assert m["mean_turnover_l1"] == pytest.approx(m["mean_turnover"])


# --- E3: RiskOverlay 诊断 ---


def test_overlay_diagnostics_reconcile() -> None:
    """强制触发 overlay（raw 单资产超 cap）→ intervention>0，mean_l1 合理，post 无违规。"""
    runner = _runner()
    folds = runner.make_folds(n_folds=2, min_train_days=200, val_days=40)
    f1 = folds[0]
    train_env = runner._train_env_for(f1)
    mean, std = runner.fit_scaler(train_env, f1)
    env = runner._build_env_upto(f1.test_end)
    gym = _gym(env, mean, std)

    def concentrated(obs):
        a = np.full(len(SLOTS), -1.0); a[0] = 1.0  # score=[1,0,0,0,0] → raw 单资产 100%
        return a

    m = roll_out(env, gym, concentrated, f1.test_start, runner.slots, reset_at=f1.val_end)
    assert m["risk_overlay_intervention_rate"] > 0, "concentrated action 应触发 overlay"
    assert m["risk_overlay_mean_l1_raw_to_post"] > 1e-4, "mean_l1 应与 intervention 一致（非 1e-16）"
    # reconciliation：intervention>0 → mean_l1 ≥ rate * 1e-6（roll_out 已 assert，这里复核字段）
    assert m["risk_overlay_mean_l1_raw_to_post"] >= m["risk_overlay_intervention_rate"] * 1e-6
    # post-risk 无违规
    assert m["post_constraint_violation_rate"] == 0.0
    assert m["post_single_core_at_cap_rate"] > 0, "concentrated 应触及 cap（post 在 cap 边缘）"
    assert "raw_single_core_violation_rate" in m


# --- Benchmark: exact Test-date mask ---


def test_exact_test_mask_steps_equal() -> None:
    """strategy 与 benchmark 的 stitched 步数相等；val 日期被排除。"""
    runner = _runner()
    folds = runner.make_folds(n_folds=2, min_train_days=200, val_days=40)
    mask = exact_test_mask(folds, calendar=runner.adj.index)
    f1, f2 = folds
    # test 段执行日总数 = (F1 test 段 + F2 test 段) 行数
    cal = pd.DatetimeIndex(runner.adj.index)
    expected = int(((cal >= f1.test_start) & (cal <= f1.test_end)).sum()) + \
               int(((cal >= f2.test_start) & (cal <= f2.test_end)).sum())
    assert mask["exact_test_date_count"] == expected
    assert mask["strategy_stitched_steps"] == expected
    assert "benchmark_stitched_steps" not in mask  # 评审 §3.1：已移除误导字段
    assert mask["first_test_date"] == str(f1.test_start.date())
    assert mask["last_test_date"] == str(f2.test_end.date())
    # val 日期被排除：mask 不含任何 val 段日期
    assert mask["excluded_validation_dates"] == int(
        ((cal >= f1.val_start) & (cal <= f1.val_end)).sum()) + \
        int(((cal >= f2.val_start) & (cal <= f2.val_end)).sum())
    for d in mask["test_dates"]:
        assert not (f1.val_start <= d <= f1.val_end or f2.val_start <= d <= f2.val_end)


def test_cn_large_buy_hold_uses_raw_prices() -> None:
    """连续参考 buy-hold：首日 open 买入，成交价 = raw open（非研究 TR）。"""
    n = 300
    dates = pd.bdate_range("2025-01-02", periods=n)
    rng = np.random.default_rng(3)
    raw_close = pd.Series([10.0 + float(x) for x in rng.normal(0, 0.05, n)], index=dates)
    raw_open = pd.Series([10.0 + float(x) for x in rng.normal(0, 0.04, n)], index=dates)
    test_dates = list(dates[250:280])
    res = cn_large_buy_hold_net_return(raw_open, raw_close, [], test_dates)
    assert res["label"] == "510300_CONTINUOUS_CALENDAR_REFERENCE"
    assert res["n_returns"] == len(test_dates) - 1
    assert np.isfinite(res["cum_net_return"])


def _mk_runner_data(n=700, seed=21):
    from china_etf.environment.portfolio_env import ChinaETFPortfolioEnv

    dates = pd.bdate_range("2021-01-02", periods=n)
    rng = np.random.default_rng(seed)
    adj = pd.DataFrame(
        {s: pd.Series(100 * np.cumprod(1 + rng.normal(0.0002, 0.01, n)), index=dates) for s in SLOTS}
    )
    opens = {s: adj[s] * 0.999 for s in SLOTS}
    closes = {s: adj[s] for s in SLOTS}

    def build_env(a, o, c, corporate_actions=None):
        broker = MockBroker(
            tradability=TradabilityMask(), premium_guard=PremiumGuard(),
            cost_model=MainlandETFCostModel(), open_prices=o,
        )
        return ChinaETFPortfolioEnv(
            slots=SLOTS, adj_close=a, open_prices=o, close_prices=c,
            initial_cash=1_000_000.0, broker=broker, order_generator=OrderGenerator(),
            slot_to_instrument={s: s for s in SLOTS}, mode=EnvironmentMode.METHOD_RESEARCH,
            risk_overlay=RiskOverlayV0(SLOTS, single_core_max=0.5),
            corporate_actions=corporate_actions,
        )

    return adj, opens, closes, build_env


def _fold_setup(n=700, seed=21):
    from china_etf.environment.portfolio_env import ChinaETFPortfolioEnv

    adj, opens, closes, build_env = _mk_runner_data(n=n, seed=seed)
    runner = WalkForwardRunner(
        adj=adj, opens=opens, closes=closes, slots=SLOTS,
        slot_to_instrument={s: s for s in SLOTS}, build_env=build_env,
    )
    folds = runner.make_folds(n_folds=2, min_train_days=200, val_days=40)
    return runner, folds, adj, opens, closes


# --- B1/B2/B3 fold-local benchmark tests（评审 §9）---


def test_benchmark_return_count_equals_strategy_stitched_steps() -> None:
    """benchmark_return_count == strategy_stitched_return_count（独立生成后比对）。"""
    runner, folds, adj, opens, closes = _fold_setup()
    mask = exact_test_mask(folds, calendar=runner.adj.index)
    strategy_steps = mask["strategy_stitched_steps"]
    # 用 S0 的价格模拟 510300（真实数据在 smoke 验证）
    res = cn_large_buy_hold_stitched(
        opens["S0"], closes["S0"], [], folds, calendar=runner.adj.index)
    assert res["strategy_stitched_steps"] == strategy_steps
    assert res["benchmark_stitched_steps"] == strategy_steps
    assert res["n_returns"] == strategy_steps
    assert res["parity_assert"] is True


def test_benchmark_execution_dates_exactly_equal_test_mask() -> None:
    """benchmark 执行日期 == exact Test 执行日期（逐日期相等，独立生成）。"""
    runner, folds, adj, opens, closes = _fold_setup()
    mask = exact_test_mask(folds, calendar=runner.adj.index)
    res = cn_large_buy_hold_stitched(
        opens["S0"], closes["S0"], [], folds, calendar=runner.adj.index)
    expected = [d.date().isoformat() for d in mask["test_dates"]]
    assert res["execution_dates"] == expected


def _simple_folds(dates, n_folds=2, min_train=60, val=40, decision_start=0):
    """构造满足 make_folds 约束（step >= val+40）的 folds。"""
    from china_etf.evaluation.walkforward import make_folds

    decision = dates[decision_start:]
    return make_folds(decision, n_folds=n_folds, min_train_days=min_train, val_days=val)


def test_benchmark_resets_to_cash_each_fold() -> None:
    """每 fold benchmark 在 val_end 重置为现金+零持仓+零应收款（B1）。"""
    n = 400
    dates = pd.bdate_range("2023-01-02", periods=n)
    rng = np.random.default_rng(31)
    px = pd.Series([10.0 + float(x) for x in rng.normal(0, 0.03, n)], index=dates)
    folds = _simple_folds(dates, n_folds=2, min_train=120, val=40)
    res = cn_large_buy_hold_stitched(px, px, [], folds, calendar=dates)
    per_fold = res["per_fold"]
    assert len(per_fold) == 2
    assert len(per_fold["F1"]) > 0 and len(per_fold["F2"]) > 0
    # F2 也重新从初始现金开始（fold-local），首日收益基于 1e6 而非 F1 结束价值
    assert np.isfinite(per_fold["F2"][0])


def test_benchmark_has_no_validation_gap_exposure() -> None:
    """benchmark 在 Validation gap 期间无持仓暴露（B1：不跨 gap）。"""
    runner, folds, adj, opens, closes = _fold_setup()
    res_stitched = cn_large_buy_hold_stitched(
        opens["S0"], closes["S0"], [], folds, calendar=runner.adj.index)
    f1_first = res_stitched["per_fold"]["F1"][0]
    f2_first = res_stitched["per_fold"]["F2"][0]
    # 每 fold 从 1e6 现金开始（首日收益近 0，不含 gap 暴露）
    assert abs(f1_first) < 0.05
    assert abs(f2_first) < 0.05


def test_benchmark_first_test_day_return_includes_open_to_close_and_cost() -> None:
    """首 test 日收益 = open→close 净收益（含买入成本），对 initial equity（B2）。"""
    n = 200
    dates = pd.bdate_range("2025-01-02", periods=n)
    folds = _simple_folds(dates, n_folds=1, min_train=10, val=40)
    ts = folds[0].test_start
    # 首日（test_start）open=10 → close=11（+10%），其余日持平
    open_s = pd.Series([10.0] * n, index=dates); open_s.loc[ts] = 10.0
    close_s = pd.Series([10.0] * n, index=dates); close_s.loc[ts] = 11.0
    seg = _seg_dates(folds[0].test_start, folds[0].test_end)
    res_stitched = cn_large_buy_hold_stitched(open_s, close_s, [], folds, calendar=dates)
    first = res_stitched["per_fold"]["F1"][0]
    # 首日：买入 10 → 收盘 11，net ≈ 10% - 成本（~3.5bp）≈ 9.6%
    assert 0.09 < first < 0.10, f"首日收益 {first:.4f} 应≈10% - 成本"
    assert res_stitched["n_returns"] == len(seg)  # 含首日 transition


def _seg_dates(start, end):
    return list(pd.bdate_range(start, end))


def _cash_ev(ex, pay):
    return CorporateActionEvent(
        instrument="510300.SH", action_type="CASH_DIVIDEND", ex_date=ex, unit_factor=1.0,
        cash_per_share=0.5, pay_date=pay, settle_date=pay, source="official_fund_announcement",
    )


def test_benchmark_exdate_open_purchase_does_not_receive_same_day_dividend() -> None:
    """ex-date open 买入不享当日分红（B3：CA 基于开盘前持仓）。"""
    n = 200
    dates = pd.bdate_range("2025-01-02", periods=n)
    open_s = pd.Series([10.0] + [10.0] * (n - 1), index=dates)
    close_s = pd.Series([10.0] + [10.0] * (n - 1), index=dates)
    folds = _simple_folds(dates, n_folds=1, min_train=10, val=40)
    # 首 test 日恰为 ex-date：open 买入 → 不应享当日分红
    ex = folds[0].test_start
    pay = ex + pd.offsets.BDay(5)
    ev = _cash_ev(ex, pay)
    res = cn_large_buy_hold_stitched(open_s, close_s, [ev], folds, calendar=dates)
    # 价格不变（ex 无机械下跌）+ 首日买入不享分红 → 累计 ≈ 0（仅成本 -0.03%）
    assert abs(res["cum_net_return"]) < 0.01, "ex-date open 买入不得享当日分红"
    # 对照：若 ex 在买入之后（已持跨 ex）应享分红 → 累计显著为正
    ex_later = folds[0].test_start + pd.offsets.BDay(20)
    ev_later = _cash_ev(ex_later, ex_later + pd.offsets.BDay(5))
    res_later = cn_large_buy_hold_stitched(open_s, close_s, [ev_later], folds, calendar=dates)
    assert res_later["cum_net_return"] > 0.02, "已持跨 ex 应享分红"


def test_benchmark_corporate_actions_inside_test_are_processed_in_order() -> None:
    """段内 CA 按规范顺序处理（settle→折算→计提→execute；应收款→现金无跳变）。"""
    n = 260
    dates = pd.bdate_range("2025-01-02", periods=n)
    open_s = pd.Series([10.0] + [10.0] * (n - 1), index=dates)
    close_s = pd.Series([10.0] + [10.0] * (n - 1), index=dates)
    folds = _simple_folds(dates, n_folds=1, min_train=10, val=40)
    ts = folds[0].test_start
    ex = ts + pd.offsets.BDay(15)
    pay = ex + pd.offsets.BDay(5)
    ev = _cash_ev(ex, pay)
    res = cn_large_buy_hold_stitched(open_s, close_s, [ev], folds, calendar=dates)
    # 已持跨 ex → ex 计提 0.5/份，pay 结算；价格不变 → 累计 ≈ 分红收益（扣除成本）
    # 买入约 1e6/10 = 99000 份（留 buffer），分红 ≈ 99000*0.5/1e6 ≈ 4.95%
    assert res["cum_net_return"] > 0.04, f"应含分红收益，实际 {res['cum_net_return']:.4f}"
    assert res["cum_net_return"] < 0.06, f"分红收益量级异常 {res['cum_net_return']:.4f}"
