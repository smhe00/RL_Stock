"""GATE_4_PILOT_READY M2 — 513690 vs 03110 wrapper-equivalence audit（评审 §5）。

目标不是证明两者一致，而是证明 513690 足以代表 HK_DIVIDEND 经济风险 Slot。
报告共同区间：daily return corr / annualized vol / max drawdown / annualized return /
rolling 120D corr median+min / tracking divergence。

- 513690 research = load_research_adj()['HK_DIVIDEND']（QMT raw + 官方事件 TR，CNY）
- 03110 research  = _hk_cny_series()['close_tr_cny']（sina raw + Global X 官方派息 ×HKD/CNY）
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


def max_drawdown(s: pd.Series) -> float:
    roll_max = s.cummax()
    return float((s / roll_max - 1.0).min())


def main() -> None:
    adj = load_research_adj()
    w690 = adj["HK_DIVIDEND"].dropna()
    w03110 = _hk_cny_series()["close_tr_cny"].dropna()
    common = w690.index.intersection(w03110.index)
    s690 = w690.reindex(common).astype(float)
    s03110 = w03110.reindex(common).astype(float)
    r690 = s690 / s690.shift(1) - 1.0
    r03110 = s03110 / s03110.shift(1) - 1.0
    r690 = r690.dropna()
    r03110 = r03110.dropna()
    days = len(common)
    years = days / 252.0

    rolling = r690.rolling(120).corr(r03110).dropna()
    tracking = r03110 - r690

    out = {
        "slot": "HK_DIVIDEND",
        "wrapper": "513690.SH (QMT raw + official events TR, CNY)",
        "reference": "03110.HK (sina raw + Global X/HKEX official distributions × HKD/CNY, preserved)",
        "common_window": {
            "start": str(common[0].date()),
            "end": str(common[-1].date()),
            "trading_days": int(days),
            "years": round(years, 2),
        },
        "metrics": {
            "daily_return_corr": float(r690.corr(r03110)),
            "annualized_return_690": float(s690.iloc[-1] / s690.iloc[0] - 1.0),
            "annualized_return_03110": float(s03110.iloc[-1] / s03110.iloc[0] - 1.0),
            "annualized_vol_690": float(r690.std() * np.sqrt(252)),
            "annualized_vol_03110": float(r03110.std() * np.sqrt(252)),
            "max_drawdown_690": max_drawdown(s690),
            "max_drawdown_03110": max_drawdown(s03110),
            "rolling_120d_corr_median": float(rolling.median()),
            "rolling_120d_corr_min": float(rolling.min()),
            "tracking_error_ann": float(tracking.std() * np.sqrt(252)),
            "tracking_mean_daily": float(tracking.mean()),
        },
    }

    print("== 513690 vs 03110 wrapper-equivalence ==")
    print(f"common window: {out['common_window']['start']} → {out['common_window']['end']} "
          f"({days} days, {years:.2f}yr)")
    for k, v in out["metrics"].items():
        print(f"  {k:28s} {v:.6f}")

    p = ROOT / "runs" / "gate4_wrapper_audit.json"
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n-> {p}")


if __name__ == "__main__":
    main()
