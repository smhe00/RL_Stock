"""Carry-Forward C3 — adjusted price PIT 语义（510300/512890/511260/515070 事件）。"""

import numpy as np
import pandas as pd

from china_etf.data.adjustments import ex_date_return, total_return_with_events


def _series(values, start="2020-01-01") -> pd.Series:
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)))


def test_512890_conversion_tr_flat_across_ex_date() -> None:
    """512890 2021-10-25 送股 1:1（split=2.0）：raw 价格腰斩，但调整后 TR ≈ 0。"""
    # 构造：ex-date 前一天收盘 2.0，除息日开盘 1.0（1:1 送股）
    idx = pd.to_datetime(["2021-10-22", "2021-10-25"])
    raw = pd.Series([2.0, 1.0], index=idx)
    tr = ex_date_return(raw, "2021-10-25", split_factor=2.0, cash=0.0)
    assert np.isclose(tr, 0.0)
    # 未调整的 raw 收益则是 -50%（假跳变）
    raw_tr = raw.iloc[1] / raw.iloc[0] - 1.0
    assert np.isclose(raw_tr, -0.5)


def test_510300_dividend_total_return() -> None:
    """510300 除息：现金分红 0.1/份，价格 4.0→3.95；TR = (3.95+0.1)/4.0 - 1 = +1.25%。"""
    idx = pd.to_datetime(["2026-01-19", "2026-01-20"])
    raw = pd.Series([4.0, 3.95], index=idx)
    tr = ex_date_return(raw, "2026-01-20", split_factor=1.0, cash=0.1)
    assert np.isclose(tr, 0.0125)


def test_total_return_series_with_events() -> None:
    px = _series([10.0, 10.5, 5.0, 5.25])
    split = pd.Series([1.0, 1.0, 2.0, 2.0], index=px.index)  # 第3日 1:1 送股（因子延续）
    tr = total_return_with_events(px, split_factor=split)
    # 送股日：5.0*2/10.5 - 1 ≈ -0.0476（真实价格变动），不是 -52.4%
    assert np.isclose(tr.loc[px.index[2]], 5.0 * 2 / 10.5 - 1.0)
    assert np.isclose(tr.loc[px.index[3]], 5.25 / 5.0 - 1.0)


def test_515070_adjustment_event_no_future_leak() -> None:
    """515070 存在份额折算（QMT front 对早期历史施加常数 0.5 因子）。
    检验：per-asset 收益特征在事件日前后与手工 TR 一致（不泄漏未来）。"""
    idx = pd.to_datetime(["2020-06-30", "2020-07-01", "2020-07-02"])
    raw = pd.Series([2.0, 1.0, 1.02], index=idx)  # 折算：2.0 → 1.0（1:2）
    tr = total_return_with_events(raw, split_factor=pd.Series([1.0, 2.0, 2.0], index=idx))
    r0 = tr.loc[idx[1]]  # 折算日：1.0*2/2.0 - 1 = 0
    r1 = tr.loc[idx[2]]  # 次日：1.02/1.0 - 1 = 2%
    assert np.isclose(r0, 0.0)
    assert np.isclose(r1, 0.02)
    # 若用 raw（无调整），折算日收益为 -50% —— 这正是 C3 禁止的
    assert not np.isclose(raw.iloc[1] / raw.iloc[0] - 1.0, 0.0)
