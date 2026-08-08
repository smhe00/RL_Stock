"""Gate 1 — 03110.HK 历史行情（sina）+ 513500 历史净值/溢价（天天基金直连）。"""

from __future__ import annotations

import time
from pathlib import Path

import akshare as ak
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "qmt" / "raw"
META = ROOT / "data" / "qmt" / "meta"
RAW.mkdir(parents=True, exist_ok=True)
META.mkdir(parents=True, exist_ok=True)


def save_hk_03110() -> None:
    df = ak.stock_hk_daily(symbol="03110", adjust="qfq")
    df = df.rename(columns={"date": "date"})
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df.to_csv(RAW / "HK_DIVIDEND_03110_HK_sina_qfq.csv", index=False)
    print(f"03110.HK sina qfq: rows={len(df)} {df['date'].iloc[0].date()} -> {df['date'].iloc[-1].date()}")


def fetch_nav_history(fund_code: str, page_size: int = 5000) -> pd.DataFrame:
    # 新浪基金净值接口：page + num=200 翻页，全历史可拿
    url = "https://stock.finance.sina.com.cn/fundInfo/api/openapi.php/CaihuiFundInfoService.getNav"
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn/"}
    page = 1
    rows: list[dict] = []
    while True:
        params = {"symbol": fund_code, "page": page, "num": 200}
        for _ in range(5):
            try:
                j = requests.get(url, params=params, headers=headers, timeout=20).json()
                batch = ((j.get("result") or {}).get("data") or {}).get("data") or []
                if batch:
                    break
            except Exception:  # noqa: BLE001
                batch = []
                time.sleep(1.5)
            time.sleep(1.0)
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < 200:
            break
        page += 1
        time.sleep(0.3)
    if not rows:
        raise RuntimeError(f"no NAV history for {fund_code}")
    out = pd.DataFrame(rows)
    out["date"] = pd.to_datetime(out["fbrq"])
    out["nav"] = pd.to_numeric(out["jjjz"], errors="coerce")
    out["acc_nav"] = pd.to_numeric(out["ljjz"], errors="coerce")
    return out[["date", "nav", "acc_nav"]].sort_values("date").reset_index(drop=True)


def premium_stats(price: pd.Series, nav: pd.Series) -> pd.DataFrame:
    price = price[~price.index.duplicated(keep="last")].sort_index()
    nav = nav[~nav.index.duplicated(keep="last")].sort_index()
    joined = pd.concat([price.rename("price"), nav.rename("nav")], axis=1).dropna()
    joined["premium_pct"] = (joined["price"] / joined["nav"] - 1.0) * 100.0
    stats = {
        "obs": len(joined),
        "start": str(joined.index[0].date()),
        "end": str(joined.index[-1].date()),
        "mean_pct": joined["premium_pct"].mean(),
        "p90_pct": joined["premium_pct"].quantile(0.90),
        "p95_pct": joined["premium_pct"].quantile(0.95),
        "p99_pct": joined["premium_pct"].quantile(0.99),
        "min_pct": joined["premium_pct"].min(),
        "max_pct": joined["premium_pct"].max(),
        "last_pct": joined["premium_pct"].iloc[-1],
    }
    print(f"\n513500 premium (price/QMT raw vs NAV/天天基金):")
    for k, v in stats.items():
        if k not in ("obs", "start", "end"):
            stats[k] = round(float(v), 3)
        print(f"  {k}: {v}")
    return joined


def main() -> None:
    save_hk_03110()
    nav = fetch_nav_history("513500")
    nav.to_csv(META / "513500_nav_history.csv", index=False)
    print(f"513500 NAV history: rows={len(nav)} {nav['date'].iloc[0].date()} -> {nav['date'].iloc[-1].date()}")
    price_file = list(RAW.glob("US_BROAD_*_raw.csv"))[0]
    price = pd.read_csv(price_file)
    price = price.rename(columns={"index": "date"})
    price["date"] = pd.to_datetime(price["date"].astype(str), format="%Y%m%d")
    price = price.set_index("date")["close"]
    prem = premium_stats(price, nav.set_index("date")["nav"])
    prem.reset_index().to_csv(META / "513500_premium_series.csv", index=False)


if __name__ == "__main__":
    main()
