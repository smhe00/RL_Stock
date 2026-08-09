"""GATE_4_LONG_HORIZON_PROXY — L2 场景 proxy 数据抓取 + 落盘（带 provenance）。

数据源优先级（用户指示）：miniQMT（xtdata）优先；QMT 无则 akshare（新浪）；真实 ETF 覆盖用真实。
本脚本是只读 fetch，输出到 data/qmt/proxy/（tracked 可选，见 packet）：
  面板研究序列（研究复权 proxy 构建在 runner 中，本脚本仅落盘 raw 代理序列 + provenance.json）

每序列记录 provenance：
  slot / proxy / source / provider / fetch_date / data_start / data_end / is_backfilled / price_or_return / note
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
PROXY_DIR = ROOT / "data" / "qmt" / "proxy"
PROXY_DIR.mkdir(parents=True, exist_ok=True)

START = "20050101"
END = "20260807"

# 槽位 -> (proxy, 数据源, 是否 backfilled)
SLOT_PROXY = {
    "CN_LARGE": ("000300.SH", "QMT", False),
    "CN_SMALL": ("000852.SH", "QMT", True),     # 中证1000 发布 2014-10，之前回溯编制
    "CN_DIVIDEND": ("000015.SH", "QMT", False),  # 上证红利
    "CHINEXT": ("399006.SZ", "QMT", False),
    "STAR": ("sh000986", "sina", False),         # 中证全指信息技术（2011-08 起连续）
    "HK_TECH": ("HSI", "sina_hk", False),        # 恒生指数
    "HK_DIVIDEND": ("HSCEI", "sina_hk", False),  # 恒生中国企业
    "US_BROAD": ("513500.SH_price", "qmt_existing", False),   # 真实 ETF price
    "GOLD": ("518880.SH_price", "qmt_existing", False),       # 真实 ETF price
    "CN_DURATION": ("CN10Y_yield", "akshare_yield", False),   # 10Y 收益率 → 久期 proxy（runner 构造）
    "CASH_LIKE": ("SHIBOR_ON + CN2Y_yield", "akshare_yield", False),  # carry-only（runner 构造）
}


def fetch_sina_index(code: str) -> pd.DataFrame:
    import akshare as ak
    df = ak.stock_zh_index_daily(symbol=code)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")


def fetch_sina_hk_index(code: str) -> pd.DataFrame:
    import akshare as ak
    df = ak.stock_hk_index_daily_sina(symbol=code)
    df = df.rename(columns={df.columns[0]: "date"})
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")


def fetch_akshare_yield() -> pd.DataFrame:
    """中国国债收益率（2Y/5Y/10Y/30Y）+ SHIBOR O/N，日频。

    用位置索引取列（列名为中文，Windows 终端下字符串字面量可能乱码）：bond_zh_us_rate
    列序 = [日期, 中国2年, 中国5年, 中国10年, 中国30年, ...]；shibor 列序 = [日期, O/N-利率, ...]。
    """
    import akshare as ak
    y = ak.bond_zh_us_rate(start_date=START)
    y = y.rename(columns={y.columns[0]: "date"})
    y["date"] = pd.to_datetime(y["date"])
    y = y.set_index("date")
    y = y.rename(columns={y.columns[0]: "yield_2y_pct", y.columns[1]: "yield_5y_pct",
                          y.columns[2]: "yield_10y_pct", y.columns[3]: "yield_30y_pct"})
    s = ak.macro_china_shibor_all()
    s = s.rename(columns={s.columns[0]: "date"})
    s["date"] = pd.to_datetime(s["date"])
    s = s.set_index("date")
    s = s.rename(columns={s.columns[0]: "shibor_on_pct"})
    return pd.concat([y, s], axis=1)


def fetch_qmt_index(code: str) -> pd.DataFrame:
    from xtquant import xtdata
    xtdata.download_history_data2([code], "1d", START, END, incrementally=True)
    d = xtdata.get_market_data_ex(["open", "high", "low", "close"], [code], "1d",
                                  START, END, dividend_type="none")
    df = d.get(code)
    if df is None or len(df) == 0:
        raise RuntimeError(f"QMT empty for {code}")
    out = df.reset_index()
    out.columns = [str(c).lower() for c in out.columns]
    out = out.rename(columns={"index": "date"})
    out["date"] = pd.to_datetime(out["date"])
    return out.set_index("date")


def main() -> None:
    prov = {"fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"), "slots": {}}
    for slot, (proxy, source, backfilled) in SLOT_PROXY.items():
        try:
            if source == "QMT":
                df = fetch_qmt_index(proxy)
            elif source == "sina":
                df = fetch_sina_index(proxy)
            elif source == "sina_hk":
                df = fetch_sina_hk_index(proxy)
            elif source == "akshare_yield":
                y = fetch_akshare_yield()
                if slot == "CN_DURATION":
                    df = y[["yield_10y_pct"]]
                else:
                    # CASH_LIKE: SHIBOR O/N + 2Y 收益率 carry（runner 按日期选择）
                    df = y[["yield_2y_pct", "shibor_on_pct"]]
                df = df.dropna(how="all")
            elif source == "qmt_existing":
                raw = ROOT / "data" / "qmt" / "raw"
                inst = proxy.replace("_price", "").replace(".SH", "").replace(".", "_")
                f = raw / f"{slot}_{inst}_SH_raw.csv"
                df = pd.read_csv(f)
                dc = next(c for c in ("index", "time", "date") if c in df.columns)
                df = df.rename(columns={dc: "date"})
                df["date"] = pd.to_datetime(df["date"].astype(str))
                df = df.set_index("date")
            else:
                raise RuntimeError(f"unhandled source {source}")
            fname = f"{slot}_{proxy.replace('.', '_')}.csv"
            df.to_csv(PROXY_DIR / fname)
            prov["slots"][slot] = {
                "proxy": proxy, "source": source, "rows": int(len(df)),
                "start": str(df.index[0].date()), "end": str(df.index[-1].date()),
                "is_backfilled_before_launch": backfilled,
                "cols": [str(c) for c in df.columns],
            }
            print(f"{slot:14s} {proxy:20s} {len(df):5d} {df.index[0].date()} -> {df.index[-1].date()}")
        except Exception as exc:  # noqa: BLE001
            prov["slots"][slot] = {"proxy": proxy, "source": source, "error": str(exc)[:120]}
            print(f"{slot:14s} {proxy:20s} FAIL {type(exc).__name__}: {str(exc)[:90]}")

    (PROXY_DIR / "provenance.json").write_text(
        json.dumps(prov, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\n-> {PROXY_DIR}")


if __name__ == "__main__":
    main()
