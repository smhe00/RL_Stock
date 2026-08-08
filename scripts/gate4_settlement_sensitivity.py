"""GATE_4_EVAL_FIX — OOS fallback pay-date settlement-delay sensitivity（评审 §OOS fallback pay dates）。

7 个保守 fallback 派息事件落入 OOS test 窗口。akshare 公告无结构化派息日 → 走评审选项 2：
settlement-delay sensitivity（+3T/+5T/+7T）on baselines + 1 代表性 RL seed，证明 immaterial impact。

理论依据：settle_date 只影响现金时点（应收款 vs 现金均 1:1 计入 portfolio_value），
决策 obs 不含 cash → 权重路径与 settle lag 无关。RL 只需训一次模型，3 种 lag 各 eval 重放。

输出：runs/gate4_settlement_sensitivity.json
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

from stable_baselines3 import PPO  # noqa: E402

from china_etf.contracts import EnvironmentMode  # noqa: E402
from china_etf.cost.mainland import MainlandETFCostModel  # noqa: E402
from china_etf.data.corporate_actions import load_corporate_actions  # noqa: E402
from china_etf.data.loader import SLOT_MAP, load_execution_prices, load_research_adj  # noqa: E402
from china_etf.environment.gym_wrapper import ChinaETFGymEnv  # noqa: E402
from china_etf.environment.portfolio_env import ChinaETFPortfolioEnv  # noqa: E402
from china_etf.evaluation.baselines import (  # noqa: E402
    equal_weight_policy, minimum_variance_policy, momentum_policy, risk_parity_policy,
)
from china_etf.evaluation.rollout import roll_out  # noqa: E402
from china_etf.evaluation.walkforward import WalkForwardRunner  # noqa: E402
from china_etf.execution.broker.mock import MockBroker  # noqa: E402
from china_etf.execution.order_generator import OrderGenerator  # noqa: E402
from china_etf.execution.premium import PremiumGuard  # noqa: E402
from china_etf.execution.tradability import TradabilityMask  # noqa: E402

LAGS = [3, 5, 7]
BASELINES = [
    ("EqualWeight", equal_weight_policy), ("RiskParity", risk_parity_policy),
    ("MinimumVariance", minimum_variance_policy), ("Momentum", momentum_policy),
]
RL_SEED = 42
RL_PASSES = 20
RL_FOLD = "F2"  # 含 512100 2025-01-15 fallback 的 test 窗口（代表 seed 单折）
SLOTS = list(SLOT_MAP.keys())
DEVICE = "cpu"  # PPO 按 Gate 3 冻结 device 映射


def build_env_factory(ca):
    def build_env(adj, opens, closes, corporate_actions=None):
        broker = MockBroker(
            tradability=TradabilityMask(),
            premium_guard=PremiumGuard(requires_protection=lambda i: i == "US_BROAD"),
            cost_model=MainlandETFCostModel(), open_prices=opens,
        )
        return ChinaETFPortfolioEnv(
            slots=SLOTS, adj_close=adj, open_prices=opens, close_prices=closes,
            initial_cash=1_000_000.0, broker=broker, order_generator=OrderGenerator(),
            slot_to_instrument={s: SLOT_MAP[s]["instrument"] for s in SLOT_MAP},
            mode=EnvironmentMode.METHOD_RESEARCH, corporate_actions=ca,
        )
    return build_env


def main() -> None:
    adj = load_research_adj()
    opens, closes = load_execution_prices()
    results = {"lags": LAGS, "baselines": {}, "rl_representative": {}, "rl_theory": {}}

    # --- baselines sensitivity（无训练）---
    print("== baselines settlement sensitivity ==")
    for lag in LAGS:
        ca = load_corporate_actions(pay_lag_bdays=lag)
        runner = WalkForwardRunner(
            adj=adj, opens=opens, closes=closes, slots=SLOTS,
            slot_to_instrument={s: SLOT_MAP[s]["instrument"] for s in SLOT_MAP},
            build_env=build_env_factory(ca), corporate_actions=ca,
        )
        folds = runner.make_folds(n_folds=4)
        results["baselines"][str(lag)] = {}
        for name, fac in BASELINES:
            cums = []
            for f in folds:
                m = runner.run_fold_baseline(f, fac)
                cums.append(m["test"]["oos_cum_return"])
            prod = 1.0
            for c in cums:
                prod *= (1.0 + c)
            results["baselines"][str(lag)][name] = {
                "per_fold_cum": [round(c, 5) for c in cums],
                "stitched_cum": round(prod - 1.0, 5),
            }
            print(f"  lag={lag}T {name:16s} stitched_cum={prod-1:.4f}")
    # 基线（lag=5 = pilot 默认）作为基准，量级差
    base5 = results["baselines"]["5"]

    # --- RL 代表性：训 PPO|42 单折（F2）一次，3 种 lag eval ---
    print("\n== RL representative (PPO|42 F2, train once, eval 3 lags) ==")
    ca5 = load_corporate_actions(pay_lag_bdays=5)
    runner5 = WalkForwardRunner(
        adj=adj, opens=opens, closes=closes, slots=SLOTS,
        slot_to_instrument={s: SLOT_MAP[s]["instrument"] for s in SLOT_MAP},
        build_env=build_env_factory(ca5), corporate_actions=ca5,
    )
    folds = runner5.make_folds(n_folds=4)
    fold = next(f for f in folds if f.name == RL_FOLD)
    t0 = time.time()
    train_env = runner5._train_env_for(fold)
    mean, std = runner5.fit_scaler(train_env, fold)
    gym_tr = ChinaETFGymEnv(train_env)
    gym_tr.set_market_scaler(mean, std)
    train_steps = runner5._train_decision_steps(train_env)
    model = PPO("MlpPolicy", gym_tr, seed=RL_SEED, policy_kwargs={"net_arch": [256, 256]},
                verbose=0, device=DEVICE)
    model.learn(total_timesteps=int(train_steps) * RL_PASSES)
    train_sec = round(time.time() - t0, 1)
    print(f"  trained PPO|{RL_SEED} {RL_FOLD} in {train_sec}s (train_steps={train_steps})")
    policy = lambda o: model.predict(o, deterministic=True)[0]  # noqa: E731

    for lag in LAGS:
        ca_lag = load_corporate_actions(pay_lag_bdays=lag)
        runner_lag = WalkForwardRunner(
            adj=adj, opens=opens, closes=closes, slots=SLOTS,
            slot_to_instrument={s: SLOT_MAP[s]["instrument"] for s in SLOT_MAP},
            build_env=build_env_factory(ca_lag), corporate_actions=ca_lag,
        )
        m = runner_lag._rollout_segment(fold, "test", mean, std, policy)
        results["rl_representative"][str(lag)] = {
            "oos_cum": round(m["oos_cum_return"], 5),
            "sharpe": round(m["sharpe"], 4) if np.isfinite(m["sharpe"]) else None,
            "total_cost": round(m["total_cost"], 2),
            "negative_cash_count": m["negative_cash_count"],
            "nan": m["nan_obs_or_reward"],
        }
        print(f"  lag={lag}T  cum={m['oos_cum_return']:.4f}  sharpe={m['sharpe']:.3f}  "
              f"neg_cash={m['negative_cash_count']}")

    # --- immaterial 判定 + 理论说明 ---
    def max_gap(name):
        vals = {str(k): v[name]["stitched_cum"] for k, v in results["baselines"].items()}
        return max(vals.values()) - min(vals.values())

    gaps = {name: max_gap(name) for name in results["baselines"]["5"]}
    max_base_gap = max(gaps.values()) if gaps else 0.0
    rl_cums = [v["oos_cum"] for v in results["rl_representative"].values()]
    rl_gap = max(rl_cums) - min(rl_cums) if rl_cums else 0.0
    results["immaterial_assessment"] = {
        "baseline_max_stitched_cum_gap_across_lags": round(max_base_gap, 5),
        "rl_representative_cum_gap_across_lags": round(rl_gap, 5),
        "verdict": "IMMATERIAL" if max_base_gap < 0.005 and rl_gap < 0.005 else "CHECK",
        "rl_theory": (
            "decision obs 不含 cash；receivable 与 cash 均 1:1 计入 portfolio_value → "
            "settle 时点不影响 RL 权重路径与 equity，仅影响现金可用性；buy 有 1% buffer 覆盖。"
        ),
    }
    print(f"\nbaseline stitched_cum max gap across lags: {max_base_gap:.5f}")
    print(f"RL representative cum gap across lags: {rl_gap:.5f}")
    print(f"verdict: {results['immaterial_assessment']['verdict']}")

    out = ROOT / "runs" / "gate4_settlement_sensitivity.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
