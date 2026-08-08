"""分红/拆分/折算 → total-return 序列（D-009 / Carry-Forward C3）。

纯函数，不依赖 xtquant。TR_t = (P_t*S_t + Cash_t*S_t)/(P_{t-1}*S_{t-1}) - 1。

GATE_4_PRECHECK C3 修正（2026-08-08）：
- `split_factor` 语义 = **累计**送转/折算因子（当前份额/旧份额），现金分红事件不改变它；
- 分红现金 `cash` 为**当前份额**口径（每份 X 元），按 `split` 换算到旧股口径再相加，
  否则份额折算后的后续分红会被错误放大 1/split 倍。

验证（独立来源 Sina raw + Sina 官方派息）：
- 510300 2023-01-16 独立 TR=(4.143+0.064)/4.144-1=+1.5203% == 本公式；
- QMT front 该日 +1.66%（+13.8bp）为其自身调整口径偏差，非 corporate-action 记账错误；
- 512100 折算(0.36555)+后续分红(0.037/0.041) 组合下，本公式与 front 累计差 ≤8bp。
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def total_return_with_events(
    raw_close: pd.Series,
    *,
    cash_distribution: pd.Series | None = None,  # 除息日 → 每股现金（instrument 币种）
    split_factor: pd.Series | None = None,  # 事件日 → 送转/折算后每股对应旧股数（如 1:1 送股 = 2.0）
) -> pd.Series:
    """在除权除息日还原 total return。

    split_factor 为**累计**因子（现金分红事件不更新），例如 1:1 送股后恒为 2.0；
    cash_distribution 为当前份额口径，内部按 split 换算到旧股口径。
    """
    p = raw_close.astype(float).sort_index()
    cash = (
        cash_distribution if cash_distribution is not None else pd.Series(dtype=float)
    ).reindex(p.index, fill_value=0.0)
    # split_factor 为累计调整因子（事件日后延续，现金分红不重置），缺失=1.0
    split = (
        split_factor if split_factor is not None else pd.Series(dtype=float)
    ).reindex(p.index).ffill().fillna(1.0)
    prev_p = p.shift(1)
    prev_split = split.shift(1)
    # C3 修正：现金为当前份额口径，×split 换算到旧股口径（份额折算后分红不被放大）
    tr = (p * split + cash * split) / (prev_p * prev_split) - 1.0
    return tr.dropna()


def ex_date_return(raw_close: pd.Series, event_date, *, split_factor: float = 1.0, cash: float = 0.0) -> float:
    """除权除息日经调整后收益（不含信息泄露）：(P_t*S+C*S)/(P_{t-1}) - 1。"""
    idx = list(raw_close.index)
    if event_date not in raw_close.index:
        raise KeyError(event_date)
    i = raw_close.index.get_loc(event_date)
    if i == 0:
        return float("nan")
    p_prev = float(raw_close.iloc[i - 1])
    p_curr = float(raw_close.iloc[i])
    return (p_curr * split_factor + cash * split_factor) / p_prev - 1.0
