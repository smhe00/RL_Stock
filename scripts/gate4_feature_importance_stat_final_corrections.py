"""GATE_4_FEATURE_ABLATION_RUNS_STAT_FINALIZATION_CORRECTIONS — 过渡语义 + 依赖感知重采样（C1-C5）。

评审（GATE_4_FEATURE_ABLATION_RUNS_STAT_FINALIZATION_REVIEWER_RESPONSE.md）TARGETED_TRANSITION_AND_RESAMPLING_CORRECTIONS_REQUIRED：
  C1 Test 隔离按决策日（非执行日）：exact_test_mask["test_dates"]（475 执行日）→ decision_dates 映射到前序决策日
     → 排除该 union；transition-based invariant：无诊断 t→t+1 的 t+1 在执行 mask 中。
  C2 block_permutation_p 是 with-replacement bootstrap → 改为 segment-aware 无替换 contiguous-block permutation
     p = (1 + count(|T_null| >= |T_obs|)) / (B + 1)。
  C3 resampling 不跨 quarantined gap：contiguous_segments 按原始日历邻接分段，段内块洗牌。
  C4 fold CI 重标签 fold-specific nested-panel descriptive CI（非独立）。
  C5 inferential p 预声明保守主尺度 block_len=60（F1 含 60 日窗口），报告 20/40/60 敏感性。

方法：outcome = 市场等权前向收益（11 槽位复权 log 收益 t→t+1），无 RL/无策略。
输出 artifacts/gate4_feature_importance_stat_final_corrections.json（tracked）。
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
from china_etf.evaluation.benchmark import exact_test_mask  # noqa: E402
from china_etf.evaluation.factor_importance import (  # noqa: E402
    bh_fdr,
    block_bootstrap_ci,
    contiguous_segments,
    decision_dates,
    holm_adjust,
    segment_block_permutation_p,
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

BLOCK_LENS = (20, 40, 60)      # C5: 敏感性
PRIMARY_BLOCK_LEN = 60         # C5: 预声明保守主尺度（= F1 最长滚动窗口）
N_PERM = 1000
N_BOOT = 500
SEED = 0


def _f0_predictor_frame(adj: pd.DataFrame) -> pd.DataFrame:
    """reduced F0 market proxy（10 预测子；非完整 104 维 F0，B5/C1 保留该标签）。"""
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

    # --- C1: 精确 475 Test 执行日 mask → 前序决策日 union 排除 ---
    mask = exact_test_mask(folds, calendar=adj.index)
    test_exec = pd.DatetimeIndex(mask["test_dates"])
    test_dec = decision_dates(test_exec, adj.index).dropna()
    excluded = set(test_dec)
    decision_days = pd.DatetimeIndex([
        d for d in adj.index if d >= runner.decision_start and d in adj.index[:-1]])
    screen = pd.DatetimeIndex(sorted(set(decision_days) - excluded))
    print(f"test_exec={len(test_exec)}  test_decision_excluded={len(excluded)}  screening={len(screen)}")

    # C1 transition-based invariant：无 screen 中 t 使 t+1 在执行 mask 中
    t_plus1 = set(adj.index[adj.index.get_indexer(screen) + 1])
    leak = t_plus1 & set(test_exec)
    assert len(leak) == 0, f"Test transition leak: {len(leak)} t+1 in test_exec"
    # val_end 不在 screen（每 fold 首 Test 决策日已排除）
    for f in folds:
        assert f.val_end not in set(screen), f"{f.name} val_end {f.val_end.date()} leaked into screening"

    f1_screen = f1.loc[screen]
    f0p_screen = f0p.loc[screen]
    fwd = mfwd.loc[screen].to_numpy(dtype=float)
    fwd_abs = np.abs(fwd)

    # C3: segment-aware 邻接段（screen 内按原始日历邻接）
    segs = contiguous_segments(screen, adj.index)
    print(f"contiguous segments (no cross-gap): {len(segs)} sizes={[len(s) for s in segs]}")

    # --- 每特征统计 ---
    per_feature: dict[str, dict] = {}
    for j, col in enumerate(F1_COLS):
        f = f1_screen.iloc[:, j].to_numpy(dtype=float)
        rho_ret = spearman(f, fwd)
        rho_risk = spearman(f, fwd_abs)
        td = tercile_discrimination(f, fwd_abs)
        # C4: per-fold nested-panel descriptive CI（fold 面板非独立，不作合成聚合 CI）
        fold_cis: dict[str, dict] = {}
        for bl in BLOCK_LENS:
            bl_cis = []
            for fld in folds:
                d = pd.DatetimeIndex(sorted(
                    set(d for d in adj.index
                        if (fld.train_start <= d <= fld.train_end or fld.val_start <= d <= fld.val_end)
                        and d >= runner.decision_start and d in adj.index[:-1]) - excluded))
                if len(d) < 10:
                    continue
                fv = f1.loc[d, col].to_numpy(dtype=float)
                fa = np.abs(mfwd.loc[d].to_numpy(dtype=float))
                bl_cis.append({"fold": fld.name, **block_bootstrap_ci(fv, fa, spearman, n_boot=N_BOOT,
                                                                      block_len=bl, seed=SEED)})
            fold_cis[str(bl)] = bl_cis
        # C2/C5: segment-aware 无替换块 permutation p（block_len 20/40/60；primary=60）
        perm_p: dict[int, float] = {}
        for bl in BLOCK_LENS:
            perm_p[bl] = segment_block_permutation_p(
                f, fwd_abs, segs, spearman, n_perm=N_PERM, block_len=bl, seed=SEED)
        per_feature[col] = {
            "spearman_fwd_ret": rho_ret,
            "spearman_fwd_abs": rho_risk,
            "tercile_gap_fwd_abs": td.get("low_minus_high_mean", float("nan")),
            "mann_whitney_p_fwd_abs": td.get("mann_whitney_p", float("nan")),
            "segment_perm_p_by_block_len": {str(bl): perm_p[bl] for bl in BLOCK_LENS},
            "segment_perm_p_primary_block_len_60": perm_p[PRIMARY_BLOCK_LEN],
            "fold_nested_descriptive_ci": fold_cis,
            "n": int(np.isfinite(f).sum()),
        }

    # --- C2/C5: 跨 6 特征 Holm/BH（primary block_len=60 的 p）---
    p_60 = np.array([per_feature[c]["segment_perm_p_primary_block_len_60"] for c in F1_COLS], dtype=float)
    p_60 = np.nan_to_num(p_60, nan=0.999)
    holm_60 = holm_adjust(p_60)
    bh_60 = bh_fdr(p_60)
    for i, c in enumerate(F1_COLS):
        per_feature[c]["holm_p_block_len_60"] = float(holm_60[i])
        per_feature[c]["bh_fdr_q_block_len_60"] = float(bh_60[i])

    # --- 残差化：reduced F0 proxy fold-local cross-fit（train fit → val apply，排除 excluded）---
    cross_fit: dict[str, dict] = {}
    for col in F1_COLS:
        per_fold = {}
        for f in folds:
            tr = pd.DatetimeIndex(sorted(set(
                d for d in adj.index if f.train_start <= d <= f.train_end
                and d >= runner.decision_start and d in adj.index[:-1]) - excluded))
            va = pd.DatetimeIndex(sorted(set(
                d for d in adj.index if f.val_start <= d <= f.val_end
                and d >= runner.decision_start and d in adj.index[:-1]) - excluded))
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
            "gate": "4_FEATURE_ABLATION_RUNS_STAT_FINALIZATION_CORRECTIONS",
            "method": "TRANSITION_QUARANTINED_SEGMENT_AWARE_FACTOR_SCREENING (no RL, no policy)",
            "test_execution_mask_count": len(test_exec),
            "test_decision_excluded": len(excluded),
            "screening_days": len(screen),
            "transition_invariant": {"no_screen_t_plus_1_in_test_exec": True,
                                     "val_end_excluded": True},
            "segment_aware": True,
            "segments_count": len(segs),
            "primary_block_len": PRIMARY_BLOCK_LEN,
            "block_lens_sensitivity": list(BLOCK_LENS),
            "n_perm": N_PERM, "n_boot": N_BOOT, "seed": SEED,
            "f0_residualization": "reduced_F0_market_proxy (10 predictors; NOT full 104-dim F0)",
            "rl_model_ablation_executed": False,
            "started_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
        "segments": [{"n_days": int(len(s))} for s in segs],
        "per_feature": per_feature,
        "cross_fit_residualization": cross_fit,
        "runtime_seconds": round(time.time() - t_start, 1),
    }

    art_dir = ROOT / "artifacts"
    art_dir.mkdir(parents=True, exist_ok=True)
    out = art_dir / "gate4_feature_importance_stat_final_corrections.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    print("\n== F1 screening (transition-quarantined, segment-aware permutation) ==")
    print(f"{'feature':38s} {'rho_abs':>8s} {'p20':>8s} {'p40':>8s} {'p60':>8s} {'holm60':>8s} {'q60':>8s}")
    for col in F1_COLS:
        e = per_feature[col]
        print(f"{col:38s} {e['spearman_fwd_abs']:8.4f} "
              f"{e['segment_perm_p_by_block_len']['20']:8.4f} "
              f"{e['segment_perm_p_by_block_len']['40']:8.4f} "
              f"{e['segment_perm_p_by_block_len']['60']:8.4f} "
              f"{e['holm_p_block_len_60']:8.4f} {e['bh_fdr_q_block_len_60']:8.4f}")
    print("\n== fold-local cross-fit residualization (reduced F0 proxy; transition-excluded) ==")
    for col in F1_COLS:
        cf = cross_fit[col]
        print(f"  {col:38s} min_rho={cf['min_rho_resid_abs']:+.4f} median_rho={cf['median_rho_resid_abs']:+.4f}")
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
