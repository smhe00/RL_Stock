"""GATE_4_NON_RL_HORSE_RACE(CORRECTIONS) — 非 RL 组合方法对比（N1-N8 修正）。

Tier A 10 方法 × 4 folds，全部走 corrected 评估路径（fold-local test reset, 1x cost, CA）：
  EW / RiskParity(IVOL) / MinimumVariance / Momentum(12-1)   （现有，corrected-path 重跑）
  ERC / HRP / MaxDiv / TrendRiskParity / MinCVaR_95 / ShrinkageMV   （N1-N6 canonical）

N7：每方法 assert n_eval_steps == exact_test_date_count（475）+ 执行日期 == mask.test_dates。
N8：结果输出到 tracked artifacts/ 路径（非 runs/）。

RL 3-seed 结果仅作为 HISTORICAL_RL_PILOT_REFERENCE（pre-correction caveat），不重训。
禁止：RL 重训 / 10-seed / Optuna / Test-informed 调参。

输出：artifacts/gate4_non_rl_horse_race_results.json + _raw.json
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from china_etf.data.loader import SLOT_MAP, load_execution_prices, load_research_adj  # noqa: E402
from china_etf.data.corporate_actions import load_corporate_actions  # noqa: E402
from china_etf.evaluation.baselines import (  # noqa: E402
    equal_weight_policy, erc_policy, hrp_policy, maximum_diversification_policy,
    minimum_cvar_policy, minimum_variance_policy, momentum_policy, risk_parity_policy,
    shrinkage_mean_variance_policy, trend_risk_parity_policy,
)
from china_etf.evaluation.walkforward import WalkForwardRunner  # noqa: E402
from gate4_3seed_pilot import build_env  # noqa: E402

TIER_A = [
    ("EqualWeight", equal_weight_policy),
    ("RiskParity_IVOL", risk_parity_policy),
    ("MinimumVariance", minimum_variance_policy),
    ("Momentum_12_1", momentum_policy),
    ("EqualRiskContribution_ERC", erc_policy),
    ("HierarchicalRiskParity_HRP", hrp_policy),
    ("MaximumDiversification", maximum_diversification_policy),
    ("TrendRiskParity", trend_risk_parity_policy),
    ("MinimumCVaR_95", minimum_cvar_policy),
    ("ShrinkageMeanVariance", shrinkage_mean_variance_policy),
]

METRICS = ["oos_cum_return", "cagr", "annualized_vol", "sharpe", "sortino",
           "max_drawdown", "calmar", "mean_turnover", "total_cost",
           "cost_over_initial_value", "mean_hhi", "mean_active_assets",
           "max_single_asset_weight", "risk_overlay_intervention_rate",
           "nan_obs_or_reward", "negative_cash_count", "n_eval_steps"]


def main() -> None:
    adj = load_research_adj()
    opens, closes = load_execution_prices()
    ca = load_corporate_actions()
    runner = WalkForwardRunner(
        adj=adj, opens=opens, closes=closes, slots=list(SLOT_MAP.keys()),
        slot_to_instrument={s: SLOT_MAP[s]["instrument"] for s in SLOT_MAP},
        build_env=build_env, corporate_actions=ca,
    )
    folds = runner.make_folds(n_folds=4)
    print(f"== Track A: decision_start={runner.decision_start.date()} "
          f"calendar_rows={(adj.index >= runner.decision_start).sum()} ==")

    # N7：exact Test mask
    from china_etf.evaluation.benchmark import exact_test_mask
    mask = exact_test_mask(folds, calendar=adj.index)
    mask_dates = mask["test_dates"]
    mask_count = mask["exact_test_date_count"]
    print(f"exact_test_date_count = {mask_count} (475)")

    results = {
        "methods": {},
        "horse_race_table": {},
        "rl_historical_reference": {},
        "timing": {},
        "exact_test_mask": {k: v for k, v in mask.items() if k != "test_dates"},
    }

    for name, fac in TIER_A:
        t0 = time.time()
        per_fold = {}
        all_ret = []
        actual_exec_dates = []  # F5：真实 rollout 执行日期（st.t_next）
        for f in folds:
            m = runner.run_fold_baseline(f, fac)
            per_fold[f.name] = {k: m["test"][k] for k in METRICS}
            all_ret.extend(m["test"]["series"]["net_returns"])
            actual_exec_dates.extend(m["test"]["series"]["execution_dates"])
            assert m["test"]["n_eval_steps"] == len(m["test"]["series"]["execution_dates"]), \
                f"{name} {f.name}: n_eval vs execution_dates mismatch"
        # F5：真实执行日期 == exact Test mask（独立于 mask 重建）
        mask_dates_str = [str(d.date()) for d in mask_dates]
        assert actual_exec_dates == mask_dates_str, \
            f"{name}: 真实执行日期 != exact Test mask（差异 {len(set(actual_exec_dates) ^ set(mask_dates_str))}）"
        assert len(all_ret) == mask_count, f"{name} stitched {len(all_ret)} != mask {mask_count}"
        results["methods"][name] = {
            "per_fold": per_fold,
            "seconds": round(time.time() - t0, 1),
            "mask_parity": {"n_eval_steps": len(all_ret), "exact_test_date_count": mask_count,
                            "actual_execution_dates_equal_mask": True},
        }
        # stitched（F6 完整诊断）
        nr = np.asarray(all_ret, float)
        cum = float(np.exp(np.log1p(nr).sum()) - 1.0)
        # active-day annualized return（非普通日历 CAGR）
        active_ann = float((1.0 + cum) ** (252.0 / len(nr)) - 1.0)
        vol = float(np.std(nr) * np.sqrt(252))
        sharpe = float(np.mean(nr) / np.std(nr) * np.sqrt(252)) if np.std(nr) > 0 else float("nan")
        downside = nr[nr < 0]
        sortino = float(np.mean(nr) / np.std(downside) * np.sqrt(252)) if len(downside) > 1 and np.std(downside) > 0 else float("nan")
        eq = np.exp(np.log1p(nr).cumsum())
        mdd = float((eq / np.maximum.accumulate(eq) - 1.0).min())
        calmar = float(active_ann / abs(mdd)) if np.isfinite(active_ann) and abs(mdd) > 1e-12 else float("nan")
        # 聚合 turnover/cost/HHI/active/maxweight/overlay（跨 fold 平均）
        def agg(key):
            vals = [per_fold[f][key] for f in per_fold if np.isfinite(per_fold[f][key])]
            return float(np.mean(vals)) if vals else float("nan")
        stitched = {
            "n_steps": len(nr), "cum_return": round(cum, 6),
            "active_day_annualized_return": round(active_ann, 6),  # 明确标注
            "annualized_vol": round(vol, 6), "sharpe": round(sharpe, 6),
            "sortino": round(sortino, 6), "max_drawdown": round(mdd, 6), "calmar": round(calmar, 6),
            "mean_turnover": round(agg("mean_turnover"), 6),
            "total_turnover": round(sum(per_fold[f]["mean_turnover"] * per_fold[f]["n_eval_steps"] for f in per_fold), 6),
            "total_cost": round(agg("total_cost") * 4, 2),
            "cost_over_initial_value": round(agg("cost_over_initial_value"), 6),
            "mean_hhi": round(agg("mean_hhi"), 6),
            "mean_active_assets": round(agg("mean_active_assets"), 6),
            "max_single_asset_weight": round(agg("max_single_asset_weight"), 6),
            "risk_overlay_intervention_rate": round(agg("risk_overlay_intervention_rate"), 6),
            "nan_obs_or_reward": int(sum(per_fold[f]["nan_obs_or_reward"] for f in per_fold)),
            "negative_cash_count": int(sum(per_fold[f]["negative_cash_count"] for f in per_fold)),
        }
        results["methods"][name]["stitched"] = stitched
        results["horse_race_table"][name] = {
            "cum_return": round(cum, 5), "active_day_annualized_return": round(active_ann, 5),
            "sharpe": round(sharpe, 5), "sortino": round(sortino, 5),
            "max_drawdown": round(mdd, 5), "calmar": round(calmar, 5),
            "mean_turnover": round(agg("mean_turnover"), 5),
            "total_cost": round(agg("total_cost") * 4, 2),
            "mean_hhi": round(agg("mean_hhi"), 5),
            "mean_active_assets": round(agg("mean_active_assets"), 5),
            "max_single_asset_weight": round(agg("max_single_asset_weight"), 5),
            "overlay_intervention_rate": round(agg("risk_overlay_intervention_rate"), 5),
            "fallback_count": 0,
        }
        print(f"{name:32s} cum={cum:+.4f} active_ann={active_ann:+.4f} sharpe={sharpe:.3f} "
              f"mdd={mdd:.3f} overlay={agg('risk_overlay_intervention_rate'):.2f}")

    # RL 历史参考（pre-correction caveat）
    rl_path = ROOT / "runs" / "gate4_3seed_pilot_results.json"
    if rl_path.exists():
        rl = json.loads(rl_path.read_text(encoding="utf-8"))
        for algo in ["TD3", "SAC", "PPO"]:
            if algo in rl.get("stitched_oos", {}):
                st = rl["stitched_oos"][algo]
                cagrs = [v["cagr"] for v in st.values()]
                sharpes = [v["sharpe"] for v in st.values()]
                mdds = [v["max_drawdown"] for v in st.values()]
                results["rl_historical_reference"][algo] = {
                    "note": "HISTORICAL_RL_PILOT_REFERENCE (pre-correction eval semantics; not formal OOS)",
                    "cagr": {"median": float(np.median(cagrs)), "mean": float(np.mean(cagrs)),
                             "min": float(np.min(cagrs)), "max": float(np.max(cagrs))},
                    "sharpe": {"median": float(np.median(sharpes)), "mean": float(np.mean(sharpes)),
                               "min": float(np.min(sharpes)), "max": float(np.max(sharpes))},
                    "max_drawdown": {"median": float(np.median(mdds)), "mean": float(np.mean(mdds)),
                                     "min": float(np.min(mdds)), "max": float(np.max(mdds))},
                }
        print("\nRL historical reference (pre-correction):")
        for algo, ref in results["rl_historical_reference"].items():
            print(f"  {algo}: cagr_median={ref['cagr']['median']:.4f} sharpe_median={ref['sharpe']['median']:.4f}")

    # N8：结果输出到 tracked artifacts/（非 runs/，可审计提交）
    art_dir = ROOT / "artifacts"
    art_dir.mkdir(parents=True, exist_ok=True)
    out = art_dir / "gate4_non_rl_horse_race_results.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    raw = art_dir / "gate4_non_rl_horse_race_raw.json"
    raw.write_text(json.dumps({"methods": results["methods"]}, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
