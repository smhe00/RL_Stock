"""GATE 3 RL SANITY (Correction) — 单 fold / 单 seed：TD3 / SAC / PPO + Equal Weight。

修正项（Reviewer BLOCKER-1..5）：
- action_space = Box(-1,1)^11 + 显式 ActionTransform（算法中立）
- RiskOverlayV0 接入 transition（single_core≤25%、ChinaGrowth≤50%）
- observation 归一化：train-only fit，保存/加载随模型
- 时序切分：Train=早期，Eval=最后 200 交易日（held-out），no shuffle
- PPO device=cpu（MlpPolicy+GPU 官方 warning）
诊断按三层权重（raw_policy / post_risk / actual）分别报告。
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
EVAL_DAYS = 200
SLOTS = list(SLOT_MAP.keys())


def build_env(adj: pd.DataFrame, opens: dict, closes: dict) -> ChinaETFPortfolioEnv:
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


def fit_train_scaler(gym_env: ChinaETFGymEnv, n: int = 500) -> tuple[np.ndarray, np.ndarray]:
    """train-only 收集观测 → mean/std（仅训练期数据）。"""
    obs, _ = gym_env.reset()
    rows = [obs]
    for _ in range(n - 1):
        obs, _, truncated, terminated, _ = gym_env.step(np.zeros(len(SLOTS), dtype=np.float32))
        rows.append(obs)
        if truncated or terminated:
            obs, _ = gym_env.reset()
            rows.append(obs)
    arr = np.stack(rows)
    return arr.mean(axis=0), arr.std(axis=0)


def held_out_rollout(env: ChinaETFPortfolioEnv, policy, eval_start_date: pd.Timestamp) -> dict:
    """从 warmup 开始按 policy 前进；仅对决策日 ≥ eval_start_date 的步骤记录诊断。"""
    env.reset()
    levels = {"raw_policy": [], "post_risk": [], "actual": []}
    rewards = []
    nan_count = 0
    n_eval = 0
    while True:
        raw = policy(env._observe(env.calendar[env._i]))
        obs, reward, done, info = env.step(raw)
        st = info["step"]
        if st.t >= eval_start_date:
            for k in levels:
                levels[k].append(info["weights"][k].values)
            rewards.append(reward)
            n_eval += 1
            if not np.isfinite(obs).all() or not np.isfinite(reward):
                nan_count += 1
        if done:
            break
    out = {}
    for k, arr in levels.items():
        W = np.array(arr)
        out[f"{k}_max_mean"] = float(W.max(axis=1).mean())
        out[f"{k}_hhi"] = float((W ** 2).sum(axis=1).mean())
        out[f"{k}_gt25_fraction"] = float((W.max(axis=1) > 0.25).mean())
        if k == "actual":
            out["actual_china_growth_mean"] = float(
                (W[:, SLOTS.index("CHINEXT")] + W[:, SLOTS.index("STAR")]).mean()
            )
            out["actual_cash_residual_mean"] = float((1.0 - W.sum(axis=1)).mean())
    out["n_eval_steps"] = n_eval
    out["nan_obs_or_reward"] = nan_count
    out["reward_mean"] = float(np.mean(rewards))
    out["reward_std"] = float(np.std(rewards))
    return out


def main() -> None:
    adj = load_research_adj()
    opens, closes = load_execution_prices()
    eval_start_idx = len(adj) - EVAL_DAYS
    eval_start_date = adj.index[eval_start_idx]
    # Train 环境：数据止于 eval_start（最后 200 交易日保留为 held-out）
    adj_tr = adj.iloc[: eval_start_idx + 1]
    opens_tr = {k: v[v.index <= adj.index[eval_start_idx]] for k, v in opens.items()}
    closes_tr = {k: v[v.index <= adj.index[eval_start_idx]] for k, v in closes.items()}
    train_core = build_env(adj_tr, opens_tr, closes_tr)
    train_gym = ChinaETFGymEnv(train_core)
    mean, std = fit_train_scaler(train_gym, n=500)
    train_gym.set_observation_scaler(mean, std)
    print(f"train scaler: mean_abs={np.abs(mean).mean():.4f} std_mean={std.mean():.4f} (train-only)")

    results = {
        "seed": SEED, "timesteps": TIMESTEPS, "net": NET,
        "train_range": [str(adj_tr.index[0].date()), str(adj_tr.index[-1].date())],
        "eval_range": [str(adj.index[eval_start_idx].date()), str(adj.index[-1].date())],
        "action_space": "Box(-1,1)^11",
        "risk_overlay": "single_core<=0.25, china_growth<=0.50",
        "equal_weight_baseline": {},
        "algorithms": {},
    }

    # EW 基线（同一环境路径，held-out）
    eval_core = build_env(adj, opens, closes)
    ew = held_out_rollout(eval_core, lambda o: np.zeros(len(SLOTS)), eval_start_date)
    results["equal_weight_baseline"] = ew
    print("== Equal Weight (held-out) ==")
    print(json.dumps(ew, indent=2, default=str))

    for algo_cls, name, device in ((TD3, "TD3", "cuda"), (SAC, "SAC", "cuda"), (PPO, "PPO", "cpu")):
        print(f"\n===== {name} training (device={device}) =====")
        gym_env = ChinaETFGymEnv(build_env(adj_tr, opens_tr, closes_tr))
        gym_env.set_observation_scaler(mean, std)
        t0 = time.time()
        model = algo_cls(
            "MlpPolicy", gym_env, seed=SEED, policy_kwargs={"net_arch": NET},
            verbose=0, device=device,
        )
        model.learn(total_timesteps=TIMESTEPS)
        train_sec = time.time() - t0
        path = ROOT / "runs" / f"gate3_{name.lower()}_seed{SEED}"
        path.mkdir(parents=True, exist_ok=True)
        model_path = path / "model.zip"
        model.save(model_path)
        loaded = algo_cls.load(model_path, device=device)
        obs, _ = gym_env.reset()
        a1, _ = model.predict(obs, deterministic=True)
        a2, _ = loaded.predict(obs, deterministic=True)
        save_load_ok = bool(np.allclose(a1, a2))
        eval_core = build_env(adj, opens, closes)
        m = held_out_rollout(eval_core, lambda o, md=model: md.predict(o, deterministic=True)[0], eval_start_date)
        m["train_seconds"] = round(train_sec, 1)
        m["device"] = device
        m["save_load_deterministic_identical"] = save_load_ok
        results["algorithms"][name] = m
        print(json.dumps(m, indent=2, default=str))

    out = ROOT / "runs" / "gate3_sanity_results.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\nresults -> {out}")


if __name__ == "__main__":
    main()
