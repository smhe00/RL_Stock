"""Gate 1 Corrections — 数据定义修正：ADV20/60、AUM(NAV-based)、相关性核验、新 tail 指标、分红抽查。"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from xtquant import xtdata

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "qmt" / "raw"
META = ROOT / "data" / "qmt" / "meta"

PREFERRED = {
    "CN_LARGE": "510300.SH", "CN_SMALL": "512100.SH", "CN_DIVIDEND": "512890.SH",
    "CHINEXT": "159915.SZ", "STAR": "588000.SH", "HK_TECH": "513180.SH",
    "HK_DIVIDEND": "03110.HK", "US_BROAD": "513500.SH", "GOLD": "518880.SH",
    "CN_DURATION": "511260.SH", "CASH_LIKE": "511360.SH",
    "SEMICONDUCTOR": "512480.SH", "AI": "515070.SH", "ROBOTICS": "159770.SZ",
    "BIOTECH": "159992.SZ", "AEROSPACE": "512660.SH",
}


def read_daily(slot: str, adjusted: bool = True) -> pd.DataFrame:
    """读行情序列。adjusted=True：A股用 QMT front（研究/收益），港股用 sina qfq；
    adjusted=False：QMT raw（执行/溢价基准）。"""
    sina = list(RAW.glob(f"{slot}_*_sina_qfq.csv"))
    if sina:
        files = sina
    elif adjusted:
        files = list(RAW.glob(f"{slot}_*_front.csv")) or list(RAW.glob(f"{slot}_*_raw.csv"))
    else:
        files = list(RAW.glob(f"{slot}_*_raw.csv"))
    df = pd.read_csv(files[0])
    dc = next((c for c in ("index", "time", "date") if c in df.columns))
    df = df.rename(columns={dc: "date"})
    raw = df["date"].astype(str).str.strip()
    df["date"] = (
        pd.to_datetime(raw, format="%Y%m%d") if raw.str.fullmatch(r"\d{8}").all()
        else pd.to_datetime(raw)
    )
    df = df.sort_values("date").reset_index(drop=True)
    return df


def nav_history(fund_code: str) -> pd.Series:
    url = "https://stock.finance.sina.com.cn/fundInfo/api/openapi.php/CaihuiFundInfoService.getNav"
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn/"}
    rows: list[dict] = []
    page = 1
    while True:
        j = requests.get(url, params={"symbol": fund_code, "page": page, "num": 200}, headers=headers, timeout=20).json()
        batch = ((j.get("result") or {}).get("data") or {}).get("data") or []
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < 200:
            break
        page += 1
        time.sleep(0.25)
    out = pd.DataFrame(rows)
    s = pd.Series(pd.to_numeric(out["jjjz"], errors="coerce").values, index=pd.to_datetime(out["fbrq"]))
    return s[~s.index.duplicated(keep="last")].sort_index()


def nav_latest_eastmoney(fund_code: str) -> float | None:
    """回退：东财 lsjz 第一页取最新单位净值（限流时等待重试）。"""
    url = "https://api.fund.eastmoney.com/f10/lsjz"
    headers = {"Referer": "https://fundf10.eastmoney.com/", "User-Agent": "Mozilla/5.0"}
    for _ in range(6):
        try:
            j = requests.get(
                url, params={"fundCode": fund_code, "pageIndex": 1, "pageSize": 49},
                headers=headers, timeout=20,
            ).json()
            batch = (j.get("Data") or {}).get("LSJZList") or []
            if batch:
                return float(batch[0]["DWJZ"])
        except Exception:  # noqa: BLE001
            pass
        time.sleep(6)
    return None


def liquidity_aum() -> pd.DataFrame:
    # 03110.HK 官方口径覆盖（Global X 2026-01 月报）
    HK_OVERRIDE = {
        "shares_outstanding": 196_000_000.0,
        "nav_latest": 30.33,
        "aum_nav_based": 196_000_000.0 * 30.33,
        "aum_source": "GlobalX 月报 2026-01（发行股数×NAV，HKD）",
    }
    rows: list[dict] = []
    for slot, code in PREFERRED.items():
        df = read_daily(slot)
        amount = pd.to_numeric(df["amount"], errors="coerce")
        last = df.iloc[-1]
        shares = 0.0
        if not code.endswith(".HK"):
            detail = xtdata.get_instrument_detail(code) or {}
            shares = float(detail.get("TotalVolume") or 0.0)
        nav_latest = float("nan")
        nav_date = ""
        aum_source = "sina NAV × TotalVolume"
        if code.endswith(".HK"):
            nav_latest = HK_OVERRIDE["nav_latest"]
            shares = HK_OVERRIDE["shares_outstanding"]
            nav_date = "2026-01"
            aum_source = HK_OVERRIDE["aum_source"]
        else:
            fund_code = code.split(".")[0]
            nav = nav_history(fund_code)
            if len(nav):
                nav_latest = float(nav.iloc[-1])
                nav_date = str(nav.index[-1].date())
            else:
                em = nav_latest_eastmoney(fund_code)
                if em is not None:
                    nav_latest = em
                    aum_source = "eastmoney lsjz latest"
                else:
                    aum_source = "NAV NOT AVAILABLE (sina/eastmoney failed)"
        rows.append(
            {
                "slot": slot, "code": code,
                "turnover_value_1d": float(amount.iloc[-1]),
                "adv20": float(amount.tail(20).mean()),
                "adv60": float(amount.tail(60).mean()),
                "median_turnover_60": float(amount.tail(60).median()),
                "shares_outstanding": shares,
                "last_close": float(last["close"]),
                "nav_latest": nav_latest,
                "nav_date": nav_date,
                "aum_nav_based": shares * nav_latest if shares and nav_latest == nav_latest else None,
                "market_cap": shares * float(last["close"]) if shares else None,
                "aum_source": aum_source,
            }
        )
        print(f"{slot:14s} {code:8s} adv20={rows[-1]['adv20']:.0f} adv60={rows[-1]['adv60']:.0f} "
              f"aum_nav={rows[-1]['aum_nav_based']} mktcap={rows[-1]['market_cap']}")
    out = pd.DataFrame(rows)
    out.to_csv(META / "liquidity_aum_correction.csv", index=False)
    return out


def alts_adv20() -> None:
    cand = pd.read_csv(META / "alternative_candidates.csv")
    top = cand.groupby("slot").head(3)
    codes = {str(c).zfill(6) + (".SH" if str(c).startswith(("5", "6")) else ".SZ") for c in top["code"]}
    codes = {c for c in codes if not c.endswith(".HK")}
    print(f"\nalternative codes to fetch: {len(codes)}")
    rows = []
    for code in sorted(codes):
        try:
            xtdata.download_history_data2([code], "1d", "20240101", "20260808", incrementally=True)
            d = xtdata.get_market_data_ex(["amount"], [code], "1d", "20240101", "20260808", dividend_type="none", fill_data=False)
            f = d.get(code)
            if f is None or f.empty:
                continue
            amt = f["amount"].dropna()
            detail = xtdata.get_instrument_detail(code) or {}
            rows.append(
                {
                    "code": code,
                    "name": detail.get("InstrumentName", ""),
                    "list_date": detail.get("OpenDate", ""),
                    "adv20": float(amt.tail(20).mean()) if len(amt) >= 20 else None,
                }
            )
        except Exception as exc:  # noqa: BLE001
            print("  fetch fail", code, str(exc)[:80])
    out = pd.DataFrame(rows)
    out.to_csv(META / "alternatives_adv20.csv", index=False)
    print(out.to_string(index=False))


def correlation_verify_and_tail() -> None:
    slots = list(PREFERRED.keys())
    px = {}
    for s in slots:
        df = read_daily(s, adjusted=True)
        px[s] = df.set_index("date")["close"].astype(float)
    ret = np.log(pd.DataFrame(px) / pd.DataFrame(px).shift(1)).dropna(how="all")
    market = ret["CN_LARGE"]
    key_pairs = [
        ("SEMICONDUCTOR", "STAR"), ("AI", "STAR"), ("AI", "SEMICONDUCTOR"),
        ("CHINEXT", "CN_LARGE"), ("AI", "CHINEXT"), ("CHINEXT", "STAR"),
        ("CN_LARGE", "CN_SMALL"), ("CN_SMALL", "ROBOTICS"), ("AI", "CN_LARGE"),
        ("CN_LARGE", "CN_DIVIDEND"), ("CN_LARGE", "CN_DURATION"), ("CN_LARGE", "GOLD"),
        ("CN_LARGE", "US_BROAD"), ("GOLD", "US_BROAD"), ("HK_DIVIDEND", "HK_TECH"),
        ("HK_DIVIDEND", "CN_DURATION"), ("HK_DIVIDEND", "GOLD"), ("CASH_LIKE", "CN_DURATION"),
    ]
    rows_all: list[dict] = []
    print("\n== 相关性核验（adjusted 序列；独立 pandas 计算；4 位小数）==")
    print(f"{'pair':24s} {'rho120':>8s} {'rho250':>8s} {'n120':>5s} {'n250':>5s} {'start250':>10s} {'end250':>10s}")
    for a, b in key_pairs:
        sub = ret[[a, b]].dropna()
        s120, s250 = sub.tail(120), sub.tail(250)
        r120, r250 = s120[a].corr(s120[b]), s250[a].corr(s250[b])
        print(f"{a+'|'+b:24s} {r120:8.4f} {r250:8.4f} {len(s120):5d} {len(s250):5d} {str(s250.index[0].date()):>10s} {str(s250.index[-1].date()):>10s}")
        down = sub[market < 0]
        stress = sub[market <= market.quantile(0.10)]
        qa, qb = sub[a].quantile(0.10), sub[b].quantile(0.10)
        ia, ib = (sub[a] <= qa).astype(int), (sub[b] <= qb).astype(int)
        p_both = (ia & ib).mean()
        p_a_given_b = float(ia[ib == 1].mean()) if ib.sum() else float("nan")
        p_b_given_a = float(ib[ia == 1].mean()) if ia.sum() else float("nan")
        rows_all.append(
            {
                "pair": f"{a}|{b}",
                "rho_120": round(float(r120), 4),
                "rho_250": round(float(r250), 4),
                "n_120": len(s120), "start_120": str(s120.index[0].date()), "end_120": str(s120.index[-1].date()),
                "n_250": len(s250), "start_250": str(s250.index[0].date()), "end_250": str(s250.index[-1].date()),
                "cn_large_downside_corr": round(float(down[a].corr(down[b])), 4),
                "cn_large_stress_corr_q10": round(float(stress[a].corr(stress[b])), 4),
                "lower_tail_co_exceedance_p_a_given_b": round(p_a_given_b, 4),
                "lower_tail_co_exceedance_p_b_given_a": round(p_b_given_a, 4),
                "tail_dependence_score_p_both_p10sq": round(float(p_both / 0.01), 3),
            }
        )
    tdf = pd.DataFrame(rows_all)
    tdf.to_csv(META / "tail_metrics_correction.csv", index=False)
    print("\n== 新 tail / stress 指标（关键对；CN_LARGE 条件化）==")
    print(tdf.to_string(index=False))


def dividend_spot_checks() -> None:
    checks = [("510300.SH", "CN_LARGE 普通股票ETF(年度分红)"),
              ("512890.SH", "CN_DIVIDEND 红利低波(2021-10 送股)"),
              ("511260.SH", "CN_DURATION 债券ETF(季度分配)"),
              ("159915.SZ", "CHINEXT 创业板(普通股票)")]
    print("\n== 分红/除息 adjustment 抽查（QMT get_divid_factors + raw/qfq 表现）==")
    for code, label in checks:
        df = xtdata.get_divid_factors(code, "20190101", "20260808")
        n = len(df) if hasattr(df, "__len__") else 0
        print(f"\n[{code}] {label} — events={n}")
        if n:
            print(df[["time", "interest", "stockBonus", "stockGift", "dr"]].to_string(index=False))


def main() -> None:
    for fn in (liquidity_aum, alts_adv20, correlation_verify_and_tail, dividend_spot_checks):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            print(f"[section failed] {fn.__name__}: {exc!r}")


if __name__ == "__main__":
    main()
