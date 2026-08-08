"""GATE_4_PRECHECK — WalkForwardRunner mechanics smoke（只验证 runner，不训练正式 RL）。

授权范围（Reviewer §14）：
- implement WalkForwardRunner / deterministic baselines ✓
- one-fold dry/smoke test：EW + TD3（低步数）在中间 fold 走通 runner 机制
- 正式 one-fold TD3/SAC/PPO seed=42 冒烟延迟到 G4.3 pilot（用户本轮选择）

输出：runs/gate4_precheck_results.json（fold 划分、EW/TD3 smoke 指标、归一化 eval 校验）。
不训练 3-seed/10-seed；不跑完整 walk-forward。
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
from china_etf.data.loader import SLOT_MAP, load_execution_prices, load_research_adj  # noqa: E402
from china_etf.environment.portfolio_env import ChinaETFPortfolioEnv  # noqa: E402
from china_etf.evaluation.baselines import equal_weight_policy  # noqa: E402
from china_etf.evaluation.walkforward import WalkForwardRunner  # noqa: E402
from china_etf.execution.broker.mock import MockBroker  # noqa: E402
from china_etf.execution.order_generator import OrderGenerator  # noqa: E402
from china_etf.execution.premium import PremiumGuard  # noqa: E402
from china_etf.execution.tradability import TradabilityMask  # noqa: E402

SEED = 42
SMOKE_TIMESTEPS = 2_000  # 机制冒烟：极低步数
SMOKE_FOLD_INDEX = 2  # F3（中间 fold，train 足够且 test 非最末）
SLOTS = list(SLOT_MAP.keys())


def build_env(adj, opens, closes) -> ChinaETFPortfolioEnv:
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
    )


def main() -> None:
    adj = load_research_adj()
    opens, closes = load_execution_prices()
    runner = WalkForwardRunner(
        adj=adj, opens=opens, closes=closes, slots=SLOTS,
        slot_to_instrument={s: SLOT_MAP[s]["instrument"] for s in SLOT_MAP},
        build_env=build_env,
    )
    folds = runner.make_folds(n_folds=4)
    print("== Track A decision region ==")
    print(f"decision_start = {runner.decision_start.date()}  "
          f"decision_end = {adj.index[-1].date()}  "
          f"decision_days = {(adj.index >= runner.decision_start).sum()}")
    print("\n== proposed 4-fold expanding walk-forward ==")
    fold_rows = []
    for f in folds:
        decision = adj.index[(adj.index >= runner.decision_start) & (adj.index <= f.test_end)]
        train_days = int(((decision >= f.train_start) & (decision <= f.train_end)).sum())
        test_days = int(((decision >= f.test_start) & (decision <= f.test_end)).sum())
        fold_rows.append({
            "fold": f.name,
            "train_range": [str(f.train_start.date()), str(f.train_end.date())],
            "test_range": [str(f.test_start.date()), str(f.test_end.date())],
            "train_days": train_days,
            "test_days": test_days,
        })
        print(f"  {f.name}: train {train_days:4d}日 [{f.train_start.date()}→{f.train_end.date()}]  "
              f"test {test_days:4d}日 [{f.test_start.date()}→{f.test_end.date()}]")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"\nsmoke fold = {folds[SMOKE_FOLD_INDEX].name}, device = {device}, "
          f"TD3 timesteps = {SMOKE_TIMESTEPS}（机制冒烟，非正式训练）")

    results = {
        "seed": SEED,
        "device": device,
        "track_a": {
            "decision_start": str(runner.decision_start.date()),
            "decision_end": str(adj.index[-1].date()),
            "decision_days": int((adj.index >= runner.decision_start).sum()),
        },
        "folds": fold_rows,
        "smoke_fold": folds[SMOKE_FOLD_INDEX].name,
        "smoke": {},
        "normalized_eval_check": {},
    }

    # --- EW baseline（同一 fold-isolation 路径） ---
    m_ew = runner.run_fold_baseline(folds[SMOKE_FOLD_INDEX], equal_weight_policy)
    results["smoke"]["equal_weight"] = m_ew
    print(f"\nEW    {m_ew['fold']}: n_eval={m_ew['n_eval_steps']}  "
          f"cum={m_ew['oos_cum_return']:.4f}  nan={m_ew['nan_obs_or_reward']}")

    # --- TD3 极低步数（机制冒烟） ---
    t0 = time.time()
    m_td3 = runner.run_fold_rl(
        folds[SMOKE_FOLD_INDEX], TD3, seed=SEED,
        total_timesteps=SMOKE_TIMESTEPS, net=(256, 256), device=device,
    )
    m_td3["train_seconds"] = round(time.time() - t0, 1)
    results["smoke"]["td3"] = m_td3
    print(f"TD3   {m_td3['fold']}: n_eval={m_td3['n_eval_steps']}  "
          f"cum={m_td3['oos_cum_return']:.4f}  nan={m_td3['nan_obs_or_reward']}  "
          f"save_load={m_td3['save_load_deterministic_identical']}  "
          f"train={m_td3['train_seconds']}s")

    # 归一化 eval 校验（修复 gate3 sanity 的 raw-obs eval）：scaler mean=1000，验证 policy 收到 raw-1000
    from china_etf.evaluation.rollout import roll_out  # noqa: E402

    market_dim = 8 * len(SLOTS) + 5
    env_te, gym_te = runner._test_env_for(
        folds[SMOKE_FOLD_INDEX], np.full(market_dim, 1000.0), np.ones(market_dim)
    )
    captured: list[tuple[np.ndarray, np.ndarray]] = []

    def spy(obs):
        raw_now = env_te._observe(env_te.calendar[env_te._i])
        captured.append((obs.copy(), raw_now))
        return np.zeros(len(SLOTS))

    roll_out(env_te, gym_te, spy, folds[SMOKE_FOLD_INDEX].test_start, SLOTS)
    obs0, raw0 = captured[0]
    results["normalized_eval_check"] = {
        "policy_received_market_minus_1000": bool(np.allclose(obs0[0:88], raw0[0:88] - 1000.0, atol=1e-2)),
        "global_normalized": bool(np.allclose(obs0[99:104], raw0[99:104] - 1000.0, atol=1e-2)),
        "weights_untouched": bool(np.allclose(obs0[88:99], raw0[88:99], atol=1e-9)),
        "n_obs_seen": len(captured),
    }
    print("\nnormalized_eval_check:", results["normalized_eval_check"])

    out = ROOT / "runs" / "gate4_precheck_results.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\nresults -> {out}")


if __name__ == "__main__":
    main()
