"""CORRECTED_F0_RL_EXECUTION_PREP — execution harness 绑定（E1/E2/E4）。

- load_protocol_config: 读 configs/rl_formal_protocol.yaml（canonical）+ 返回 config_sha256。
- run_fold_rl_config: config-driven RL fold（显式传冻结超参，fail-closed on env override，E1）。
- validate_runtime_invariants: 5 项 hard-stop invariants（E2，publication 前 fail-closed）。
- evaluate_go_nogo: 确定性 per-algorithm/project-level GO/NO-GO + Pareto vs MaxDiv（E4，无 Test ranking）。

本模块不训练 RL（执行在 CORRECTED_F0_RL_3SEED 门）；构造 spy 验证超参绑定。
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]  # src/china_etf/evaluation/ -> repo root

_CONFIG_PATH = ROOT / "configs" / "rl_formal_protocol.yaml"

# 禁止的 formal-run env overrides（E1 fail-closed）：pilot 遗留
FORBIDDEN_OVERRIDES = ("GATE4_PILOT_SEEDS", "GATE4_PILOT_PASSES", "GATE4_PILOT_ALGOS")


class FormalConfigError(RuntimeError):
    """config 校验/绑定失败（fail-closed）。"""


class InvariantViolation(RuntimeError):
    """hard-stop invariant 失败（publication 前 fail-closed）。"""


def load_protocol_config() -> dict:
    """读 canonical config + 计算 config_sha256。返回 {config, config_sha256}。"""
    import yaml
    raw = _CONFIG_PATH.read_bytes()
    cfg = yaml.safe_load(raw.decode("utf-8"))
    cfg["_config_path"] = str(_CONFIG_PATH)
    digest = hashlib.sha256(raw).hexdigest()
    return {"config": cfg, "config_sha256": digest}


def check_no_forbidden_overrides() -> None:
    """E1：formal run 禁止 pilot env overrides——存在则 fail-closed raise。"""
    active = [k for k in FORBIDDEN_OVERRIDES if k in os.environ]
    if active:
        raise FormalConfigError(f"formal run forbids env overrides: {active}")


def _algorithm_kwargs(algo_name: str, cfg: dict) -> dict:
    """E1：从 config 提取 algo 的显式构造 kwargs（不依赖 SB3 默认）。"""
    algo = cfg["algorithms"].get(algo_name)
    if algo is None:
        raise FormalConfigError(f"algo {algo_name} not in config")
    return dict(algo)


def run_fold_rl_config(runner, fold, algo_cls, algo_name: str, seed: int, cfg: dict) -> dict:
    """config-driven RL fold：显式传冻结超参（E1），fail-closed on override。

    runner: WalkForwardRunner 实例（复用其 _train_env_for / fit_scaler / _rollout_segment）。
    algo_cls: PPO/SAC/TD3 类。cfg: load_protocol_config()["config"]。
    """
    check_no_forbidden_overrides()
    kwargs = _algorithm_kwargs(algo_name, cfg)
    net = list(cfg["net_arch"])
    device = cfg["device"][algo_name]
    train_passes = int(cfg["train_passes"])

    train_env = runner._train_env_for(fold)
    mean, std = runner.fit_scaler(train_env, fold)
    from ..environment.gym_wrapper import ChinaETFGymEnv
    gym_tr = ChinaETFGymEnv(train_env)
    gym_tr.set_market_scaler(np.asarray(mean, dtype=np.float32), np.asarray(std, dtype=np.float32))
    train_steps = runner._train_decision_steps(train_env)
    total_timesteps = int(train_steps) * train_passes

    model = algo_cls(
        "MlpPolicy",
        gym_tr,
        seed=seed,
        policy_kwargs={"net_arch": net},
        verbose=0,
        device=device,
        **kwargs,  # 显式冻结超参（覆盖默认）
    )
    model.learn(total_timesteps=total_timesteps)
    save_load_ok = runner._save_load_identical(algo_cls, model, gym_tr, device)
    policy = lambda o: model.predict(o, deterministic=True)[0]  # noqa: E731
    val_m = runner._rollout_segment(fold, "validation", mean, std, policy)
    test_m = runner._rollout_segment(fold, "test", mean, std, policy)
    return {
        "fold": fold.name,
        "kind": "rl",
        "algo": algo_name,
        "seed": seed,
        "train_decision_steps": train_steps,
        "train_passes": train_passes,
        "total_timesteps": int(total_timesteps),
        "device": str(device),
        "config_sha256": cfg["_config_path"],
        "save_load_deterministic_identical": save_load_ok,
        "validation": val_m,
        "test": test_m,
    }


def validate_runtime_invariants(results: dict, mask_dates) -> None:
    """E2：publication 前 fail-closed 校验 5 项 invariants。失败 raise InvariantViolation。

    results: 聚合结果（含 per_algo 的 per_fold test series）；mask_dates: 475 执行日集合。
    """
    mask = set(pd_timestamp(d) for d in mask_dates)

    problems: list[str] = []
    per_algo = results.get("per_algorithm", {})
    if not per_algo:
        problems.append("no per_algorithm results")
    n_total = 0
    for algo, ag in per_algo.items():
        for seed_key, seed_res in ag.items():
            # 同一 (algo, seed) 内 fold 必须互异且覆盖 F1-F4（跨 algo/seed 重复是合法的）
            folds_in_seed = set(seed_res.keys())
            if len(folds_in_seed) != len(seed_res):
                problems.append(f"{algo}|{seed_key}: duplicate fold")
            if not {"F1", "F2", "F3", "F4"} <= folds_in_seed:
                problems.append(f"{algo}|{seed_key}: missing folds {sorted({'F1','F2','F3','F4'} - folds_in_seed)}")
            for fold_name, fm in seed_res.items():
                series = fm.get("test", {}).get("series", {})
                exec_dates = series.get("execution_dates", [])
                n_eval = fm.get("test", {}).get("n_eval_steps")
                if set(pd_timestamp(d) for d in exec_dates) != mask:
                    problems.append(f"{algo}|{seed_key}|{fold_name}: execution_dates != 475 mask")
                if n_eval != len(mask):
                    problems.append(f"{algo}|{seed_key}|{fold_name}: n_eval_steps {n_eval} != 475")
                if "costs" in series and "fees" in series:
                    if abs(sum(series["costs"]) - sum(series["fees"])) > 1e-6:
                        problems.append(f"{algo}|{seed_key}|{fold_name}: cost reconciliation fail")
                n_total += 1
    if n_total != 36:
        problems.append(f"expected 36 runs, got {n_total}")
    if problems:
        raise InvariantViolation("; ".join(problems[:20]))


def pd_timestamp(d):
    import pandas as pd
    return pd.Timestamp(d)


def _median(values: list[float]) -> float:
    vals = [v for v in values if np.isfinite(v)]
    return float(np.median(vals)) if vals else float("nan")


def evaluate_go_nogo(per_algo_stitched: dict, cfg: dict) -> dict:
    """E4：确定性 config-driven GO/NO-GO evaluator。

    per_algo_stitched: {algo: {"active_day_annualized_return": {seed: float}, "sharpe": {...},
                               "max_drawdown": {...}, "n_seeds": int, "stop_violations": int}}.
    返回 per_algorithm GO/NO_GO + reasons、project_level、pareto_vs_maxdiv。无 Test-based ranking。
    """
    hurdle = cfg["benchmark"]["primary_return_hurdle"]
    frontier = cfg["benchmark"]["risk_adjusted_frontier"]
    h_ret = hurdle["active_day_annualized_return"]
    h_sharpe = hurdle["sharpe"]
    h_mdd = hurdle["max_drawdown"]

    per_algorithm: dict[str, dict] = {}
    for algo, st in per_algo_stitched.items():
        rets = list(st.get("active_day_annualized_return", {}).values())
        sharpes = list(st.get("sharpe", {}).values())
        mdds = list(st.get("max_drawdown", {}).values())
        med_ret = _median(rets)
        med_sharpe = _median(sharpes)
        med_mdd = _median(mdds)
        n_seeds = st.get("n_seeds", 0)
        stop_violations = st.get("stop_violations", 0)
        n_pass_sharpe = sum(1 for s in sharpes if s >= h_sharpe)
        reasons: list[str] = []
        if stop_violations > 0:
            reasons.append(f"stop_violations={stop_violations}")
        if not (med_ret >= h_ret):
            reasons.append(f"median active_day_annualized_return {med_ret:.4f} < {h_ret:.4f}")
        if not (med_sharpe >= h_sharpe):
            reasons.append(f"median sharpe {med_sharpe:.3f} < {h_sharpe:.2f}")
        if not (med_mdd >= h_mdd):
            reasons.append(f"median max_drawdown {med_mdd:.4f} < {h_mdd:.4f}")
        if n_pass_sharpe < 2:
            reasons.append(f"only {n_pass_sharpe}/{n_seeds} seeds sharpe >= hurdle")
        go = not reasons
        per_algorithm[algo] = {
            "decision": "GO" if go else "NO_GO",
            "reasons": reasons,
            "median_active_day_annualized_return": med_ret,
            "median_sharpe": med_sharpe,
            "median_max_drawdown": med_mdd,
            "seeds_passing_sharpe": n_pass_sharpe,
            "n_seeds": n_seeds,
        }

    n_go = sum(1 for v in per_algorithm.values() if v["decision"] == "GO")
    project_level = "PROMISING" if n_go >= 1 else "NO_GO"

    # Pareto vs MaxDiv frontier（Sharpe / MaxDD / Calmar；非 Test ranking，仅报告）
    f_sharpe, f_mdd, f_calmar = frontier["sharpe"], frontier["max_drawdown"], frontier["calmar"]
    pareto: dict[str, dict] = {}
    for algo, v in per_algorithm.items():
        med_sharpe = v["median_sharpe"]
        med_mdd = v["median_max_drawdown"]
        med_calmar = per_algo_stitched[algo].get("calmar_median", float("nan"))
        dominated_dims = []
        if med_sharpe < f_sharpe:
            dominated_dims.append("sharpe")
        if med_mdd < f_mdd:
            dominated_dims.append("max_drawdown")
        if np.isfinite(med_calmar) and med_calmar < f_calmar:
            dominated_dims.append("calmar")
        pareto[algo] = {
            "vs_max_div": "dominated" if dominated_dims else "not_dominated",
            "dominated_dims": dominated_dims,
            "max_div": {"sharpe": f_sharpe, "max_drawdown": f_mdd, "calmar": f_calmar},
            "rl_median": {"sharpe": med_sharpe, "max_drawdown": med_mdd, "calmar": med_calmar},
        }

    return {
        "per_algorithm": per_algorithm,
        "project_level": project_level,
        "pareto_vs_maxdiv": pareto,
        "hurdle": hurdle,
        "note": "deterministic config-driven evaluation; no Test-based algorithm ranking",
    }
