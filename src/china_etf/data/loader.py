"""Gate 3 真实数据加载器（读本地 data/qmt 快照，不连 QMT）。

研究序列（research_total_return_series）：
  - A股 ETF：QMT raw 收盘 + 官方公司行为事件表（data/qmt/meta/divid_events/）→
    total-return 水平指数（GATE_4_PRECHECK C3 修正）。
    原因：QMT front 对多事件品种存在系统性日收益放大（510300 2015-07-08 显示
    -12.48% 超过 ±10% 涨跌停；2012-2026 累计高估 +4464bp），不能用。
  - HK_DIVIDEND(03110.HK)：sina 收盘（raw）+ Global X/HKEX 官方派息（divid_events/03110.HK.csv）
    → 总收益指数 × HKD/CNY（中行折算价/100）。
    原因（GATE_4_PRECHECK H1）：akshare `stock_hk_daily(adjust="qfq")` 对 03110 返回的
    就是 raw（OHLC 全列逐位相同，未做任何分红调整），除息日系统性漏掉派息
    （2025-09-24 漏 531bp、2024-09-24 漏 599bp、2022-09-26 漏 671bp）。
执行价格（execution_price_series）：
  - A股：QMT raw open/close；03110：sina open/close × FX
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "qmt" / "raw"
META = ROOT / "data" / "qmt" / "meta"
EVENTS = META / "divid_events"

# P4：Slot → 研究序列映射（禁止静默 drop；ActionDim 恒 11）
SLOT_MAP: dict[str, dict] = {
    "CN_LARGE": {"instrument": "510300.SH", "source": "QMT raw + official events TR", "currency": "CNY"},
    "CN_SMALL": {"instrument": "512100.SH", "source": "QMT raw + official events TR", "currency": "CNY"},
    "CN_DIVIDEND": {"instrument": "512890.SH", "source": "QMT raw + official events TR", "currency": "CNY"},
    "CHINEXT": {"instrument": "159915.SZ", "source": "QMT raw (=front, no events)", "currency": "CNY"},
    "STAR": {"instrument": "588000.SH", "source": "QMT raw (=front, no events)", "currency": "CNY"},
    "HK_TECH": {"instrument": "513180.SH", "source": "QMT raw (=front, no events)", "currency": "CNY"},
    "HK_DIVIDEND": {"instrument": "513690.SH", "source": "QMT raw + official events TR (Track A mainland wrapper; 03110 deferred)", "currency": "CNY"},
    "US_BROAD": {"instrument": "513500.SH", "source": "QMT raw + official events TR", "currency": "CNY"},
    "GOLD": {"instrument": "518880.SH", "source": "QMT raw (=front, no events)", "currency": "CNY"},
    "CN_DURATION": {"instrument": "511260.SH", "source": "QMT raw + official events TR", "currency": "CNY"},
    "CASH_LIKE": {"instrument": "511360.SH", "source": "QMT raw (=front, no events)", "currency": "CNY"},
}


def _read_csv(pattern: str) -> pd.DataFrame:
    files = list(RAW.glob(pattern))
    if not files:
        raise FileNotFoundError(pattern)
    df = pd.read_csv(files[0])
    dc = next((c for c in ("index", "time", "date") if c in df.columns))
    df = df.rename(columns={dc: "date"})
    raw = df["date"].astype(str).str.strip()
    df["date"] = (
        pd.to_datetime(raw, format="%Y%m%d")
        if raw.str.fullmatch(r"\d{8}").all()
        else pd.to_datetime(raw)
    )
    return df.sort_values("date").set_index("date")


def _slot_raw_file(slot: str, suffix: str = "raw") -> str:
    """按 instrument 构造精确文件名，避免 glob 命中同一 slot 的历史 instrument（如 03110 vs 513690）。"""
    inst = SLOT_MAP[slot]["instrument"]
    return f"{slot}_{inst.replace('.', '_')}_{suffix}.csv"


def load_fx_hkd_cny() -> pd.Series:
    df = pd.read_csv(META / "hkd_cny_boc.csv", parse_dates=["日期"])
    s = pd.Series(
        (pd.to_numeric(df["中行折算价"], errors="coerce") / 100.0).to_numpy(),
        index=pd.to_datetime(df["日期"]),
    )
    return s[~s.index.duplicated(keep="last")].sort_index()


def _load_events(instrument: str) -> pd.DataFrame | None:
    """QMT 公司行为事件表（本地固化；研究核心不 import xtquant，EXECUTION_SPEC §50）。"""
    path = EVENTS / f"{instrument}.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, parse_dates=["date"])
    return df.sort_values("date").reset_index(drop=True)


def total_return_index(raw_close: pd.Series, events: pd.DataFrame | None) -> pd.Series:
    """raw 收盘 + 官方事件 → 总收益水平指数（GATE_4_PRECHECK C3 修正公式）。

    TR_t = (P_t*S_t + Cash_t*S_t)/(P_{t-1}*S_{t-1}) - 1；S=累计折算因子；
    index_t = index_{t-1} * (1 + TR_t)，首值 = raw 首值（保持尺度连续）。
    """
    p = raw_close.astype(float)
    if events is None or len(events) == 0:
        return p
    ev = events.set_index("date")
    per = (1.0 + ev["stockBonus"] + ev["stockGift"]).reindex(p.index).fillna(1.0)
    split = per.cumprod()
    cash = ev["interest"].reindex(p.index).fillna(0.0)
    tr = (p * split + cash * split) / (p.shift(1) * split.shift(1)) - 1.0
    idx = (1.0 + tr.fillna(0.0)).cumprod() * p.iloc[0]
    return idx


def _hk_cny_series() -> pd.DataFrame:
    """03110 保留研究序列（H1 成果；Gate 4 已 defer，供 wrapper-equivalence audit 用）。"""
    hk = _read_csv("HK_DIVIDEND_03110_HK_sina_qfq.csv")  # 03110 sina 收盘（qfq==raw，H1 已验证）
    fx = load_fx_hkd_cny()
    fx = fx.reindex(hk.index).ffill()
    out = pd.DataFrame(index=hk.index)
    # H1 修正：raw + 官方派息 → 总收益水平指数（HKD），再 × FX → CNY
    events = _load_events("03110.HK")
    tr_idx_hkd = total_return_index(hk["close"], events)
    # 执行价必须用 raw 成交价（×FX）；研究序列用总收益指数
    out["open"] = hk["open"] * fx
    out["close"] = hk["close"] * fx
    out["close_tr_cny"] = tr_idx_hkd * fx
    out["close_hkd"] = hk["close"]
    return out


def load_research_adj() -> pd.DataFrame:
    """11 slots 研究复权收盘（CNY）。

    C3 修正后：全部 = QMT raw + 官方事件 total-return 指数（不用 QMT front）；
    HK_DIVIDEND = 513690.SH（境内 Track A wrapper；03110 已 defer）。
    """
    px = {}
    for slot, meta in SLOT_MAP.items():
        raw_close = _read_csv(_slot_raw_file(slot))["close"].astype(float)
        px[slot] = total_return_index(raw_close, _load_events(meta["instrument"]))
    adj = pd.DataFrame(px).sort_index()
    return _fill_gaps_after_listing(adj)


def _fill_gaps_after_listing(df: pd.DataFrame) -> pd.DataFrame:
    """联合日历对齐：上市后缺口（市场休市/数据缺失）ffill；上市前保持 NaN。"""
    out = df.copy()
    for col in out.columns:
        first = out[col].first_valid_index()
        if first is not None:
            out.loc[first:, col] = out.loc[first:, col].ffill()
    return out


def load_execution_prices() -> tuple[dict[str, pd.Series], dict[str, pd.Series]]:
    opens, closes = {}, {}
    for slot, meta in SLOT_MAP.items():
        inst = meta["instrument"]
        df = _read_csv(_slot_raw_file(slot))
        opens[inst] = df["open"].astype(float)
        closes[inst] = df["close"].astype(float)
    opens = {k: _fill_series_gaps(v) for k, v in opens.items()}
    closes = {k: _fill_series_gaps(v) for k, v in closes.items()}
    return opens, closes


def _fill_series_gaps(s: pd.Series) -> pd.Series:
    df = s.to_frame("v")
    return _fill_gaps_after_listing(df)["v"]


def slot_manifest() -> pd.DataFrame:
    rows = []
    for slot, meta in SLOT_MAP.items():
        adj = load_research_adj()[slot].dropna()
        rows.append(
            {
                "asset_slot": slot,
                "instrument": meta["instrument"],
                "source": meta["source"],
                "currency": meta["currency"],
                "start": str(adj.index[0].date()),
                "end": str(adj.index[-1].date()),
                "rows": int(len(adj)),
            }
        )
    return pd.DataFrame(rows)
