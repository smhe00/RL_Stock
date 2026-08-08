"""Gate 1 — 基于 AkShare 全量场内 ETF 名单做槽位替代品筛选（名称关键词 + 流动性）。"""

from __future__ import annotations

from pathlib import Path

import akshare as ak
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
META = ROOT / "data" / "qmt" / "meta"

SLOT_KEYWORDS = {
    "CN_LARGE": ["沪深300"],
    "CN_SMALL": ["中证1000"],
    "CN_DIVIDEND": ["红利低波", "中证红利"],
    "CHINEXT": ["创业板"],
    "STAR": ["科创50"],
    "HK_TECH": ["恒生科技"],
    "HK_DIVIDEND": ["港股通高股息", "港股高股息", "港股红利", "恒生红利", "红利港股"],
    "US_BROAD": ["标普500"],
    "GOLD": ["黄金ETF", "金ETF"],
    "CN_DURATION": ["国债ETF", "政金债", "十年国债"],
    "CASH_LIKE": ["短融", "货币ETF", "日利", "添益"],
    "SEMICONDUCTOR": ["半导体", "芯片"],
    "AI": ["人工智能"],
    "ROBOTICS": ["机器人"],
    "BIOTECH": ["创新药", "生物医药"],
    "AEROSPACE": ["军工", "国防", "航空航天", "空天"],
}


def main() -> None:
    spot = ak.fund_etf_spot_em()
    spot["成交额"] = pd.to_numeric(spot["成交额"], errors="coerce").fillna(0.0)
    rows: list[dict] = []
    for slot, kws in SLOT_KEYWORDS.items():
        mask = spot["名称"].str.contains("|".join(kws), na=False)
        cand = spot[mask].copy()
        cand = cand.sort_values("成交额", ascending=False)
        for _, r in cand.iterrows():
            rows.append(
                {
                    "slot": slot,
                    "code": r["代码"],
                    "name": r["名称"],
                    "adv_cny": round(float(r["成交额"]), 2),
                    "premium_pct": r.get("基金折价率", None),
                }
            )
    out = pd.DataFrame(rows)
    out.to_csv(META / "alternative_candidates.csv", index=False)
    for slot in SLOT_KEYWORDS:
        g = out[out["slot"] == slot]
        top = g.head(6)
        print(f"\n[{slot}]")
        print(top[["code", "name", "adv_cny"]].to_string(index=False))


if __name__ == "__main__":
    main()
