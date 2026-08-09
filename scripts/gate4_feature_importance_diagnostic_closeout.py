"""GATE_4_FEATURE_ABLATION_DIAGNOSTIC_CLOSEOUT — 退役确认性推断，仅保留描述性（D1-D3）。

评审（GATE_4_FEATURE_ABLATION_RUNS_STAT_FINALIZATION_CORRECTIONS_REVIEWER_RESPONSE.md）TARGETED_RESAMPLING_CLOSEOUT_REQUIRED：
  D1 block_len=60 permutation 在 [359,60,60,60] 段上退化（60 日段=单块，洗牌恒等）→ 退役确认性 p/Holm/BH
  D2 fold bootstrap CI 在 compact array 跨 gap → 移除 bootstrap CI 证据
  D3 结论收窄为描述性 negative evidence

本脚本**只保留描述性统计**：transition-quarantined 面板上的 point estimates / per-segment summaries /
reduced-F0-proxy cross-fit 残差。**无 p / Holm / BH / bootstrap CI**。

结论（评审 §D3 原文风格）：
  transition-quarantined development 数据上，6 个冻结 F1 特征均无大而稳的单调关联；
  先前 Test 的 vol_ratio 关联未以同号复现。这是描述性 negative evidence，不授权删除 F1 或改 RL 观察/net。

输出 artifacts/gate4_feature_importance_diagnostic_closeout.json（tracked）。
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
    contiguous_segments,
    decision_dates,
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


def _f0_predictor_frame(adj: pd.DataFrame) -> pd.DataFrame:
    """reduced F0 market proxy（10 预测子；非完整 104 维 F0）。"""
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

    # --- C1: 475 执行日 → 前序决策日排除（保留已闭环的 transition 隔离）---
    mask = exact_test_mask(folds, calendar=adj.index)
    test_exec = pd.DatetimeIndex(mask["test_dates"])
    test_dec = decision_dates(test_exec, adj.index).dropna()
    excluded = set(test_dec)
    decision_days = pd.DatetimeIndex([
        d for d in adj.index if d >= runner.decision_start and d in adj.index[:-1]])
    screen = pd.DatetimeIndex(sorted(set(decision_days) - excluded))
    t_plus1 = set(adj.index[adj.index.get_indexer(screen) + 1])
    leak = t_plus1 & set(test_exec)
    assert len(leak) == 0, f"Test transition leak: {len(leak)}"
    for f in folds:
        assert f.val_end not in set(screen), f"{f.name} val_end leaked"
    print(f"test_exec={len(test_exec)}  excluded_decision={len(excluded)}  screening={len(screen)}")

    f1_screen = f1.loc[screen]
    fwd = mfwd.loc[screen].to_numpy(dtype=float)
    fwd_abs = np.abs(fwd)
    segs = contiguous_segments(screen, adj.index)
    print(f"segments: sizes={[len(s) for s in segs]}")

    # --- per-feature 描述性点估计（无 inferential 统计）---
    per_feature: dict[str, dict] = {}
    for j, col in enumerate(F1_COLS):
        f = f1_screen.iloc[:, j].to_numpy(dtype=float)
        td = tercile_discrimination(f, fwd_abs)
        # per-segment descriptive summaries
        seg_rho: list[dict] = []
        for si, seg in enumerate(segs):
            fv = f[seg]
            fa = fwd_abs[seg]
            seg_rho.append({"seg": si, "n": int(len(seg)),
                            "rho_abs": spearman(fv, fa)})
        per_feature[col] = {
            "spearman_fwd_ret": spearman(f, fwd),          # 描述性点估计
            "spearman_fwd_abs": spearman(f, fwd_abs),       # 描述性点估计
            "tercile_fwd_abs_mean": {k: td[k]["mean_fwd_ret"] for k in ("low", "mid", "high")},
            "tercile_gap_low_minus_high": td.get("low_minus_high_mean", float("nan")),
            "mann_whitney_p_exploratory_only": td.get("mann_whitney_p", float("nan")),
            "per_segment_spearman_abs": seg_rho,
            "n": int(np.isfinite(f).sum()),
        }

    # --- reduced-F0-proxy fold-local cross-fit 残差化（描述性 point ρ；transition-excluded）---
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
            "gate": "4_FEATURE_ABLATION_DIAGNOSTIC_CLOSEOUT",
            "method": "TRANSITION_QUARANTINED_DESCRIPTIVE_ONLY (no RL, no policy; market equal-weight fwd return)",
            "inferential_claims_retired": True,   # 无 p / Holm / BH / bootstrap CI（D1/D2）
            "descriptive_only": True,
            "test_execution_mask_count": len(test_exec),
            "excluded_decision_days": len(excluded),
            "screening_days": len(screen),
            "transition_invariant": {"no_screen_t_plus_1_in_test_exec": True, "val_end_excluded": True},
            "segments_sizes": [int(len(s)) for s in segs],
            "f0_residualization": "reduced_F0_market_proxy (10 predictors; NOT full 104-dim F0)",
            "rl_model_ablation_executed": False,
            "conclusion": (
                "Descriptive negative evidence only: on transition-quarantined development data, "
                "none of the six frozen F1 features shows a large, stable monotonic association with "
                "next-day market absolute return; the previously observed Test vol-ratio association "
                "does not reproduce with the same sign. Does not authorize deleting F1 features or "
                "changing RL observation/network; frozen F1 candidate set unchanged."
            ),
            "started_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
        "per_feature": per_feature,
        "cross_fit_residualization": cross_fit,
        "runtime_seconds": round(time.time() - t_start, 1),
    }

    art_dir = ROOT / "artifacts"
    art_dir.mkdir(parents=True, exist_ok=True)
    out = art_dir / "gate4_feature_importance_diagnostic_closeout.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    print("\n== F1 descriptive summary (transition-quarantined; NO inferential claims) ==")
    print(f"{'feature':38s} {'rho_ret':>8s} {'rho_abs':>8s} {'gap_lmh':>9s} {'seg_rho(min/max)':>18s}")
    for col in F1_COLS:
        e = per_feature[col]
        seg_rhos = [s["rho_abs"] for s in e["per_segment_spearman_abs"] if np.isfinite(s["rho_abs"])]
        seg_s = f"{min(seg_rhos):+.3f}/{max(seg_rhos):+.3f}" if seg_rhos else "n/a"
        print(f"{col:38s} {e['spearman_fwd_ret']:8.4f} {e['spearman_fwd_abs']:8.4f} "
              f"{e['tercile_gap_low_minus_high']:9.5f} {seg_s:>18s}")
    print("\n== reduced-F0-proxy cross-fit residualization (descriptive point rho) ==")
    for col in F1_COLS:
        cf = cross_fit[col]
        print(f"  {col:38s} min={cf['min_rho_resid_abs']:+.4f} median={cf['median_rho_resid_abs']:+.4f}")
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
