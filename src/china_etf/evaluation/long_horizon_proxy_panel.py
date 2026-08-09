"""L2 proxy 研究面板构建（GATE_4_LONG_HORIZON_PROXY_PREP 冻结契约 + PREP_FIX_2）。

性质：SCENARIO_NOT_STRICT_PIT_OOS（Track C scenario proxy research）。
从 data/qmt/proxy/ raw 序列构建统一 price-return 研究面板：
- 统一 SH 交易日历
- A股+利率：T 收盘可用；HK(HSI/HSCEI)/US(513500)/GOLD(518880)/FX：T-1 lag（收盘晚于上海 15:00）
- FX：hkd_cny 用 T-1（与 HK 一致）
- CN_DURATION：单位安全 return-space 公式（y_decimal=y_percent/100, carry=days/365, D=7.5）
- CASH_LIKE：carry-only（SHIBOR O/N 主 + 2Y-carry bridge 于 SHIBOR 前）
- 全部 price-return；income-aware TR 仅作 sensitivity（不在主面板）
- no-lookahead：决策 T 仅用 ≤ 决策可用输入
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
PROXY_DIR = ROOT / "data" / "qmt" / "proxy"

D_EFF = 7.5  # CN_DURATION 冻结久期
SLOT_ORDER = ["CN_LARGE", "CN_SMALL", "CN_DIVIDEND", "CHINEXT", "STAR", "HK_TECH",
              "HK_DIVIDEND", "US_BROAD", "GOLD", "CN_DURATION", "CASH_LIKE"]
# 决策可用首日（A股/利率 T；非A股 T-1）
DECISION_AVAIL = {
    "CN_LARGE": "2005-01-04", "CN_SMALL": "2005-01-04", "CN_DIVIDEND": "2005-01-04",
    "CHINEXT": "2010-06-01", "STAR": "2011-08-02",
    "HK_TECH": "2013-08-20", "HK_DIVIDEND": "2013-08-20",
    "US_BROAD": "2014-01-15", "GOLD": "2013-07-29",
    "CN_DURATION": "2005-01-03", "CASH_LIKE": "2005-01-03",
}
LAG_1_SLOTS = {"HK_TECH", "HK_DIVIDEND", "US_BROAD", "GOLD"}  # T-1 决策可用


def _load_close(slot: str) -> pd.Series:
    """加载 proxy 收盘序列（指数 close / ETF close / 收益率列）。"""
    files = {
        "CN_LARGE": "CN_LARGE_000300_SH.csv", "CN_SMALL": "CN_SMALL_000852_SH.csv",
        "CN_DIVIDEND": "CN_DIVIDEND_000015_SH.csv", "CHINEXT": "CHINEXT_399006_SZ.csv",
        "STAR": "STAR_sh000986.csv", "HK_TECH": "HK_TECH_HSI.csv",
        "HK_DIVIDEND": "HK_DIVIDEND_HSCEI.csv", "US_BROAD": "US_BROAD_513500_SH_price.csv",
        "GOLD": "GOLD_518880_SH_price.csv", "CN_DURATION": "CN_DURATION_CN10Y_yield.csv",
        "CASH_LIKE": "CASH_LIKE_SHIBOR_ON + CN2Y_yield.csv",
    }
    df = pd.read_csv(PROXY_DIR / files[slot])
    dc = "date" if "date" in df.columns else df.columns[0]
    df[dc] = pd.to_datetime(df[dc].astype(str))
    df = df.set_index(dc)
    df.index = df.index.normalize()
    if slot in ("CN_DURATION", "CASH_LIKE"):
        return df  # yield 面板单独处理
    close_col = "close" if "close" in df.columns else df.columns[1]
    return df[close_col].astype(float)


def _build_yield_panel() -> pd.DataFrame:
    """10Y 收益率 + 2Y 收益率 + SHIBOR O/N，先 ffill 再差分（缺日不当作多次冲击）。"""
    cnd = pd.read_csv(PROXY_DIR / "CN_DURATION_CN10Y_yield.csv")
    cash = pd.read_csv(PROXY_DIR / "CASH_LIKE_SHIBOR_ON + CN2Y_yield.csv")
    dc_cnd = "date" if "date" in cnd.columns else cnd.columns[0]
    dc_cash = "date" if "date" in cash.columns else cash.columns[0]
    cnd[dc_cnd] = pd.to_datetime(cnd[dc_cnd].astype(str))
    cash[dc_cash] = pd.to_datetime(cash[dc_cash].astype(str))
    cnd = cnd.set_index(dc_cnd)
    cash = cash.set_index(dc_cash)
    out = pd.concat([cnd[["yield_10y_pct"]], cash[["yield_2y_pct", "shibor_on_pct"]]], axis=1)
    out.index = out.index.normalize()
    return out


def _cn_duration_series(y: pd.DataFrame) -> pd.Series:
    """单位安全久期价格序列（PREP_FIX_2 冻结公式）。

    y_t_decimal = y_t_percent / 100
    Δy_t = y_t_decimal − y_{t-1}_decimal     （缺日先 ffill 再差分）
    carry_t = y_{t-1}_decimal × Δdays/365
    log_return_t = −D_eff × Δy_t + carry_t
    price_t = price_{t-1} × exp(log_return_t)
    """
    yp = y["yield_10y_pct"].ffill()
    ydec = yp / 100.0
    dy = ydec.diff()
    days = yp.index.to_series().diff().dt.days.fillna(1.0)
    carry = ydec.shift(1) * days / 365.0
    log_ret = -D_EFF * dy + carry
    price = np.exp(log_ret.fillna(0.0).cumsum())
    return price


def _cash_like_series(y: pd.DataFrame) -> pd.Series:
    """carry-only 现金（近零久期）：SHIBOR O/N 主 + 2Y carry-only bridge（SHIBOR 前）。"""
    shibor = y["shibor_on_pct"].ffill()
    y2 = y["yield_2y_pct"].ffill()
    days = y.index.to_series().diff().dt.days.fillna(1.0)
    rate = shibor.where(shibor.notna(), y2)  # SHIBOR 前用 2Y carry-only bridge
    r = (rate / 100.0) * days / 365.0
    return np.exp(r.cumsum())


def build_panel() -> tuple[pd.DataFrame, pd.DataFrame, pd.DatetimeIndex]:
    """构建分离的研究面板（BLOCKER 1 修正：信号 vs 收益面板解耦）。

    返回 (signal_panel, return_levels, calendar)：
      signal_panel: 决策可用水平（rolling cov/vol/momentum 用）。HK/US/GOLD/FX 按冻结信息规则
                   lag 1 天（T-1 收盘晚于上海 15:00）→ signal_panel(T) 仅含 ≤T 决策可用信息。
      return_levels: 经济 proxy 原始水平（无信号 lag）→ 已实现收益 price(T)->price(T+1)，
                    与决策 T 的权重对应 T->T+1 区间（评审冻结 return-alignment）。
      calendar: SH 数据日历（L1 日历，含 2026-08-07）。
    """
    # SH 交易日历（决策日历）：用 L1 数据日历（含 2026-08-07）。
    # 注意：QMT get_trading_dates 不含 08-07（滞后一天），而冻结契约末执行日 = 2026-08-07，
    # 且各 proxy 序列/数据均含 08-07 → 以数据日历为准（评审契约 fail-closed 对齐）。
    from china_etf.data.loader import load_research_adj
    cal = load_research_adj().index.normalize()
    assert cal[-1] == pd.Timestamp("2026-08-07"), f"data calendar must end 2026-08-07 (got {cal[-1].date()})"

    y = _build_yield_panel().reindex(cal).ffill()
    cash = _cash_like_series(y)
    dur = _cn_duration_series(y)

    # FX：HKD->CNY（hkd_cny_boc，中行折算价 /100，日频 ffill）。
    # 冻结契约：决策 T 使用 T-1 FX（与 HK 输入一致的保守可用规则，PREP_FIX_2）。
    from china_etf.data.loader import load_fx_hkd_cny
    fx_hkd_cny = load_fx_hkd_cny().reindex(cal).ffill()

    # 原始经济水平（return_panel 用；无信号 lag）。
    # HK 槽位 = raw HKD 指数点数 × HKD/CNY FX（CNY 计价跨资产面板，评审 FX BLOCKER 修正）。
    return_levels: dict[str, pd.Series] = {}
    for slot in SLOT_ORDER:
        if slot == "CN_DURATION":
            return_levels[slot] = dur
        elif slot == "CASH_LIKE":
            return_levels[slot] = cash
        else:
            s = _load_close(slot)
            s = s.reindex(cal).ffill()
            if slot in ("HK_TECH", "HK_DIVIDEND"):
                # 冻结契约：raw_hk_level_cny(t) = raw_hk_index_hkd(t) * hkd_cny(t)
                # FX 序列以决策 T 可用（T-1）——但 return_levels 为原始经济水平（无 lag），
                # 用 T 日 FX（fx 已 reindex 到 cal + ffill；hkd_cny 收盘晚于上海，见 signal 层 T-1）。
                # 冻结要求 return_level_cny(T) 与 signal 解耦；此处 return 用 T 日 FX，
                # signal 层对 HK 额外 shift(1) 实现 FX T-1（见下）。
                s = s * fx_hkd_cny
            return_levels[slot] = s
    return_levels = pd.DataFrame(return_levels)

    # 信号水平（signal_panel 用；HK/US/GOLD/FX lag 1）
    signal: dict[str, pd.Series] = {}
    for slot in SLOT_ORDER:
        s = return_levels[slot].copy()
        if slot in LAG_1_SLOTS:
            s = s.shift(1)  # T-1 决策可用（HK/US/GOLD 收盘晚于上海 15:00）
        signal[slot] = s
    signal_panel = pd.DataFrame(signal)
    return signal_panel, return_levels, cal
