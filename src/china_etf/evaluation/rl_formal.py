"""CORRECTED_F0_RL_EXECUTION_PREP_CORRECTIONS — execution harness 绑定修正（H1-H7）。

- load_protocol_config: 读 configs/rl_formal_protocol.yaml（canonical）+ config_sha256（真 digest，H2）。
- _construct_model: 单一共享构造路径（H1），run_fold_rl_config 与 dry-run spy 都用。
- run_fold_rl_config: config-driven RL fold（显式冻结超参，fail-closed on override）。
- validate_runtime_invariants: fold-segment + stitched 475 mask、cost reconciliation evidence、raw 完整性、
  精确 config 派生身份（H3/H4/H5）。
- evaluate_go_nogo: 精确 seed 集 + finite + 2/3 阈值（H6）；真 Pareto dominance（H7）。

本模块不训练 RL（执行在 CORRECTED_F0_RL_3SEED 门）。
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]  # repo root

_CONFIG_PATH = ROOT / "configs" / "rl_formal_protocol.yaml"

# 禁止的 formal-run env overrides（E1/H1 fail-closed）
FORBIDDEN_OVERRIDES = ("GATE4_PILOT_SEEDS", "GATE4_PILOT_PASSES", "GATE4_PILOT_ALGOS")

# 真实 fold test 长度（H3）
FOLD_TEST_LENS = {"F1": 118, "F2": 118, "F3": 118, "F4": 121}
STITCHED_N = 475


class FormalConfigError(RuntimeError):
    """config 校验/绑定失败（fail-closed）。"""


class InvariantViolation(RuntimeError):
    """hard-stop invariant 失败（publication 前 fail-closed）。"""


def load_protocol_config() -> dict:
    """读 canonical config + 计算真 SHA-256（H2）。返回 {config, config_sha256}。"""
    import yaml
    raw = _CONFIG_PATH.read_bytes()
    cfg = yaml.safe_load(raw.decode("utf-8"))
    digest = hashlib.sha256(raw).hexdigest()
    return {"config": cfg, "config_sha256": digest}


def check_no_forbidden_overrides() -> None:
    """E1/H1：formal run 禁止 pilot env overrides——存在则 fail-closed raise。"""
    active = [k for k in FORBIDDEN_OVERRIDES if k in os.environ]
    if active:
        raise FormalConfigError(f"formal run forbids env overrides: {active}")


def _algorithm_kwargs(algo_name: str, cfg: dict) -> dict:
    algo = cfg["algorithms"].get(algo_name)
    if algo is None:
        raise FormalConfigError(f"algo {algo_name} not in config")
    return dict(algo)


def _construct_model(algo_cls, algo_name: str, seed: int, cfg: dict, gym_tr) -> object:
    """H1/F1：单一共享构造路径——显式传 config 冻结超参 + net + device + seed（非 SB3 默认）。

    F1：校验 algo_cls 身份与 canonical algo_name 匹配，不匹配 → FormalConfigError（构造前）。
    """
    if algo_cls.__name__.upper() != algo_name.upper():
        raise FormalConfigError(f"algo_name '{algo_name}' != algo_cls '{algo_cls.__name__}'")
    kwargs = _algorithm_kwargs(algo_name, cfg)
    net = list(cfg["net_arch"])
    device = cfg["device"][algo_name]
    return algo_cls(
        "MlpPolicy",
        gym_tr,
        seed=seed,
        policy_kwargs={"net_arch": net},
        verbose=0,
        device=device,
        **kwargs,
    )


def run_fold_rl_config(runner, fold, algo_cls, algo_name: str, seed: int, config_envelope: dict) -> dict:
    """config-driven RL fold（H1/H2）。config_envelope = load_protocol_config()。"""
    check_no_forbidden_overrides()
    cfg = config_envelope["config"]
    sha = config_envelope["config_sha256"]
    if seed not in cfg["seeds"]:
        raise FormalConfigError(f"seed {seed} not in config seeds {cfg['seeds']}")
    train_passes = int(cfg["train_passes"])

    train_env = runner._train_env_for(fold)
    mean, std = runner.fit_scaler(train_env, fold)
    from ..environment.gym_wrapper import ChinaETFGymEnv
    gym_tr = ChinaETFGymEnv(train_env)
    gym_tr.set_market_scaler(np.asarray(mean, dtype=np.float32), np.asarray(std, dtype=np.float32))
    train_steps = runner._train_decision_steps(train_env)
    total_timesteps = int(train_steps) * train_passes

    model = _construct_model(algo_cls, algo_name, seed, cfg, gym_tr)
    model.learn(total_timesteps=total_timesteps)
    device = cfg["device"][algo_name]
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
        "config_sha256": sha,  # H2：真 64-hex digest
        "save_load_deterministic_identical": save_load_ok,
        "validation": val_m,
        "test": test_m,
    }


def validate_runtime_invariants(results: dict, mask_dates, cfg: dict = None) -> None:
    """E2/H3/H4/H5：publication 前 fail-closed 校验。失败 raise InvariantViolation。

    results: 含 per_algorithm {algo: {seed: {fold: {"test": {series, total_cost, n_eval_steps, ...}}}}}.
    mask_dates: 有序 475 执行日列表（canonical RESEARCH_BENCHMARK_TEST）。
    cfg: config（需含 algorithms/seeds；缺省则从 results 推断计数）。
    """
    expected_algos = list(cfg["algorithms"].keys()) if cfg else sorted(set(
        a for a in results.get("per_algorithm", {})))
    expected_seeds = list(cfg["seeds"]) if cfg else sorted(set(
        int(s) for ag in results.get("per_algorithm", {}).values() for s in ag))
    ordered_mask = [str(d.date()) if hasattr(d, "date") else str(d) for d in mask_dates]

    problems: list[str] = []
    per_algo = results.get("per_algorithm", {})
    if not per_algo:
        problems.append("no per_algorithm results")

    # H5：精确身份——expected = algorithms × seeds × F1-F4，无缺无多
    expected_identities = {(a, s) for a in expected_algos for s in expected_seeds}
    actual_identities = {(a, int(s)) for a, ag in per_algo.items() for s in ag}
    if actual_identities != expected_identities:
        missing = expected_identities - actual_identities
        extra = actual_identities - expected_identities
        problems.append(f"identity mismatch: missing={sorted(missing)} extra={sorted(extra)}")

    n_total = 0
    for algo, ag in per_algo.items():
        for seed_key, seed_res in ag.items():
            folds_in_seed = set(seed_res.keys())
            if folds_in_seed != set(FOLD_TEST_LENS):
                problems.append(f"{algo}|{seed_key}: folds {sorted(folds_in_seed)} != {sorted(FOLD_TEST_LENS)}")
            stitched_dates: list[str] = []
            for fold_name in ("F1", "F2", "F3", "F4"):
                fm = seed_res.get(fold_name)
                if fm is None:
                    problems.append(f"{algo}|{seed_key}|{fold_name}: missing")
                    continue
                test = fm.get("test", {})
                series = test.get("series", {})
                exec_dates = [str(d) for d in series.get("execution_dates", [])]
                n_eval = test.get("n_eval_steps")
                # H3 fold 级：execution_dates == 该 fold 自己的段（有序）
                fold_len = FOLD_TEST_LENS[fold_name]
                if len(exec_dates) != fold_len:
                    problems.append(f"{algo}|{seed_key}|{fold_name}: len(execution_dates) {len(exec_dates)} != {fold_len}")
                # F2：缺失 n_eval_steps 即 fail-closed
                if n_eval is None:
                    problems.append(f"{algo}|{seed_key}|{fold_name}: n_eval_steps missing")
                elif n_eval != fold_len:
                    problems.append(f"{algo}|{seed_key}|{fold_name}: n_eval_steps {n_eval} != {fold_len}")
                stitched_dates.extend(exec_dates)
                # H4 cost reconciliation：sum(series.costs) == test.total_cost（证据缺失 fail-closed）
                costs = series.get("costs")
                total_cost = test.get("total_cost")
                if costs is None or total_cost is None:
                    problems.append(f"{algo}|{seed_key}|{fold_name}: cost reconciliation evidence missing")
                elif abs(sum(float(c) for c in costs) - float(total_cost)) > 1e-6 * max(1.0, abs(float(total_cost))):
                    problems.append(f"{algo}|{seed_key}|{fold_name}: sum(costs) != total_cost")
                # F3：raw 完整性——7 数组长度兼容 + weight row shape == action_dim
                for key in ("execution_dates", "net_returns", "costs", "cash"):
                    val = series.get(key)
                    if val is None:
                        problems.append(f"{algo}|{seed_key}|{fold_name}: raw {key} missing")
                    elif len(val) != fold_len:
                        problems.append(f"{algo}|{seed_key}|{fold_name}: raw {key} len {len(val)} != {fold_len}")
                for key in ("actual_weights", "raw_weights", "post_risk_weights"):
                    val = series.get(key)
                    if val is None:
                        problems.append(f"{algo}|{seed_key}|{fold_name}: raw {key} missing")
                    elif len(val) != fold_len:
                        problems.append(f"{algo}|{seed_key}|{fold_name}: raw {key} len {len(val)} != {fold_len}")
                    elif val and any(len(row) != 11 for row in val):
                        problems.append(f"{algo}|{seed_key}|{fold_name}: raw {key} row width != 11")
                n_total += 1
            # H3 stitched 级：F1→F4 有序拼接 == 475 ordered mask
            if stitched_dates != ordered_mask:
                problems.append(f"{algo}|{seed_key}: stitched execution_dates != 475 ordered mask")
    if n_total != 36:
        problems.append(f"expected 36 runs, got {n_total}")
    if problems:
        raise InvariantViolation("; ".join(problems[:25]))


def _median(values: list[float]) -> float:
    vals = [v for v in values if np.isfinite(v)]
    return float(np.median(vals)) if vals else float("nan")


def evaluate_go_nogo(per_algo_stitched: dict, cfg: dict) -> dict:
    """E4/H6/H7：确定性 config-driven GO/NO-GO。

    H6：要求精确 seed 集 + 全部决策指标 finite；2/3 阈值从 config seeds 派生；不完整 → NO_GO/INCOMPLETE。
    H7：真 Pareto dominance（comparator 全目标 ≥ 且至少一严格 >；Sharpe/Calmar 高好，MaxDD 高好[更浅]）。
    """
    hurdle = cfg["benchmark"]["primary_return_hurdle"]
    frontier = cfg["benchmark"]["risk_adjusted_frontier"]
    h_ret = hurdle["active_day_annualized_return"]
    h_sharpe = hurdle["sharpe"]
    h_mdd = hurdle["max_drawdown"]
    expected_seeds = list(cfg["seeds"])
    req_pass = max(2, int(np.ceil(2 / 3 * len(expected_seeds))))  # H6：从 config 派生 ≥2/3

    per_algorithm: dict[str, dict] = {}
    expected_seeds_set = set(expected_seeds)
    for algo, st in per_algo_stitched.items():
        seed_keys = set(st.get("seed_keys", st.get("active_day_annualized_return", {}).keys()))
        reasons: list[str] = []
        # H6/F4：精确 seed 集 + 每 metric map 精确 seed keys
        if seed_keys != expected_seeds_set:
            reasons.append(f"INCOMPLETE: seeds {sorted(seed_keys)} != {expected_seeds}")
        metric_maps = {
            "active_day_annualized_return": st.get("active_day_annualized_return", {}),
            "sharpe": st.get("sharpe", {}),
            "max_drawdown": st.get("max_drawdown", {}),
        }
        for mname, mmap in metric_maps.items():
            if set(mmap.keys()) != expected_seeds_set:
                reasons.append(f"INCOMPLETE: metric {mname} seed keys {sorted(mmap.keys())} != {expected_seeds}")
        rets = [metric_maps["active_day_annualized_return"].get(s, float("nan")) for s in expected_seeds]
        sharpes = [metric_maps["sharpe"].get(s, float("nan")) for s in expected_seeds]
        mdds = [metric_maps["max_drawdown"].get(s, float("nan")) for s in expected_seeds]
        if not all(np.isfinite(v) for v in rets + sharpes + mdds) or not (rets and sharpes and mdds):
            reasons.append("non-finite/missing decision metrics")
        med_ret, med_sharpe, med_mdd = _median(rets), _median(sharpes), _median(mdds)
        stop_violations = int(st.get("stop_violations", 0))
        if stop_violations > 0:
            reasons.append(f"stop_violations={stop_violations}")
        if not (med_ret >= h_ret):
            reasons.append(f"median active_day_annualized_return {med_ret:.4f} < {h_ret:.4f}")
        if not (med_sharpe >= h_sharpe):
            reasons.append(f"median sharpe {med_sharpe:.3f} < {h_sharpe:.2f}")
        if not (med_mdd >= h_mdd):
            reasons.append(f"median max_drawdown {med_mdd:.4f} < {h_mdd:.4f}")
        n_pass_sharpe = sum(1 for s in sharpes if s >= h_sharpe)
        if n_pass_sharpe < req_pass:
            reasons.append(f"only {n_pass_sharpe}/{len(expected_seeds)} seeds sharpe >= hurdle (need {req_pass})")
        decision = "GO" if not reasons else ("NO_GO" if not any("INCOMPLETE" in r or "non-finite" in r for r in reasons)
                                             else "NO_GO")
        status = "INCOMPLETE" if any("INCOMPLETE" in r or "non-finite" in r for r in reasons) else decision
        per_algorithm[algo] = {
            "decision": decision,
            "status": status,
            "reasons": reasons,
            "median_active_day_annualized_return": med_ret,
            "median_sharpe": med_sharpe,
            "median_max_drawdown": med_mdd,
            "seeds_passing_sharpe": n_pass_sharpe,
            "required_seeds_pass": req_pass,
            "n_seeds_expected": len(expected_seeds),
        }

    n_go = sum(1 for v in per_algorithm.values() if v["decision"] == "GO")
    # F4：project-level 仅当算法集 == config algos（缺 algo → INCOMPLETE，不当作有意缺席）
    expected_algos_set = set(cfg["algorithms"].keys())
    actual_algos_set = set(per_algo_stitched.keys())
    algos_complete = actual_algos_set == expected_algos_set
    if algos_complete:
        project_level = "PROMISING" if n_go >= 1 else "NO_GO"
    else:
        project_level = "INCOMPLETE"

    # H7/F5：真 Pareto dominance vs MaxDiv；F5 要求全部冻结维度 finite 否则 UNAVAILABLE
    f_sharpe, f_mdd, f_calmar = frontier["sharpe"], frontier["max_drawdown"], frontier["calmar"]
    pareto: dict[str, dict] = {}
    for algo, v in per_algorithm.items():
        med_sharpe = v["median_sharpe"]
        med_mdd = v["median_max_drawdown"]
        med_calmar = per_algo_stitched[algo].get("calmar_median", float("nan"))
        dims = {
            "sharpe": (med_sharpe, f_sharpe, True),     # 高好
            "max_drawdown": (med_mdd, f_mdd, True),     # 高好（更浅）
            "calmar": (med_calmar, f_calmar, True),     # 高好
        }
        all_finite = all(np.isfinite(rl) and np.isfinite(mx) for rl, mx, _ in dims.values())
        if not all_finite:
            pareto[algo] = {
                "vs_max_div": "UNAVAILABLE/INCOMPLETE",
                "pareto_dominated": None,
                "underperforms_maxdiv_dimensions": [],
                "max_div": {"sharpe": f_sharpe, "max_drawdown": f_mdd, "calmar": f_calmar},
                "rl_median": {"sharpe": med_sharpe, "max_drawdown": med_mdd, "calmar": med_calmar},
            }
            continue
        # 真 Pareto（H7）：RL 被 MaxDiv 主导 ⟺ RL 全部目标 ≤ MaxDiv 且至少一严格 <
        le_all = all(dims[k][0] <= dims[k][1] for k in dims)
        strict_lt_any = any(dims[k][0] < dims[k][1] for k in dims)
        dominated = bool(dims) and le_all and strict_lt_any
        underperf = [k for k, (rl, mx, _) in dims.items() if rl < mx]
        pareto[algo] = {
            "vs_max_div": "dominated" if dominated else "not_dominated",
            "pareto_dominated": dominated,
            "underperforms_maxdiv_dimensions": underperf,
            "max_div": {"sharpe": f_sharpe, "max_drawdown": f_mdd, "calmar": f_calmar},
            "rl_median": {"sharpe": med_sharpe, "max_drawdown": med_mdd, "calmar": med_calmar},
        }

    return {
        "per_algorithm": per_algorithm,
        "project_level": project_level,
        "algos_complete": algos_complete,
        "pareto_vs_maxdiv": pareto,
        "hurdle": hurdle,
        "note": "deterministic config-driven evaluation; no Test-based algorithm ranking",
    }


def finalize_publish(results: dict, config_envelope: dict, mask_dates, per_algo_stitched: dict) -> dict:
    """F6：artifact 级 config provenance + publication 顺序（fail-closed）。

    1. 顶层 config_sha256 == config_envelope digest；
    2. 校验每 run config_sha256 == 顶层 == 当前 frozen digest（mismatch → 不 publish）；
    3. validate_runtime_invariants（失败 → raise，不 publish）；
    4. 仅 invariant 通过后跑 evaluate_go_nogo；
    5. 任何失败 → 不写最终 tracked artifact（本函数不写盘，返回可写 payload）。

    返回 {config_sha256, go_nogo, results}（publish-ready）。
    """
    cfg = config_envelope["config"]
    top_sha = config_envelope["config_sha256"]

    # 校验每 run config_sha256 == 顶层
    for algo, ag in results.get("per_algorithm", {}).items():
        for seed_key, seed_res in ag.items():
            for fold_name, fm in seed_res.items():
                run_sha = fm.get("config_sha256")
                if run_sha is None:
                    raise InvariantViolation(f"{algo}|{seed_key}|{fold_name}: run config_sha256 missing")
                if run_sha != top_sha:
                    raise InvariantViolation(
                        f"{algo}|{seed_key}|{fold_name}: run sha {run_sha[:8]} != top {top_sha[:8]}")

    # invariant 校验（失败 raise）
    validate_runtime_invariants(results, mask_dates, cfg)

    # 仅 invariant 通过后跑 GO/NO-GO
    go_nogo = evaluate_go_nogo(per_algo_stitched, cfg)

    return {
        "config_sha256": top_sha,
        "go_nogo": go_nogo,
        "results": results,
        "published": True,
    }
