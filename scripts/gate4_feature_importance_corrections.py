"""GATE_4_FEATURE_ABLATION_RUNS_CORRECTIONS — Train/Val-only 因子 screening（A1-A5）。

评审（GATE_4_FEATURE_ABLATION_RUNS_REVIEWER_RESPONSE.md）REVISIONS_REQUIRED：
  A1 Test-informed feature screening → Test 隔离（原 475-Test artifact 保留为
     EXPLORATORY_TEST_SCREENING_ONLY，不用于选择）
  A2 非 RL screening/diagnostic 子门（无 canonical RL F0-vs-F1 模型 ablation；RL retraining forbidden）
  A3 iid 显著性 → block bootstrap CI + Holm/BH-FDR 多重检验
  A4 full-Test F0 残差化 → Train/Validation-only + fold-local cross-fit（train fit → val apply）
  A5 composite score → 弃用，分开报告各指标

方法（fold-local，TEST 隔离）：
  outcome = 市场等权前向收益（11 槽位复权 log 收益，决策日 t → t+1），无 RL/无策略 rollout。
  每 fold：screening 决策日 = 该 fold 的 train∪val（不含该 fold 自身 test）；
  统计 per-fold 计算（Spearman / tercile gap / MWp / block bootstrap CI），跨 fold 汇总；
  残差化 = fold-local cross-fit（train fit → val apply）。

输出 artifacts/gate4_feature_importance_corrections.json（tracked）。
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

from china_etf.data.loader import SLOT_MAP, load_research_adj  # noqa: E402
from china_etf.evaluation.factor_importance import (  # noqa: E402
    bh_fdr,
    block_bootstrap_ci,
    holm_adjust,
    spearman,
    tercile_discrimination,
)
from china_etf.evaluation.walkforward import WalkForwardRunner  # noqa: E402
from china_etf.features.ablation_features import f1_features  # noqa: E402
from china_etf.features.etf_features import global_features, per_asset_features  # noqa: E402
from gate4_3seed_pilot import build_env  # noqa: E402

F1_COLS = ["corr_pc1_share_60", "equity_bond_corr_change_20_60", "equity_gold_corr_change_20_60",
           "cn_us_corr_60", "equity_vol_ratio_20_60", "equity_downside_semivol_60"]

F0_GLOBAL_COLS = ["cross_sectional_dispersion_20", "equity_average_corr_60",
                  "cn_large_vol_percentile_252", "gold_equity_corr_60", "bond_equity_corr_60"]
F0_ASSET_COLS = ["log_return_20", "realized_vol_20", "realized_vol_60", "drawdown_60", "drawdown_250"]
EQUITY_SLOT = "CN_LARGE"

BLOCK_LEN = 20  # 预声明 block 长度（= 最长滚动窗口）
N_BOOT = 500
SEED = 0


def _f0_predictor_frame(adj: pd.DataFrame) -> pd.DataFrame:
    g = global_features(adj)[F0_GLOBAL_COLS]
    a = per_asset_features(adj[EQUITY_SLOT])[F0_ASSET_COLS].rename(
        columns={c: f"eq_{c}" for c in F0_ASSET_COLS})
    return pd.concat([g, a], axis=1)


def _market_fwd(adj: pd.DataFrame) -> pd.Series:
    """11 槽位等权市场前向收益：t 决策 → t+1 收盘。"""
    r = np.log(adj / adj.shift(1))
    return r.mean(axis=1).shift(-1)


def _fold_screen_days(adj: pd.DataFrame, fold, decision_start) -> pd.DatetimeIndex:
    """该 fold 的 train∪val 决策日（>= decision_start，非 terminal mark，不含自身 test）。"""
    days = pd.DatetimeIndex([
        d for d in adj.index
        if (fold.train_start <= d <= fold.train_end) or (fold.val_start <= d <= fold.val_end)
    ])
    days = days[(days >= decision_start) & days.isin(adj.index[:-1])]
    return days


def _per_fold_stat(f: np.ndarray, fwd_abs: np.ndarray) -> dict:
    td = tercile_discrimination(f, fwd_abs)
    return {
        "rho_abs": spearman(f, fwd_abs),
        "tercile_gap": td.get("low_minus_high_mean", float("nan")),
        "mw_p": td.get("mann_whitney_p", float("nan")),
        "n": int(np.isfinite(f).sum()),
    }


def main() -> None:
    t_start = time.time()
    adj = load_research_adj()
    runner = WalkForwardRunner(
        adj=adj, opens={}, closes={}, slots=list(SLOT_MAP.keys()),
        slot_to_instrument={s: SLOT_MAP[s]["instrument"] for s in SLOT_MAP},
        build_env=build_env,
    )
    folds = runner.make_folds(n_folds=4)
    print(f"== decision_start={runner.decision_start.date()} ==")

    mfwd = _market_fwd(adj)
    f1 = f1_features(adj)
    f0p = _f0_predictor_frame(adj)

    # --- per-fold screening 面板（fold-local，自身 test 排除）---
    fold_stats: dict[str, dict] = {}
    per_feature: dict[str, dict] = {}
    for col in F1_COLS:
        per_feature[col] = {"per_fold": {}, "holm_p": float("nan"), "bh_fdr_q": float("nan")}

    # 先做 per-fold stat + bootstrap，收集 MW p 供多重检验
    mw_p_by_feature = {c: [] for c in F1_COLS}
    for f in folds:
        days = _fold_screen_days(adj, f, runner.decision_start)
        fs = f1.loc[days]
        fwd_abs = np.abs(mfwd.loc[days].to_numpy(dtype=float))
        row: dict = {}
        for col in F1_COLS:
            fv = fs[col].to_numpy(dtype=float)
            st = _per_fold_stat(fv, fwd_abs)
            row[col] = st
            mw_p_by_feature[col].append(st["mw_p"])
        fold_stats[f.name] = {"n_days": int(len(days)),
                              "train_range": [str(f.train_start.date()), str(f.train_end.date())],
                              "val_range": [str(f.val_start.date()), str(f.val_end.date())],
                              "per_feature": row}

    # --- 多重检验：跨 fold median MW p（6 特征 family）---
    median_p = {c: float(np.median([p for p in mw_p_by_feature[c] if np.isfinite(p)]))
                if any(np.isfinite(p) for p in mw_p_by_feature[c]) else float("nan")
                for c in F1_COLS}
    p_arr = np.array([median_p[c] if np.isfinite(median_p[c]) else 0.999 for c in F1_COLS])
    holm = holm_adjust(p_arr)
    bh = bh_fdr(p_arr)
    for i, c in enumerate(F1_COLS):
        per_feature[c]["holm_p_median_mw"] = float(holm[i])
        per_feature[c]["bh_fdr_q_median_mw"] = float(bh[i])

    # --- block bootstrap CI：对 pooled fold-local 面板（去重后非 test 决策日）---
    # 以各 fold 自己的 train∪val 收集，跨 fold 不重叠的部分独立 bootstrap；
    # 简化：对"不含任何 fold 自身 test"的最大干净集做 bootstrap 太复杂——
    # 改为：对每 fold 各自 bootstrap，跨 fold 取中位 CI。
    for col in F1_COLS:
        cis = []
        for f in folds:
            days = _fold_screen_days(adj, f, runner.decision_start)
            fv = f1.loc[days, col].to_numpy(dtype=float)
            fa = np.abs(mfwd.loc[days].to_numpy(dtype=float))
            ci = block_bootstrap_ci(
                fv, fa, spearman, n_boot=N_BOOT, block_len=BLOCK_LEN, seed=SEED)
            cis.append(ci)
        finite_ci = [c for c in cis if np.isfinite(c["ci_low"]) and np.isfinite(c["ci_high"])]
        per_feature[col]["bs_spearman_ci_per_fold"] = cis
        if finite_ci:
            per_feature[col]["bs_spearman_ci_median"] = {
                "ci_low": float(np.median([c["ci_low"] for c in finite_ci])),
                "ci_high": float(np.median([c["ci_high"] for c in finite_ci])),
                "p_bs_median": float(np.median([c["p_bs"] for c in finite_ci])),
            }
        else:
            per_feature[col]["bs_spearman_ci_median"] = {"ci_low": float("nan"),
                                                         "ci_high": float("nan"),
                                                         "p_bs_median": float("nan")}

    # --- fold-local cross-fit 残差化（A4：train fit → val apply）---
    cross_fit: dict[str, dict] = {}
    for col in F1_COLS:
        per_fold = {}
        for f in folds:
            tr = pd.DatetimeIndex([d for d in adj.index
                                   if f.train_start <= d <= f.train_end and d >= runner.decision_start
                                   and d in adj.index[:-1]])
            va = pd.DatetimeIndex([d for d in adj.index
                                   if f.val_start <= d <= f.val_end and d >= runner.decision_start
                                   and d in adj.index[:-1]])
            fv_tr = f1.loc[tr, col].to_numpy(dtype=float)
            fv_va = f1.loc[va, col].to_numpy(dtype=float)
            X_tr = f0p.loc[tr].to_numpy(dtype=float)
            X_va = f0p.loc[va].to_numpy(dtype=float)
            o_va = np.abs(mfwd.loc[va].to_numpy(dtype=float))
            mtr = np.isfinite(fv_tr) & np.isfinite(X_tr).all(axis=1)
            mva = np.isfinite(fv_va) & np.isfinite(X_va).all(axis=1) & np.isfinite(o_va)
            if mtr.sum() < X_tr.shape[1] + 3 or mva.sum() < 10:
                per_fold[f.name] = {"rho_resid_abs": float("nan"), "n_train": int(mtr.sum()),
                                    "n_val": int(mva.sum())}
                continue
            beta, *_ = np.linalg.lstsq(
                np.column_stack([np.ones(int(mtr.sum())), X_tr[mtr]]), fv_tr[mtr], rcond=None)
            resid_va = fv_va[mva] - np.column_stack([np.ones(int(mva.sum())), X_va[mva]]) @ beta
            per_fold[f.name] = {
                "rho_resid_abs": spearman(resid_va, o_va[mva]),
                "n_train": int(mtr.sum()), "n_val": int(mva.sum()),
            }
        rhos = [v["rho_resid_abs"] for v in per_fold.values() if np.isfinite(v["rho_resid_abs"])]
        cross_fit[col] = {
            "per_fold": per_fold,
            "min_rho_resid_abs": float(min(rhos)) if rhos else float("nan"),
            "median_rho_resid_abs": float(np.median(rhos)) if rhos else float("nan"),
        }

    results = {
        "manifest": {
            "gate": "4_FEATURE_ABLATION_RUNS_CORRECTIONS",
            "method": "FOLD_LOCAL_TRAIN_VAL_ONLY_FACTOR_SCREENING (no RL, no policy; market equal-weight fwd return)",
            "test_quarantined": True,
            "test_artifact_status": "EXPLORATORY_TEST_SCREENING_ONLY (preserved, not used for selection)",
            "rl_model_ablation_executed": False,
            "block_len": BLOCK_LEN, "n_boot": N_BOOT, "seed": SEED,
            "started_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
        "fold_stats": fold_stats,
        "per_feature": per_feature,
        "cross_fit_residualization": cross_fit,
        "runtime_seconds": round(time.time() - t_start, 1),
    }

    art_dir = ROOT / "artifacts"
    art_dir.mkdir(parents=True, exist_ok=True)
    out = art_dir / "gate4_feature_importance_corrections.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    print("\n== F1 screening (TRAIN/VAL, TEST quarantined, fold-local) ==")
    print(f"{'feature':38s} {'med_rho_abs':>11s} {'med_gap':>9s} {'medMWp':>8s} "
          f"{'holm':>7s} {'bsCI_median':>15s}")
    for col in F1_COLS:
        pf = per_feature[col]
        med_rho = np.median([fold_stats[fn]["per_feature"][col]["rho_abs"]
                             for fn in fold_stats if np.isfinite(fold_stats[fn]["per_feature"][col]["rho_abs"])]) \
            if any(np.isfinite(fold_stats[fn]["per_feature"][col]["rho_abs"]) for fn in fold_stats) else float("nan")
        med_gap = np.median([fold_stats[fn]["per_feature"][col]["tercile_gap"]
                             for fn in fold_stats if np.isfinite(fold_stats[fn]["per_feature"][col]["tercile_gap"])]) \
            if any(np.isfinite(fold_stats[fn]["per_feature"][col]["tercile_gap"]) for fn in fold_stats) else float("nan")
        ci = pf["bs_spearman_ci_median"]
        print(f"{col:38s} {med_rho:11.4f} {med_gap:9.5f} {median_p[col]:8.4f} "
              f"{pf['holm_p_median_mw']:7.4f} [{ci['ci_low']:+.3f},{ci['ci_high']:+.3f}]")
    print("\n== fold-local cross-fit residualization (train fit -> val apply) ==")
    for col in F1_COLS:
        cf = cross_fit[col]
        print(f"  {col:38s} min_rho={cf['min_rho_resid_abs']:+.4f} median_rho={cf['median_rho_resid_abs']:+.4f}")
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
