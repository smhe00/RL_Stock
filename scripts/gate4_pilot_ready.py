"""GATE_4_PILOT_READY — 机制冒烟（只验证 runner，不训练正式 RL）。

授权范围（评审 §33-§34）：
- Train/Val/Test runner（4 folds，val 60）走通
- 真实数据公司行为（513690 2025-12-17 派息在 F4 test 窗口）验证
- EW baseline + TD3 低预算（train_passes=2，机制冒烟）在 F4
- 边界语义：test 决策数 = 日历行数 - 1（terminal mark）

不训练 3-seed/10-seed；不跑完整 walk-forward。输出 runs/gate4_pilot_ready_smoke.json。
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

from stable_baselines3 import TD3  # noqa: E402

from china_etf.contracts import EnvironmentMode  # noqa: E402
from china_etf.cost.mainland import MainlandETFCostModel  # noqa: E402
from china_etf.data.corporate_actions import load_corporate_actions  # noqa: E402
from china_etf.data.loader import SLOT_MAP, load_execution_prices, load_research_adj  # noqa: E402
from china_etf.environment.portfolio_env import ChinaETFPortfolioEnv  # noqa: E402
from china_etf.evaluation.baselines import equal_weight_policy  # noqa: E402
from china_etf.evaluation.walkforward import WalkForwardRunner  # noqa: E402
from china_etf.execution.broker.mock import MockBroker  # noqa: E402
from china_etf.execution.order_generator import OrderGenerator  # noqa: E402
from china_etf.execution.premium import PremiumGuard  # noqa: E402
from china_etf.execution.tradability import TradabilityMask  # noqa: E402

SEED = 42
SMOKE_TRAIN_PASSES = 2  # 机制冒烟：极低 pass（正式 pilot 用 20）
SMOKE_FOLD_INDEX = 3  # F4（test 含 513690 2025-12-17 派息，验证真实 CA）
SLOTS = list(SLOT_MAP.keys())
CA = load_corporate_actions()


def build_env(adj, opens, closes, corporate_actions=None) -> ChinaETFPortfolioEnv:
    broker = MockBroker(
        tradability=TradabilityMask(),
        premium_guard=PremiumGuard(requires_protection=lambda i: i == "US_BROAD"),
        cost_model=MainlandETFCostModel(),
        open_prices=opens,
    )
    return ChinaETFPortfolioEnv(
        slots=SLOTS,
        adj_close=adj,
        open_prices=opens,
        close_prices=closes,
        initial_cash=1_000_000.0,
        broker=broker,
        order_generator=OrderGenerator(),
        slot_to_instrument={s: SLOT_MAP[s]["instrument"] for s in SLOT_MAP},
        mode=EnvironmentMode.METHOD_RESEARCH,
        corporate_actions=corporate_actions,
    )


def check_ca_513690_in_fold(fold) -> bool:
    """验证 F4 test 窗口内 513690 派息（2025-12-17）在 env step 中被计提。"""
    env = build_env(
        load_research_adj().loc[:fold.test_end],
        {k: v[v.index <= fold.test_end] for k, v in load_execution_prices()[0].items()},
        {k: v[v.index <= fold.test_end] for k, v in load_execution_prices()[1].items()},
        CA,
    )
    env.reset()
    ex = pd.Timestamp("2025-12-17")
    accrued = False
    while env._i < len(env.calendar) - 1:
        t_next = env.calendar[env._i + 1]
        env.step(np.zeros(len(SLOTS)))
        if t_next == ex:
            accrued = "513690.SH" in env.accounting.dividend_receivable
            break
    return accrued


def main() -> None:
    adj = load_research_adj()
    opens, closes = load_execution_prices()
    runner = WalkForwardRunner(
        adj=adj, opens=opens, closes=closes, slots=SLOTS,
        slot_to_instrument={s: SLOT_MAP[s]["instrument"] for s in SLOT_MAP},
        build_env=build_env,
        corporate_actions=CA,
    )
    folds = runner.make_folds(n_folds=4)  # train core 300 + val 60，新 513690 日历
    print("== Track A decision region ==")
    print(f"decision_start = {runner.decision_start.date()}  "
          f"decision_end = {adj.index[-1].date()}  "
          f"decision_days = {(adj.index >= runner.decision_start).sum()}")
    print("\n== 4-fold expanding (train core + val 60 + test) ==")
    fold_rows = []
    for f in folds:
        decision = pd.DatetimeIndex(adj.index[(adj.index >= runner.decision_start) & (adj.index <= f.test_end)])
        train_d = int(((decision >= f.train_start) & (decision <= f.train_end)).sum())
        val_d = int(((decision >= f.val_start) & (decision <= f.val_end)).sum())
        test_d = int(((decision >= f.test_start) & (decision <= f.test_end)).sum())
        fold_rows.append({
            "fold": f.name,
            "train": [str(f.train_start.date()), str(f.train_end.date()), train_d],
            "val": [str(f.val_start.date()), str(f.val_end.date()), val_d],
            "test": [str(f.test_start.date()), str(f.test_end.date()), test_d],
        })
        print(f"  {f.name}: train {train_d:4d}日  val {val_d:2d}日  test {test_d:3d}日  "
              f"[{f.train_start.date()}→{f.test_end.date()}]")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    smoke_fold = folds[SMOKE_FOLD_INDEX]
    print(f"\nsmoke fold = {smoke_fold.name}, device = {device}, TD3 train_passes = {SMOKE_TRAIN_PASSES}")

    results = {
        "seed": SEED, "device": device,
        "track_a": {"decision_start": str(runner.decision_start.date()),
                    "decision_end": str(adj.index[-1].date()),
                    "decision_days": int((adj.index >= runner.decision_start).sum())},
        "folds": fold_rows,
        "smoke_fold": smoke_fold.name,
        "corporate_action_513690_accrued_in_test": None,
        "boundary": {},
        "smoke": {},
    }

    # 真实 CA：513690 派息在 F4 test 窗口被计提
    results["corporate_action_513690_accrued_in_test"] = check_ca_513690_in_fold(smoke_fold)
    print(f"CA 513690 2025-12-17 派息计提: {results['corporate_action_513690_accrued_in_test']}")

    # EW baseline（F4，含 CA）
    m_ew = runner.run_fold_baseline(smoke_fold, equal_weight_policy)
    results["smoke"]["equal_weight"] = m_ew["test"]
    print(f"EW  {smoke_fold.name}: test n_eval={m_ew['test']['n_eval_steps']}  "
          f"cum={m_ew['test']['oos_cum_return']:.4f}  nan={m_ew['test']['nan_obs_or_reward']}")

    # TD3 低预算（机制冒烟）
    t0 = time.time()
    m_td3 = runner.run_fold_rl(
        smoke_fold, TD3, seed=SEED, train_passes=SMOKE_TRAIN_PASSES, net=(256, 256), device=device,
    )
    m_td3["train_seconds"] = round(time.time() - t0, 1)
    results["smoke"]["td3"] = {
        "fold": m_td3["fold"], "kind": m_td3["kind"],
        "train_decision_steps": m_td3["train_decision_steps"],
        "train_passes": m_td3["train_passes"], "total_timesteps": m_td3["total_timesteps"],
        "save_load_deterministic_identical": m_td3["save_load_deterministic_identical"],
        "train_seconds": m_td3["train_seconds"],
        "validation": m_td3["validation"],
        "test": m_td3["test"],
    }
    print(f"TD3 {smoke_fold.name}: train_steps={m_td3['train_decision_steps']} "
          f"timesteps={m_td3['total_timesteps']} save_load={m_td3['save_load_deterministic_identical']} "
          f"train={m_td3['train_seconds']}s")
    v, t = m_td3["validation"], m_td3["test"]
    print(f"   val n_eval={v['n_eval_steps']} cum={v['oos_cum_return']:.4f} nan={v['nan_obs_or_reward']}  "
          f"test n_eval={t['n_eval_steps']} cum={t['oos_cum_return']:.4f} nan={t['nan_obs_or_reward']}")

    # 边界语义：test 决策数 = 测试区日历行数 - 1
    test_env = runner._build_env_upto(smoke_fold.test_end)
    cal = pd.DatetimeIndex(test_env.calendar)
    rows = int((cal >= smoke_fold.test_start).sum())
    boundary = {
        "test_calendar_rows": rows,
        "test_decision_count": m_td3["test"]["n_eval_steps"],
        "decisions_equal_rows_minus_one": m_td3["test"]["n_eval_steps"] == rows - 1,
    }
    results["boundary"] = boundary
    print(f"\nboundary: test rows={rows} decisions={m_td3['test']['n_eval_steps']} "
          f"(rows-1)={rows-1} match={boundary['decisions_equal_rows_minus_one']}")

    out = ROOT / "runs" / "gate4_pilot_ready_smoke.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\nresults -> {out}")


if __name__ == "__main__":
    main()
