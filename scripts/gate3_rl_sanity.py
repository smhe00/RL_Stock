"""GATE 3 RL SANITY — 单 fold / 单 seed：TD3 / SAC / PPO + Equal Weight 基线。

目标仅验证 RL pipeline 正确性与 policy 行为 sanity（不做性能结论）。
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stable_baselines3 import PPO, SAC, TD3  # noqa: E402

from china_etf.contracts import EnvironmentMode  # noqa: E402
from china_etf.cost.mainland import MainlandETFCostModel  # noqa: E402
from china_etf.data.loader import SLOT_MAP, load_execution_prices, load_research_adj  # noqa: E402
from china_etf.environment.gym_wrapper import ChinaETFGymEnv  # noqa: E402
from china_etf.environment.portfolio_env import ChinaETFPortfolioEnv  # noqa: E402
from china_etf.execution.broker.mock import MockBroker  # noqa: E402
from china_etf.execution.order_generator import OrderGenerator  # noqa: E402
from china_etf.execution.premium import PremiumGuard  # noqa: E402
from china_etf.execution.tradability import TradabilityMask  # noqa: E402

SEED = 42
TIMESTEPS = 12_000
NET = [256, 256]
SLOTS = list(SLOT_MAP.keys())


def build_env() -> ChinaETFPortfolioEnv:
    adj = load_research_adj()
    opens, closes = load_execution_prices()
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


def rollout_metrics(env: ChinaETFPortfolioEnv, policy, n_steps: int = 200) -> dict:
    """按给定 policy（action → weights）rollout，收集 sanity 指标。"""
    obs = env.reset()
    weights = []
    rewards = []
    actions = []
    nan_count = 0
    for _ in range(n_steps):
        raw = policy(obs)
        actions.append(raw)
        obs, reward, done, info = env.step(raw)
        if not np.isfinite(obs).all() or not np.isfinite(reward):
            nan_count += 1
        rewards.append(reward)
        st = info["step"]
        marks = env._close_marks(st.t_next)
        snap = env.accounting.snapshot(st.t_next, marks, env._fx())
        w = np.zeros(len(SLOTS))
        for i, slot in enumerate(SLOTS):
            inst = env.slot_to_instrument[slot]
            if inst in snap.positions:
                w[i] = snap.positions[inst] * marks.get(inst, 0.0) / snap.portfolio_value
        weights.append(w)
        if done:
            env.reset()
    W = np.array(weights)
    A = np.array(actions)
    hhi = (W ** 2).sum(axis=1).mean()
    turnover = np.abs(np.diff(W, axis=0)).sum(axis=1).mean()
    single_gt_50 = (W.max(axis=1) > 0.5).mean()
    cash_residual = (1.0 - W.sum(axis=1)).mean()
    return {
        "n_steps": n_steps,
        "nan_obs_or_reward": nan_count,
        "action_mean": float(A.mean()),
        "action_std": float(A.std()),
        "weight_mean": float(W.mean()),
        "weight_max_mean": float(W.max(axis=1).mean()),
        "weight_concentration_hhi": float(hhi),
        "daily_turnover": float(turnover),
        "fraction_steps_single_asset_gt_50pct": float(single_gt_50),
        "cash_residual_mean": float(cash_residual),
        "reward_mean": float(np.mean(rewards)),
        "reward_std": float(np.std(rewards)),
    }


def main() -> None:
    results = {"seed": SEED, "timesteps": TIMESTEPS, "net": NET, "algorithms": {}}
    env_core = build_env()

    # Equal Weight 基线（同一环境路径）
    ew = rollout_metrics(env_core, lambda obs: np.zeros(len(SLOTS)), n_steps=200)
    results["equal_weight_baseline"] = ew
    print("== Equal Weight ==")
    print(json.dumps(ew, indent=2, default=str))

    for algo_cls, name in ((TD3, "TD3"), (SAC, "SAC"), (PPO, "PPO")):
        print(f"\n===== {name} training =====")
        gym_env = ChinaETFGymEnv(build_env())
        t0 = time.time()
        model = algo_cls(
            "MlpPolicy", gym_env, seed=SEED, policy_kwargs={"net_arch": NET},
            verbose=0, device="cuda",
        )
        model.learn(total_timesteps=TIMESTEPS)
        train_sec = time.time() - t0
        # save/load
        path = ROOT / "runs" / f"gate3_{name.lower()}_seed{SEED}"
        path.mkdir(parents=True, exist_ok=True)
        model_path = path / "model.zip"
        model.save(model_path)
        loaded = algo_cls.load(model_path, device="cuda")
        obs, _ = gym_env.reset()
        a1, _ = model.predict(obs, deterministic=True)
        a2, _ = loaded.predict(obs, deterministic=True)
        save_load_ok = bool(np.allclose(a1, a2))
        # rollout
        core = build_env()
        m = rollout_metrics(core, lambda o: model.predict(o, deterministic=True)[0], n_steps=200)
        m["train_seconds"] = round(train_sec, 1)
        m["save_load_deterministic_identical"] = save_load_ok
        results["algorithms"][name] = m
        print(json.dumps(m, indent=2, default=str))

    out = ROOT / "runs" / "gate3_sanity_results.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\nresults -> {out}")


if __name__ == "__main__":
    main()
