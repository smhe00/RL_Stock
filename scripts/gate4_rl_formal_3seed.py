"""CORRECTED_F0_RL_3SEED — frozen corrected F0 3-seed 正式执行（36 RL runs，并行编排）。

评审（CORRECTED_F0_RL_EXECUTION_PUBLICATION_SCHEMA_CLOSEOUT_REVIEWER_RESPONSE.md）授权。
执行契约：F0 dim 104 | PPO/SAC/TD3 | seeds 42/2026/7 | folds F1-F4 | 36 runs | train_passes 20
net [256,256] | final endpoint | configs/rl_formal_protocol.yaml | run_fold_rl_config/shared constructor
Test mask: canonical 475 RESEARCH_BENCHMARK_TEST | Test-informed selection: forbidden
fail-closed: 任何 hard-stop/invariant/异常 → 报告，不用 Test 调参
publication: finalize_publish() → GO/NO-GO 仅 derived from validated raw 36-run tree

并行模式：
  --algo PPO   （cpu）每进程只跑一个 algo → runs/gate4_rl_formal_partial_<algo>.json
  --algo SAC   （gpu）
  --algo TD3   （gpu）
  --aggregate  读 3 个 partial → 合并 → validate + finalize_publish → tracked artifacts

输出（tracked，finalize_publish 通过才写）：
  artifacts/gate4_rl_formal_results.json   汇总（canonical + go_nogo + Pareto + per-seed）
  artifacts/gate4_rl_formal_raw.json       原始 series
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from china_etf.data.corporate_actions import load_corporate_actions  # noqa: E402
from china_etf.data.loader import SLOT_MAP, load_execution_prices, load_research_adj  # noqa: E402
from china_etf.evaluation.benchmark import exact_test_mask  # noqa: E402
from china_etf.evaluation.rl_formal import (  # noqa: E402
    check_no_forbidden_overrides,
    finalize_publish,
    load_protocol_config,
    run_fold_rl_config,
)
from china_etf.evaluation.walkforward import WalkForwardRunner  # noqa: E402
from gate4_3seed_pilot import build_env  # noqa: E402

PARTIAL_DIR = ROOT / "runs"


def _algo_classes():
    from stable_baselines3 import PPO, SAC, TD3
    return {"PPO": PPO, "SAC": SAC, "TD3": TD3}


def _build_runner():
    adj = load_research_adj()
    opens, closes = load_execution_prices()
    ca = load_corporate_actions()
    runner = WalkForwardRunner(
        adj=adj, opens=opens, closes=closes, slots=list(SLOT_MAP.keys()),
        slot_to_instrument={s: SLOT_MAP[s]["instrument"] for s in SLOT_MAP},
        build_env=build_env, corporate_actions=ca,
    )
    return runner


def run_algo(algo_name: str, envelope: dict, runner, folds, mask_str: list[str]) -> dict:
    """跑一个 algo 的全部 3 seeds × 4 folds = 12 runs。返回该 algo 的 per_algorithm[algo] 子树。"""
    cfg = envelope["config"]
    sha = envelope["config_sha256"]
    algo_cls = _algo_classes()[algo_name]
    per_algo: dict = {}
    stop_flags: list[str] = []
    for seed in cfg["seeds"]:
        per_algo[seed] = {}
        for fold in folds:
            key = f"{algo_name}|{seed}|{fold.name}"
            print(f"[{key}] starting...", flush=True)
            t0 = time.time()
            try:
                run = run_fold_rl_config(runner, fold, algo_cls, algo_name, seed, envelope)
            except Exception as exc:  # noqa: BLE001
                print(f"[{key}] EXCEPTION: {str(exc)[:200]}", flush=True)
                per_algo[seed][fold.name] = {
                    "config_sha256": sha, "error": str(exc)[:300],
                    "test": {"series": {"execution_dates": mask_str, "net_returns": [], "costs": [],
                                        "cash": [], "actual_weights": [], "raw_weights": [],
                                        "post_risk_weights": []},
                             "n_eval_steps": 0, "total_cost": 0,
                             "nan_obs_or_reward": 1, "negative_cash_count": 0}}
                stop_flags.append(f"{seed}|{fold.name}:exception")
                continue
            per_algo[seed][fold.name] = run
            test = run["test"]
            problems = []
            if test["nan_obs_or_reward"] > 0:
                problems.append("NaN/Inf")
            if test["negative_cash_count"] > 0:
                problems.append("negative_cash")
            if not run["save_load_deterministic_identical"]:
                problems.append("save_load_mismatch")
            if not np.isfinite(test.get("oos_cum_return", float("nan"))):
                problems.append("non_finite_oos")
            if problems:
                stop_flags.append(f"{seed}|{fold.name}:{';'.join(problems)}")
            print(f"[{key}] done {time.time()-t0:6.1f}s  test_cum={test['oos_cum_return']:.4f} "
                  f"sharpe={test['sharpe']:.2f} mdd={test['max_drawdown']:.3f} "
                  f"nan={test['nan_obs_or_reward']} neg_cash={test['negative_cash_count']} "
                  f"save_load={run['save_load_deterministic_identical']}", flush=True)
    return {"per_algorithm": {algo_name: per_algo}, "stop_flags": stop_flags, "algo": algo_name}


def aggregate(envelope: dict, runner, folds, mask_str: list[str]) -> None:
    """读 3 个 partial → 合并 → validate + finalize_publish → tracked artifacts。"""
    merged: dict = {}
    all_stops: dict[str, list[str]] = {}
    for algo in envelope["config"]["algorithms"]:
        partial_path = PARTIAL_DIR / f"gate4_rl_formal_partial_{algo}.json"
        if not partial_path.exists():
            sys.exit(f"missing partial: {partial_path}")
        part = json.loads(partial_path.read_text(encoding="utf-8"))
        merged.update(part["per_algorithm"])
        all_stops[algo] = part.get("stop_flags", [])
    raw_series: dict[str, dict] = {}
    for algo, ag in merged.items():
        for seed_key, seed_res in ag.items():
            for fold_name, fm in seed_res.items():
                raw_series[f"{algo}|{seed_key}|{fold_name}"] = fm.get("test", {}).get("series", {})

    results = {"per_algorithm": merged}
    t_start = time.time()
    payload = finalize_publish(results, envelope, mask_str)
    go_nogo = payload["go_nogo"]
    canonical = payload["canonical_stitched"]

    print("\n== GO/NO-GO ==", flush=True)
    for algo, v in go_nogo["per_algorithm"].items():
        print(f"  {algo}: {v['decision']} ({v['status']}) "
              f"median_ret={v['median_active_day_annualized_return']:.4f} "
              f"median_sharpe={v['median_sharpe']:.3f} median_mdd={v['median_max_drawdown']:.4f} "
              f"seeds_pass={v['seeds_passing_sharpe']}/{v['required_seeds_pass']}", flush=True)
    print(f"  project_level = {go_nogo['project_level']}", flush=True)
    print("  Pareto vs MaxDiv:", flush=True)
    for algo, p in go_nogo["pareto_vs_maxdiv"].items():
        print(f"    {algo}: {p['vs_max_div']} underperf={p['underperforms_maxdiv_dimensions']}", flush=True)

    report = {
        "manifest": {
            "gate": "CORRECTED_F0_RL_3SEED",
            "observation": "F0", "observation_dim": 104,
            "algorithms": list(envelope["config"]["algorithms"]),
            "seeds": envelope["config"]["seeds"],
            "folds": len(folds),
            "total_runs": sum(len(seed_res) for ag in merged.values() for seed_res in ag.values()),
            "train_passes": envelope["config"]["train_passes"],
            "net_arch": envelope["config"]["net_arch"],
            "config_sha256": envelope["config_sha256"],
            "test_mask_label": "RESEARCH_BENCHMARK_TEST", "test_mask_count": 475,
            "runtime_seconds": round(time.time() - t_start, 1),
            "stop_flags": all_stops,
        },
        "go_nogo": go_nogo,
        "canonical_stitched": canonical,
        "per_seed_metrics": {
            algo: {
                "per_seed": {str(s): {k: round(v, 8) for k, v in ps.items()}
                             for s, ps in ag["per_seed"].items()},
                "medians": {"active_day_annualized_return": round(
                    float(np.median([x for x in ag["active_day_annualized_return"].values()])), 6),
                    "sharpe": round(float(np.median([x for x in ag["sharpe"].values()])), 6),
                    "max_drawdown": round(float(np.median([x for x in ag["max_drawdown"].values()])), 6),
                    "calmar": round(float(ag["calmar_median"]), 6)},
            }
            for algo, ag in canonical.items()
        },
        "benchmark_reference": {
            "equal_weight_hurdle": envelope["config"]["benchmark"]["primary_return_hurdle"],
            "max_div_frontier": envelope["config"]["benchmark"]["risk_adjusted_frontier"],
        },
    }

    art_dir = ROOT / "artifacts"
    art_dir.mkdir(parents=True, exist_ok=True)
    out = art_dir / "gate4_rl_formal_results.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    raw_path = art_dir / "gate4_rl_formal_raw.json"
    raw_path.write_text(json.dumps({"series": raw_series}, indent=2, ensure_ascii=False, default=str),
                        encoding="utf-8")
    print(f"\n-> {out}\n-> {raw_path}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--algo", type=str, default=None, help="run one algo (PPO/SAC/TD3)")
    ap.add_argument("--aggregate", action="store_true", help="merge partials -> finalize_publish")
    args = ap.parse_args()

    check_no_forbidden_overrides()
    envelope = load_protocol_config()
    cfg = envelope["config"]
    sha = envelope["config_sha256"]

    runner = _build_runner()
    folds = runner.make_folds(n_folds=4)
    mask = exact_test_mask(folds, calendar=runner.adj.index)
    assert mask["exact_test_date_count"] == 475
    mask_str = [str(d.date()) for d in mask["test_dates"]]

    if args.algo:
        if args.algo not in cfg["algorithms"]:
            sys.exit(f"unknown algo {args.algo}")
        print(f"== CORRECTED_F0_RL_3SEED --algo {args.algo}: "
              f"seeds={cfg['seeds']} folds={len(folds)} mask=475 config_sha256={sha[:12]} ==", flush=True)
        result = run_algo(args.algo, envelope, runner, folds, mask_str)
        PARTIAL_DIR.mkdir(parents=True, exist_ok=True)
        out = PARTIAL_DIR / f"gate4_rl_formal_partial_{args.algo}.json"
        out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        print(f"-> {out}", flush=True)
        return

    if args.aggregate:
        aggregate(envelope, runner, folds, mask_str)
        return

    ap.print_help()


if __name__ == "__main__":
    main()
