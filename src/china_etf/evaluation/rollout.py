"""Out-of-sample rollout 诊断（GATE_4_PRECHECK / GATE_4_3_SEED_PILOT）。

关键修正：policy 输入必须是**归一化** obs（与训练一致）。
Gate 3 sanity 的 held_out_rollout 直接喂 `env._observe()`（raw），对训练在
normalized obs 上的网络是分布偏移 —— runner 一律经 `gym._normalize` 后再交给 policy。

GATE_4_3_SEED_PILOT（评审 §20）：除聚合诊断外，返回逐 step 序列（series）与段级绩效指标
（CAGR / ann vol / Sharpe / Sortino / MaxDD / Calmar / turnover / cost / cash 等），
供 stitched OOS 聚合与 seed dispersion 分析。
"""

from __future__ import annotations

import numpy as np


def _cagr(net_returns: np.ndarray) -> float:
    if len(net_returns) < 2:
        return float("nan")
    cum = float(np.exp(np.log1p(net_returns).sum()) - 1.0)
    return float((1.0 + cum) ** (252.0 / len(net_returns)) - 1.0)


def _max_drawdown(net_returns: np.ndarray) -> float:
    if len(net_returns) == 0:
        return float("nan")
    cum = np.exp(np.log1p(net_returns).cumsum())
    return float((cum / np.maximum.accumulate(cum) - 1.0).min())


def _sharpe(net_returns: np.ndarray) -> float:
    if len(net_returns) < 2:
        return float("nan")
    std = float(np.std(net_returns))
    if std <= 0:
        return float("nan")
    return float(np.mean(net_returns) / std * np.sqrt(252))


def _sortino(net_returns: np.ndarray) -> float:
    if len(net_returns) < 2:
        return float("nan")
    downside = net_returns[net_returns < 0]
    dstd = float(np.std(downside)) if len(downside) > 1 else 0.0
    if dstd <= 0:
        return float("nan")
    return float(np.mean(net_returns) / dstd * np.sqrt(252))


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
    costs: list[float] = []
    cash_after: list[float] = []
    active_assets: list[int] = []
    turnovers: list[float] = []
    prev_fees = 0.0
    prev_actual: np.ndarray | None = None
    initial_value = float("nan")
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
            actual = info["weights"]["actual"].values
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
            step_cost = float(st.fees_paid - prev_fees)
            costs.append(step_cost)
            prev_fees = float(st.fees_paid)
            cash_after.append(float(env.accounting.cash))
            active_assets.append(int((actual > 1e-6).sum()))
            if prev_actual is not None:
                turnovers.append(float(np.abs(actual - prev_actual).sum()))
            prev_actual = actual
            if np.isnan(initial_value):
                initial_value = float(st.value_before)
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
    if net_returns:
        out["oos_cum_return"] = float(np.exp(np.log1p(np.asarray(net_returns)).sum()) - 1.0)
    else:
        out["oos_cum_return"] = float("nan")

    # GATE_4_3_SEED_PILOT（评审 §20）：段级绩效 + 逐 step 序列
    nr = np.asarray(net_returns, dtype=float) if net_returns else np.zeros(0)
    W_actual = np.asarray(levels["actual"]) if len(levels["actual"]) else np.zeros((0, len(slots)))
    if len(nr):
        out["cagr"] = _cagr(nr)
        out["annualized_vol"] = float(np.std(nr) * np.sqrt(252))
        out["sharpe"] = _sharpe(nr)
        out["sortino"] = _sortino(nr)
        out["max_drawdown"] = _max_drawdown(nr)
        mdd = out["max_drawdown"]
        cagr = out["cagr"]
        out["calmar"] = float(cagr / abs(mdd)) if np.isfinite(cagr) and np.isfinite(mdd) and abs(mdd) > 1e-12 else float("nan")
    else:
        for k in ("cagr", "annualized_vol", "sharpe", "sortino", "max_drawdown", "calmar"):
            out[k] = float("nan")
    out["mean_turnover"] = float(np.mean(turnovers)) if turnovers else float("nan")
    out["total_turnover"] = float(sum(turnovers))
    out["mean_active_assets"] = float(np.mean(active_assets)) if active_assets else float("nan")
    out["max_single_asset_weight"] = float(W_actual.max()) if len(W_actual) else float("nan")
    out["mean_hhi"] = float((W_actual ** 2).sum(axis=1).mean()) if len(W_actual) else float("nan")
    out["total_cost"] = float(sum(costs))
    out["cost_over_initial_value"] = float(sum(costs) / initial_value) if np.isfinite(initial_value) and initial_value > 0 else float("nan")
    out["min_broker_cash"] = float(min(cash_after)) if cash_after else float("nan")
    out["negative_cash_count"] = int(sum(c < -1e-6 for c in cash_after))
    out["series"] = {
        "net_returns": [float(x) for x in net_returns],
        "rewards": [float(x) for x in rewards],
        "costs": [float(x) for x in costs],
        "cash": [float(x) for x in cash_after],
        "active_assets": list(active_assets),
        "turnovers": [float(x) for x in turnovers],
        "actual_weights": W_actual.tolist(),
        "raw_weights": np.asarray(levels["raw_policy"]).tolist() if len(levels["raw_policy"]) else [],
        "post_risk_weights": np.asarray(levels["post_risk"]).tolist() if len(levels["post_risk"]) else [],
    }
    return out
