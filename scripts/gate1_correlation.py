"""Gate 1 — 相关性分析（ρ120 / ρ250 / downside / tail），基于 QMT 前复权日线。

所有相关性均报告 overlap 区间与观测数（Reviewer §19.4）。
定义（Reviewer §19.5）：
- 全样本相关: Pearson ρ(daily log return)，overlap 期。
- Downside: 限定 CN_LARGE 日收益 < 0 的交易日，Pearson ρ。
- Tail (co-crash): 限定两序列中至少一个位于自身全期收益分位 ≤10% 的日子，Pearson ρ。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "qmt" / "raw"

SLOTS = [
    "CN_LARGE", "CN_SMALL", "CN_DIVIDEND", "CHINEXT", "STAR",
    "HK_TECH", "HK_DIVIDEND", "US_BROAD", "GOLD", "CN_DURATION", "CASH_LIKE",
    "SEMICONDUCTOR", "AI", "ROBOTICS", "BIOTECH", "AEROSPACE",
]


def load_front(slot: str) -> pd.Series:
    def _read(pattern: str) -> pd.Series:
        files = list(RAW.glob(pattern))
        if not files:
            raise FileNotFoundError(f"{slot}: {pattern}")
        df = pd.read_csv(files[0])
        date_col = next((c for c in ("time", "date", "index") if c in df.columns), None)
        if date_col is None:
            raise KeyError(f"no date column in {files[0]}: {list(df.columns)}")
        df = df.rename(columns={date_col: "date"})
        raw_str = df["date"].astype(str).str.strip()
        if raw_str.str.fullmatch(r"\d{8}").all():
            df["date"] = pd.to_datetime(raw_str, format="%Y%m%d")
        else:
            df["date"] = pd.to_datetime(raw_str)
        return df.set_index("date")["close"].sort_index().astype(float)

    try:
        series = _read(f"{slot}_*_front.csv")
        if series.eq(0).all():
            series = _read(f"{slot}_*_raw.csv")
        if series.eq(0).all():
            raise ValueError("all-zero prices")
        return series
    except (FileNotFoundError, ValueError):
        # 回退：sina 提供的港股 ETF 数据
        return _read(f"{slot}_*_sina_qfq.csv")


def main() -> None:
    px = pd.DataFrame({s: load_front(s) for s in SLOTS})
    ret = np.log(px / px.shift(1)).dropna(how="all")
    market = ret["CN_LARGE"]
    n = len(ret)
    end = ret.index[-1]
    rows: list[dict] = []

    pairs = []
    for i, a in enumerate(SLOTS):
        for b in SLOTS[i + 1:]:
            pairs.append((a, b))

    for a, b in pairs:
        pkey = "|".join(sorted((a, b)))
        sub = ret[[a, b]].dropna()
        if len(sub) < 60:
            continue
        # 最近 120 / 250 交易日窗口（truncate 到共同历史）
        for window in (120, 250):
            seg = sub.tail(window) if len(sub) >= window else sub
            r = seg[a].corr(seg[b])
            rows.append(
                {
                    "pair": pkey, "metric": f"rho_{window}",
                    "value": round(r, 4) if np.isfinite(r) else None,
                    "obs": len(seg), "start": str(seg.index[0].date()), "end": str(seg.index[-1].date()),
                }
            )
        # Downside（以 CN_LARGE 为市场代理）
        down_mask = market < 0
        sub_down = sub[down_mask.reindex(sub.index, fill_value=False)]
        if len(sub_down) >= 40:
            r = sub_down[a].corr(sub_down[b])
            rows.append(
                {
                    "pair": pkey, "metric": "downside",
                    "value": round(r, 4) if np.isfinite(r) else None,
                    "obs": len(sub_down), "start": str(sub_down.index[0].date()), "end": str(sub_down.index[-1].date()),
                }
            )
        # Tail (co-crash, 两序列任一处于自身底部 10%)
        q10a = sub[a].quantile(0.10)
        q10b = sub[b].quantile(0.10)
        tail_mask = (sub[a] <= q10a) | (sub[b] <= q10b)
        sub_tail = sub[tail_mask]
        if len(sub_tail) >= 30:
            r = sub_tail[a].corr(sub_tail[b])
            rows.append(
                {
                    "pair": pkey, "metric": "tail",
                    "value": round(r, 4) if np.isfinite(r) else None,
                    "obs": len(sub_tail), "start": str(sub_tail.index[0].date()), "end": str(sub_tail.index[-1].date()),
                }
            )

    out = pd.DataFrame(rows)
    out.to_csv(ROOT / "data" / "qmt" / "meta" / "correlations.csv", index=False)
    print(f"total rows: {len(out)}; obs end date: {end.date()}")
    # 关键重复暴露对（统一按字母序 pair 名）
    key_pairs = {
        frozenset(["CN_LARGE", "GOLD"]), frozenset(["CN_LARGE", "US_BROAD"]),
        frozenset(["CN_LARGE", "CN_DIVIDEND"]), frozenset(["CN_LARGE", "CN_DURATION"]),
        frozenset(["CN_DURATION", "GOLD"]), frozenset(["GOLD", "US_BROAD"]),
        frozenset(["CHINEXT", "SEMICONDUCTOR"]), frozenset(["CHINEXT", "STAR"]),
        frozenset(["HK_TECH", "STAR"]), frozenset(["HK_TECH", "CHINEXT"]),
        frozenset(["SEMICONDUCTOR", "STAR"]), frozenset(["AI", "SEMICONDUCTOR"]),
        frozenset(["ROBOTICS", "AI"]), frozenset(["BIOTECH", "SEMICONDUCTOR"]),
        frozenset(["AEROSPACE", "SEMICONDUCTOR"]), frozenset(["HK_DIVIDEND", "HK_TECH"]),
        frozenset(["CASH_LIKE", "CN_DURATION"]), frozenset(["CN_DIVIDEND", "HK_DIVIDEND"]),
    }
    out["pair_key"] = out["pair"].apply(lambda p: frozenset(p.split("|")))
    key = out[out["pair_key"].isin(key_pairs)]
    print("\n== 关键对 (rho_250 / rho_120 / downside / tail) ==")
    pivot = key.pivot_table(index="pair", columns="metric", values="value").sort_index()
    print(pivot.round(3).to_string())
    print("\n== HK_DIVIDEND 参与的对（验证 fallback）==")
    print(out[out["pair"].str.contains("HK_DIVIDEND")][["pair", "metric", "value"]].to_string(index=False))
    print("\n== ρ250 最高 12 对（重复暴露审查）==")
    top = out[out["metric"] == "rho_250"].sort_values("value", ascending=False).head(12)
    print(top[["pair", "value", "obs"]].to_string(index=False))


if __name__ == "__main__":
    main()
