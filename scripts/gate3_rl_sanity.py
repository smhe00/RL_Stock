"""GATE 3 RL SANITY (Final Correction) — 单 fold / 单 seed：TD3 / SAC / PPO + EW。

修正项（Reviewer 2026-08-08）：
- ActionTransform V2：score=(a+1)/2 归一化（可表达 0 权重；无 softmax 隐含下限）
- RiskOverlayV0 强制接入 transition（single_core≤25%、ChinaGrowth≤50%）
- Observation 归一化 V2：仅 93 维外生特征 train-only fit（policy-independent）；
  11 维 actual weights 不归一化
- 时序：Train=[start, eval_start) / Eval=[eval_start, end]，严格无重叠
- PPO device=cpu
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


def fit_market_scaler(train_core: ChinaETFPortfolioEnv) -> tuple[np.ndarray, np.ndarray]:
    """policy-independent：直接从 train 有效外生特征矩阵 fit（非 EW trajectory）。"""
    market = train_core.market_feature_frame()
    warm = train_core._warmup_index
    valid = market.iloc[warm:]
    assert valid.notna().all().all(), "train 外生特征必须全 finite"
    return valid.mean().to_numpy(), valid.std().to_numpy().clip(min=1e-8)


def held_out_rollout(env: ChinaETFPortfolioEnv, policy, eval_start_date: pd.Timestamp) -> dict:
    """从 warmup 开始按 policy 前进；仅对决策日 ≥ eval_start_date 的步骤记录诊断。"""
    env.reset()
    levels = {"raw_policy": [], "post_risk": [], "actual": []}
    rewards = []
    nan_count = 0
    n_eval = 0
    raw_lt_1pct = 0
    raw_zero = 0
    overlay_l1_total = 0.0
    overlay_intervened = 0
    single_cap_hit = 0
    growth_cap_hit = 0
    total_weights_count = 0
    while True:
        raw = policy(env._observe(env.calendar[env._i]))
        obs, reward, done, info = env.step(raw)
        st = info["step"]
        if st.t >= eval_start_date:
            for k in levels:
                levels[k].append(info["weights"][k].values)
            rw = info["weights"]["raw_policy"]
            pr = info["weights"]["post_risk"]
            raw_lt_1pct += int((rw < 0.01).sum())
            raw_zero += int((rw <= 1e-9).sum())
            total_weights_count += len(rw)
            l1 = float((rw - pr).abs().sum())
            overlay_l1_total += l1
            overlay_intervened += int(l1 > 1e-6)
            single_cap_hit += int(pr.max() >= 0.25 - 1e-6)
            growth_cap_hit += int(pr["CHINEXT"] + pr["STAR"] >= 0.50 - 1e-6)
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
            out["actual_min_mean"] = float(W.min(axis=1).mean())
            out["actual_cash_residual_mean"] = float((1.0 - W.sum(axis=1)).mean())
            out["actual_turnover"] = float(np.abs(np.diff(W, axis=0)).sum(axis=1).mean())
    out["raw_min_weight_mean"] = float(np.array(levels["raw_policy"]).min(axis=1).mean())
    out["raw_fraction_lt_1pct"] = raw_lt_1pct / max(total_weights_count, 1)
    out["raw_fraction_zero_or_eps"] = raw_zero / max(total_weights_count, 1)
    out["risk_overlay_intervention_rate"] = overlay_intervened / max(n_eval, 1)
    out["risk_overlay_mean_l1_raw_to_post"] = overlay_l1_total / max(n_eval, 1)
    out["single_core_cap_hit_rate"] = single_cap_hit / max(n_eval, 1)
    out["china_growth_cap_hit_rate"] = growth_cap_hit / max(n_eval, 1)
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
    # Train 环境：数据止于 eval_start-1（[start, eval_start) 半开区间，严格无重叠）
    train_last = adj.index[eval_start_idx - 1]
    adj_tr = adj.iloc[:eval_start_idx]
    opens_tr = {k: v[v.index <= train_last] for k, v in opens.items()}
    closes_tr = {k: v[v.index <= train_last] for k, v in closes.items()}
    train_core = build_env(adj_tr, opens_tr, closes_tr)
    train_gym = ChinaETFGymEnv(train_core)
    mean, std = fit_market_scaler(train_core)
    train_gym.set_market_scaler(mean, std)
    print(f"train scaler: mean_abs={np.abs(mean).mean():.4f} std_mean={std.mean():.4f} (train-only)")

    results = {
        "seed": SEED, "timesteps": TIMESTEPS, "net": NET,
        "raw_data_start": str(adj.index[0].date()),
        "effective_obs_start": str(adj.index[train_core._warmup_index].date()),
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
        gym_env.set_market_scaler(mean, std)
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
