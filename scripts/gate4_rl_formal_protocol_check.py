"""RL_FORMAL_PROTOCOL_PREP_CORRECTIONS — 冻结协议可执行性验证（P7 机器可读 config，无训练）。

读取 configs/rl_formal_protocol.yaml（canonical 输入）并验证：
- exact_test_mask == 475 执行日
- 每 fold train/val/test 决策日数
- 两层 benchmark（EqualWeight primary + MaxDiv frontier）与 horse-race artifact 一致
- P7：config 超参与 SB3 默认一致（PPO/SAC/TD3）
- P8：hard-stop invariants 契约存在
不训练任何 RL。输出 runs/gate4_rl_formal_protocol_check.json（gitignored）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from china_etf.data.corporate_actions import load_corporate_actions  # noqa: E402
from china_etf.data.loader import SLOT_MAP, load_research_adj  # noqa: E402
from china_etf.evaluation.benchmark import exact_test_mask  # noqa: E402
from china_etf.evaluation.walkforward import WalkForwardRunner  # noqa: E402
from gate4_3seed_pilot import build_env  # noqa: E402


def load_config() -> dict:
    cfg_path = ROOT / "configs" / "rl_formal_protocol.yaml"
    return yaml.safe_load(cfg_path.read_text(encoding="utf-8"))


def check_hyperparams_match_sb3(cfg: dict) -> dict:
    """P7：config 超参与 SB3 默认一致（run_fold_rl 只用 policy_kwargs/seed/device 覆盖）。"""
    from stable_baselines3 import PPO, SAC, TD3
    import inspect
    results = {}
    for cls, name in ((PPO, "PPO"), (SAC, "SAC"), (TD3, "TD3")):
        sig = inspect.signature(cls.__init__)
        cfg_algo = cfg["algorithms"][name]
        mismatches = {}
        for param, frozen in cfg_algo.items():
            default = sig.parameters[param].default
            if default is not inspect.Parameter.empty and str(default) != str(frozen):
                mismatches[param] = {"config": frozen, "sb3_default": str(default)}
        results[name] = {"match": len(mismatches) == 0, "mismatches": mismatches}
    return results


def main() -> None:
    cfg = load_config()
    adj = load_research_adj()
    ca = load_corporate_actions()
    runner = WalkForwardRunner(
        adj=adj, opens={}, closes={}, slots=list(SLOT_MAP.keys()),
        slot_to_instrument={s: SLOT_MAP[s]["instrument"] for s in SLOT_MAP},
        build_env=build_env, corporate_actions=ca,
    )
    folds = runner.make_folds(n_folds=4)

    mask = exact_test_mask(folds, calendar=adj.index)
    n_test = mask["exact_test_date_count"]

    fold_regions = {}
    for f in folds:
        dec = adj.index[(adj.index >= runner.decision_start) & (adj.index <= f.test_end)]
        fold_regions[f.name] = {
            "train_days": int(((dec >= f.train_start) & (dec <= f.train_end)).sum()),
            "val_days": int(((dec >= f.val_start) & (dec <= f.val_end)).sum()),
            "test_days": int(((dec >= f.test_start) & (dec <= f.test_end)).sum()),
        }

    art = ROOT / "artifacts" / "gate4_non_rl_horse_race_results.json"
    hr = json.loads(art.read_text(encoding="utf-8"))["horse_race_table"]

    # P4：两层 benchmark 与 artifact 一致
    ew_cfg = cfg["benchmark"]["primary_return_hurdle"]
    mxd_cfg = cfg["benchmark"]["risk_adjusted_frontier"]
    ew = hr["EqualWeight"]
    mxd = hr["MaximumDiversification"]
    ew_ok = (abs(ew["active_day_annualized_return"] - ew_cfg["active_day_annualized_return"]) < 1e-3
             and abs(ew["sharpe"] - ew_cfg["sharpe"]) < 1e-2)
    mxd_ok = (abs(mxd["active_day_annualized_return"] - mxd_cfg["active_day_annualized_return"]) < 1e-3
              and abs(mxd["sharpe"] - mxd_cfg["sharpe"]) < 1e-2)

    # P7：超参匹配 SB3 默认
    hp = check_hyperparams_match_sb3(cfg)

    # 配置一致性断言（无训练）
    assert n_test == cfg["meta"]["test_mask_count"] == 475, f"mask {n_test} != 475"
    assert cfg["meta"]["test_mask_label"] == "RESEARCH_BENCHMARK_TEST"
    assert cfg["meta"]["forward_holdout"] == "FUTURE_FINAL_FORWARD_HOLDOUT"
    assert cfg["checkpoint_policy"] == "final_training_endpoint_only"
    assert cfg["seeds"] == [42, 2026, 7]
    assert ew_ok, "EqualWeight hurdle mismatch with artifact"
    assert mxd_ok, "MaxDiv frontier mismatch with artifact"
    assert all(v["match"] for v in hp.values()), "config hyperparams != SB3 defaults"
    assert len(cfg["hard_stop_invariants"]) >= 5, "P8 hard-stop invariants missing"
    total_runs = len(cfg["algorithms"]) * len(cfg["seeds"]) * len(folds)
    assert total_runs == 36

    results = {
        "config_source": "configs/rl_formal_protocol.yaml",
        "exact_test_mask": {"label": cfg["meta"]["test_mask_label"], "count": n_test,
                            "first": str(mask["first_test_date"]), "last": str(mask["last_test_date"]),
                            "forward_holdout": cfg["meta"]["forward_holdout"]},
        "fold_regions": fold_regions,
        "benchmark": {
            "primary_return_hurdle": {"name": ew_cfg["name"], "matches_artifact": ew_ok,
                                      "cagr": ew["active_day_annualized_return"], "sharpe": ew["sharpe"],
                                      "mdd": ew["max_drawdown"]},
            "risk_adjusted_frontier": {"name": mxd_cfg["name"], "matches_artifact": mxd_ok,
                                       "cagr": mxd["active_day_annualized_return"], "sharpe": mxd["sharpe"],
                                       "mdd": mxd["max_drawdown"], "calmar": mxd["calmar"]},
        },
        "hyperparams_match_sb3": hp,
        "hard_stop_invariants": cfg["hard_stop_invariants"],
        "checkpoint_policy": cfg["checkpoint_policy"],
        "total_runs_3seed": total_runs,
        "rl_training_executed": False,
        "checks_passed": True,
    }
    out = ROOT / "runs" / "gate4_rl_formal_protocol_check.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    print(f"config: {cfg['meta']['gate']}  observation={cfg['meta']['observation']} "
          f"obs_dim={cfg['meta']['observation_dim']}")
    print(f"exact_test_mask = {n_test} (475)  [{mask['first_test_date']} .. {mask['last_test_date']}] "
          f"label={cfg['meta']['test_mask_label']}")
    print("fold train/val/test decision days:")
    for name, r in fold_regions.items():
        print(f"  {name}: train={r['train_days']} val={r['val_days']} test={r['test_days']}")
    print(f"benchmark EW(primary): cagr={ew['active_day_annualized_return']:.4f} sharpe={ew['sharpe']:.2f} "
          f"match={ew_ok} | MaxDiv(frontier): sharpe={mxd['sharpe']:.2f} mdd={mxd['max_drawdown']:.4f} match={mxd_ok}")
    print(f"hyperparams match SB3: { {k: v['match'] for k, v in hp.items()} }")
    print(f"hard_stop_invariants: {len(cfg['hard_stop_invariants'])}  checkpoint={cfg['checkpoint_policy']}")
    print(f"-> {out}")


if __name__ == "__main__":
    main()
