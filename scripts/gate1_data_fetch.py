"""Gate 1 — Data & Universe Audit: 拉取 ETF 历史行情与元数据（只读研究用途）。

数据来源: AkShare (fund_etf_hist_sina / stock_hk_daily)。
说明: 东方财富 push2his 的 kline 接口（fund_etf_hist_em / stock_hk_hist）对当前
出口 IP 触发反爬拦截（TLS 握手后直接断连），故统一改用 Sina 数据源；列结构略有
不同（date/open/high/low/close/volume/amount），下游按 date 列对齐即可。
输出: data/raw/ 下 CSV（该目录不入库）。
"""

from __future__ import annotations

from pathlib import Path

import akshare as ak
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "data" / "raw"
OUT.mkdir(parents=True, exist_ok=True)

CORE = {
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
}
THEMES = {
    "SEMICONDUCTOR": "512480",
    "AI": "515070",
    "ROBOTICS": "159770",
    "BIOTECH": "159992",
    "AEROSPACE": "512660",
}
ALL = {**CORE, **THEMES}


def fetch_ashare_etf(code: str) -> pd.DataFrame | None:
    try:
        prefix = "sh" if code.startswith("5") else "sz"
        df = ak.fund_etf_hist_sina(symbol=f"{prefix}{code}")
        if df is None or df.empty:
            return None
        df["date"] = pd.to_datetime(df["date"])
        return df[df["date"] >= "2005-01-01"]
    except Exception as exc:  # noqa: BLE001
        print(f"  A-share fetch error {code}: {str(exc)[:160]}")
        return None


def fetch_hk_etf(code: str) -> pd.DataFrame | None:
    try:
        df = ak.stock_hk_daily(symbol=code.replace(".HK", ""), adjust="qfq")
        if df is None or df.empty:
            return None
        df["date"] = pd.to_datetime(df["date"])
        return df[(df["date"] >= "2010-01-01") & (df["date"] <= "2026-08-08")]
    except Exception as exc:  # noqa: BLE001
        print(f"  HK fetch error {code}: {str(exc)[:160]}")
        return None


def main() -> None:
    summary: list[dict[str, object]] = []
    for slot, code in ALL.items():
        df = fetch_hk_etf(code) if code.endswith(".HK") else fetch_ashare_etf(code)
        if df is None or df.empty:
            print(f"{slot} {code}: NO DATA")
            continue
        # 统一列名
        df = df.rename(columns={"日期": "date"})
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        fname = f"{slot}_{code.replace('.', '_')}.csv"
        df.to_csv(OUT / fname, index=False)
        summary.append(
            {
                "slot": slot, "code": code, "rows": len(df),
                "start": str(df["date"].iloc[0].date()),
                "end": str(df["date"].iloc[-1].date()),
            }
        )
        print(f"{slot:14s} {code:8s} rows={len(df):5d} {df['date'].iloc[0].date()} -> {df['date'].iloc[-1].date()}")
    pd.DataFrame(summary).to_csv(OUT / "_summary.csv", index=False)


if __name__ == "__main__":
    main()
