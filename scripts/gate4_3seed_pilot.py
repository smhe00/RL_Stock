"""GATE_4_3_SEED_PILOT — 评审 §18 授权的 3-seed walk-forward pilot。

4 folds × TD3 / SAC / PPO × seeds 42 / 2026 / 7 × TRAIN_PASSES=20 × 1x cost = 36 RL trainings
+ EW / RiskParity / MinVariance / Momentum baselines（同 folds/执行/记账路径，不重复 seed）。

执行顺序（评审 §26 早停优化）：seed 42 全 4 folds × 3 algos 先行；全部通过 stop 条件再跑 seeds 2026/7。
禁止：按 Test 调参、winner 结论、Optuna、改超参/步骤/网络（§16/§17/§27 冻结）。

输出：
  runs/gate4_3seed_pilot_results.json  主结果（评审 §32 清单，不含 series）
  runs/gate4_3seed_pilot_raw.json      原始 series（net_returns/weights/costs 等）
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stable_baselines3 import PPO, SAC, TD3  # noqa: E402

from china_etf.contracts import EnvironmentMode  # noqa: E402
from china_etf.cost.mainland import MainlandETFCostModel  # noqa: E402
from china_etf.data.corporate_actions import load_corporate_actions  # noqa: E402
from china_etf.data.loader import SLOT_MAP, load_execution_prices, load_research_adj  # noqa: E402
from china_etf.environment.portfolio_env import ChinaETFPortfolioEnv  # noqa: E402
from china_etf.evaluation.baselines import (  # noqa: E402
    equal_weight_policy,
    minimum_variance_policy,
    momentum_policy,
    risk_parity_policy,
)
from china_etf.evaluation.walkforward import WalkForwardRunner  # noqa: E402
from china_etf.execution.broker.mock import MockBroker  # noqa: E402
from china_etf.execution.order_generator import OrderGenerator  # noqa: E402
from china_etf.execution.premium import PremiumGuard  # noqa: E402
from china_etf.execution.tradability import TradabilityMask  # noqa: E402

import os as _os

# 评审 §16 冻结 TRAIN_PASSES=20；dry-run 验证可用环境变量覆盖（正式跑勿设置）
SEEDS = [int(x) for x in (_os.environ.get("GATE4_PILOT_SEEDS", "42,2026,7").split(",")) if x.strip()]
TRAIN_PASSES = int(_os.environ.get("GATE4_PILOT_PASSES", "20"))
_ALGO_SUBSET = [x.strip() for x in _os.environ.get("GATE4_PILOT_ALGOS", "TD3,SAC,PPO").split(",") if x.strip()]
ALGOS = [(n, c, d) for (n, c, d) in [("TD3", TD3, "cuda"), ("SAC", SAC, "cuda"), ("PPO", PPO, "cpu")] if n in _ALGO_SUBSET]
BASELINES = [
    ("EqualWeight", equal_weight_policy),
    ("RiskParity", risk_parity_policy),
    ("MinimumVariance", minimum_variance_policy),
    ("Momentum", momentum_policy),
]
SLOTS = list(SLOT_MAP.keys())
CA = load_corporate_actions()

# 聚合字段（test 指标子集，用于主 JSON）
TEST_FIELDS = [
    "oos_cum_return", "cagr", "annualized_vol", "sharpe", "sortino", "max_drawdown", "calmar",
    "mean_turnover", "total_turnover", "mean_active_assets", "max_single_asset_weight", "mean_hhi",
    "total_cost", "cost_over_initial_value", "min_broker_cash", "negative_cash_count",
    "risk_overlay_intervention_rate", "risk_overlay_mean_l1_raw_to_post",
    "single_core_cap_hit_rate", "china_growth_cap_hit_rate",
    "n_eval_steps", "nan_obs_or_reward", "actual_cash_residual_mean", "actual_china_growth_mean",
]


def build_env(adj, opens, closes, corporate_actions=None) -> ChinaETFPortfolioEnv:
    broker = MockBroker(
        tradability=TradabilityMask(),
        premium_guard=PremiumGuard(requires_protection=lambda i: i == "US_BROAD"),
        cost_model=MainlandETFCostModel(),
        open_prices=opens,
    )
    return ChinaETFPortfolioEnv(
        slots=SLOTS, adj_close=adj, open_prices=opens, close_prices=closes,
        initial_cash=1_000_000.0, broker=broker, order_generator=OrderGenerator(),
        slot_to_instrument={s: SLOT_MAP[s]["instrument"] for s in SLOT_MAP},
        mode=EnvironmentMode.METHOD_RESEARCH,
        corporate_actions=corporate_actions,
    )


def fallback_paydate_inventory(folds) -> dict:
    """评审 §7/§30：fallback pay-date 清单。"""
    total = official = 0
    fallback: list[dict] = []
    in_test: list[dict] = []
    for inst, evs in CA.items():
        for ev in evs:
            if ev.action_type != "CASH_DIVIDEND":
                continue
            total += 1
            if ev.source == "official_fund_announcement":
                official += 1
            else:
                row = {"instrument": inst, "ex_date": str(ev.ex_date.date()),
                       "settle_date": str(ev.settle_date.date()),
                       "cash_per_share": ev.cash_per_share}
                fallback.append(row)
                for f in folds:
                    if f.test_start <= ev.settle_date <= f.test_end:
                        in_test.append({**row, "fold": f.name})
                        break
    return {
        "total_cash_events": total, "official_pay_date_events": official,
        "conservative_fallback_events": len(fallback),
        "fallback_events_in_test_windows": len(in_test),
        "fallback_list": fallback, "fallback_in_test_list": in_test,
    }


def check_stop_conditions(test: dict, save_load_ok: bool) -> list[str]:
    """评审 §25 stop conditions。"""
    problems = []
    if test["nan_obs_or_reward"] > 0:
        problems.append("NaN/Inf")
    if test["negative_cash_count"] > 0:
        problems.append("negative_broker_cash")
    if not save_load_ok:
        problems.append("save_load_mismatch")
    if not np.isfinite(test.get("oos_cum_return", float("nan"))):
        problems.append("non_finite_oos_return")
    return problems


def stitched_metrics(series_list: list[dict]) -> dict:
    """评审 §22/§23：按 F1→F4 顺序拼接 test net_returns，重算整体 OOS 指标。"""
    rets = []
    turn_sum = 0.0
    n_turn = 0
    for s in series_list:
        rets.extend(s["net_returns"])
        if s.get("turnovers"):
            turn_sum += float(np.mean(s["turnovers"]))
            n_turn += 1
    nr = np.asarray(rets, dtype=float)
    mean_turn = turn_sum / n_turn if n_turn else float("nan")
    if len(nr) == 0:
        return {"n_steps": 0, "cum_return": float("nan"), "cagr": float("nan"),
                "annualized_vol": float("nan"), "sharpe": float("nan"),
                "max_drawdown": float("nan"), "calmar": float("nan"), "mean_turnover": mean_turn}
    cum = float(np.exp(np.log1p(nr).sum()) - 1.0)
    cagr = float((1.0 + cum) ** (252.0 / len(nr)) - 1.0)
    vol = float(np.std(nr) * np.sqrt(252))
    sharpe = float(np.mean(nr) / np.std(nr) * np.sqrt(252)) if np.std(nr) > 0 else float("nan")
    eq = np.exp(np.log1p(nr).cumsum())
    mdd = float((eq / np.maximum.accumulate(eq) - 1.0).min())
    calmar = float(cagr / abs(mdd)) if np.isfinite(cagr) and abs(mdd) > 1e-12 else float("nan")
    return {"n_steps": int(len(nr)), "cum_return": cum, "cagr": cagr, "annualized_vol": vol,
            "sharpe": sharpe, "max_drawdown": mdd, "calmar": calmar, "mean_turnover": mean_turn}


def seed_dispersion(values: list[float]) -> dict:
    vals = [v for v in values if np.isfinite(v)]
    if not vals:
        return {"median": float("nan"), "mean": float("nan"), "std": float("nan"),
                "min": float("nan"), "max": float("nan")}
    return {"median": float(np.median(vals)), "mean": float(np.mean(vals)),
            "std": float(np.std(vals)), "min": float(np.min(vals)), "max": float(np.max(vals))}


def main() -> None:
    adj = load_research_adj()
    opens, closes = load_execution_prices()
    runner = WalkForwardRunner(
        adj=adj, opens=opens, closes=closes, slots=SLOTS,
        slot_to_instrument={s: SLOT_MAP[s]["instrument"] for s in SLOT_MAP},
        build_env=build_env, corporate_actions=CA,
    )
    folds = runner.make_folds(n_folds=4)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    n_cal = int((adj.index >= runner.decision_start).sum())
    print(f"== Track A: decision_start={runner.decision_start.date()} calendar_rows={n_cal} "
          f"max_full_transitions={n_cal - 1} device={device} train_passes={TRAIN_PASSES} ==")

    results = {
        "manifest": {
            "gate": "4_3_SEED_PILOT", "folds": 4, "algorithms": ["TD3", "SAC", "PPO"],
            "seeds": SEEDS, "train_passes": TRAIN_PASSES, "cost": "1x",
            "rl_training_runs": len(ALGOS) * len(SEEDS) * len(folds),
            "net_arch": [256, 256],
            "track_a": {"decision_start": str(runner.decision_start.date()),
                        "calendar_rows": n_cal, "max_full_transitions": n_cal - 1},
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "packages": {
                "sb3": __import__("stable_baselines3").__version__,
                "torch": torch.__version__, "gymnasium": __import__("gymnasium").__version__,
                "pandas": pd.__version__, "numpy": np.__version__,
            },
        },
        "folds": [],
        "fallback_paydate_inventory": None,
        "baselines": {},
        "rl": {},
        "completion_matrix": [],
        "stitched_oos": {},
        "seed_dispersion": {},
        "runtime_seconds": {},
        "stop_conditions": [],
        "failed_runs": [],
    }

    for f in folds:
        decision = pd.DatetimeIndex(adj.index[(adj.index >= runner.decision_start) & (adj.index <= f.test_end)])
        results["folds"].append({
            "fold": f.name,
            "train": [str(f.train_start.date()), str(f.train_end.date()),
                      int(((decision >= f.train_start) & (decision <= f.train_end)).sum())],
            "val": [str(f.val_start.date()), str(f.val_end.date()),
                    int(((decision >= f.val_start) & (decision <= f.val_end)).sum())],
            "test": [str(f.test_start.date()), str(f.test_end.date()),
                     int(((decision >= f.test_start) & (decision <= f.test_end)).sum())],
        })
    print("\n== folds ==")
    for fr in results["folds"]:
        print(f"  {fr['fold']}: train {fr['train'][2]}  val {fr['val'][2]}  test {fr['test'][2]}  "
              f"[{fr['train'][0]}→{fr['test'][1]}]")

    results["fallback_paydate_inventory"] = fallback_paydate_inventory(folds)
    fi = results["fallback_paydate_inventory"]
    print(f"\n== fallback inventory: total_cash={fi['total_cash_events']} "
          f"official={fi['official_pay_date_events']} fallback={fi['conservative_fallback_events']} "
          f"in_test={fi['fallback_events_in_test_windows']} ==")

    # --- baselines ---
    print("\n== baselines ==")
    for name, fac in BASELINES:
        t0 = time.time()
        rows = []
        for f in folds:
            m = runner.run_fold_baseline(f, fac)
            rows.append({"fold": f.name, **{k: m["test"][k] for k in (
                "oos_cum_return", "cagr", "sharpe", "max_drawdown", "mean_turnover",
                "total_cost", "cost_over_initial_value", "nan_obs_or_reward", "n_eval_steps")}})
        results["baselines"][name] = {"per_fold": rows, "seconds": round(time.time() - t0, 1)}
        print(f"  {name:16s} {time.time()-t0:6.1f}s  " +
              " ".join(f"{r['fold']}={r['oos_cum_return']:.3f}" for r in rows))

    # --- RL（评审 §26：seed 42 先行）---
    series_store: dict[tuple, dict] = {}  # (algo, seed, fold) -> test.series
    completed = 0
    target = len(SEEDS) * len(ALGOS) * len(folds)
    for seed in SEEDS:
        seed_ok = True
        t_seed0 = time.time()
        for algo_name, algo_cls, dev in ALGOS:
            results["rl"].setdefault(algo_name, {})[seed] = {}
            for f in folds:
                key = f"{algo_name}|{seed}|{f.name}"
                print(f"\n[{key}] starting...", flush=True)
                t0 = time.time()
                try:
                    run = runner.run_fold_rl(f, algo_cls, seed=seed, train_passes=TRAIN_PASSES,
                                             net=(256, 256), device=dev)
                except Exception as exc:  # noqa: BLE001
                    results["failed_runs"].append({"key": key, "error": str(exc)[:300]})
                    results["completion_matrix"].append(
                        {"algo": algo_name, "seed": seed, "fold": f.name, "pass": False,
                         "reason": f"exception: {str(exc)[:120]}"})
                    seed_ok = False
                    continue
                dt = time.time() - t0
                test = run["test"]
                problems = check_stop_conditions(test, run["save_load_deterministic_identical"])
                results["completion_matrix"].append(
                    {"algo": algo_name, "seed": seed, "fold": f.name, "pass": len(problems) == 0,
                     "reason": ";".join(problems) if problems else "ok"})
                results["rl"][algo_name][seed][f.name] = {
                    "train_decision_steps": run["train_decision_steps"],
                    "train_passes": run["train_passes"],
                    "total_timesteps": run["total_timesteps"],
                    "save_load_deterministic_identical": run["save_load_deterministic_identical"],
                    "train_seconds": round(dt, 1),
                    "test": {k: test[k] for k in TEST_FIELDS},
                }
                series_store[(algo_name, seed, f.name)] = test["series"]
                if problems:
                    seed_ok = False
                    results["stop_conditions"].append({"key": key, "problems": problems})
                completed += 1
                print(f"[{key}] done {dt:6.1f}s  test_cum={test['oos_cum_return']:.4f} "
                      f"sharpe={test['sharpe']:.2f} mdd={test['max_drawdown']:.3f} "
                      f"nan={test['nan_obs_or_reward']} neg_cash={test['negative_cash_count']} "
                      f"save_load={run['save_load_deterministic_identical']}", flush=True)
        results["runtime_seconds"][str(seed)] = round(time.time() - t_seed0, 1)
        print(f"\n== seed {seed} done in {results['runtime_seconds'][str(seed)]:.1f}s "
              f"(all_ok={seed_ok}) ==", flush=True)
        if not seed_ok:
            results["stop_conditions"].append(
                {"seed": seed, "note": "stop conditions violated in this seed group"})
            print(f"STOP: seed {seed} group has failures — not running remaining seeds.", flush=True)
            break

    # --- stitched OOS per algo×seed + seed dispersion（评审 §21-§23）---
    for algo_name, _, _ in ALGOS:
        results["stitched_oos"][algo_name] = {}
        for seed in SEEDS:
            if str(seed) not in results["runtime_seconds"]:
                continue  # 未跑（早停）
            series_list = [series_store[(algo_name, seed, f.name)] for f in folds]
            st = stitched_metrics(series_list)
            results["stitched_oos"][algo_name][seed] = st
    for algo_name, _, _ in ALGOS:
        st = results["stitched_oos"].get(algo_name, {})
        disp = {
            "OOS_cagr": seed_dispersion([v["cagr"] for v in st.values()]),
            "OOS_sharpe": seed_dispersion([v["sharpe"] for v in st.values()]),
            "OOS_maxdd": seed_dispersion([v["max_drawdown"] for v in st.values()]),
            "mean_turnover": seed_dispersion([v["mean_turnover"] for v in st.values()]),
        }
        results["seed_dispersion"][algo_name] = disp
        print(f"\n== {algo_name} seed dispersion ==")
        for k, v in disp.items():
            print(f"  {k:14s} median={v['median']:.4f} mean={v['mean']:.4f} "
                  f"std={v['std']:.4f} min={v['min']:.4f} max={v['max']:.4f}")

    # --- 写盘 ---
    out = ROOT / "runs" / "gate4_3seed_pilot_results.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    raw_path = ROOT / "runs" / "gate4_3seed_pilot_raw.json"
    raw = {"series": {f"{a}|{s}|{fname}": series_store[(a, s, fname)]
                      for (a, s, fname) in series_store}}
    raw_path.write_text(json.dumps(raw, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\nresults -> {out}")
    print(f"raw series -> {raw_path}  (completed={completed}/{target})")
    print("STITCHED OOS:")
    for algo_name, _, _ in ALGOS:
        for seed in SEEDS:
            if str(seed) in results["runtime_seconds"]:
                st = results["stitched_oos"][algo_name][seed]
                print(f"  {algo_name:4s} seed={seed:5d}  cum={st['cum_return']:.4f} "
                      f"cagr={st['cagr']:.4f} sharpe={st['sharpe']:.4f} mdd={st['max_drawdown']:.4f}")


if __name__ == "__main__":
    main()
