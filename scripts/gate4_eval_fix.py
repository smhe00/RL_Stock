"""GATE_4_EVAL_FIX — 修复后 corrected seed42 mechanics/regression smoke（评审要求：不重跑全部 36）。

验证：
1. E1 段边界记账重置生效（test 从 val_end 重置，首执行 test_start open，manifest 字段）
2. E2 段成本对账 assert 通过（total_cost == fees delta）
3. E3 RiskOverlay 诊断扩展 + reconciliation（TD3 早期干预率高时 mean_l1 合理）
4. Benchmark：exact Test-mask 步数相等 + 可执行 510300 buy-hold
5. 1 个 fold 的 TD3/SAC/PPO（低 passes 机制冒烟）

输出：runs/gate4_eval_fix_smoke.json
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stable_baselines3 import PPO, SAC, TD3  # noqa: E402

from china_etf.contracts import EnvironmentMode  # noqa: E402
from china_etf.cost.mainland import MainlandETFCostModel  # noqa: E402
from china_etf.data.corporate_actions import load_corporate_actions  # noqa: E402
from china_etf.data.loader import SLOT_MAP, load_execution_prices, load_research_adj  # noqa: E402
from china_etf.environment.portfolio_env import ChinaETFPortfolioEnv  # noqa: E402
from china_etf.evaluation.baselines import equal_weight_policy  # noqa: E402
from china_etf.evaluation.benchmark import cn_large_buy_hold_net_return, exact_test_mask  # noqa: E402
from china_etf.evaluation.walkforward import WalkForwardRunner  # noqa: E402
from china_etf.execution.broker.mock import MockBroker  # noqa: E402
from china_etf.execution.order_generator import OrderGenerator  # noqa: E402
from china_etf.execution.premium import PremiumGuard  # noqa: E402
from china_etf.execution.tradability import TradabilityMask  # noqa: E402

SEED = 42
SMOKE_PASSES = 2  # 机制冒烟（正式 20）
SMOKE_FOLD = "F1"
SLOTS = list(SLOT_MAP.keys())
CA = load_corporate_actions()


def build_env(adj, opens, closes, corporate_actions=None) -> ChinaETFPortfolioEnv:
    broker = MockBroker(
        tradability=TradabilityMask(),
        premium_guard=PremiumGuard(requires_protection=lambda i: i == "US_BROAD"),
        cost_model=MainlandETFCostModel(), open_prices=opens,
    )
    return ChinaETFPortfolioEnv(
        slots=SLOTS, adj_close=adj, open_prices=opens, close_prices=closes,
        initial_cash=1_000_000.0, broker=broker, order_generator=OrderGenerator(),
        slot_to_instrument={s: SLOT_MAP[s]["instrument"] for s in SLOT_MAP},
        mode=EnvironmentMode.METHOD_RESEARCH, corporate_actions=corporate_actions,
    )


def main() -> None:
    adj = load_research_adj()
    opens, closes = load_execution_prices()
    runner = WalkForwardRunner(
        adj=adj, opens=opens, closes=closes, slots=SLOTS,
        slot_to_instrument={s: SLOT_MAP[s]["instrument"] for s in SLOT_MAP},
        build_env=build_env, corporate_actions=CA,
    )
    folds = runner.make_folds(n_folds=4)
    fold = next(f for f in folds if f.name == SMOKE_FOLD)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    results = {"fold": SMOKE_FOLD, "device": device, "train_passes": SMOKE_PASSES,
               "rl": {}, "benchmark": {}, "manifest": {}}

    print(f"== E1/E2/E3 smoke: fold={SMOKE_FOLD} seed={SEED} device={device} ==")

    # --- Benchmark: exact mask + 可执行 buy-hold ---
    mask = exact_test_mask(folds, calendar=adj.index)
    results["benchmark"]["mask"] = {k: v for k, v in mask.items() if k != "test_dates"}
    assert mask["strategy_stitched_steps"] == mask["benchmark_stitched_steps"]
    print(f"test-mask steps={mask['exact_test_date_count']} "
          f"first={mask['first_test_date']} last={mask['last_test_date']} "
          f"excluded_val={mask['excluded_validation_dates']}")

    raw_open_510 = load_execution_prices()[0]["510300.SH"]
    raw_close_510 = load_execution_prices()[1]["510300.SH"]
    bh = cn_large_buy_hold_net_return(
        raw_open_510, raw_close_510, CA.get("510300.SH", []), mask["test_dates"])
    results["benchmark"]["cn_large_executable_buy_hold"] = {
        "label": bh["label"], "cum_net_return": round(bh["cum_net_return"], 5),
        "n_returns": bh["n_returns"], "total_cost": round(bh["total_cost"], 2)}
    print(f"CN_LARGE_EXECUTABLE_NET_BUY_HOLD cum={bh['cum_net_return']:.4f} "
          f"n={bh['n_returns']} cost={bh['total_cost']:.0f}")

    # --- RL 冒烟（3 algos × 1 fold，低 passes）---
    for algo_name, algo_cls, dev in [("TD3", TD3, "cuda"), ("SAC", SAC, "cuda"), ("PPO", PPO, "cpu")]:
        t0 = time.time()
        run = runner.run_fold_rl(fold, algo_cls, seed=SEED, train_passes=SMOKE_PASSES,
                                 net=(256, 256), device=dev)
        dt = round(time.time() - t0, 1)
        test = run["test"]
        # E1 manifest
        results["manifest"][algo_name] = {
            "segment_predecision_date": test["segment_predecision_date"],
            "segment_first_execution_date": test["segment_first_execution_date"],
            "segment_first_metric_date": test["segment_first_metric_date"],
            "initial_cash": test["initial_cash"],
            "initial_positions": test["initial_positions"],
        }
        # E2 对账已在 roll_out 内部 assert（不抛异常即通过）；这里复核
        assert test["total_cost"] == pytest_sum(test["series"]["costs"]), "E2 对账"
        # E3 诊断
        e3 = {k: test[k] for k in ["risk_overlay_intervention_rate",
                                   "risk_overlay_mean_l1_raw_to_post",
                                   "raw_single_core_violation_rate",
                                   "post_constraint_violation_rate",
                                   "post_single_core_at_cap_rate"]}
        results["rl"][algo_name] = {
            "train_seconds": dt, "total_timesteps": run["total_timesteps"],
            "save_load_deterministic_identical": run["save_load_deterministic_identical"],
            "test_cum": round(test["oos_cum_return"], 5),
            "test_n_eval": test["n_eval_steps"],
            "test_nan": test["nan_obs_or_reward"],
            "test_neg_cash": test["negative_cash_count"],
            "cost_over_initial_equity": round(test["cost_over_initial_equity"], 6),
            "e3": e3,
        }
        print(f"[{algo_name}] {dt}s  cum={test['oos_cum_return']:.4f}  "
              f"nan={test['nan_obs_or_reward']} neg_cash={test['negative_cash_count']} "
              f"cost_over_init={test['cost_over_initial_equity']:.5f} "
              f"e3_intervention={test['risk_overlay_intervention_rate']:.3f}")

    # E1 关键验证：test 首执行日 == test_start；n_eval == test 段执行日行数
    cal = pd.DatetimeIndex(adj.index)
    test_rows = int(((cal >= fold.test_start) & (cal <= fold.test_end)).sum())
    for algo_name, run_ in results["rl"].items():
        assert results["manifest"][algo_name]["segment_first_execution_date"] == str(fold.test_start.date())
        assert run_["test_n_eval"] == test_rows, f"{algo_name} n_eval 应为 {test_rows}"
    print(f"\nE1 verified: all algos first_execution={fold.test_start.date()} n_eval={test_rows}")

    out = ROOT / "runs" / "gate4_eval_fix_smoke.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\n-> {out}")


def pytest_sum(xs):
    return float(sum(xs))


if __name__ == "__main__":
    main()
