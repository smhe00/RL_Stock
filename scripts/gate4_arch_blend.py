"""POST_L2_DETERMINISTIC_ARCHITECTURE_RUN — MaxDiv Core × Momentum Engine 静态混合架构（评审授权 RUN）。

冻结契约（POST_L2_DETERMINISTIC_ARCHITECTURE_PREP + CORRECTION）：
  候选：C0=100% MaxDiv, C1=100% Momentum, C2=75/25, C3=50/50, C4=25/75
  混合语义：w_blend_raw(T) = alpha*w_maxdiv(T) + (1-alpha)*w_mom(T)
            w_final(T) = RiskOverlayV0(w_blend_raw(T))
  成本/换手在最终可执行权重路径计算（非平均各自独立）
  父策略不可变：MaxDiv 120/0.5 project-constrained；Momentum 252/21 positive-score
  同一 11 槽位、2800 区间 Track-C 面板、signal/return 分离、CNY HK FX、stress regimes
  C0/C1 确定性重建 + 断言与 gen3 metrics 精确 parity（失败 = STOP）
  成功准则 R1-R6：R1 cagr-C0>=0.005；R2 mdd>=C0_mdd-0.05；R3 Sharpe>=0.80 & Calmar>=0.40；
                 R4 cost_cum_delta>= -0.03；R5 非 Pareto 支配；R6 terminal-wealth 仅当 R2/R3
  RL 算法缺席；无 dense/dynamic alpha；QMT live 禁止

--check：只验证契约/parity/方法集/无 RL，不跑完整 RUN。
输出：artifacts/gate4_arch_blend_results.json + _raw.json
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# 复用 L2 runner（build_panel/ProxyPolicy/_apply_overlay/compute_metrics/sub_periods）
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location("l2_proxy", ROOT / "scripts" / "gate4_long_horizon_proxy.py")
_l2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_l2)

FROZEN = {
    "label": "POST_L2_DETERMINISTIC_ARCHITECTURE",
    "decision_start": "2015-01-28",
    "last_decision": "2026-08-06",
    "n_intervals": 2800,
}

CANDIDATES = [
    ("C0_MaxDiv_100", 1.00),
    ("C1_Momentum_100", 0.00),
    ("C2_75_25", 0.75),
    ("C3_50_50", 0.50),
    ("C4_25_75", 0.25),
]

# gen3 精确 C0/C1 metrics（parity 断言基准，评审冻结）
GEN3_C0 = {
    "calendar_cagr": 0.059496, "max_drawdown": -0.103874, "sharpe": 1.024270,
    "cum_return": 0.946411, "sortino": 1.280387, "calmar": 0.594678,
    "annualized_vol": 0.060305, "active_day_annualized_return": 0.061772,
    "worst_rolling_12m_return": -0.090676,
}
GEN3_C1 = {
    "calendar_cagr": 0.083909, "max_drawdown": -0.442797, "sharpe": 0.571106,
    "cum_return": 1.530719, "sortino": 0.638823, "calmar": 0.196831,
    "annualized_vol": 0.172710, "active_day_annualized_return": 0.087156,
    "worst_rolling_12m_return": -0.352144,
}

C0_METRICS = GEN3_C0  # 成功准则基线（C0 = 100% MaxDiv）
C0_cagr = C0_METRICS["calendar_cagr"]
C0_mdd = C0_METRICS["max_drawdown"]

COST_BPS = 0.00035  # 1x Mainland 近似（与 L2 一致）


def build_panels():
    signal_panel, return_levels, cal = _l2.build_panel()
    ds = pd.Timestamp(FROZEN["decision_start"])
    ds_i = cal.get_loc(ds)
    last_dec_i = len(cal) - 2
    n = (last_dec_i + 1) - ds_i
    assert n == FROZEN["n_intervals"], f"fail-closed: n_intervals {n} != 2800"
    decision_dates = cal[ds_i:last_dec_i + 1]
    exec_dates = cal[ds_i + 1:last_dec_i + 2]
    ret_full = return_levels.pct_change()
    ret_panel = ret_full.reindex(exec_dates)
    return signal_panel, ret_panel, decision_dates, exec_dates


def run_candidate(alpha: float, signal_panel, ret_panel, decision_dates, exec_dates) -> dict:
    pol_maxdiv = _l2.ProxyPolicy(signal_panel, "MaximumDiversification")
    pol_mom = _l2.ProxyPolicy(signal_panel, "Momentum_12_1")
    W_raw_all, W_all, turn = [], [], []
    prev = None
    pre_viol = post_viol = 0
    caps = np.full(len(_l2.SLOT_ORDER), 0.25)
    growth_idx = [i for i, s in enumerate(_l2.SLOT_ORDER) if s in ("CHINEXT", "STAR")]
    for t in decision_dates:
        w_maxdiv = np.clip(np.asarray(pol_maxdiv(t), dtype=float), 0.0, None)
        w_maxdiv = w_maxdiv / w_maxdiv.sum()
        w_mom = np.clip(np.asarray(pol_mom(t), dtype=float), 0.0, None)
        w_mom = w_mom / w_mom.sum()
        w_blend_raw = alpha * w_maxdiv + (1.0 - alpha) * w_mom
        w_final = _l2._apply_overlay(w_blend_raw, _l2.SLOT_ORDER)
        W_raw_all.append(w_blend_raw)
        W_all.append(w_final)
        if prev is not None:
            turn.append(float(np.abs(w_final - prev).sum()))
        prev = w_final
        pre_viol += int((w_blend_raw > caps + 1e-6).any() or (w_blend_raw[growth_idx].sum() > 0.50 + 1e-6))
        post_viol += int((w_final > caps + 1e-6).any() or (w_final[growth_idx].sum() > 0.50 + 1e-6))
    W_raw = np.asarray(W_raw_all)
    W = np.asarray(W_all)
    strat = np.asarray([W[i] @ ret_panel.iloc[i].to_numpy() for i in range(len(decision_dates))])
    exec_str = [str(d.date()) for d in exec_dates]
    mets = _l2.compute_metrics(strat, exec_str)
    # 1x 成本敏感性（最终可执行路径）
    per_period_cost = np.abs(np.diff(W, axis=0)).sum(axis=1) * COST_BPS
    net_strat = np.asarray([strat[i] - (per_period_cost[i] if i < len(per_period_cost) else 0.0)
                            for i in range(len(decision_dates))])
    m_net = _l2.compute_metrics(net_strat, exec_str)
    total_turn = float(np.abs(np.diff(W, axis=0)).sum())
    return {
        "metrics": {k: (round(v, 6) if isinstance(v, float) else v) for k, v in mets.items()},
        "sub_periods": _l2.sub_periods(strat, exec_str),
        "mean_turnover": float(np.mean(turn)) if turn else float("nan"),
        "total_turnover": total_turn,
        "mean_hhi": float((W ** 2).sum(axis=1).mean()),
        "max_single_asset_weight": float(W.max()),
        "avg_weight_by_slot": {s: float(W[:, i].mean()) for i, s in enumerate(_l2.SLOT_ORDER)},
        "max_weight_by_slot": {s: float(W[:, i].max()) for i, s in enumerate(_l2.SLOT_ORDER)},
        "overlay_violations": {"pre_overlay_count": int(pre_viol), "post_overlay_count": int(post_viol)},
        "cost_sensitivity": {
            "cum_return_no_cost": round(mets["cum_return"], 6),
            "cum_return_net_1x": round(m_net["cum_return"], 6),
            "cost_cum_delta": round(m_net["cum_return"] - mets["cum_return"], 6),
            "est_total_cost_over_initial": round(total_turn * COST_BPS, 6),
            "active_day_annualized_net_1x": round(m_net["active_day_annualized_return"], 6),
        },
        "weights_post_overlay": W.tolist(),
        "net_returns": [float(x) for x in strat],
    }


def evaluate_criteria(metrics: dict, cost: dict) -> dict:
    """R1-R6 ex-ante 成功准则（冻结于 PREP）。"""
    cagr = metrics["calendar_cagr"]
    mdd = metrics["max_drawdown"]
    sharpe = metrics["sharpe"]
    calmar = metrics["calmar"]
    cost_delta = cost["cost_cum_delta"]
    r1 = bool(cagr - C0_cagr >= 0.005)
    r2 = bool(mdd >= C0_mdd - 0.05)
    r3 = bool(sharpe >= 0.80 and calmar >= 0.40)
    r4 = bool(cost_delta >= -0.03)
    return {"R1_cagr_gain_ge_0.5pct": r1, "R2_maxdd_deg_le_5pct": r2,
            "R3_sharpe_ge_0.80_and_calmar_ge_0.40": r3, "R4_cost_delta_ge_-3pct": r4,
            "passes_R1_R4": bool(r1 and r2 and r3 and r4)}


def main() -> None:
    if "--check" in sys.argv:
        _run_check()
        return
    signal_panel, ret_panel, decision_dates, exec_dates = build_panels()
    results = {
        "manifest": {
            "gate": "POST_L2_DETERMINISTIC_ARCHITECTURE",
            "label": FROZEN["label"],
            "candidates": [c for c, _ in CANDIDATES],
            "blend_semantics": "w_final = RiskOverlayV0(alpha*w_maxdiv + (1-alpha)*w_mom); cost on final executable path",
            "success_criteria": {"C0_cagr": C0_cagr, "C0_mdd": C0_mdd,
                                 "R1": "cagr-C0>=0.005", "R2": "mdd>=C0_mdd-0.05",
                                 "R3": "Sharpe>=0.80 & Calmar>=0.40", "R4": "cost_delta>=-0.03",
                                 "R5": "non-Pareto-dominated", "R6": "terminal-wealth only if R2/R3"},
            "no_rl": True,
            "no_dense_search": True,
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "candidates": {},
        "parity": {},
        "no_go_threshold": None,
    }

    # C0/C1 parity 断言（gen3 精确 metrics，评审冻结；失败 = STOP）
    for label, alpha in CANDIDATES:
        r = run_candidate(alpha, signal_panel, ret_panel, decision_dates, exec_dates)
        m = r["metrics"]
        results["candidates"][label] = r
        if label == "C0_MaxDiv_100":
            parity_keys = ["calendar_cagr", "max_drawdown", "sharpe", "cum_return"]
            diffs = {k: round(m[k] - GEN3_C0[k], 8) for k in parity_keys}
            results["parity"]["C0_vs_gen3"] = {"diffs": diffs,
                                               "pass": all(abs(v) < 1e-4 for v in diffs.values())}
            if not results["parity"]["C0_vs_gen3"]["pass"]:
                raise SystemExit("C0 parity to gen3 FAILED — STOP (do not use a new parent baseline)")
        elif label == "C1_Momentum_100":
            parity_keys = ["calendar_cagr", "max_drawdown", "sharpe", "cum_return"]
            diffs = {k: round(m[k] - GEN3_C1[k], 8) for k in parity_keys}
            results["parity"]["C1_vs_gen3"] = {"diffs": diffs,
                                               "pass": all(abs(v) < 1e-4 for v in diffs.values())}
            if not results["parity"]["C1_vs_gen3"]["pass"]:
                raise SystemExit("C1 parity to gen3 FAILED — STOP")
        # 成功准则评估（对 C2-C4；C0/C1 为对照）
        crit = evaluate_criteria(m, r["cost_sensitivity"])
        results["candidates"][label]["success_criteria"] = crit
        print(f"{label:18s} cum={m['cum_return']:+.4f} cagr={m['calendar_cagr']:+.4f} "
              f"sharpe={m['sharpe']:.3f} mdd={m['max_drawdown']:.4f} calmar={m['calmar']:.3f} "
              f"postV={r['overlay_violations']['post_overlay_count']} "
              f"R1={crit['R1_cagr_gain_ge_0.5pct']} R2={crit['R2_maxdd_deg_le_5pct']} "
              f"R3={crit['R3_sharpe_ge_0.80_and_calmar_ge_0.40']} R4={crit['R4_cost_delta_ge_-3pct']}", flush=True)

    # Pareto 检查（R5）：C2-C4 vs C0/C1 在 cum/cagr/Sharpe/MaxDD
    def dominates(a, b):
        """a 支配 b iff a 在全部维度不劣且至少一项更优。"""
        dims = [("cum_return", True), ("calendar_cagr", True), ("sharpe", True), ("max_drawdown", False)]
        le_all = True
        for key, higher_better in dims:
            av, bv = a[key], b[key]
            if higher_better:
                if not (av >= bv - 1e-9):
                    le_all = False
            else:
                if not (av <= bv + 1e-9):
                    le_all = False
        strict_any = any(
            (a[k] > b[k] + 1e-9) if hb else (a[k] < b[k] - 1e-9)
            for k, hb in dims)
        return le_all and strict_any

    parents = {lbl: results["candidates"][lbl]["metrics"] for lbl in ("C0_MaxDiv_100", "C1_Momentum_100")}
    for lbl in ("C2_75_25", "C3_50_50", "C4_25_75"):
        m = results["candidates"][lbl]["metrics"]
        dominated_by = [pl for pl, pm in parents.items() if dominates(pm, m)]
        results["candidates"][lbl]["pareto_dominated_by"] = dominated_by
        results["candidates"][lbl]["success_criteria"]["R5_not_pareto_dominated"] = (len(dominated_by) == 0)
        print(f"{lbl:18s} Pareto dominated by: {dominated_by or 'none'}")

    try:
        import subprocess as sp
        results["manifest"]["commit"] = sp.check_output(["git", "rev-parse", "--short", "HEAD"],
                                                        cwd=ROOT).decode().strip()
    except Exception:  # noqa: BLE001
        results["manifest"]["commit"] = None

    art = ROOT / "artifacts"
    art.mkdir(parents=True, exist_ok=True)
    out = art / "gate4_arch_blend_results.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    raw = art / "gate4_arch_blend_raw.json"
    raw.write_text(json.dumps(
        {"manifest": {"label": FROZEN["label"], "n_intervals": len(decision_dates)},
         "candidates": {lbl: {"net_returns": results["candidates"][lbl]["net_returns"],
                               "weights_post_overlay": results["candidates"][lbl]["weights_post_overlay"],
                               "execution_dates": [str(d.date()) for d in exec_dates]}
                        for lbl, _ in CANDIDATES}},
        indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\n-> {out}")


def _run_check() -> None:
    print("== Architecture RUN --check ==")
    signal_panel, ret_panel, decision_dates, exec_dates = build_panels()
    assert list(signal_panel.columns) == _l2.SLOT_ORDER
    assert len(decision_dates) == FROZEN["n_intervals"] == 2800
    print(f"panel slots: {list(signal_panel.columns)}")
    print(f"n_intervals: {len(decision_dates)} (expected 2800)")
    print(f"candidates: {[c for c, _ in CANDIDATES]}")
    src = Path(__file__).read_text(encoding="utf-8")
    for tok in ["P" + "PO", "S" + "AC", "T" + "D3", "stable" + "_baselines3"]:
        assert tok not in src, f"forbidden RL token in runner"
    assert "SCENARIO_NOT_STRICT_PIT_OOS" in Path(ROOT / "scripts" / "gate4_long_horizon_proxy.py").read_text(encoding="utf-8")
    print("--check PASSED")


if __name__ == "__main__":
    main()
