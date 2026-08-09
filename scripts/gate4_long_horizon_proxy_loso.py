"""GATE_4_LONG_HORIZON_PROXY — Leave-one-slot-out 诊断（PREP 冻结计划 §7）。

评审 Interpretation 要求报告是否被单一 proxy 主导（尤其 CASH_LIKE / GOLD / CN_DURATION /
technology proxies）。本脚本对冻结方法集中受影响最大的三个 risk-based 方法
（MaximumDiversification / MinimumVariance / RiskParity_IVOL）在剔除单个槽位后的
10-slot 子集上重算全期指标。仅诊断，不改策略。

性质：SCENARIO_NOT_STRICT_PIT_OOS。不改变 L2 主表结果。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_spec = importlib.util.spec_from_file_location("l2_mod", ROOT / "scripts" / "gate4_long_horizon_proxy.py")
_l2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_l2)

METHODS = ["MaximumDiversification", "MinimumVariance", "RiskParity_IVOL"]
DROPS = ["CASH_LIKE", "GOLD", "CN_DURATION", "STAR"]  # 评审点名 proxy（cash/gold/duration/tech）


def run_subset(name: str, panel: pd.DataFrame, decision_dates, exec_dates):
    sub = panel[panel.columns]
    ret = panel.pct_change().reindex(exec_dates)
    pol = _l2.ProxyPolicy(sub, name)
    W = []
    for t in decision_dates:
        w = np.clip(pol(t), 0.0, None)
        w = w / w.sum()
        W.append(w)
    W = np.asarray(W)
    strat = np.asarray([W[i] @ ret.iloc[i].to_numpy() for i in range(len(decision_dates))])
    exec_str = [str(d.date()) for d in exec_dates]
    m = _l2.compute_metrics(strat, exec_str)
    return m, W


def main() -> None:
    panel, cal = _l2.build_panel()
    ds = pd.Timestamp("2015-01-28")
    ds_i = cal.get_loc(ds)
    last_dec_i = len(cal) - 2
    decision_dates = cal[ds_i:last_dec_i + 1]
    exec_dates = cal[ds_i + 1:last_dec_i + 2]

    out = {}
    print("== Leave-one-slot-out (10-slot subsets) ==")
    for drop in DROPS:
        sub = panel.drop(columns=[drop])
        print(f"--- drop {drop} ---")
        row = {}
        for name in METHODS:
            m, W = run_subset(name, sub, decision_dates, exec_dates)
            hhi = float((W ** 2).sum(axis=1).mean())
            row[name] = {
                "cum_return": round(m["cum_return"], 5),
                "active_day_annualized_return": round(m["active_day_annualized_return"], 5),
                "sharpe": round(m["sharpe"], 4),
                "max_drawdown": round(m["max_drawdown"], 5),
                "calmar": round(m["calmar"], 4),
                "mean_hhi": round(hhi, 4),
                "max_single_weight": float(W.max()),
            }
            print(f"  {name:24s} cum={m['cum_return']:+.4f} ann={m['active_day_annualized_return']:+.4f} "
                  f"sharpe={m['sharpe']:.3f} mdd={m['max_drawdown']:.4f} hhi={hhi:.4f}")
        out[drop] = row

    # 写入主结果 artifact 的 leave_one_slot_out 段（不动主表）
    art = ROOT / "artifacts" / "gate4_long_horizon_proxy_results.json"
    if art.exists():
        d = json.loads(art.read_text(encoding="utf-8"))
        d["leave_one_slot_out"] = out
        art.write_text(json.dumps(d, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        print(f"\n-> appended leave_one_slot_out to {art}")


if __name__ == "__main__":
    main()
