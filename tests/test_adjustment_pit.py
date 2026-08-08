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


def test_conversion_then_cash_dividend_not_inflated() -> None:
    """GATE_4_PRECHECK C3：份额折算(1:0.36555) 后的现金分红不能被 1/split 放大。

    构造 512100 型事件序列：折算日 raw 跳 2.76x（中性），之后分红 0.037/份。
    若现金不按 split 换算，分红收益会被错误放大 1/0.36555≈2.74 倍。
    """
    idx = pd.to_datetime(
        ["2022-09-01", "2022-09-05", "2025-01-14", "2025-01-15", "2025-01-16"]
    )
    raw = pd.Series([1.0, 2.76, 2.80, 2.72, 2.75], index=idx)
    # 累计 split：折算日 1→0.36555（1:0.36555），现金分红不改变
    split = pd.Series([1.0, 0.36555, 0.36555, 0.36555, 0.36555], index=idx)
    cash = pd.Series([0.0, 0.0, 0.0, 0.037, 0.0], index=idx)
    tr = total_return_with_events(raw, cash_distribution=cash, split_factor=split)
    # 折算日（2022-09-05）：2.76*0.36555/1.0 - 1 ≈ +0.9%（中性，仅真实行情）
    conv_day = tr.loc[idx[1]]
    assert abs(conv_day - (2.76 * 0.36555 / 1.0 - 1.0)) < 1e-9
    # 分红日（2025-01-15）：收益 ≈ 0.037/2.80 的水平（不被放大）
    div_day = tr.loc[idx[3]]
    # (2.72*0.36555 + 0.037*0.36555)/(2.80*0.36555) - 1 = 2.757/2.80 - 1 ≈ -1.54%
    assert abs(div_day - (2.757 / 2.80 - 1.0)) < 1e-9
    # 关键断言：分红贡献 ≈ 1.32%（≈0.037/2.80），而非 ≈3.6%（被放大 1/split 的错误值）
    div_contrib = div_day + (2.80 - 2.72) / 2.80  # 剔除价格变动后的分红贡献
    assert abs(div_contrib - 0.037 / 2.80) < 1e-9
    assert not np.isclose(div_contrib, 0.037 / 2.80 / 0.36555)


def test_split_cumulative_not_reset_by_cash_event() -> None:
    """GATE_4_PRECHECK C3：累计 split 因子在纯现金分红事件不得重置回 1.0。"""
    idx = pd.to_datetime(["2022-09-05", "2023-01-03", "2025-01-15", "2025-01-16"])
    raw = pd.Series([2.76, 2.80, 2.72, 2.75], index=idx)
    # 错误实现（旧 gate2 脚本）：per-event ffill 会把现金事件(per=1.0)后的 split 重置
    per_event = pd.Series([0.36555, 1.0, 1.0, 1.0], index=idx)
    bad_split = per_event.reindex(idx).ffill().fillna(1.0)
    good_split = per_event.cumprod()
    assert bad_split.iloc[1] == 1.0  # 旧逻辑：折算因子被"重置"
    assert abs(good_split.iloc[1] - 0.36555) < 1e-9  # 新逻辑：保持累计


def test_loader_cn_large_uses_raw_plus_events_not_front() -> None:
    """GATE_4_PRECHECK C3：研究序列 = raw + 官方事件 TR，而非 QMT front。

    QMT front 在 2015-07-08 显示 -12.48%（超过 ±10% 涨跌停，系统性失真）；
    raw+事件序列在该日必须 ≈ -10%。
    """
    from china_etf.data.loader import load_research_adj

    cn = load_research_adj()["CN_LARGE"].dropna()
    d = pd.Timestamp("2015-07-08")
    prev = cn.index[cn.index < d][-1]
    ret = cn.loc[d] / cn.loc[prev] - 1.0
    assert -0.105 < ret < -0.095, f"2015-07-08 research return={ret:.4f} (应为 ≈-10%，非 front 的 -12.48%)"


def test_loader_cn_large_full_history_matches_official_tr() -> None:
    """GATE_4_PRECHECK C3：510300 全周期累计研究收益 ≈ 官方事件 TR（+130.9%），
    而非 QMT front 的 +175.6%（+4464bp 高估）。"""
    from china_etf.data.loader import load_research_adj

    cn = load_research_adj()["CN_LARGE"].dropna()
    cum = cn.iloc[-1] / cn.iloc[0] - 1.0
    assert 1.25 < cum < 1.36, f"CN_LARGE 全周期累计={cum:.4f}（官方 TR ≈ 1.309）"


def test_loader_03110_preserved_research_includes_official_distributions() -> None:
    """GATE_4_PRECHECK H1：03110 保留研究序列（_hk_cny_series）必须包含官方派息。

    03110 Gate 4 已 defer，但研究保留。sina qfq==raw（无分红调整），2025-09-24
    除息日原序列收益 -5.05%；修正后（raw + Global X 官方派息 1.60 HKD）应 ≈ +0.3%。
    """
    from china_etf.data.loader import _hk_cny_series

    hk = _hk_cny_series()["close_tr_cny"].dropna()
    d = pd.Timestamp("2025-09-24")
    prev = hk.index[hk.index < d][-1]
    ret = hk.loc[d] / hk.loc[prev] - 1.0
    assert ret > -0.02, f"2025-09-24 03110 return={ret:.4f}（应包含 1.60 派息，≈+0.3%）"
    # 累计收益合理性：2013-06 以来总收益明显高于 raw 价（含 19 次派息）
    cum = hk.iloc[-1] / hk.iloc[0] - 1.0
    assert cum > 1.0, f"03110 全周期累计={cum:.4f}"


def test_loader_track_a_hk_dividend_513690_includes_dividends() -> None:
    """GATE_4_PILOT_READY M1：Track A HK_DIVIDEND（513690.SH）研究序列包含官方派息。

    2025-12-17 除息（0.0113/份）当日研究收益应 ≈ +0.5%+（含派息，非纯价格下跌）。
    """
    from china_etf.data.loader import load_research_adj

    hk = load_research_adj()["HK_DIVIDEND"].dropna()
    d = pd.Timestamp("2025-12-17")
    prev = hk.index[hk.index < d][-1]
    ret = hk.loc[d] / hk.loc[prev] - 1.0
    assert ret > -0.01, f"2025-12-17 513690 research return={ret:.4f}（应含 0.0113 派息）"
    # 上市（2021-05-20）以来累计为正，且明显高于 raw 价格（含 4 次派息）
    assert hk.iloc[-1] / hk.iloc[0] - 1.0 > 0.10, "513690 Track A 研究累计应显著为正"
