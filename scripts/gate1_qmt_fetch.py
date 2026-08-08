"""Gate 1 — 用券商 QMT (xtdata) 拉取 16 只 ETF 日线 + 合约元数据（只读）。

与 scripts/gate1_data_fetch.py（AkShare）互为交叉验证源。
输出: data/qmt/raw/*.csv、data/qmt/meta/*.csv（不入库）。
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from xtquant import xtdata

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "qmt" / "raw"
META = ROOT / "data" / "qmt" / "meta"
RAW.mkdir(parents=True, exist_ok=True)
META.mkdir(parents=True, exist_ok=True)

SLOTS = {
    "CN_LARGE": "510300.SH",
    "CN_SMALL": "512100.SH",
    "CN_DIVIDEND": "512890.SH",
    "CHINEXT": "159915.SZ",
    "STAR": "588000.SH",
    "HK_TECH": "513180.SH",
    "HK_DIVIDEND": "03110.HK",
    "US_BROAD": "513500.SH",
    "GOLD": "518880.SH",
    "CN_DURATION": "511260.SH",
    "CASH_LIKE": "511360.SH",
    "SEMICONDUCTOR": "512480.SH",
    "AI": "515070.SH",
    "ROBOTICS": "159770.SZ",
    "BIOTECH": "159992.SZ",
    "AEROSPACE": "512660.SH",
}

FIELDS = ["open", "high", "low", "close", "volume", "amount", "suspendFlag"]
START = "20050101"
END = "20260808"


def qmt_connect() -> None:
    # xtdata 连接本机运行的 QMT/miniQMT 行情服务；失败时抛错。
    dates = xtdata.get_trading_dates("SH", START, END)
    if not dates:
        raise RuntimeError("xtdata trading calendar empty - QMT service unreachable")
    print(f"QMT connected. SH trading days in range: {len(dates)}")


def main() -> None:
    qmt_connect()
    codes = list(SLOTS.values())
    # 批量下载日线到 QMT 本地缓存（只读行情，非交易）
    xtdata.download_history_data2(codes, "1d", START, END, incrementally=True)
    meta_rows = []
    for code in codes:
        detail = xtdata.get_instrument_detail(code) or {}
        meta_rows.append(
            {
                "code": code,
                "instrumentname": detail.get("instrumentname", ""),
                "listeddate": detail.get("listeddate", ""),
                "expiredate": detail.get("expiredate", ""),
                "exchange": detail.get("ExchangeID", ""),
                "type": detail.get("Type", ""),
                "raw": detail,
            }
        )
        print(f"  meta {code}: {detail.get('instrumentname', '?')} listed={detail.get('listeddate', '?')}")
    pd.DataFrame([{k: v for k, v in r.items() if k != "raw"} for r in meta_rows]).to_csv(
        META / "instrument_details.csv", index=False
    )
    # 原始价（dividend_type=none）作为 point-in-time 基准
    raw = xtdata.get_market_data_ex(
        FIELDS, codes, "1d", START, END, dividend_type="none", fill_data=False
    )
    # 前复权用于收益/相关性分析
    front = xtdata.get_market_data_ex(
        FIELDS, codes, "1d", START, END, dividend_type="front", fill_data=False
    )
    summary = []
    for slot, code in SLOTS.items():
        frame = raw.get(code)
        if frame is None or frame.empty:
            print(f"{slot:14s} {code:8s} RAW EMPTY")
            continue
        out = frame.reset_index()
        out.to_csv(RAW / f"{slot}_{code.replace('.', '_')}_raw.csv", index=False)
        fframe = front.get(code)
        if fframe is not None and not fframe.empty:
            fframe.reset_index().to_csv(RAW / f"{slot}_{code.replace('.', '_')}_front.csv", index=False)
        summary.append(
            {
                "slot": slot, "code": code,
                "rows_raw": len(frame),
                "start": str(frame.index[0]),
                "end": str(frame.index[-1]),
            }
        )
        print(f"{slot:14s} {code:8s} raw_rows={len(frame):5d} {frame.index[0]} -> {frame.index[-1]}")
    pd.DataFrame(summary).to_csv(META / "_summary.csv", index=False)


if __name__ == "__main__":
    main()
