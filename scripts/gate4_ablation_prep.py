"""GATE_4_FEATURE_ABLATION_PREP — 确定性 feature-construction smoke（评审 §7 项 10）。

用真实 11 槽位数据 + 合成 macro（F2 数据契约验证）：
- 4 个 feature set 的 exog/obs 维度断言（93/99/99/105 exog；104/110/110/116 obs）
- F-A2 train-only imputation：train 内零星 NaN impute + 每 obs 全 finite + val 只 transform
- 不训练 RL。

输出：runs/gate4_ablation_prep_smoke.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from china_etf.data.loader import load_research_adj  # noqa: E402
from china_etf.features.ablation_features import (  # noqa: E402
    OBS_DIM,
    EXOG_DIM,
    market_feature_frame,
)
from china_etf.features.preprocessor import FeaturePreprocessor  # noqa: E402


def _synthetic_macro(china_index):
    """合成 macro（native-calendar-first，P1）：VIX 用 US native 日历（剔除 7/4），其余用 China 日历。

    VIX 仅工作日且剔除 7/4（US 独立日）→ native 观测数 < China 日数，验证 native 窗口语义。
    """
    china = pd.DatetimeIndex(china_index)
    rng = np.random.default_rng(7)
    us_dates = pd.DatetimeIndex(
        [d for d in pd.bdate_range(china[0], china[-1]) if not (d.month == 7 and d.day == 4)]
    )
    n_us = len(us_dates)
    vix = pd.Series(20 + 5 * np.sin(np.arange(n_us) / 20) + rng.normal(0, 1, n_us), index=us_dates)
    n_cn = len(china)
    usd = pd.Series(7.0 + 0.05 * np.arange(n_cn) / n_cn + rng.normal(0, 0.01, n_cn), index=china)
    cgb = pd.Series(0.03 + 0.002 * np.sin(np.arange(n_cn) / 40), index=china)
    dr = pd.Series(0.02 + 0.003 * np.sin(np.arange(n_cn) / 25) + rng.normal(0, 0.0005, n_cn), index=china)
    to = pd.Series(8000 + 3000 * np.sin(np.arange(n_cn) / 60) + rng.normal(0, 300, n_cn), index=china)
    return {"vix": vix, "usd_cny": usd, "cgb10y": cgb, "dr007": dr, "a_share_turnover": to}


def main() -> None:
    adj = load_research_adj()
    macro = _synthetic_macro(adj.index)
    results = {"feature_sets": {}, "imputation": {}}

    print("== feature-set dimension smoke ==")
    for fs in ["F0", "F1", "F2", "F3"]:
        mff = market_feature_frame(adj, fs, macro if fs in ("F2", "F3") else None)
        exog = mff.shape[1]
        obs = exog + 11
        ok = exog == EXOG_DIM[fs] and obs == OBS_DIM[fs]
        results["feature_sets"][fs] = {
            "exog_dim": exog, "obs_dim": obs,
            "expected_exog": EXOG_DIM[fs], "expected_obs": OBS_DIM[fs],
            "ok": bool(ok),
        }
        print(f"  {fs}: exog={exog} obs={obs} (expected {EXOG_DIM[fs]}/{OBS_DIM[fs]}) {'OK' if ok else 'FAIL'}")

    # F-A2 imputation 隔离（用 F1，含内部特征）
    print("\n== F-A2 train-only imputation smoke ==")
    f1 = market_feature_frame(adj, "F1")
    finite_idx = f1.dropna(how="any").index
    idx = list(finite_idx)
    cut = int(len(idx) * 0.5)
    train_idx = pd.DatetimeIndex(idx[:cut])
    val_idx = pd.DatetimeIndex(idx[cut:])
    df = f1.copy()
    # 在 train 与 val 各注入零星 NaN
    df.loc[train_idx[10], df.columns[0]] = np.nan
    df.loc[train_idx[20], df.columns[1]] = np.nan
    df.loc[val_idx[5], df.columns[2]] = np.nan

    pre = FeaturePreprocessor().fit_train(df.loc[train_idx])
    tr_out = pre.transform(df.loc[train_idx])
    va_out = pre.transform(df.loc[val_idx])
    finite_ok = bool(np.isfinite(tr_out).all() and np.isfinite(va_out).all())
    imputed_ok = bool(abs(va_out[5, 2]) < 0.5)
    results["imputation"] = {
        "train_rows": len(train_idx), "val_rows": len(val_idx),
        "all_finite_train": bool(np.isfinite(tr_out).all()),
        "all_finite_val": bool(np.isfinite(va_out).all()),
        "imputed_approx_zero": imputed_ok,
        "fit_columns": len(pre._columns),
    }
    print(f"  train_rows={len(train_idx)} val_rows={len(val_idx)} "
          f"finite_train={results['imputation']['all_finite_train']} "
          f"finite_val={results['imputation']['all_finite_val']} "
          f"imputed_approx_zero={imputed_ok}")

    out = ROOT / "runs" / "gate4_ablation_prep_smoke.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\n-> {out}")
    assert all(v["ok"] for v in results["feature_sets"].values()), "维度断言失败"
    assert finite_ok and imputed_ok, "F-A2 imputation 断言失败"


if __name__ == "__main__":
    main()
