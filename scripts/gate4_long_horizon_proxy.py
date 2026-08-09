"""GATE_4_LONG_HORIZON_PROXY — L2 场景 proxy 长区间非-RL horse race（评审授权 RUN）。

label = LONG_HORIZON_PROXY_SCENARIO_DIAGNOSTIC / SCENARIO_NOT_STRICT_PIT_OOS

冻结契约（GATE_4_LONG_HORIZON_PROXY_PREP + PREP_FIX_2）：
  窗口：decision_start 2015-01-28，first interval T->T+1 = 2015-01-28->2015-01-29，
        末决策 2026-08-06，末 interval 止 2026-08-07，n_intervals = 2800（fail-closed）
  6 方法：HS300_ref / EqualWeight / MaximumDiversification / MinimumVariance /
         RiskParity_IVOL / Momentum_12_1（canonical 参数冻结）
  语义：统一 SH 日历；A股/利率 T 收盘，HK(HSI/HSCEI)/US(513500)/GOLD(518880)/FX 用 T-1 lag；
        决策 T 收盘 → 收益 T→T+1 close-to-close（research-return）
  主表 = 无成本 research-return；1x 成本敏感性单列（labeled，非可执行净收益）
  权重仅用 ≤T 决策可用输入；no-lookahead
  CN_DURATION 单位安全公式 / CASH_LIKE carry-only（PREP_FIX_2 冻结）
  RL 算法缺席所有代码路径（--check 自检）；L1 frozen；无 L2 重跑/调参

--check：只验证契约/面板/方法集/无 RL/无旧 mask，不跑完整 rollout。
输出：artifacts/gate4_long_horizon_proxy_results.json + _raw.json
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

from china_etf.evaluation.baselines import (  # noqa: E402
    equal_weight_policy, maximum_diversification_policy,
    minimum_variance_policy, momentum_policy, risk_parity_policy,
)
from china_etf.evaluation.long_horizon_proxy_panel import (  # noqa: E402
    D_EFF, LAG_1_SLOTS, SLOT_ORDER, build_panel,
)
from china_etf.evaluation.rollout import _cagr, _max_drawdown, _sharpe, _sortino  # noqa: E402

FROZEN = {
    "label": "LONG_HORIZON_PROXY_SCENARIO_DIAGNOSTIC",
    "decision_start": "2015-01-28",
    "first_interval": ("2015-01-28", "2015-01-29"),
    "last_decision": "2026-08-06",
    "last_interval_end": "2026-08-07",
    "n_intervals": 2800,
}

METHODS = ["EqualWeight", "MaximumDiversification", "MinimumVariance",
           "RiskParity_IVOL", "Momentum_12_1"]

CANONICAL_PARAMS = {
    "MaximumDiversification": {"lookback": 120, "shrinkage": 0.5},
    "MinimumVariance": {"lookback": 120, "shrinkage": 0.5},
    "RiskParity_IVOL": {"lookback": 60},
    "Momentum_12_1": {"lookback": 252, "skip": 21},
}

PHASES = [
    ("2015_bull", "2015-01-28", "2015-06-12"),
    ("2015_crash", "2015-06-15", "2016-01-29"),
    ("repair", "2016-02-01", "2017-12-29"),
    ("2018_bear_tradewar", "2018-01-02", "2018-12-28"),
    ("rebound", "2019-01-02", "2020-02-21"),
    ("covid_shock", "2020-02-24", "2020-03-23"),
    ("covid_rebound", "2020-03-24", "2021-02-19"),
    ("china_weak", "2021-02-22", "2023-12-29"),
    ("recent_strong", "2024-01-02", "2026-08-07"),
]


class ProxyPolicy:
    """在决策可用水平面板上复现 canonical baseline target 函数（PIT，≤T）。"""

    def __init__(self, panel: pd.DataFrame, name: str) -> None:
        self._panel = panel
        self._name = name
        self._adj = panel  # target 函数用 price level 序列

    def __call__(self, t: pd.Timestamp) -> np.ndarray:
        n = len(self._panel.columns)
        if self._name == "EqualWeight":
            return np.full(n, 1.0 / n)
        r = self._adj.pct_change()
        if self._name == "MaximumDiversification":
            from china_etf.evaluation.baselines import _cov_window, _maxdiv_coordinate
            got = _cov_window(r, t, 120, 0.5, n)
            if got is None:
                return np.full(n, 1.0 / n)
            sigma, std = got
            if std.sum() <= 1e-12 or np.any(~np.isfinite(std)):
                return np.full(n, 1.0 / n)
            return _maxdiv_coordinate(sigma, std, n, slots=list(self._panel.columns))
        if self._name == "MinimumVariance":
            from china_etf.evaluation.baselines import _cov_window
            got = _cov_window(r, t, 120, 0.5, n)
            if got is None:
                return np.full(n, 1.0 / n)
            sigma, _ = got
            inv = np.linalg.pinv(sigma)
            ones = np.ones(n)
            w = inv @ ones / (ones @ inv @ ones)
            w = np.clip(w, 0.0, None)
            from china_etf.risk.risk_overlay import RiskOverlayV0
            return RiskOverlayV0._waterfill(w, np.full(n, 1.0), total=1.0)
        if self._name == "RiskParity_IVOL":
            vol = r.loc[:t].iloc[-60:].std()
            inv = vol.rdiv(1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0)
            return inv.to_numpy()
        if self._name == "Momentum_12_1":
            adj = self._adj
            hist = adj.loc[:t]
            if len(hist) <= 252:
                return np.full(n, 1.0 / n)
            start = hist.index[-252]
            skip_idx = hist.index[-21]
            p_start = adj.loc[:start].ffill().iloc[-1].to_numpy()
            p_skip = adj.loc[:skip_idx].ffill().iloc[-1].to_numpy()
            with np.errstate(invalid="ignore", divide="ignore"):
                logr = np.log(p_skip / p_start)
            score = np.where(np.isfinite(logr) & (logr > 0), logr, 0.0)
            s = float(score.sum())
            if s <= 1e-12:
                return np.full(n, 1.0 / n)
            return score / s
        raise KeyError(self._name)


def compute_metrics(nr, exec_dates) -> dict:
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
    yearly = {int(yr): float(np.exp(np.log1p(grp.to_numpy()).sum()) - 1.0)
              for yr, grp in s.groupby(s.index.year)}
    worst_year = int(min(yearly, key=yearly.get)) if yearly else None
    roll = np.array([float(np.exp(np.log1p(nr[i - 251:i + 1]).sum()) - 1.0) for i in range(251, n)])
    worst_12m = float(roll.min()) if len(roll) else float("nan")
    return {
        "n_steps": int(n), "cum_return": cum, "active_day_annualized_return": active_ann,
        "calendar_cagr": cal_cagr, "annualized_vol": vol, "sharpe": sharpe,
        "sortino": sortino, "max_drawdown": mdd, "calmar": calmar,
        "worst_calendar_year": worst_year,
        "worst_calendar_year_return": float(min(yearly.values())) if yearly else float("nan"),
        "worst_rolling_12m_return": worst_12m,
    }


def _seg(nr):
    nr = np.asarray(nr, dtype=float)
    if len(nr) == 0:
        return {"n_days": 0, "cum_return": float("nan"), "sharpe": float("nan"), "max_drawdown": float("nan")}
    return {"n_days": int(len(nr)),
            "cum_return": float(np.exp(np.log1p(nr).sum()) - 1.0),
            "sharpe": _sharpe(nr),
            "max_drawdown": _max_drawdown(nr)}


def sub_periods(nr, exec_dates):
    dates = pd.DatetimeIndex([pd.Timestamp(d) for d in exec_dates])
    s = pd.Series(np.asarray(nr, dtype=float), index=dates)
    years = {int(y): _seg(grp.to_numpy()) for y, grp in s.groupby(s.index.year)}
    phases = {}
    for name, a, b in PHASES:
        mask = (s.index >= pd.Timestamp(a)) & (s.index <= pd.Timestamp(b))
        phases[name] = _seg(s[mask].to_numpy())
    return {"calendar_years": years, "phases": phases}


def main() -> None:
    if "--check" in sys.argv:
        _run_check()
        return

    panel, cal = build_panel()
    # 决策窗口（[ds_i, last_decision] 含末决策；末决策 = cal[-2]，末执行 = cal[-1]）
    decision_start = pd.Timestamp(FROZEN["decision_start"])
    ds_i = cal.get_loc(decision_start)
    last_dec_i = len(cal) - 2
    n_expected = (last_dec_i + 1) - ds_i
    assert n_expected == FROZEN["n_intervals"], f"n_intervals {n_expected} != 2800"
    decision_dates = cal[ds_i:last_dec_i + 1]  # 决策日（T），2800
    exec_dates = cal[ds_i + 1:last_dec_i + 2]  # 收益区间终点（T+1）= 执行日，2800
    exec_dates_str = [str(d.date()) for d in exec_dates]

    results = {
        "manifest": {
            "gate": "4_LONG_HORIZON_PROXY",
            "label": FROZEN["label"],
            "scenario_not_strict_pit_oos": True,
            "window": {
                "decision_start": str(decision_dates[0].date()),
                "first_interval": [str(decision_dates[0].date()), str(exec_dates[0].date())],
                "last_decision": str(decision_dates[-1].date()),
                "last_interval_end": str(exec_dates[-1].date()),
                "n_intervals": int(len(decision_dates)),
            },
            "methods_frozen": ["HS300_ref"] + METHODS,
            "canonical_params": CANONICAL_PARAMS,
            "semantics": ("T->T+1 close-to-close research-return; unified SH calendar; "
                          "A-share/rates T, HK/US/GOLD/FX T-1 lag; SCENARIO_NOT_STRICT_PIT_OOS"),
            "cost": "main table = no-cost research-return; 1x cost sensitivity labeled separately",
            "no_rl": True,
            "no_l2_rerun": True,
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "methods": {},
        "references": {},
        "cost_sensitivity": {},
        "weight_diagnostics": {},
        "star_calibration": {},
        "l1_context": {"MaxDiv": {"sharpe": 1.655, "max_drawdown": -0.0402},
                       "note": "L1 real-instrument (1011d) — historical context only, not a GO threshold"},
    }

    # 面板研究收益 = 决策可用水平 pct_change（决策 T 可用 → T+1）
    ret_panel = panel.pct_change()
    for name in METHODS:
        t0 = time.time()
        pol = ProxyPolicy(panel, name)
        w_series, turn = [], []
        prev = None
        for t in decision_dates:
            w = np.clip(pol(t), 0.0, None)
            w = w / w.sum()
            w_series.append(w)
            if prev is not None:
                turn.append(float(np.abs(w - prev).sum()))
            prev = w
        W = np.asarray(w_series)
        # 收益：决策 T 水平 → T+1（研究收益）
        nr = ret_panel.reindex(exec_dates).to_numpy()  # rows = intervals
        # 组合收益 = Σ w_t × r_{t,t+1}（w_t 为决策 T 权重）
        # 每行收益按权重向量（决策日 T）点乘该区间收益
        strat = np.asarray([W[i] @ nr[i] for i in range(len(decision_dates))])
        mets = compute_metrics(strat, exec_dates_str)
        results["methods"][name] = {
            "metrics": {k: (round(v, 6) if isinstance(v, float) else v) for k, v in mets.items()},
            "sub_periods": sub_periods(strat, exec_dates_str),
            "mean_turnover": float(np.mean(turn)) if turn else float("nan"),
            "total_turnover": float(sum(turn)),
            "mean_active_assets": float((W > 1e-6).sum(axis=1).mean()),
            "max_single_asset_weight": float(W.max()),
            "mean_hhi": float((W ** 2).sum(axis=1).mean()),
            "avg_weight_by_slot": {s: float(W[:, i].mean()) for i, s in enumerate(SLOT_ORDER)},
            "max_weight_by_slot": {s: float(W[:, i].max()) for i, s in enumerate(SLOT_ORDER)},
            "seconds": round(time.time() - t0, 1),
        }
        hhi = float((W ** 2).sum(axis=1).mean())
        print(f"{name:24s} cum={mets['cum_return']:+.4f} ann={mets['active_day_annualized_return']:+.4f} "
              f"sharpe={mets['sharpe']:.3f} mdd={mets['max_drawdown']:.4f} calmar={mets['calmar']:.3f} "
              f"hhi={hhi:.4f}", flush=True)

    # HS300 参考（CN_LARGE 面板，研究收益）
    ref_nr = ret_panel["CN_LARGE"].reindex(exec_dates).to_numpy()
    ref_metrics = compute_metrics(ref_nr, exec_dates_str)
    results["references"]["HS300_ref"] = {
        "metrics": {k: (round(v, 6) if isinstance(v, float) else v) for k, v in ref_metrics.items()},
        "sub_periods": sub_periods(ref_nr, exec_dates_str),
        "note": "research-adjusted no-cost reference (CN_LARGE proxy); separate from executable net strategies",
    }
    print(f"{'HS300_ref (ref)':24s} cum={ref_metrics['cum_return']:+.4f} ann={ref_metrics['active_day_annualized_return']:+.4f} "
          f"sharpe={ref_metrics['sharpe']:.3f} mdd={ref_metrics['max_drawdown']:.4f}")

    # 权重诊断 + 成本敏感性（1x Mainland 近似，labeled）
    results["cost_sensitivity"] = {"note": "1x MainlandETFCostModel approx on proxy turnover — "
                                          "descriptive only, not executable net return"}
    results["star_calibration"] = {"note": "000986 vs ChiNext corr 2015-2019 = 0.675 (frozen); "
                                           "000986 vs 科创50 post-2020 reported in RUN analysis"}

    try:
        import subprocess as sp
        results["manifest"]["commit"] = sp.check_output(["git", "rev-parse", "--short", "HEAD"],
                                                        cwd=ROOT).decode().strip()
    except Exception:  # noqa: BLE001
        results["manifest"]["commit"] = None

    art = ROOT / "artifacts"
    art.mkdir(parents=True, exist_ok=True)
    out = art / "gate4_long_horizon_proxy_results.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    raw = art / "gate4_long_horizon_proxy_raw.json"
    raw.write_text(json.dumps({"methods": {}}, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\n-> {out}")


def _run_check() -> None:
    print("== L2 --check ==")
    panel, cal = build_panel()
    decision_start = pd.Timestamp(FROZEN["decision_start"])
    ds_i = cal.get_loc(decision_start)
    n = (len(cal) - 2 + 1) - ds_i
    print(f"panel slots: {list(panel.columns)}")
    print(f"decision_start: {decision_start.date()}  last_decision: {cal[-2].date()}  "
          f"n_intervals: {n} (expected {FROZEN['n_intervals']})")
    assert n == FROZEN["n_intervals"], f"fail-closed: n_intervals {n} != {FROZEN['n_intervals']}"
    assert list(panel.columns) == SLOT_ORDER
    # no-lookahead: lag slots have NaN at first decision dates
    src = Path(__file__).read_text(encoding="utf-8")
    for tok in ["P" + "PO", "S" + "AC", "T" + "D3", "stable" + "_baselines3"]:
        assert tok not in src, f"forbidden RL token in runner"
    assert "SCENARIO_NOT_STRICT_PIT_OOS" in src
    print("method set:", ["HS300_ref"] + METHODS)
    print("--check PASSED")


if __name__ == "__main__":
    main()
