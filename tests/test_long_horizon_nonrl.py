"""GATE_4_LONG_HORIZON_NON_RL — L1 长区间非-RL 测试（评审 hard guards #1-#10）。

覆盖：
- guard #1  窗口 parity fail-closed（derive-then-assert；篡改数据必须失败）
- guard #2  不用旧 475-day mask（数量 != 475；runner 源码无旧 mask 标识）
- guard #3  6 方法集冻结精确
- guard #4  canonical 参数冻结精确
- guard #5  因果 T+1 单段执行（合成 env 断言执行日 = 决策日后下一交易日）
- guard #7  HS300 研究复权参考独立、可分离
- no-RL     runner 源码无任何 RL 导入/字面量
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from china_etf.data.loader import load_research_adj  # noqa: E402
from china_etf.evaluation.long_horizon_contract import (  # noqa: E402
    CANONICAL_PARAMS, FROZEN_CONTRACT, METHOD_NAMES_FROZEN,
    ContractParityError, check_contract, derive_window,
)

RUNNER_SRC = (ROOT / "scripts" / "gate4_long_horizon_nonrl.py").read_text(encoding="utf-8")


# --- guard #1: 窗口 parity fail-closed ---


def test_frozen_window_parity_real_data() -> None:
    adj = load_research_adj()
    w = derive_window(adj)
    assert str(w["decision_start"].date()) == FROZEN_CONTRACT["decision_start_date"] == "2022-06-09"
    assert str(w["first_execution"].date()) == FROZEN_CONTRACT["start_execution_date"] == "2022-06-10"
    assert str(w["last_decision"].date()) == FROZEN_CONTRACT["last_decision_date"] == "2026-08-06"
    assert str(w["last_execution"].date()) == FROZEN_CONTRACT["end_execution_date"] == "2026-08-07"
    assert w["n_decision_days"] == FROZEN_CONTRACT["n_decision_days"] == 1011
    assert w["n_execution_dates"] == FROZEN_CONTRACT["n_execution_dates"] == 1011
    check_contract(adj)  # no raise


def test_contract_fails_closed_on_tampered_data() -> None:
    adj = load_research_adj()
    with pytest.raises(ContractParityError):
        check_contract(adj.iloc[:-1])  # 删除末行 → last_execution 偏移


# --- guard #2: 不用旧 475-day mask 决定评估日 ---


def test_window_is_not_old_475_mask() -> None:
    adj = load_research_adj()
    w = derive_window(adj)
    assert w["n_decision_days"] != 475
    assert w["n_execution_dates"] != 475
    for tok in ("exact_test_mask", "RESEARCH_BENCHMARK_TEST"):
        assert tok not in RUNNER_SRC, f"runner references forbidden old-mask identifier {tok}"


# --- guard #3: 6 方法集不可变 ---


def test_six_method_set_frozen_exact() -> None:
    assert METHOD_NAMES_FROZEN == [
        "HS300_ref", "EqualWeight", "MaximumDiversification",
        "MinimumVariance", "RiskParity_IVOL", "Momentum_12_1",
    ]
    assert len(METHOD_NAMES_FROZEN) == 6
    for name in METHOD_NAMES_FROZEN:
        assert name in RUNNER_SRC, f"{name} absent from runner"


# --- guard #4: canonical 参数 ---


def test_canonical_params_frozen() -> None:
    assert CANONICAL_PARAMS == {
        "MaximumDiversification": {"lookback": 120, "shrinkage": 0.5},
        "MinimumVariance": {"lookback": 120, "shrinkage": 0.5},
        "RiskParity_IVOL": {"lookback": 60},
        "Momentum_12_1": {"lookback": 252, "skip": 21},
    }
    # runner 必须通过契约常量路由参数（单一事实源，禁硬编码不同值）
    assert "CANONICAL_PARAMS" in RUNNER_SRC
    for tok in ('p["lookback"]', 'p["shrinkage"]', 'p["skip"]'):
        assert tok in RUNNER_SRC, f"runner must route frozen params via CANONICAL_PARAMS ({tok})"


# --- no-RL：runner 无 RL 导入/字面量 ---


def test_no_rl_in_runner_source() -> None:
    for tok in ("PPO", "SAC", "TD3", "stable_baselines3", "torch"):
        assert tok not in RUNNER_SRC, f"runner references RL token {tok}"


# --- guard #7: HS300 研究复权参考独立 ---


def test_hs300_reference_is_research_adjusted_and_separate() -> None:
    adj = load_research_adj()
    w = derive_window(adj)
    exec_dates = adj.index[(adj.index >= w["first_execution"]) & (adj.index <= w["last_execution"])]
    ref = adj["CN_LARGE"].pct_change().reindex(exec_dates)
    assert len(ref) == 1011
    assert ref.notna().all()
    assert "references" in RUNNER_SRC, "HS300 must live in a separate references section"
    assert "CN_LARGE" in RUNNER_SRC


# --- guard #5: 单段因果 T+1 执行（合成 env）---


def _synthetic_env(n=400, seed=5, slots=("S0", "S1", "S2", "S3", "S4", "CASH_LIKE")):
    from china_etf.contracts import EnvironmentMode
    from china_etf.cost.mainland import MainlandETFCostModel
    from china_etf.environment.portfolio_env import ChinaETFPortfolioEnv
    from china_etf.execution.broker.mock import MockBroker
    from china_etf.execution.order_generator import OrderGenerator
    from china_etf.execution.premium import PremiumGuard
    from china_etf.execution.tradability import TradabilityMask
    from china_etf.risk.risk_overlay import RiskOverlayV0
    dates = pd.bdate_range("2021-01-02", periods=n)
    rng = np.random.default_rng(seed)
    adj = pd.DataFrame(
        {s: pd.Series(100 * np.cumprod(1 + rng.normal(0.0002, 0.01, n)), index=dates) for s in slots}
    )
    opens = {s: adj[s] * 0.999 for s in slots}
    closes = {s: adj[s] for s in slots}
    broker = MockBroker(tradability=TradabilityMask(), premium_guard=PremiumGuard(),
                        cost_model=MainlandETFCostModel(), open_prices=opens)
    return ChinaETFPortfolioEnv(
        slots=list(slots), adj_close=adj, open_prices=opens, close_prices=closes,
        initial_cash=1_000_000.0, broker=broker, order_generator=OrderGenerator(),
        slot_to_instrument={s: s for s in slots}, mode=EnvironmentMode.METHOD_RESEARCH,
        risk_overlay=RiskOverlayV0(list(slots), single_core_max=1.0),
    )


def test_rollout_causal_single_segment_execution_dates() -> None:
    """决策日 D 收盘决策 → 执行日 = 下一交易日开盘（T+1，无未来数据）。"""
    from china_etf.environment.gym_wrapper import ChinaETFGymEnv
    from china_etf.evaluation.baselines import equal_weight_policy
    from china_etf.evaluation.rollout import roll_out
    env = _synthetic_env()
    gym = ChinaETFGymEnv(env)
    gym.set_market_scaler(np.zeros(gym._market_dim, np.float32), np.ones(gym._market_dim, np.float32))
    cal = env.calendar
    warmup = env._warmup_index
    reset_at = cal[warmup]       # 决策日（段边界收盘决策）
    eval_start = cal[warmup + 1]  # 首执行日
    m = roll_out(env, gym, equal_weight_policy(env), eval_start, env.slots, reset_at=reset_at)
    dates = m["series"]["execution_dates"]
    expected = [str(d.date()) for d in cal[warmup + 1:]]
    assert dates == expected, "执行日必须 = 决策日后下一交易日（T+1）"
    assert dates[0] == str(cal[warmup + 1].date())
    assert dates[-1] == str(cal[-1].date())
    assert m["n_eval_steps"] == len(cal) - 1 - warmup
    assert len(dates) == len(set(dates)), "执行日无重复（单段连续）"
