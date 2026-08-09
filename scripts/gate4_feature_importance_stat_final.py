"""GATE_4_FEATURE_ABLATION_RUNS_STAT_FINALIZATION — 统计严谨性修正（B1-B5）。

评审（GATE_4_FEATURE_ABLATION_RUNS_CORRECTIONS_REVIEWER_RESPONSE.md）TARGETED_STATISTICAL_FINALIZATION_REQUIRED：
  B1 global Test 隔离：global_test_union = ∪ fold.test 决策日，从每个 screening/fit 数据集排除
     （expanding 下后 fold train 含前 fold test，fold-local 不足够 → 全局排除）
  B2 median-p→Holm/BH 无效 → block_permutation_p（null-centered）每特征一个有效 p，跨 6 特征 Holm/BH
  B3 median-of-CI 非聚合 CI → 报告 per-fold bootstrap CI（不合成聚合置信水平）+ block_len 敏感性 20/40/60
  B4 p_bs 非 null-centered → 移除（block_bootstrap_ci 仅描述性 percentile CI）
  B5 残差化 reduced F0 proxy（10 变量非完整 104 F0）→ 重标签 reduced_F0_market_proxy + 收窄结论

方法：outcome = 市场等权前向收益（11 槽位复权 log 收益 t→t+1），无 RL/无策略。
输出 artifacts/gate4_feature_importance_stat_final.json（tracked）。
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
    block_permutation_p,
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

BLOCK_LENS = (20, 40, 60)  # block_len 敏感性（B3；F1 含 60 日窗口，不做单一 claim）
N_PERM = 1000
N_BOOT = 500
SEED = 0


def _f0_predictor_frame(adj: pd.DataFrame) -> pd.DataFrame:
    """reduced F0 market proxy（10 预测子：5 global + CN_LARGE per-asset 5）。非完整 104 维 F0（B5）。"""
    g = global_features(adj)[F0_GLOBAL_COLS]
    a = per_asset_features(adj[EQUITY_SLOT])[F0_ASSET_COLS].rename(
        columns={c: f"eq_{c}" for c in F0_ASSET_COLS})
    return pd.concat([g, a], axis=1)


def _market_fwd(adj: pd.DataFrame) -> pd.Series:
    r = np.log(adj / adj.shift(1))
    return r.mean(axis=1).shift(-1)


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

    # --- B1: global_test_union（所有 fold test 决策日并集）---
    global_test = set()
    for f in folds:
        global_test.update(adj.index[(adj.index >= f.test_start) & (adj.index <= f.test_end)])
    decision_days = pd.DatetimeIndex([
        d for d in adj.index if d >= runner.decision_start and d in adj.index[:-1]])
    screen = pd.DatetimeIndex(sorted(set(decision_days) - global_test))
    print(f"global_test_union={len(global_test)}  screening (test-free)={len(screen)}")

    f1_screen = f1.loc[screen]
    f0p_screen = f0p.loc[screen]
    fwd = mfwd.loc[screen].to_numpy(dtype=float)
    fwd_abs = np.abs(fwd)
    X = f0p_screen.to_numpy(dtype=float)

    # --- 每特征统计（B2/B3/B4）---
    per_feature: dict[str, dict] = {}
    for j, col in enumerate(F1_COLS):
        f = f1_screen.iloc[:, j].to_numpy(dtype=float)
        rho_ret = spearman(f, fwd)
        rho_risk = spearman(f, fwd_abs)
        td = tercile_discrimination(f, fwd_abs)
        # B3: per-fold bootstrap CI（不合成聚合 CI）+ block_len 敏感性
        fold_cis: dict[str, dict] = {}
        for bl in BLOCK_LENS:
            bl_cis = []
            for fld in folds:
                d = pd.DatetimeIndex(sorted(
                    set(d for d in adj.index
                        if (fld.train_start <= d <= fld.train_end or fld.val_start <= d <= fld.val_end)
                        and d >= runner.decision_start and d in adj.index[:-1]) - global_test))
                if len(d) < 10:
                    continue
                fv = f1.loc[d, col].to_numpy(dtype=float)
                fa = np.abs(mfwd.loc[d].to_numpy(dtype=float))
                bl_cis.append(block_bootstrap_ci(fv, fa, spearman, n_boot=N_BOOT,
                                                 block_len=bl, seed=SEED))
            fold_cis[str(bl)] = bl_cis
        # B2/B4: null-centered block permutation p（每特征一个有效 p）
        p_perm = block_permutation_p(f, fwd_abs, spearman, n_perm=N_PERM,
                                     block_len=BLOCK_LENS[0], seed=SEED)
        per_feature[col] = {
            "spearman_fwd_ret": rho_ret,
            "spearman_fwd_abs": rho_risk,
            "tercile_gap_fwd_abs": td.get("low_minus_high_mean", float("nan")),
            "mann_whitney_p_fwd_abs": td.get("mann_whitney_p", float("nan")),
            "block_permutation_p_fwd_abs": p_perm,
            "fold_bootstrap_ci": fold_cis,   # per-fold，无合成聚合 CI（B3）
            "n": int(np.isfinite(f).sum()),
        }

    # --- B2: 跨 6 特征 Holm/BH 校正 block-permutation p ---
    p_arr = np.array([per_feature[c]["block_permutation_p_fwd_abs"] for c in F1_COLS], dtype=float)
    p_arr = np.nan_to_num(p_arr, nan=0.999)
    holm = holm_adjust(p_arr)
    bh = bh_fdr(p_arr)
    for i, c in enumerate(F1_COLS):
        per_feature[c]["holm_p_block_perm"] = float(holm[i])
        per_feature[c]["bh_fdr_q_block_perm"] = float(bh[i])

    # --- B5: reduced F0 proxy fold-local cross-fit（train fit → val apply，global-test-excluded）---
    cross_fit: dict[str, dict] = {}
    for col in F1_COLS:
        per_fold = {}
        for f in folds:
            tr = pd.DatetimeIndex(sorted(set(
                d for d in adj.index if f.train_start <= d <= f.train_end
                and d >= runner.decision_start and d in adj.index[:-1]) - global_test))
            va = pd.DatetimeIndex(sorted(set(
                d for d in adj.index if f.val_start <= d <= f.val_end
                and d >= runner.decision_start and d in adj.index[:-1]) - global_test))
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
            "gate": "4_FEATURE_ABLATION_RUNS_STAT_FINALIZATION",
            "method": "GLOBAL_TEST_FREE_FACTOR_SCREENING (no RL, no policy; market equal-weight fwd return)",
            "test_quarantined_globally": True,
            "global_test_union_size": len(global_test),
            "screening_days": len(screen),
            "test_artifact_status": "EXPLORATORY_TEST_SCREENING_ONLY (preserved, not used for selection)",
            "rl_model_ablation_executed": False,
            "block_lens_sensitivity": list(BLOCK_LENS),
            "n_perm": N_PERM, "n_boot": N_BOOT, "seed": SEED,
            "f0_residualization": "reduced_F0_market_proxy (10 predictors; NOT full 104-dim F0 contract)",
            "started_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
        "per_feature": per_feature,
        "cross_fit_residualization": cross_fit,
        "runtime_seconds": round(time.time() - t_start, 1),
    }

    art_dir = ROOT / "artifacts"
    art_dir.mkdir(parents=True, exist_ok=True)
    out = art_dir / "gate4_feature_importance_stat_final.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    print("\n== F1 screening (global Test-free, block permutation Holm/BH) ==")
    print(f"{'feature':38s} {'rho_abs':>8s} {'MWp':>8s} {'perm_p':>8s} {'holm':>7s} {'q':>7s}")
    for col in F1_COLS:
        e = per_feature[col]
        print(f"{col:38s} {e['spearman_fwd_abs']:8.4f} {e['mann_whitney_p_fwd_abs']:8.4f} "
              f"{e['block_permutation_p_fwd_abs']:8.4f} {e['holm_p_block_perm']:7.4f} "
              f"{e['bh_fdr_q_block_perm']:7.4f}")
    print("\n== fold-local cross-fit residualization (reduced F0 proxy; global-test-excluded) ==")
    for col in F1_COLS:
        cf = cross_fit[col]
        print(f"  {col:38s} min_rho={cf['min_rho_resid_abs']:+.4f} median_rho={cf['median_rho_resid_abs']:+.4f}")
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
