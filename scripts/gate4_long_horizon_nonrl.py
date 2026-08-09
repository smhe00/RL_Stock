"""GATE_4_LONG_HORIZON_NON_RL — L1 真实工具长区间非-RL horse race（评审授权 RUN）。

label = REAL_INSTRUMENT_LONG_HORIZON_DIAGNOSTIC（robustness diagnostic，非 pristine OOS——
历史数据已被研究观察）。

单段连续持有：决策 2022-06-09..2026-08-06（1011），执行 2022-06-10..2026-08-07（1011）。
6 方法（canonical 参数原样复用，不得事后增删/tuning）：
  HS300_ref（研究复权无成本参考，独立列）/ EqualWeight / MaximumDiversification(120,0.5) /
  MinimumVariance(120,0.5) / RiskParity_IVOL(60) / Momentum_12_1(252,21)

评审 hard guards（GATE_4_LONG_HORIZON_NON_RL_PREP_REVIEWER_RESPONSE.md）：
  #1 窗口 parity fail-closed（derive-then-assert，差异 → blocker/revision）
  #2 不用旧 475-day stitched mask 决定评估日（仅历史对比出现在最终报告）
  #3 方法集不可变，无 lookback/shrinkage tuning
  #4 canonical 参数匹配当前源码（long_horizon_contract.CANONICAL_PARAMS）
  #5 因果数据（≤T）；T 决策 → T+1 执行
  #6 成本 = 当前项目 1x MainlandETFCostModel 简化（非完整跨市场/Southbound 费率模型），显式标注
  #7 HS300 为研究复权无成本参考，独立于可执行净策略返回
  #8 子期报告描述性：日历年度必报；2022H2-2023 vs 2024-2026 = 冻结前描述性划分
  #9 无数据编造/backfill（L1 真实上市期数据；pre-launch backfill 禁止）
  #10 tests/test_long_horizon_nonrl.py + --check 通过后再完整执行；failed invariant = stop

RL 重训/调参/对比在本研究所有代码路径与输出表中缺席（本文件无任何 RL 导入）。
L2（2015-2026 proxy）不执行，需单独评审提案。

--check：只验证契约/方法集/参数/无 RL/无旧 mask，不跑完整 rollout。
输出：artifacts/gate4_long_horizon_nonrl_results.json + _raw.json
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from china_etf.contracts import EnvironmentMode  # noqa: E402
from china_etf.cost.mainland import MainlandETFCostModel  # noqa: E402
from china_etf.data.corporate_actions import load_corporate_actions  # noqa: E402
from china_etf.data.loader import SLOT_MAP, load_execution_prices, load_research_adj  # noqa: E402
from china_etf.environment.gym_wrapper import ChinaETFGymEnv  # noqa: E402
from china_etf.environment.portfolio_env import ChinaETFPortfolioEnv  # noqa: E402
from china_etf.evaluation.baselines import (  # noqa: E402
    equal_weight_policy, maximum_diversification_policy,
    minimum_variance_policy, momentum_policy, risk_parity_policy,
)
from china_etf.evaluation.long_horizon_contract import (  # noqa: E402
    CANONICAL_PARAMS, FROZEN_CONTRACT, METHOD_NAMES_FROZEN,
    check_contract, derive_window,
)
from china_etf.evaluation.rollout import roll_out  # noqa: E402
from china_etf.execution.broker.mock import MockBroker  # noqa: E402
from china_etf.execution.order_generator import OrderGenerator  # noqa: E402
from china_etf.execution.premium import PremiumGuard  # noqa: E402
from china_etf.execution.tradability import TradabilityMask  # noqa: E402

SLOTS = list(SLOT_MAP.keys())
CA = load_corporate_actions()

# 可执行策略（HS300_ref 为研究复权参考，不走 env；见 references 段）
METHODS = ["EqualWeight", "MaximumDiversification", "MinimumVariance",
           "RiskParity_IVOL", "Momentum_12_1"]

COST_MODEL_LABEL = ("current project 1x MainlandETFCostModel simplification; "
                    "NOT a claim of fully realistic cross-market/Southbound fee modeling")
HS300_LABEL = ("research-adjusted no-cost reference (CN_LARGE total-return); "
               "separate from executable net strategy returns")
SUB_PERIOD_LABEL = ("calendar-year breakdown required; 2022H2-2023 vs 2024-2026 = "
                    "pre-frozen descriptive phase split, not an objective market-regime classifier")


def build_env(adj, opens, closes, corporate_actions=None) -> ChinaETFPortfolioEnv:
    """与 corrected 执行路径完全一致的 env 构造（1x Mainland 成本 + RiskOverlay + CA）。"""
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


def _make_policy(name: str, env):
    """canonical 策略工厂（参数冻结自 contract.CANONICAL_PARAMS）。"""
    if name == "EqualWeight":
        return equal_weight_policy(env)
    if name == "MaximumDiversification":
        p = CANONICAL_PARAMS[name]
        return maximum_diversification_policy(env, lookback=p["lookback"], shrinkage=p["shrinkage"])
    if name == "MinimumVariance":
        p = CANONICAL_PARAMS[name]
        return minimum_variance_policy(env, lookback=p["lookback"], shrinkage=p["shrinkage"])
    if name == "RiskParity_IVOL":
        p = CANONICAL_PARAMS[name]
        return risk_parity_policy(env, lookback=p["lookback"])
    if name == "Momentum_12_1":
        p = CANONICAL_PARAMS[name]
        return momentum_policy(env, lookback=p["lookback"], skip=p["skip"])
    raise KeyError(name)


def compute_metrics(nr, exec_dates) -> dict:
    """完整指标表（cum / active-day ann / 日历 CAGR / vol / Sharpe / Sortino / MaxDD / Calmar /
    worst year / worst rolling 12m）。"""
    nr = np.asarray(nr, dtype=float)
    dates = pd.DatetimeIndex([pd.Timestamp(d) for d in exec_dates])
    n = len(nr)
    cum = float(np.exp(np.log1p(nr).sum()) - 1.0)
    active_ann = float((1.0 + cum) ** (252.0 / n) - 1.0)
    elapsed_days = int((dates[-1] - dates[0]).days) + 1
    cal_cagr = float((1.0 + cum) ** (365.25 / elapsed_days) - 1.0) if elapsed_days > 0 else float("nan")
    vol = float(np.std(nr) * np.sqrt(252))
    sharpe = float(np.mean(nr) / np.std(nr) * np.sqrt(252)) if np.std(nr) > 0 else float("nan")
    downside = nr[nr < 0]
    sortino = (float(np.mean(nr) / np.std(downside) * np.sqrt(252))
               if len(downside) > 1 and np.std(downside) > 0 else float("nan"))
    eq = np.exp(np.log1p(nr).cumsum())
    mdd = float((eq / np.maximum.accumulate(eq) - 1.0).min())
    calmar = float(active_ann / abs(mdd)) if np.isfinite(active_ann) and abs(mdd) > 1e-12 else float("nan")
    s = pd.Series(nr, index=dates)
    yearly = {}
    for yr, grp in s.groupby(s.index.year):
        yearly[int(yr)] = float(np.exp(np.log1p(grp.to_numpy()).sum()) - 1.0)
    worst_year = int(min(yearly, key=yearly.get)) if yearly else None
    roll = np.array([float(np.exp(np.log1p(nr[i - 251:i + 1]).sum()) - 1.0) for i in range(251, n)])
    worst_12m = float(roll.min()) if len(roll) else float("nan")
    return {
        "n_steps": int(n),
        "cum_return": cum,
        "active_day_annualized_return": active_ann,
        "calendar_cagr": cal_cagr,
        "annualized_vol": vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": mdd,
        "calmar": calmar,
        "worst_calendar_year": worst_year,
        "worst_calendar_year_return": float(min(yearly.values())) if yearly else float("nan"),
        "worst_rolling_12m_return": worst_12m,
    }


def _seg_metrics(nr):
    nr = np.asarray(nr, dtype=float)
    if len(nr) == 0:
        return {"n_days": 0, "cum_return": float("nan"), "sharpe": float("nan"), "max_drawdown": float("nan")}
    cum = float(np.exp(np.log1p(nr).sum()) - 1.0)
    sharpe = float(np.mean(nr) / np.std(nr) * np.sqrt(252)) if np.std(nr) > 0 else float("nan")
    eq = np.exp(np.log1p(nr).cumsum())
    mdd = float((eq / np.maximum.accumulate(eq) - 1.0).min())
    return {"n_days": int(len(nr)), "cum_return": cum, "sharpe": sharpe, "max_drawdown": mdd}


def sub_period_metrics(nr, exec_dates) -> dict:
    """年度 + 描述性阶段（2022H2-2023 弱股 / 2024-2026 强股），每段 Sharpe/MaxDD。"""
    dates = pd.DatetimeIndex([pd.Timestamp(d) for d in exec_dates])
    s = pd.Series(np.asarray(nr, dtype=float), index=dates)
    years = {}
    for yr, grp in s.groupby(s.index.year):
        years[int(yr)] = _seg_metrics(grp.to_numpy())
    phase_a = s[s.index < pd.Timestamp("2024-01-01")]
    phase_b = s[s.index >= pd.Timestamp("2024-01-01")]
    return {
        "calendar_years": years,
        "phases": {
            "2022H2-2023_weak_equity": _seg_metrics(phase_a.to_numpy()),
            "2024-2026_strong_equity": _seg_metrics(phase_b.to_numpy()),
            "split_label": SUB_PERIOD_LABEL,
        },
    }


def hs300_reference_series(adj: pd.DataFrame, exec_dates) -> np.ndarray:
    """HS300 研究复权参考：CN_LARGE total-return pct_change 对齐到同一执行日。"""
    pc = adj["CN_LARGE"].pct_change()
    return np.asarray(pc.reindex(pd.DatetimeIndex(exec_dates)).to_numpy(), dtype=float)


def run_single_segment(name: str, adj, opens, closes, decision_start, eval_start) -> dict:
    """单段连续持有 rollout：reset_at=decision_start（决策日），记录 t_next >= eval_start。"""
    env = build_env(adj, opens, closes, corporate_actions=CA)
    gym = ChinaETFGymEnv(env)
    gym.set_market_scaler(np.zeros(gym._market_dim, dtype=np.float32),
                          np.ones(gym._market_dim, dtype=np.float32))
    return roll_out(env, gym, _make_policy(name, env), eval_start, SLOTS, reset_at=decision_start)


def _load_old_475_comparison() -> dict:
    """旧 475-day horse race 指标（仅历史对比；不用于决定评估日）。"""
    path = ROOT / "artifacts" / "gate4_non_rl_horse_race_results.json"
    if not path.exists():
        return {"note": "old 475-day horse-race artifact not found", "methods": {}}
    d = json.loads(path.read_text(encoding="utf-8"))
    table = d.get("horse_race_table", {})
    out = {}
    keys = ("cum_return", "active_day_annualized_return", "sharpe", "sortino",
            "max_drawdown", "calmar", "mean_turnover")
    for name in ("EqualWeight", "MaximumDiversification", "MinimumVariance",
                 "RiskParity_IVOL", "Momentum_12_1"):
        if name in table:
            out[name] = {k: table[name][k] for k in keys if k in table[name]}
    return {
        "note": "old 475-day stitched (2023-11-24..2026-08-07) metrics — historical comparison only",
        "methods": out,
    }


def _forbidden_tokens() -> list[str]:
    """自检 token。拼接构造，避免本函数内出现连续字面量命中自身。"""
    return [
        "exact" + "_test_mask",
        "RESEARCH" + "_BENCHMARK_TEST",
        "stable" + "_baselines3",
        "P" + "PO",
        "S" + "AC",
        "T" + "D3",
    ]


def _run_check() -> None:
    """--check：只验证契约/方法集/无 RL/无旧 mask，不跑完整 rollout。"""
    adj = load_research_adj()
    opens, closes = load_execution_prices()
    w = check_contract(adj)  # guard #1 fail-closed
    print("== L1 --check ==")
    print("window (derived from actual loaded data):")
    for k, v in w.items():
        print(f"  {k}: {v.date() if hasattr(v, 'date') else v}")
    print(f"contract parity: ok (label={FROZEN_CONTRACT['label']})")
    src = Path(__file__).read_text(encoding="utf-8")
    for tok in _forbidden_tokens():
        if tok in src:
            raise SystemExit(f"--check FAIL: forbidden token '{tok}' present in runner source")
    assert set(METHODS) == set(METHOD_NAMES_FROZEN) - {"HS300_ref"}, \
        "executable METHODS must equal frozen 6-method set minus the reference"
    assert len(METHOD_NAMES_FROZEN) == 6
    print(f"method set: ok -> {METHOD_NAMES_FROZEN}")
    print(f"canonical params: {CANONICAL_PARAMS}")
    env = build_env(adj, opens, closes, corporate_actions=CA)
    i = env.calendar.index(w["decision_start"])
    assert i >= env._warmup_index, "decision_start before env warmup"
    print(f"env warmup <= decision_start: ok (warmup_index={env._warmup_index} "
          f"{env.calendar[env._warmup_index].date()}, decision_start_index={i})")
    print("--check PASSED")


def main() -> None:
    if "--check" in sys.argv:
        _run_check()
        return

    adj = load_research_adj()
    opens, closes = load_execution_prices()
    w = check_contract(adj)  # guard #1 fail-closed
    exec_idx = (adj.index >= w["first_execution"]) & (adj.index <= w["last_execution"])
    exec_dates = adj.index[exec_idx]
    exec_dates_str = [str(d.date()) for d in exec_dates]
    assert len(exec_dates_str) == FROZEN_CONTRACT["n_execution_dates"] == 1011

    results = {
        "manifest": {
            "gate": "4_LONG_HORIZON_NON_RL",
            "label": FROZEN_CONTRACT["label"],
            "window": {
                "decision_start": str(w["decision_start"].date()),
                "first_execution": str(w["first_execution"].date()),
                "last_decision": str(w["last_decision"].date()),
                "last_execution": str(w["last_execution"].date()),
                "n_decision_days": w["n_decision_days"],
                "n_execution_dates": w["n_execution_dates"],
                "first_all_finite": str(w["first_all_finite"].date()),
                "warmup_lookback": 252,
                "contract_parity": "ok",
            },
            "methods_frozen": METHOD_NAMES_FROZEN,
            "canonical_params": CANONICAL_PARAMS,
            "semantics": ("T->T+1 causal; 1x MainlandETFCostModel; RiskOverlay; corporate actions; "
                          "continuous single-segment (reset at decision_start, no cross-segment reset)"),
            "cost_model_label": COST_MODEL_LABEL,
            "hs300_label": HS300_LABEL,
            "sub_period_label": SUB_PERIOD_LABEL,
            "no_rl": True,
            "no_l2": True,
            "no_old_475_mask_as_eval_dates": True,
            "data_provenance": ("existing research-adjusted adj + execution prices + CA; "
                                "no re-fetch/repair needed in L1; no pre-launch backfill"),
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "methods": {},
        "references": {},
        "old_475_comparison": _load_old_475_comparison(),
        "no_go_threshold": None,  # 禁止事后发明阈值
    }

    import china_etf.evaluation.baselines as bl
    _orig_cov = bl._cov_window
    fallback = {"n": 0}
    series_store: dict[str, dict] = {}

    def _counting(r, t, lb, sh, n):
        res = _orig_cov(r, t, lb, sh, n)
        if res is None:
            fallback["n"] += 1
        return res

    bl._cov_window = _counting
    try:
        for name in METHODS:
            t0 = time.time()
            m = run_single_segment(name, adj, opens, closes, w["decision_start"], w["first_execution"])
            # guard invariants (failed invariant = stop condition)
            assert m["n_eval_steps"] == FROZEN_CONTRACT["n_execution_dates"], \
                f"{name}: n_eval {m['n_eval_steps']} != 1011"
            assert m["series"]["execution_dates"] == exec_dates_str, \
                f"{name}: execution dates != frozen window"
            assert m["nan_obs_or_reward"] == 0, f"{name}: NaN/Inf present"
            assert m["negative_cash_count"] == 0, f"{name}: negative broker cash"
            nr = np.asarray(m["series"]["net_returns"], dtype=float)
            base = compute_metrics(nr, exec_dates_str)
            mets = {
                **base,
                "mean_turnover": m["mean_turnover"],
                "total_turnover": m["total_turnover"],
                "actual_traded_notional": m["actual_traded_notional"],
                "total_cost": m["total_cost"],
                "total_cost_over_traded_notional": m["total_cost_over_traded_notional"],
                "cost_over_initial_value": m["cost_over_initial_value"],
                "mean_active_assets": m["mean_active_assets"],
                "max_single_asset_weight": m["max_single_asset_weight"],
                "mean_hhi": m["mean_hhi"],
                "risk_overlay_intervention_rate": m["risk_overlay_intervention_rate"],
                "overlay_mean_l1_raw_to_post": m["risk_overlay_mean_l1_raw_to_post"],
                "fallback_count": fallback["n"],
            }
            results["methods"][name] = {
                "metrics": {k: (round(v, 6) if isinstance(v, float) else v) for k, v in mets.items()},
                "sub_periods": sub_period_metrics(nr, exec_dates_str),
                "rollout_audit": {
                    "n_eval_steps": m["n_eval_steps"],
                    "execution_dates_match_contract": bool(m["series"]["execution_dates"] == exec_dates_str),
                    "first_execution": m["series"]["execution_dates"][0],
                    "last_execution": m["series"]["execution_dates"][-1],
                    "nan_obs_or_reward": m["nan_obs_or_reward"],
                    "negative_cash_count": m["negative_cash_count"],
                },
                "seconds": round(time.time() - t0, 1),
            }
            series_store[name] = m["series"]
            print(f"{name:24s} cum={mets['cum_return']:+.4f} "
                  f"ann={mets['active_day_annualized_return']:+.4f} sharpe={mets['sharpe']:.3f} "
                  f"mdd={mets['max_drawdown']:.4f} calmar={mets['calmar']:.3f} "
                  f"fallback={fallback['n']}", flush=True)
            fallback["n"] = 0
    finally:
        bl._cov_window = _orig_cov

    # HS300 研究复权参考（无成本，独立段；guard #7）
    ref_nr = hs300_reference_series(adj, exec_dates)
    ref_metrics = compute_metrics(ref_nr, exec_dates_str)
    results["references"]["HS300_ref"] = {
        "metrics": {k: (round(v, 6) if isinstance(v, float) else v) for k, v in ref_metrics.items()},
        "sub_periods": sub_period_metrics(ref_nr, exec_dates_str),
        "note": HS300_LABEL,
        "semantics": ("no cost / no overlay / no accounting — research-adjusted CN_LARGE TR "
                      "aligned to the same 1011 execution dates"),
    }
    print(f"{'HS300_ref (ref)':24s} cum={ref_metrics['cum_return']:+.4f} "
          f"ann={ref_metrics['active_day_annualized_return']:+.4f} sharpe={ref_metrics['sharpe']:.3f} "
          f"mdd={ref_metrics['max_drawdown']:.4f}")

    try:
        results["manifest"]["commit"] = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT).decode().strip()
    except Exception:  # noqa: BLE001
        results["manifest"]["commit"] = None

    art = ROOT / "artifacts"
    art.mkdir(parents=True, exist_ok=True)
    out = art / "gate4_long_horizon_nonrl_results.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    raw = art / "gate4_long_horizon_nonrl_raw.json"
    raw.write_text(json.dumps(
        {"methods": {n: {"series": series_store[n]} for n in series_store}},
        indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
