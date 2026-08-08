"""Gate 1 — 快照元数据（AkShare）+ QMT 板块候选筛选（只读）。"""

from __future__ import annotations

import json
import re
from pathlib import Path

import akshare as ak
import pandas as pd

from xtquant import xtdata

ROOT = Path(__file__).resolve().parents[1]
META = ROOT / "data" / "qmt" / "meta"
META.mkdir(parents=True, exist_ok=True)

SLOTS = {
    "CN_LARGE": "510300",
    "CN_SMALL": "512100",
    "CN_DIVIDEND": "512890",
    "CHINEXT": "159915",
    "STAR": "588000",
    "HK_TECH": "513180",
    "HK_DIVIDEND": "03110.HK",
    "US_BROAD": "513500",
    "GOLD": "518880",
    "CN_DURATION": "511260",
    "CASH_LIKE": "511360",
    "SEMICONDUCTOR": "512480",
    "AI": "515070",
    "ROBOTICS": "159770",
    "BIOTECH": "159992",
    "AEROSPACE": "512660",
}

# 槽位关键词 → 用于在 ETF 板块中筛替代品
SLOT_KEYWORDS = {
    "CN_LARGE": ["沪深300"],
    "CN_SMALL": ["中证1000", "1000ETF"],
    "CN_DIVIDEND": ["红利低波", "中证红利", "红利ETF"],
    "CHINEXT": ["创业板"],
    "STAR": ["科创50"],
    "HK_TECH": ["恒生科技"],
    "HK_DIVIDEND": ["恒生高股息", "港股高股息", "恒生红利"],
    "US_BROAD": ["标普500"],
    "GOLD": ["黄金ETF", "金ETF"],
    "CN_DURATION": ["国债", "政金债", "十年"],
    "CASH_LIKE": ["短融", "货币", "日利", "添益"],
    "SEMICONDUCTOR": ["半导体", "芯片"],
    "AI": ["人工智能", "AI", "信息技术"],
    "ROBOTICS": ["机器人"],
    "BIOTECH": ["创新药", "生物医药", "医药"],
    "AEROSPACE": ["军工", "国防", "航天"],
}


def main() -> None:
    spot = ak.fund_etf_spot_em()
    codes = [c for c in SLOTS.values() if not c.endswith(".HK")]
    sub = spot[spot["代码"].isin(codes)].copy()
    sub = sub.sort_values("代码")
    cols = ["代码", "名称", "最新价", "成交额", "最新份额", "总市值", "基金折价率", "IOPV实时估值", "换手率", "数据日期"]
    sub[cols].to_csv(META / "spot_snapshot_20260808.csv", index=False)
    print(sub[cols].to_string(index=False))

    # QMT 板块：找出 ETF 相关板块并按其成员匹配关键词
    sectors = xtdata.get_sector_list()
    etf_sectors = [s for s in sectors if ("ETF" in s or "指数" in s or "基金" in s)]
    print(f"\nQMT sectors containing ETF/指数/基金: {len(etf_sectors)}")
    for s in sorted(etf_sectors):
        print("  ", s)

    member_pool: dict[str, list[dict]] = {}
    for name in etf_sectors:
        try:
            members = xtdata.get_stock_list_in_sector(name)
        except Exception:  # noqa: BLE001
            continue
        for m in members:
            if not re.fullmatch(r"\d{6}\.(SH|SZ)", m):
                continue
            member_pool.setdefault(m, []).append(name)
    with (META / "qmt_etf_sector_members.json").open("w", encoding="utf-8") as fh:
        json.dump(member_pool, fh, ensure_ascii=False, indent=1)

    # 名称关键词匹配
    names = {}
    for m in member_pool:
        try:
            detail = xtdata.get_instrument_detail(m)
            if detail:
                names[m] = detail.get("instrumentname", "")
        except Exception:  # noqa: BLE001
            pass
    matched: dict[str, list[str]] = {}
    for slot, kws in SLOT_KEYWORDS.items():
        hits = []
        for code, nm in names.items():
            if any(kw.lower() in nm.lower() for kw in kws):
                hits.append(f"{code} {nm}")
        matched[slot] = sorted(set(hits))
        print(f"\n[{slot}] {len(hits)} hits")
        for h in matched[slot][:25]:
            print("   ", h)
    with (META / "alternative_candidates.json").open("w", encoding="utf-8") as fh:
        json.dump(matched, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
