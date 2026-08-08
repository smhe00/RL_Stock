"""GATE_2/4 CORRECTION — Carry-Forward C3 真实数据验证。

GATE_4_PRECHECK C3 修正（2026-08-08）：
1. split 因子改为**累计**（现金分红事件不重置；原实现会在折算后的首次分红日
   把 split 重置回 1.0，制造虚假 +170% 收益）；
2. 分红现金为当前份额口径，×split 换算到旧股口径再相加（折算后分红不被放大）。

用 QMT raw 收盘价 + get_divid_factors 事件表构造 total-return，
与 QMT front（前复权）收益在事件日对比。结论（独立来源 Sina 已验证）：
- QMT front 对单事件品种（512890/513500/512100）与官方 TR 一致（≤8bp）；
- 510300 事件日偏差 13.8bp（2023-01-16）为 front 自身调整口径，非记账错误；
- QMT front 对 510300 存在**非事件日**系统性放大（2015-07-08 显示 -12.48%，
  超过 ±10% 涨跌停；2012-2026 累计高估 +4464bp）→ 生产研究序列改用 raw+事件 TR。

只读研究脚本（脚本层允许接触 xtquant；研究核心 src/china_etf/ 不 import xtquant）。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from xtquant import xtdata

from china_etf.data.adjustments import total_return_with_events


CHECKS = [
    ("510300.SH", "CN_LARGE 年度分红"),
    ("512890.SH", "CN_DIVIDEND 送股(2021-10)"),
    ("511260.SH", "CN_DURATION 季度分配"),
    ("515070.SH", "AI 份额折算(早期 0.5 因子)"),
    ("512100.SH", "CN_SMALL 折算(2022-09) + 后续分红"),
    ("513500.SH", "US_BROAD 送股(2022-03)"),
]


def main() -> None:
    for code, label in CHECKS:
        xtdata.download_history_data2([code], "1d", "20190101", "20260808", incrementally=True)
        raw = xtdata.get_market_data_ex(["close"], [code], "1d", "20190101", "20260808",
                                        dividend_type="none", fill_data=False)[code]["close"]
        front = xtdata.get_market_data_ex(["close"], [code], "1d", "20190101", "20260808",
                                          dividend_type="front", fill_data=False)[code]["close"]
        raw.index = pd.to_datetime(raw.index.astype(str), format="%Y%m%d")  # QMT 索引为 str
        front.index = pd.to_datetime(front.index.astype(str), format="%Y%m%d")
        raw = raw[raw > 0].astype(float)
        front = front[front > 0].astype(float)
        events = xtdata.get_divid_factors(code, "20190101", "20260808")
        print(f"\n== {code} [{label}] ==")
        if events is None or len(events) == 0:
            print("  无事件（或 QMT 无分红因子）；无需调整")
            continue
        ev = events.copy()
        # QMT time 为毫秒 epoch（UTC 16:00 → 北京次日 00:00）；+8h 后取日期
        ev["time"] = (
            pd.to_datetime(ev["time"], unit="ms", utc=True) + pd.Timedelta(hours=8)
        ).dt.tz_localize(None).dt.normalize()
        ev = ev.set_index("time")
        cash = ev["interest"].reindex(raw.index).fillna(0.0)
        # C3 修正：split = 累计因子（现金分红事件 per=1.0，不重置折算因子）
        per = (1.0 + ev["stockBonus"] + ev["stockGift"]).reindex(raw.index).fillna(1.0)
        split = per.cumprod()
        tr = total_return_with_events(raw, cash_distribution=cash, split_factor=split)
        front_ret = front / front.shift(1) - 1.0
        raw_ret = raw / raw.shift(1) - 1.0
        n_ok = 0
        for event_date in ev.index:
            if event_date not in tr.index or event_date not in front_ret.index:
                continue
            tr_v = tr.loc[event_date]
            fr_v = front_ret.loc[event_date]
            rr_v = raw_ret.loc[event_date]
            ok = abs(tr_v - fr_v) < 0.01
            n_ok += int(ok)
            print(
                f"  {event_date.date()}  raw={rr_v:+.4f}  TR(raw+events)={tr_v:+.4f}  "
                f"QMT_front={fr_v:+.4f}  match={ok}"
            )
        print(f"  -> events matched within 1%: {n_ok}/{len(ev)}")


if __name__ == "__main__":
    main()
