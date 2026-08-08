"""GATE_4_PILOT_READY M2 — 513690 vs 03110 wrapper-equivalence audit（FINAL_FIX P1）。

修复：区分累计 / 几何 CAGR / 算术日均×252；03110 分报 HKD TR 与 CNY TR（归一化 FX）；
对照 Global X 官方性能验证量级（评审 §5/§6）。

- 513690 research = load_research_adj()['HK_DIVIDEND']（QMT raw + 官方事件 TR，CNY）
- 03110 research  = _hk_cny_series()['close_tr_cny']（CNY，FX 归一化）与 ['close_hkd']（HKD）
输出：runs/gate4_wrapper_audit.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from china_etf.data.loader import _hk_cny_series, load_research_adj  # noqa: E402

# Global X 官方性能（03110 恒生高股息 ETF；HKD，NAV total return）——FINAL_FIX P1 对照
GLOBALX_SINCE_INCEPTION_CUM = 1.8169  # 2013 上市 → 2026-07-28 官方累计 +181.69%
GLOBALX_SINCE_START = "2013-06-01"


def cagr(index: pd.Series) -> float:
    """几何年化：CAGR = (TR_end/TR_start)^(365.2425/elapsed_days) - 1（评审 §5）。"""
    s = index.dropna()
    if len(s) < 2:
        return float("nan")
    elapsed = (s.index[-1] - s.index[0]).days
    if elapsed <= 0:
        return float("nan")
    return float((s.iloc[-1] / s.iloc[0]) ** (365.2425 / elapsed) - 1.0)


def max_drawdown(s: pd.Series) -> float:
    roll_max = s.cummax()
    return float((s / roll_max - 1.0).min())


def annualized_vol(returns: pd.Series) -> float:
    return float(returns.std() * np.sqrt(252))


def arith_mean_ann(returns: pd.Series) -> float:
    return float(returns.mean() * 252)


def main() -> None:
    adj = load_research_adj()
    w690 = adj["HK_DIVIDEND"].dropna()
    hk = _hk_cny_series()
    w03110_cny = hk["close_tr_cny"].dropna()
    w03110_hkd = hk["close_tr_hkd"].dropna()  # HKD total-return index（含派息）
    # 隐含 FX = CNY raw close / HKD raw close
    fx_implied = (hk["close"] / hk["close_hkd"]).dropna()

    # 513690 vs 03110 CNY 共同窗口
    common = w690.index.intersection(w03110_cny.index)
    s690 = w690.reindex(common).astype(float)
    s03110 = w03110_cny.reindex(common).astype(float)
    r690 = (s690 / s690.shift(1) - 1.0).dropna()
    r03110 = (s03110 / s03110.shift(1) - 1.0).dropna()
    days = len(common)
    rolling = r690.rolling(120).corr(r03110).dropna()
    tracking = r03110 - r690

    # 03110 全周期（since 2013）HKD TR 对照 Global X 官方
    s_hkd_full = w03110_hkd[w03110_hkd.index >= pd.Timestamp(GLOBALX_SINCE_START)]
    hkd_full_cum = float(s_hkd_full.iloc[-1] / s_hkd_full.iloc[0] - 1.0)

    # 03110 HKD vs CNY 共同窗口（验证 FX 只计入变动，无 double count）
    s_hkd_cw = w03110_hkd.reindex(common).astype(float)
    s_cny_cw = s03110.reindex(common).astype(float)
    hkd_cw_cum = float(s_hkd_cw.iloc[-1] / s_hkd_cw.iloc[0] - 1.0)
    cny_cw_cum = float(s_cny_cw.iloc[-1] / s_cny_cw.iloc[0] - 1.0)
    fx_cw0 = float(fx_implied.asof(common[0]))
    fx_cw1 = float(fx_implied.asof(common[-1]))

    out = {
        "slot": "HK_DIVIDEND",
        "wrapper": "513690.SH (QMT raw + official events TR, CNY)",
        "reference": "03110.HK (sina raw + Global X/HKEX official distributions; HKD + CNY FX-normalized)",
        "common_window": {
            "start": str(common[0].date()),
            "end": str(common[-1].date()),
            "trading_days": int(days),
        },
        "metrics": {
            # 明确分离：累计 / 几何 CAGR / 算术日均×252 / 年化波动（评审 §5）
            "cumulative_total_return_690": float(s690.iloc[-1] / s690.iloc[0] - 1.0),
            "cumulative_total_return_03110_cny": cny_cw_cum,
            "cumulative_total_return_03110_hkd": hkd_cw_cum,
            "cagr_690": cagr(s690),
            "cagr_03110_cny": cagr(s03110),
            "arith_mean_ann_690": arith_mean_ann(r690),
            "arith_mean_ann_03110_cny": arith_mean_ann(r03110),
            "annualized_vol_690": annualized_vol(r690),
            "annualized_vol_03110_cny": annualized_vol(r03110),
            "max_drawdown_690": max_drawdown(s690),
            "max_drawdown_03110_cny": max_drawdown(s03110),
            "daily_return_corr": float(r690.corr(r03110)),
            "tracking_error_ann": float(tracking.std() * np.sqrt(252)),
            "tracking_mean_daily": float(tracking.mean()),
            "rolling_120d_corr_median": float(rolling.median()),
            "rolling_120d_corr_min": float(rolling.min()),
        },
        "03110_cny_conversion_validation": {
            # FINAL_FIX P1：CNY 累计 ≈ HKD 累计 × FX 变动（只计 FX 变动，无 double count）
            "hkd_cum_cw": hkd_cw_cum,
            "cny_cum_cw": cny_cw_cum,
            "fx_move_cw": float(fx_cw1 / fx_cw0 - 1.0),
            "note": "cny_cum = (1+hkd_cum)*(1+fx_move)-1",
        },
        "global_x_official_check": {
            "official_since_inception_cum_03110": GLOBALX_SINCE_INCEPTION_CUM,
            "reconstructed_hkd_cum_since_2013": hkd_full_cum,
            "delta_pp": (hkd_full_cum - GLOBALX_SINCE_INCEPTION_CUM) * 100.0,
            "check": "PASS within 2pp" if abs(hkd_full_cum - GLOBALX_SINCE_INCEPTION_CUM) < 0.02 else "CHECK",
        },
    }

    # FINAL_FIX P1 assertions：无 FX/dividend double count；03110 重建与官方量级一致
    assert abs(cny_cw_cum - ((1.0 + hkd_cw_cum) * (fx_cw1 / fx_cw0) - 1.0)) < 1e-6, \
        "CNY cumulative must equal (1+HKD cum) * (1+FX move) - 1 (no double count)"
    assert abs(hkd_full_cum - GLOBALX_SINCE_INCEPTION_CUM) < 0.02, \
        f"03110 reconstructed HKD TR {hkd_full_cum:.4f} must match Global X official {GLOBALX_SINCE_INCEPTION_CUM:.4f} within 2pp"

    print("== 513690 vs 03110 wrapper-equivalence (FINAL_FIX P1) ==")
    print(f"common window: {out['common_window']['start']} → {out['common_window']['end']} "
          f"({days} days)")
    for k, v in out["metrics"].items():
        print(f"  {k:34s} {v:.6f}" if isinstance(v, float) else f"  {k:34s} {v}")
    print("\n== 03110 CNY conversion validation ==")
    cv = out["03110_cny_conversion_validation"]
    print(f"  hkd_cum={cv['hkd_cum_cw']:.4f}  cny_cum={cv['cny_cum_cw']:.4f}  fx_move={cv['fx_move_cw']:.4f}")
    print("  check: cny_cum ≈ (1+hkd_cum)*(1+fx_move)-1")
    print("\n== Global X official check (03110 HKD, since 2013) ==")
    gx = out["global_x_official_check"]
    print(f"  official_cum={gx['official_since_inception_cum_03110']:.4f}  "
          f"reconstructed={gx['reconstructed_hkd_cum_since_2013']:.4f}  delta={gx['delta_pp']:.2f}pp  "
          f"{gx['check']}")

    p = ROOT / "runs" / "gate4_wrapper_audit.json"
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\n-> {p}")


if __name__ == "__main__":
    main()
