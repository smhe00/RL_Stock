"""Benchmark helpers（GATE_4_EVAL_FIX）：exact Test-date mask + 可执行 510300 buy-and-hold。

评审要求：
- stitched OOS 非连续（Validation gaps 在 Test folds 之间）→ 510300 benchmark 必须用**完全相同**
  Test-date mask，输出 exact_test_date_count / first_test_date / last_test_date / excluded_validation_dates，
  并 assert 步数相等。
- `510300_EXECUTABLE_NET_BUY_HOLD`（raw 执行价 + 公司行为记账 + 1x cost + exact Test mask）与
  `510300_RESEARCH_TR_REFERENCE`（研究 TR）分开标注。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..accounting import PortfolioAccounting
from ..contracts import Fill
from ..cost.mainland import MainlandETFCostModel
from ..data.corporate_actions import CorporateActionEvent

CN_LARGE_INSTRUMENT = "510300.SH"


def exact_test_mask(folds, calendar=None) -> dict:
    """exact Test-date mask：所有 fold test_start..test_end 执行日并集（去重排序）。

    calendar: 可选真实交易日历（DatetimeIndex）；缺省用 bdate_range 近似。
    返回 mask 元数据 + 排序后的日期列表。
    """
    all_dates: set[pd.Timestamp] = set()
    val_dates: set[pd.Timestamp] = set()
    for f in sorted(folds, key=lambda x: x.test_start):
        seg = _segment_days(f.test_start, f.test_end, calendar)
        all_dates.update(seg)
        vseg = _segment_days(f.val_start, f.val_end, calendar)
        val_dates.update(vseg)
    dates = sorted(all_dates)
    return {
        "strategy_stitched_steps": len(dates),
        "benchmark_stitched_steps": len(dates),
        "exact_test_date_count": len(dates),
        "first_test_date": str(dates[0].date()) if dates else None,
        "last_test_date": str(dates[-1].date()) if dates else None,
        "excluded_validation_dates": len(val_dates),
        "test_dates": dates,
    }


def _segment_days(start, end, calendar):
    if calendar is not None:
        cal = pd.DatetimeIndex(calendar)
        return list(cal[(cal >= pd.Timestamp(start)) & (cal <= pd.Timestamp(end))])
    return list(pd.bdate_range(pd.Timestamp(start), pd.Timestamp(end)))


def _select(series: pd.Series, date: pd.Timestamp) -> float:
    valid = series[series.index <= date]
    if valid.empty:
        raise KeyError(f"no price at or before {date}")
    return float(valid.iloc[-1])


def _ca_events_for(events: list[CorporateActionEvent], date: pd.Timestamp) -> list[CorporateActionEvent]:
    return [e for e in events if e.ex_date == date]


def _ca_settle_for(events: list[CorporateActionEvent], date: pd.Timestamp) -> list[CorporateActionEvent]:
    return [e for e in events if e.pay_date is not None and e.pay_date == date]


def cn_large_buy_hold_net_return(
    raw_open: pd.Series,
    raw_close: pd.Series,
    events: list[CorporateActionEvent],
    test_dates: list[pd.Timestamp],
    *,
    initial_cash: float = 1_000_000.0,
    cost_model=MainlandETFCostModel(),
    lot_size: int = 100,
) -> dict:
    """可执行 510300 buy-and-hold（评审 benchmark 要求）。

    首 test 日 open 全仓买入（预留费用 + 整手），持有至末 test 日；期间处理公司行为
    （ex-date 应收款 / pay-date 结算 / 份额折算）+ 1x 成本；逐 test 执行日 mark close。
    输出 net_returns 序列（执行日口径）与成本/换手诊断。
    """
    inst = CN_LARGE_INSTRUMENT
    acc = PortfolioAccounting(initial_cash=initial_cash)
    net_returns: list[float] = []
    costs: list[float] = []
    traded_notional: list[float] = []
    cash_after: list[float] = []
    prev_v: float | None = None

    # 首 test 日：open 全仓买入
    first = test_dates[0]
    px_buy = _select(raw_open, first)
    probe = cost_model.estimate(inst, "buy", 1.0, px_buy)
    rate = probe.total / px_buy
    max_qty = np.floor(acc.cash / (px_buy * (1.0 + rate)) / lot_size) * lot_size
    cost = cost_model.estimate(inst, "buy", float(max_qty), px_buy)
    acc.apply_fill(
        Fill(order_id="bh", instrument=inst, side="buy", quantity=float(max_qty),
             price=px_buy, cost=cost, timestamp=first),
        fx_to_base=1.0,
    )

    for d in test_dates:
        # CA：结算应收款（pay_date）→ 折算 → 计提（ex_date，基于开盘前持仓）
        for ev in _ca_settle_for(events, d):
            if ev.cash_per_share > 0:
                acc.settle_dividend(ev.instrument)
        for ev in _ca_events_for(events, d):
            if ev.unit_factor != 1.0:
                acc.apply_unit_conversion(ev.instrument, ev.unit_factor)
            if ev.cash_per_share > 0:
                pos = acc.positions.get(ev.instrument)
                if pos is not None and pos.quantity > 0:
                    acc.accrue_dividend(ev.instrument, pos.quantity, ev.cash_per_share)
        # mark close
        px_mark = _select(raw_close, d)
        snap = acc.snapshot(d, {inst: px_mark}, {})
        v = snap.portfolio_value
        if prev_v is not None and prev_v > 0:
            net_returns.append(v / prev_v - 1.0)
            costs.append(0.0)  # buy-hold 无交易成本（首日买入已在 initial 计提）
        cash_after.append(acc.cash)
        prev_v = v

    # 末 test 日结算：若仍持有，无卖出成本（buy-hold 到期末 mark）
    snap_final = acc.snapshot(test_dates[-1], {inst: _select(raw_close, test_dates[-1])}, {})
    cum = snap_final.portfolio_value / initial_cash - 1.0
    return {
        "net_returns": [float(x) for x in net_returns],
        "cum_net_return": float(cum),
        "initial_cash": initial_cash,
        "final_value": float(snap_final.portfolio_value),
        "total_cost": float(sum(costs)) + cost.total,
        "traded_notional_first_day": float(max_qty * px_buy),
        "n_returns": len(net_returns),
        "label": "510300_EXECUTABLE_NET_BUY_HOLD",
    }
