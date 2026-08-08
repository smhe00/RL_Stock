"""Out-of-sample rollout 诊断（GATE_4_PRECHECK，替代 gate3_rl_sanity.held_out_rollout）。

关键修正：policy 输入必须是**归一化** obs（与训练一致）。
Gate 3 sanity 的 held_out_rollout 直接喂 `env._observe()`（raw），对训练在
normalized obs 上的网络是分布偏移 —— runner 一律经 `gym._normalize` 后再交给 policy。
"""

from __future__ import annotations

import numpy as np


def roll_out(
    env,
    gym,
    policy,
    eval_start,
    slots: list[str],
) -> dict:
    """按 policy 推进整个测试 env；只记录决策日 ≥ eval_start 的步骤。

    env   : ChinaETFPortfolioEnv（含数据至测试区间末尾）
    gym   : ChinaETFGymEnv(env)，已 set_market_scaler(train-only)
    policy: callable(obs_normalized) -> action
    slots : 槽位顺序（用于 ChinaGrowth 诊断）
    """
    env.reset()
    levels = {"raw_policy": [], "post_risk": [], "actual": []}
    rewards: list[float] = []
    net_returns: list[float] = []
    nan_count = 0
    n_eval = 0
    raw_lt_1pct = 0
    raw_zero = 0
    overlay_l1_total = 0.0
    overlay_intervened = 0
    single_cap_hit = 0
    growth_cap_hit = 0
    total_weights_count = 0
    growth_idx = [
        i for i, s in enumerate(slots) if s in ("CHINEXT", "STAR")
    ]
    growth_names = [s for s in slots if s in ("CHINEXT", "STAR")]
    while True:
        raw_obs = env._observe(env.calendar[env._i])
        obs_n = gym._normalize(raw_obs).astype(np.float32)
        action = policy(obs_n)
        obs, reward, done, info = env.step(action)
        st = info["step"]
        if st.t >= eval_start:
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
            if growth_names:
                growth_cap_hit += int(float(pr[growth_names].sum()) >= 0.50 - 1e-6)
            rewards.append(float(reward))
            net_returns.append(float(st.net_return))
            n_eval += 1
            if not np.isfinite(obs).all() or not np.isfinite(reward):
                nan_count += 1
        if done:
            break
    out: dict = {}
    for k, arr in levels.items():
        W = np.array(arr)
        out[f"{k}_max_mean"] = float(W.max(axis=1).mean()) if len(W) else float("nan")
        out[f"{k}_hhi"] = float((W ** 2).sum(axis=1).mean()) if len(W) else float("nan")
        out[f"{k}_gt25_fraction"] = float((W.max(axis=1) > 0.25).mean()) if len(W) else float("nan")
        if k == "actual" and len(W):
            out["actual_china_growth_mean"] = float(W[:, growth_idx].sum(axis=1).mean())
            out["actual_min_mean"] = float(W.min(axis=1).mean())
            out["actual_cash_residual_mean"] = float((1.0 - W.sum(axis=1)).mean())
            out["actual_turnover"] = float(np.abs(np.diff(W, axis=0)).sum(axis=1).mean())
    if total_weights_count:
        out["raw_min_weight_mean"] = float(np.array(levels["raw_policy"]).min(axis=1).mean())
        out["raw_fraction_lt_1pct"] = raw_lt_1pct / total_weights_count
        out["raw_fraction_zero_or_eps"] = raw_zero / total_weights_count
    out["risk_overlay_intervention_rate"] = overlay_intervened / max(n_eval, 1)
    out["risk_overlay_mean_l1_raw_to_post"] = overlay_l1_total / max(n_eval, 1)
    out["single_core_cap_hit_rate"] = single_cap_hit / max(n_eval, 1)
    out["china_growth_cap_hit_rate"] = growth_cap_hit / max(n_eval, 1)
    out["n_eval_steps"] = n_eval
    out["nan_obs_or_reward"] = nan_count
    out["reward_mean"] = float(np.mean(rewards)) if rewards else float("nan")
    out["reward_std"] = float(np.std(rewards)) if rewards else float("nan")
    out["net_return_mean"] = float(np.mean(net_returns)) if net_returns else float("nan")
    out["net_return_std"] = float(np.std(net_returns)) if net_returns else float("nan")
    # OOS 累计净收益：prod(1+r) - 1（研究口径；不计复利年化，避免样本口径混淆）
    if net_returns:
        out["oos_cum_return"] = float(np.exp(np.log1p(np.asarray(net_returns)).sum()) - 1.0)
    else:
        out["oos_cum_return"] = float("nan")
    return out
