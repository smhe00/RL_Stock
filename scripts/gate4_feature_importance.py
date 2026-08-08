"""GATE_4_FEATURE_ABLATION_RUNS — F1 因子重要性发现（非 RL，用户定向）。

用户定向：不训练 RL（评审授权 GATE_4_FEATURE_ABLATION_RUNS，但 RL_RETRAINING forbidden）。
用 corrected 评估路径重跑便宜的非 RL 参考策略（EW / RiskParity_IVOL / MinimumVariance），
叠加冻结的 F1 特征（ablation_features.f1_features，6 个内部特征），做因子判别分析：

- 每 F1 特征 vs 前向收益/前向风险（Spearman + 三分位判别 gap + Mann-Whitney p）
- F0 基线残差化（top 候选）：F1 特征去除 F0 已有 corr/vol 信息后，残差是否仍预测前向风险
  → 回答 "F1 是否超出 F0 已有信息"（F0 vs F1）
- 跨策略 regime 响应：F1 特征 low/mid/high 分位内，各参考策略 OOS Sharpe

输出 artifacts/gate4_feature_importance_results.json（tracked）。无 RL 训练。
禁止：RL 重训 / 10-seed / Optuna / F2/F3 真实宏观（FEATURE_DATA_READY 门）。
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

from china_etf.data.corporate_actions import load_corporate_actions  # noqa: E402
from china_etf.data.loader import SLOT_MAP, load_execution_prices, load_research_adj  # noqa: E402
from china_etf.evaluation.baselines import (  # noqa: E402
    equal_weight_policy,
    minimum_variance_policy,
    risk_parity_policy,
)
from china_etf.evaluation.factor_importance import (  # noqa: E402
    decision_dates,
    ols_residual,
    spearman,
    tercile_discrimination,
    tercile_labels,
)
from china_etf.evaluation.walkforward import WalkForwardRunner  # noqa: E402
from china_etf.features.ablation_features import f1_features  # noqa: E402
from china_etf.features.etf_features import global_features, per_asset_features  # noqa: E402
from gate4_3seed_pilot import build_env  # noqa: E402

F1_COLS = ["corr_pc1_share_60", "equity_bond_corr_change_20_60", "equity_gold_corr_change_20_60",
           "cn_us_corr_60", "equity_vol_ratio_20_60", "equity_downside_semivol_60"]

# 参考策略（cheap，corrected 评估路径）
REFERENCE_STRATEGIES = [
    ("EqualWeight", equal_weight_policy),
    ("RiskParity_IVOL", risk_parity_policy),
    ("MinimumVariance", minimum_variance_policy),
]

# F0 残差化预测子：F0 global（5）+ CN_LARGE per-asset 关键（5），共 10 列
F0_GLOBAL_COLS = ["cross_sectional_dispersion_20", "equity_average_corr_60",
                  "cn_large_vol_percentile_252", "gold_equity_corr_60", "bond_equity_corr_60"]
F0_ASSET_COLS = ["log_return_20", "realized_vol_20", "realized_vol_60", "drawdown_60", "drawdown_250"]
EQUITY_SLOT = "CN_LARGE"


def _f0_predictor_frame(adj: pd.DataFrame) -> pd.DataFrame:
    """F0 基线预测子：global(5) + CN_LARGE per-asset(5)，index = adj.index。"""
    g = global_features(adj)[F0_GLOBAL_COLS]
    a = per_asset_features(adj[EQUITY_SLOT])[F0_ASSET_COLS].rename(
        columns={c: f"eq_{c}" for c in F0_ASSET_COLS})
    return pd.concat([g, a], axis=1)


def _roll_panel(runner, folds, fac):
    """逐 fold 跑参考策略，收集 (decision_date, fwd_ret) 面板。"""
    dates, rets = [], []
    for f in folds:
        m = runner.run_fold_baseline(f, fac)
        s = m["test"]["series"]
        ex = s["execution_dates"]
        nr = s["net_returns"]
        d = decision_dates(ex, runner.adj.index)
        dates.extend(d)
        rets.extend(float(x) for x in nr)
    return pd.DatetimeIndex(dates), np.asarray(rets, dtype=float)


def _sharpe(rets: np.ndarray) -> float:
    r = np.asarray(rets, dtype=float)
    r = r[np.isfinite(r)]
    if len(r) < 2 or np.std(r) == 0:
        return float("nan")
    return float(np.mean(r) / np.std(r) * np.sqrt(252))


def main() -> None:
    t_start = time.time()
    adj = load_research_adj()
    opens, closes = load_execution_prices()
    ca = load_corporate_actions()
    runner = WalkForwardRunner(
        adj=adj, opens=opens, closes=closes, slots=list(SLOT_MAP.keys()),
        slot_to_instrument={s: SLOT_MAP[s]["instrument"] for s in SLOT_MAP},
        build_env=build_env, corporate_actions=ca,
    )
    folds = runner.make_folds(n_folds=4)
    print(f"== Track A: decision_start={runner.decision_start.date()} ==")

    f1 = f1_features(adj)
    f0p = _f0_predictor_frame(adj)
    print(f"f1_features: {f1.shape} cols={list(f1.columns)}")
    print(f"F0 predictors: {f0p.shape} cols={list(f0p.columns)}")

    # --- 1. 逐参考策略面板 ---
    panels: dict[str, dict] = {}
    for name, fac in REFERENCE_STRATEGIES:
        t0 = time.time()
        dates, rets = _roll_panel(runner, folds, fac)
        panels[name] = {"dates": dates, "fwd_ret": rets,
                        "fwd_abs_ret": np.abs(rets), "fwd_downside": np.minimum(rets, 0.0)}
        print(f"  {name:16s} n_transitions={len(dates)}  {time.time()-t0:.1f}s")

    # 合并面板（用于 F0 残差化 + regime 响应：以 EW 面板为参考轴）
    ew = panels["EqualWeight"]
    d = ew["dates"]
    m = ~pd.isna(d)
    idx = d[m]
    f1_aligned = f1.loc[idx].to_numpy(dtype=float)
    f0p_aligned = f0p.loc[idx].to_numpy(dtype=float)
    ew_abs = ew["fwd_abs_ret"][m]
    ew_ret = ew["fwd_ret"][m]
    print(f"aligned panel: n={len(idx)}")

    # --- 2. 每特征重要性（每参考策略）---
    importance: dict[str, dict] = {}
    for j, col in enumerate(F1_COLS):
        f = f1_aligned[:, j]
        entry: dict = {"per_strategy": {}}
        for name, _ in REFERENCE_STRATEGIES:
            # 对齐到该策略面板（同 dates）
            p = panels[name]
            pm = ~pd.isna(p["dates"])
            pdates = p["dates"][pm]
            pf = f1.loc[pdates, col].to_numpy(dtype=float)
            pr = p["fwd_ret"][pm]
            pa = p["fwd_abs_ret"][pm]
            entry["per_strategy"][name] = {
                "spearman_fwd_ret": spearman(pf, pr),
                "spearman_fwd_abs_ret": spearman(pf, pa),
                "tercile_disc_fwd_ret": tercile_discrimination(pf, pr),
                "tercile_disc_fwd_abs_ret": tercile_discrimination(pf, pa),
            }
        # F0 残差化（EW 面板为参考轴）
        resid = ols_residual(f, f0p_aligned)
        entry["f0_residualization"] = {
            "n_resid": int(np.isfinite(resid).sum()),
            "spearman_resid_fwd_abs_ret": spearman(resid, ew_abs),
            "spearman_resid_fwd_ret": spearman(resid, ew_ret),
            "spearman_raw_fwd_abs_ret": spearman(f, ew_abs),
            "spearman_raw_fwd_ret": spearman(f, ew_ret),
        }
        # 跨策略 regime 响应（以该特征三分位）
        lab = tercile_labels(f)
        regime: dict[str, dict] = {}
        for k, rname in ((0, "low"), (1, "mid"), (2, "high")):
            sel = lab == k
            regime[rname] = {
                "n": int(sel.sum()),
                "per_strategy_sharpe": {n: _sharpe(panels[n]["fwd_ret"][m][sel])
                                        for n, _ in REFERENCE_STRATEGIES},
                "fwd_abs_ret_mean": float(np.mean(ew_abs[sel])) if sel.sum() else float("nan"),
            }
        entry["regime_response"] = regime
        importance[col] = entry

    # --- 3. 复合重要性排序 ---
    ranked = []
    for col, e in importance.items():
        rho_ret = [e["per_strategy"][n]["spearman_fwd_ret"] for n, _ in REFERENCE_STRATEGIES]
        rho_risk = [e["per_strategy"][n]["spearman_fwd_abs_ret"] for n, _ in REFERENCE_STRATEGIES]
        rho_ret_f = [v for v in rho_ret if np.isfinite(v)]
        rho_risk_f = [v for v in rho_risk if np.isfinite(v)]
        score = (np.mean(rho_ret_f) if rho_ret_f else 0.0) + (np.mean(rho_risk_f) if rho_risk_f else 0.0)
        # 跨策略最强 Mann-Whitney 显著性（low vs high fwd_abs_ret）
        pvals = [e["per_strategy"][n]["tercile_disc_fwd_abs_ret"]["mann_whitney_p"]
                 for n, _ in REFERENCE_STRATEGIES]
        pvals_f = [p for p in pvals if np.isfinite(p)]
        ranked.append({"feature": col, "importance_score": round(float(score), 6),
                       "mean_abs_spearman_fwd_ret": round(float(np.mean(np.abs(rho_ret_f))), 6) if rho_ret_f else float("nan"),
                       "mean_abs_spearman_fwd_risk": round(float(np.mean(np.abs(rho_risk_f))), 6) if rho_risk_f else float("nan"),
                       "min_mw_p_fwd_risk": round(float(min(pvals_f)), 6) if pvals_f else float("nan")})
    ranked.sort(key=lambda r: r["importance_score"], reverse=True)

    results = {
        "manifest": {
            "gate": "4_FEATURE_ABLATION_RUNS",
            "method": "NON_RL_F1_FACTOR_IMPORTANCE_DISCOVERY (user-directed; no RL training)",
            "reference_strategies": [n for n, _ in REFERENCE_STRATEGIES],
            "f1_features": F1_COLS,
            "n_panel_transitions": {n: int(len(p["dates"])) for n, p in panels.items()},
            "folds": 4,
            "started_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
        "importance": importance,
        "ranked_importance": ranked,
        "runtime_seconds": round(time.time() - t_start, 1),
    }

    art_dir = ROOT / "artifacts"
    art_dir.mkdir(parents=True, exist_ok=True)
    out = art_dir / "gate4_feature_importance_results.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    print("\n== F1 importance ranking ==")
    print(f"{'feature':38s} {'score':>8s} {'|rho_ret|':>9s} {'|rho_risk|':>9s} {'minMWp':>8s}")
    for r in ranked:
        print(f"{r['feature']:38s} {r['importance_score']:8.4f} {r['mean_abs_spearman_fwd_ret']:9.4f} "
              f"{r['mean_abs_spearman_fwd_risk']:9.4f} {r['min_mw_p_fwd_risk']:8.4f}")
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
