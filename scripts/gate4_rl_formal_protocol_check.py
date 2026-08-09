"""RL_FORMAL_PROTOCOL_PREP — 冻结协议契约可执行性验证（无训练）。

验证协议（docs/features/RL_FORMAL_PROTOCOL.md）冻结值与既有 corrected 路径一致：
- exact_test_mask == 475 执行日
- 每 fold train/val/test 决策日数
- EqualWeight benchmark hurdle 值（artifacts/gate4_non_rl_horse_race_results.json）
- 算法/seed/配置一致性断言
不训练任何 RL。输出 runs/gate4_rl_formal_protocol_check.json（gitignored）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from china_etf.data.corporate_actions import load_corporate_actions  # noqa: E402
from china_etf.data.loader import SLOT_MAP, load_research_adj  # noqa: E402
from china_etf.evaluation.benchmark import exact_test_mask  # noqa: E402
from china_etf.evaluation.walkforward import WalkForwardRunner  # noqa: E402
from gate4_3seed_pilot import build_env  # noqa: E402

# 协议冻结值（RL_FORMAL_PROTOCOL.md）
PROTOCOL = {
    "algorithms": ["PPO", "SAC", "TD3"],
    "seeds": [42, 2026, 7],
    "train_passes": 20,
    "net_arch": [256, 256],
    "hurdle": {"cagr": 0.2687, "sharpe": 1.64, "max_drawdown": -0.0881},
}


def main() -> None:
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

    # 每 fold train/val/test 决策日数
    fold_regions = {}
    for f in folds:
        dec = adj.index[(adj.index >= runner.decision_start) & (adj.index <= f.test_end)]
        fold_regions[f.name] = {
            "train_days": int(((dec >= f.train_start) & (dec <= f.train_end)).sum()),
            "val_days": int(((dec >= f.val_start) & (dec <= f.val_end)).sum()),
            "test_days": int(((dec >= f.test_start) & (dec <= f.test_end)).sum()),
        }

    # EqualWeight benchmark hurdle（corrected 路径，artifact）
    art = ROOT / "artifacts" / "gate4_non_rl_horse_race_results.json"
    hr = json.loads(art.read_text(encoding="utf-8"))["horse_race_table"]["EqualWeight"]
    hurdle_ok = (abs(hr["active_day_annualized_return"] - PROTOCOL["hurdle"]["cagr"]) < 1e-3
                 and abs(hr["sharpe"] - PROTOCOL["hurdle"]["sharpe"]) < 1e-2
                 and abs(hr["max_drawdown"] - PROTOCOL["hurdle"]["max_drawdown"]) < 1e-3)

    # 配置一致性断言（无训练）
    assert n_test == 475, f"exact_test_mask={n_test} != 475"
    assert hurdle_ok, "EqualWeight hurdle mismatch with artifact"
    total_runs = len(PROTOCOL["algorithms"]) * len(PROTOCOL["seeds"]) * len(folds)
    assert total_runs == 36

    results = {
        "protocol": PROTOCOL,
        "exact_test_mask": {"count": n_test, "first": str(mask["first_test_date"]),
                            "last": str(mask["last_test_date"])},
        "fold_regions": fold_regions,
        "benchmark_hurdle_equal_weight": {
            "cagr": hr["active_day_annualized_return"], "sharpe": hr["sharpe"],
            "max_drawdown": hr["max_drawdown"], "matches_protocol": hurdle_ok},
        "total_runs_3seed": total_runs,
        "rl_training_executed": False,
        "checks_passed": True,
    }
    out = ROOT / "runs" / "gate4_rl_formal_protocol_check.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    print(f"exact_test_mask = {n_test} (475)  [{mask['first_test_date']} .. {mask['last_test_date']}]")
    print("fold train/val/test decision days:")
    for name, r in fold_regions.items():
        print(f"  {name}: train={r['train_days']} val={r['val_days']} test={r['test_days']}")
    print(f"EqualWeight hurdle: cagr={hr['active_day_annualized_return']:.4f} "
          f"sharpe={hr['sharpe']:.2f} mdd={hr['max_drawdown']:.4f} matches={hurdle_ok}")
    print(f"total 3-seed runs (3 algos x 3 seeds x 4 folds) = {total_runs}")
    print(f"-> {out}")


if __name__ == "__main__":
    main()
