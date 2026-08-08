"""Benchmark helpers（GATE_4_EVAL_FIX_CORRECTIONS B1/B2/B3）。

评审要求（`GATE_4_EVAL_FIX_REVIEWER_RESPONSE.md` §5-§9）：
- 可执行 510300 benchmark 必须与 RL/baseline walk-forward **Test-mask 等价**：
  每 fold 在 val_end 重置为现金+零持仓+零应收款，test_start open 买入 510300 + 1x 成本，
  首日记录 open→close 收益（对 initial equity），仅在本 fold Test 段内持仓，
  逐 CA 按规范顺序（先基于开盘前持仓 apply → 再 execute），**不跨 Validation gap**。
- `benchmark_return_count == strategy_stitched_return_count`（独立生成后比对，非同一 len）。
- 拼接 F1→F4 Test 返回 → `510300_EXECUTABLE_NET_STITCHED_BUY_HOLD`。
- 可保留连续日历 buy-hold 作为**另一参考**，但必须标注 `510300_CONTINUOUS_CALENDAR_REFERENCE`
  且不得当作 stitched OOS mask 等价。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..accounting import PortfolioAccounting
from ..contracts import Fill
from ..cost.mainland import MainlandETFCostModel
from ..data.corporate_actions import CorporateActionEvent

CN_LARGE_INSTRUMENT = "510300.SH"
STITCHED_LABEL = "510300_EXECUTABLE_NET_STITCHED_BUY_HOLD"
CONTINUOUS_LABEL = "510300_CONTINUOUS_CALENDAR_REFERENCE"


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


def _ca_on(events: list[CorporateActionEvent], date: pd.Timestamp) -> list[CorporateActionEvent]:
    return [e for e in events if e.ex_date == date]


def _ca_settle_on(events: list[CorporateActionEvent], date: pd.Timestamp) -> list[CorporateActionEvent]:
    return [e for e in events if e.pay_date is not None and e.pay_date == date]


def _apply_corporate_actions(acc: PortfolioAccounting, events: list[CorporateActionEvent], date: pd.Timestamp) -> None:
    """按规范顺序（GATE_4_EVAL_FIX_CORRECTIONS B3）：settle → 折算 → 计提（基于开盘前持仓）。"""
    for ev in _ca_settle_on(events, date):
        if ev.cash_per_share > 0:
            acc.settle_dividend(ev.instrument)
    for ev in _ca_on(events, date):
        if ev.unit_factor != 1.0:
            acc.apply_unit_conversion(ev.instrument, ev.unit_factor)
        if ev.cash_per_share > 0:
            pos = acc.positions.get(ev.instrument)
            if pos is not None and pos.quantity > 0:
                acc.accrue_dividend(ev.instrument, pos.quantity, ev.cash_per_share)


def _fold_buy_hold(
    raw_open: pd.Series,
    raw_close: pd.Series,
    events: list[CorporateActionEvent],
    test_dates: list[pd.Timestamp],
    *,
    initial_cash: float = 1_000_000.0,
    cost_model=MainlandETFCostModel(),
    lot_size: int = 100,
) -> list[float]:
    """单 fold 可执行 510300 buy-hold：val_end 重置现金 → test_start open 买入 → 段内 mark → 返回。

    返回：该 fold Test 段每个执行日（含首日）对 initial equity 的净收益序列。
    """
    inst = CN_LARGE_INSTRUMENT
    acc = PortfolioAccounting(initial_cash=initial_cash)  # B1：每 fold 重置现金+零持仓+零应收款
    net_returns: list[float] = []
    prev_v: float | None = None
    for d in test_dates:
        # B3：先 apply CA（基于开盘前持仓）→ 再执行（首日开盘前零持仓，不享 ex-date 当日分红）
        _apply_corporate_actions(acc, events, d)
        if prev_v is None:
            # 首 test 日：open 全仓买入 + 1x 成本
            px_buy = _select(raw_open, d)
            probe = cost_model.estimate(inst, "buy", 1.0, px_buy)
            rate = probe.total / px_buy
            max_qty = np.floor(acc.cash / (px_buy * (1.0 + rate)) / lot_size) * lot_size
            cost = cost_model.estimate(inst, "buy", float(max_qty), px_buy)
            acc.apply_fill(
                Fill(order_id="bh", instrument=inst, side="buy", quantity=float(max_qty),
                     price=px_buy, cost=cost, timestamp=d),
                fx_to_base=1.0,
            )
        # 收盘 mark
        px_mark = _select(raw_close, d)
        v = acc.snapshot(d, {inst: px_mark}, {}).portfolio_value
        if prev_v is not None and prev_v > 0:
            net_returns.append(v / prev_v - 1.0)
        elif prev_v is None:
            # 首日：相对 initial equity 的净收益（open→close + 成本）——B2：首 transition 计入
            net_returns.append(v / initial_cash - 1.0)
        prev_v = v
    return net_returns


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
    """可执行 510300 buy-hold（连续日历版本，供独立参考）。

    注意：此版本为连续持仓参考（`510300_CONTINUOUS_CALENDAR_REFERENCE`），
    **不等价于 stitched OOS Test mask**（跨 fold 连续持仓、无 val gap 重置）。
    正式 stitched 对比请用 `cn_large_buy_hold_stitched`。
    """
    inst = CN_LARGE_INSTRUMENT
    acc = PortfolioAccounting(initial_cash=initial_cash)
    net_returns: list[float] = []
    prev_v: float | None = None
    for d in test_dates:
        _apply_corporate_actions(acc, events, d)
        if prev_v is None:
            px_buy = _select(raw_open, d)
            probe = cost_model.estimate(inst, "buy", 1.0, px_buy)
            rate = probe.total / px_buy
            max_qty = np.floor(acc.cash / (px_buy * (1.0 + rate)) / lot_size) * lot_size
            cost = cost_model.estimate(inst, "buy", float(max_qty), px_buy)
            acc.apply_fill(
                Fill(order_id="bh", instrument=inst, side="buy", quantity=float(max_qty),
                     price=px_buy, cost=cost, timestamp=d),
                fx_to_base=1.0,
            )
        px_mark = _select(raw_close, d)
        v = acc.snapshot(d, {inst: px_mark}, {}).portfolio_value
        if prev_v is not None and prev_v > 0:
            net_returns.append(v / prev_v - 1.0)
        prev_v = v
    final = acc.snapshot(test_dates[-1], {inst: _select(raw_close, test_dates[-1])}, {})
    return {
        "label": CONTINUOUS_LABEL,
        "net_returns": [float(x) for x in net_returns],
        "cum_net_return": float(final.portfolio_value / initial_cash - 1.0),
        "n_returns": len(net_returns),
    }


def cn_large_buy_hold_stitched(
    raw_open: pd.Series,
    raw_close: pd.Series,
    events: list[CorporateActionEvent],
    folds,
    *,
    calendar=None,
    initial_cash: float = 1_000_000.0,
    cost_model=MainlandETFCostModel(),
    lot_size: int = 100,
) -> dict:
    """fold-local 可执行 510300 buy-hold（B1/B2/B3 修复版，正式 stitched 对比用）。

    每 fold 在 val_end 重置现金+零持仓+零应收款；test_start open 买入 + 1x 成本；
    首日记录 open→close 对 initial equity 的净收益；仅本 fold Test 段内持仓；
    不跨 Validation gap；逐 CA 按规范顺序。
    拼接 F1→F4 Test 返回 → `510300_EXECUTABLE_NET_STITCHED_BUY_HOLD`。
    """
    mask = exact_test_mask(folds, calendar=calendar)
    test_dates = mask["test_dates"]
    all_returns: list[float] = []
    per_fold: dict[str, list[float]] = {}
    for f in sorted(folds, key=lambda x: x.test_start):
        seg = _segment_days(f.test_start, f.test_end, calendar)
        rets = _fold_buy_hold(raw_open, raw_close, events, seg,
                              initial_cash=initial_cash, cost_model=cost_model, lot_size=lot_size)
        per_fold[f.name] = [float(x) for x in rets]
        all_returns.extend(rets)
    nr = np.asarray(all_returns, dtype=float)
    cum = float(np.exp(np.log1p(nr).sum()) - 1.0) if len(nr) else float("nan")
    return {
        "label": STITCHED_LABEL,
        "per_fold": {k: [round(x, 6) for x in v] for k, v in per_fold.items()},
        "net_returns": [float(x) for x in all_returns],
        "cum_net_return": round(cum, 6),
        "n_returns": len(all_returns),
        "strategy_stitched_steps": mask["strategy_stitched_steps"],
        "benchmark_stitched_steps": len(all_returns),
        "execution_dates": [str(d.date()) for d in test_dates],
        "parity_assert": bool(len(all_returns) == mask["strategy_stitched_steps"]),
    }
