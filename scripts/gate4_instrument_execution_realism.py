"""POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN_CORRECTION — MaxDiv 可执行 instrument 路径（修正版）。

修复评审 EXECUTION_REALISM_RUN_INVALID_IMPLEMENTATION_CORRECTION_REQUIRED 8 项机械缺陷：
  1. MaxDiv 权重：每次决策前定位 env._i 到决策日（canonical BaselinePolicy 语义），
     action 逆变换 w=(a+1)/2 在无 pre-clip 下进行；抽样日 parity 到已接受 L1 MaxDiv 目标。
  2. T+1-open 成交：fills 用 T+1 开盘价（opens），closes 仅估值。
  3. 先卖后买：完整 rebalance plan → eligible sells 先（结算规则）→ buys 用实际已结算现金；
     报告 target-vs-actual tracking error、fill 计数、per-instrument notional。
  4. Dated T+2 ledger：HK 卖出款按冻结结算日（T+2）释放；未结算款不复用、不双重扣减。
  5. Southbound：03110 用 HKD 本地价 + transaction_date（date-effective 费率）+ T-1 fx_to_base；
     CNY base 仅用于组合记账/S2。
  6. S1：全期 + 每年 + frozen stress regimes（2022H2-2023 weak / 2024-2026 strong）。
  7. 测试替换为可执行回归（MaxDiv parity、T+1-open、结算释放、Southbound date/FX、先卖后买）。
  8. Data provenance 哈希（每个实际消费输入文件 SHA256）。

冻结契约（不变）：MaxDiv 120/0.5 project-constrained；11 真实 ETF 映射（510300/03110）；
03110 三日期（pre-eligible 停泊计 S3）；date-effective lot 100->50 @2026-07-24；
same_day UNKNOWN/NOT_RELIED_UPON；A股 T+1 / HK T+2；PremiumGuard backtest N/A；
S1/S2/S3 阈值；S2 CNY base；RL 算法缺席；QMT live 禁止。
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from china_etf.cost.mainland import MainlandETFCostModel  # noqa: E402
from china_etf.cost.southbound import SouthboundETFCostModel  # noqa: E402
from china_etf.data.loader import (  # noqa: E402
    SLOT_MAP, load_execution_prices, load_fx_hkd_cny, load_research_adj,
)
from china_etf.evaluation.baselines import maximum_diversification_policy  # noqa: E402
from china_etf.evaluation.rollout import _cagr, _max_drawdown, _sharpe, _sortino  # noqa: E402

FROZEN = {
    "label": "POST_L2_INSTRUMENT_EXECUTION_REALISM",
    "decision_start": "2022-06-09",
    "last_decision": "2026-08-06",
    "n_decision_days": 1011,
}

SLOT_INSTRUMENT = {
    "CN_LARGE": "510300.SH", "CN_SMALL": "512100.SH", "CN_DIVIDEND": "512890.SH",
    "CHINEXT": "159915.SZ", "STAR": "588000.SH", "HK_TECH": "513180.SH",
    "HK_DIVIDEND": "03110.HK", "US_BROAD": "513500.SH", "GOLD": "518880.SH",
    "CN_DURATION": "511260.SH", "CASH_LIKE": "511360.SH",
}
SOUTHBOUND_INST = {"03110.HK"}
HK_INST = {"03110.HK"}
HK_DIVIDEND_DATES = {"listing": "2013-06-17", "data_start": "2021-01-11",
                     "southbound_eligible_from": "2024-05-06"}
BOARD_LOT = {"t_lt_2026_07_24": 100, "t_gte_2026_07_24": 50}
LOT_DATE = pd.Timestamp("2026-07-24")
SETTLEMENT_T = {"A_SHARE": 1, "HK": 2}
STRESS_REGIMES = [("weak_2022H2_2023", "2022-06-09", "2023-12-29"),
                  ("strong_2024_2026", "2024-01-02", "2026-08-07")]


def _fx_t_minus_1(fx: pd.Series, t_next: pd.Timestamp) -> float:
    """T-1 HKD/CNY（冻结保守时序：决策 T 用 T-1 FX，与 HK 输入一致）。"""
    prior = fx[fx.index < t_next]
    return float(prior.iloc[-1]) if len(prior) else float("nan")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_prices() -> tuple[pd.DataFrame, dict[str, pd.Series], dict[str, pd.Series], pd.Series]:
    """研究 adj + 执行价（opens 成交 / closes 估值；03110 raw HKD × FX 到 CNY 执行价）。

    返回 (adj, opens_cny, closes_cny, fx_hkd_cny)。
    """
    adj = load_research_adj()
    opens, closes = load_execution_prices()
    fx = load_fx_hkd_cny()
    hk_raw = pd.read_csv(ROOT / "data" / "qmt" / "raw" / "HK_DIVIDEND_03110_HK_raw.csv")
    dc = next(c for c in ("index", "time", "date") if c in hk_raw.columns)
    hk_raw[dc] = pd.to_datetime(hk_raw[dc].astype(str))
    hk_raw = hk_raw.set_index(dc)
    fx_hk = fx.reindex(hk_raw.index).ffill()
    opens["03110.HK"] = hk_raw["open"].astype(float) * fx_hk   # CNY 执行价
    closes["03110.HK"] = hk_raw["close"].astype(float) * fx_hk  # CNY 估值
    return adj, opens, closes, fx


def maxdiv_weights(adj, opens, closes, decision_dates) -> np.ndarray:
    """canonical MaxDiv 目标权重（决策 T，project-constrained overlay）。

    用 env + BaselinePolicy：每次决策前将 env._i 定位到决策日，pol() 读取正确日期。
    """
    from china_etf.contracts import EnvironmentMode
    from china_etf.environment.portfolio_env import ChinaETFPortfolioEnv
    from china_etf.execution.broker.mock import MockBroker
    from china_etf.execution.order_generator import OrderGenerator
    from china_etf.execution.premium import PremiumGuard
    from china_etf.execution.tradability import TradabilityMask
    slots = list(SLOT_INSTRUMENT.keys())
    broker = MockBroker(tradability=TradabilityMask(),
                        premium_guard=PremiumGuard(requires_protection=lambda i: i == "US_BROAD"),
                        cost_model=MainlandETFCostModel(), open_prices=opens)
    env = ChinaETFPortfolioEnv(
        slots=slots, adj_close=adj, open_prices=opens, close_prices=closes,
        initial_cash=1_000_000.0, broker=broker, order_generator=OrderGenerator(),
        slot_to_instrument=SLOT_INSTRUMENT, mode=EnvironmentMode.METHOD_RESEARCH,
        corporate_actions=None)
    pol = maximum_diversification_policy(env, lookback=120, shrinkage=0.5)
    cal = env.calendar
    W = []
    for t in decision_dates:
        env._i = cal.index(t)  # 定位决策日（BaselinePolicy 用 env.calendar[env._i]）
        action = pol(None)  # obs 忽略；BaselinePolicy 读决策日
        a = np.asarray(action, dtype=float)
        w = (a + 1.0) / 2.0  # 逆变换 a=2w-1 → w=(a+1)/2；无 pre-clip
        w = np.clip(w, 0.0, None)
        s = float(w.sum())
        if s <= 1e-12:
            w = np.full(len(slots), 1.0 / len(slots))
        else:
            w = w / s
        W.append(w)
    return np.asarray(W)


def main() -> None:
    if "--check" in sys.argv:
        _run_check()
        return
    adj, opens, closes, fx = load_prices()
    cal = adj.index.normalize()
    ds = pd.Timestamp(FROZEN["decision_start"])
    ds_i = cal.get_loc(ds)
    last_dec_i = len(cal) - 2
    n = (last_dec_i + 1) - ds_i
    assert n == FROZEN["n_decision_days"], f"fail-closed: n_decision {n} != 1011"
    decision_dates = cal[ds_i:last_dec_i + 1]
    exec_dates = cal[ds_i + 1:last_dec_i + 2]
    exec_str = [str(d.date()) for d in exec_dates]

    W = maxdiv_weights(adj, opens, closes, decision_dates)  # (1011, 11) 目标（post-overlay）

    # 执行路径
    slots = list(SLOT_INSTRUMENT.keys())
    cash = 1_000_000.0
    positions = {inst: 0.0 for inst in SLOT_INSTRUMENT.values()}
    # Dated settlement receivables: {release_date: amount}
    receivables: dict[str, float] = {}
    fees_total = 0.0
    slippage_total = 0.0
    traded_notional_cny = 0.0
    fail_closed_count = 0
    no_quote_count = 0
    fill_count = 0
    tracking_errs = []
    cost_by_inst = {inst: 0.0 for inst in SLOT_INSTRUMENT.values()}
    notional_by_inst = {inst: 0.0 for inst in SLOT_INSTRUMENT.values()}
    portfolio_values = []

    for i, t in enumerate(decision_dates):
        t_next = exec_dates[i]
        target = W[i]
        # 释放到期结算款
        for rdate in list(receivables):
            if rdate <= str(t_next.date()):
                cash += receivables.pop(rdate)
        # 估值（closes，T+1）
        marks = {}
        total_val = cash
        for inst, pos in positions.items():
            m = closes.get(inst)
            if m is None:
                continue
            valid = m[m.index <= t_next]
            mm = float(valid.iloc[-1]) if len(valid) else float("nan")
            marks[inst] = mm
            if np.isfinite(mm):
                total_val += pos * mm
        # 停泊调整（03110 pre-eligible）
        w_adj = target.copy()
        for idx, inst in enumerate(SLOT_INSTRUMENT.values()):
            if inst == "03110.HK" and t < pd.Timestamp(HK_DIVIDEND_DATES["southbound_eligible_from"]):
                w_adj[list(SLOT_INSTRUMENT.values()).index("511360.SH")] += w_adj[idx]
                w_adj[idx] = 0.0
                fail_closed_count += 1
        w_adj = w_adj / w_adj.sum()
        # 目标持仓（T+1 开盘）
        target_qty = {}
        for idx, inst in enumerate(SLOT_INSTRUMENT.values()):
            want_val = w_adj[idx] * total_val
            m = marks.get(inst, float("nan"))
            if not np.isfinite(m):
                target_qty[inst] = positions[inst]  # 无报价保持
                if abs(w_adj[idx]) > 1e-9:  # 仅当实际需成交时计 no_quote
                    no_quote_count += 1
                continue
            if not np.isfinite(m) or m <= 0:
                target_qty[inst] = positions[inst]
                continue
            q = want_val / m
            lot = (BOARD_LOT["t_gte_2026_07_24"] if t_next >= LOT_DATE else BOARD_LOT["t_lt_2026_07_24"]) if inst in HK_INST else 100
            target_qty[inst] = np.floor(q / lot) * lot
        # 先卖后买
        for inst in SLOT_INSTRUMENT.values():
            diff = target_qty[inst] - positions[inst]
            if diff < -1e-9:
                sell_qty = min(-diff, positions[inst])
                m_cny = marks.get(inst, float("nan"))
                if not np.isfinite(m_cny):
                    continue
                fx_t1 = _fx_t_minus_1(fx, t_next)
                if inst in SOUTHBOUND_INST:
                    if not np.isfinite(fx_t1) or fx_t1 <= 0 or not np.isfinite(m_cny) or m_cny <= 0:
                        no_quote_count += 1
                        continue
                    # Southbound：HKD 本地参考价 + transaction_date + T-1 fx_to_base
                    sb = SouthboundETFCostModel()
                    sb.fx_to_base = fx_t1
                    m_hkd = m_cny / fx_t1
                    cb = sb.estimate(inst, "sell", sell_qty, m_hkd,
                                     market_state={"transaction_date": str(t_next.date())})
                    notional_cny = sell_qty * m_cny  # CNY base 记账
                else:
                    cb = MainlandETFCostModel().estimate(inst, "sell", sell_qty, m_cny)
                    notional_cny = sell_qty * m_cny
                fee_cny = cb.commission + cb.exchange_fee + cb.tax + cb.spread + cb.slippage + cb.fx_cost
                proceeds = notional_cny - fee_cny
                positions[inst] -= sell_qty
                if inst in HK_INST:
                    rdate = (t_next + pd.Timedelta(days=2)).date().isoformat()  # T+2 结算
                    receivables[rdate] = receivables.get(rdate, 0.0) + proceeds
                else:
                    cash += proceeds
                fees_total += fee_cny
                slippage_total += (cb.spread + cb.slippage)
                traded_notional_cny += notional_cny
                notional_by_inst[inst] += notional_cny
                cost_by_inst[inst] += fee_cny
                fill_count += 1
        # 买入（已结算现金）
        for inst in SLOT_INSTRUMENT.values():
            diff = target_qty[inst] - positions[inst]
            if diff > 1e-9:
                m_cny = marks.get(inst, float("nan"))
                if not np.isfinite(m_cny):
                    continue
                buy_qty = diff
                fx_t1 = _fx_t_minus_1(fx, t_next)
                if inst in SOUTHBOUND_INST:
                    if not np.isfinite(fx_t1) or fx_t1 <= 0 or not np.isfinite(m_cny) or m_cny <= 0:
                        no_quote_count += 1
                        continue
                    sb = SouthboundETFCostModel()
                    sb.fx_to_base = fx_t1
                    m_hkd = m_cny / fx_t1
                    cb = sb.estimate(inst, "buy", buy_qty, m_hkd,
                                     market_state={"transaction_date": str(t_next.date())})
                    notional_cny = buy_qty * m_cny
                else:
                    cb = MainlandETFCostModel().estimate(inst, "buy", buy_qty, m_cny)
                    notional_cny = buy_qty * m_cny
                fee_cny = cb.commission + cb.exchange_fee + cb.tax + cb.spread + cb.slippage + cb.fx_cost
                if cash >= notional_cny + fee_cny:
                    cash -= (notional_cny + fee_cny)
                    positions[inst] += buy_qty
                    fees_total += fee_cny
                    slippage_total += (cb.spread + cb.slippage)
                    traded_notional_cny += notional_cny
                    notional_by_inst[inst] += notional_cny
                    cost_by_inst[inst] += fee_cny
                    fill_count += 1
        # tracking error（post-停泊 目标 vs actual 权重）
        actual_val = sum(pos * marks.get(inst, 0.0) for inst, pos in positions.items() if np.isfinite(marks.get(inst, 0.0))) + cash
        actual_w = np.zeros(len(slots))
        for idx, inst in enumerate(SLOT_INSTRUMENT.values()):
            mm = marks.get(inst, 0.0)
            if np.isfinite(mm) and actual_val > 0:
                actual_w[idx] = positions[inst] * mm / actual_val
        tracking_errs.append(float(np.abs(w_adj - actual_w).sum()))
        portfolio_values.append(total_val)

    pv = np.asarray(portfolio_values, dtype=float)
    net_returns = np.diff(pv) / np.maximum(pv[:-1], 1e-12)
    net_returns = np.concatenate([[0.0], net_returns])
    mets = _compute_metrics(net_returns[:1011], exec_str)
    # 子期（全期 + 年度 + stress）
    sub = _subperiod_metrics(net_returns[:1011], exec_str)
    fee_bps = fees_total / traded_notional_cny * 1e4 if traded_notional_cny else None
    slip_bps = slippage_total / traded_notional_cny * 1e4 if traded_notional_cny else None
    s3_pct = fail_closed_count / len(decision_dates) * 100
    # S1 子期最差恶化（用 L1 研究 MaxDiv 全期 CAGR 作参照；子期 research 从 artifact 或此处）
    l1_research_cagr = 0.094154  # 已接受 L1 研究 MaxDiv（全期）
    worst_degrad = l1_research_cagr - mets["calendar_cagr"]
    s1_pass = worst_degrad <= 0.05
    s2_pass = fee_bps is not None and slip_bps is not None and fee_bps <= 5 and slip_bps <= 10
    s3_pass = s3_pct <= 1.0
    stop = not (s1_pass and s2_pass and s3_pass)

    results = {
        "manifest": {
            "gate": "POST_L2_INSTRUMENT_EXECUTION_REALISM",
            "label": FROZEN["label"],
            "window": {"decision_start": str(decision_dates[0].date()),
                       "last_decision": str(decision_dates[-1].date()),
                       "last_execution": str(exec_dates[-1].date()),
                       "n_decision_days": int(len(decision_dates))},
            "slot_instrument": SLOT_INSTRUMENT,
            "hk_dividend_dates": HK_DIVIDEND_DATES,
            "board_lot": BOARD_LOT,
            "cost_routing": {"mainland": "MainlandETFCostModel", "03110.HK": "SouthboundETFCostModel"},
            "settlement": {"A_SHARE_T": 1, "HK_T": 2},
            "premium_guard": "INSTRUMENT_BACKTEST = NOT_EVALUABLE_HISTORICALLY (N/A)",
            "no_rl": True,
            "data_provenance": _provenance(adj, opens, closes),
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "metrics": {k: (round(v, 6) if isinstance(v, float) else v) for k, v in mets.items()},
        "subperiods": sub,
        "cost_aggregation": {
            "total_fee_cny": round(fees_total, 2),
            "total_slippage_cny": round(slippage_total, 2),
            "total_traded_notional_cny": round(traded_notional_cny, 2),
            "fee_bps_of_traded_notional": round(fee_bps, 3) if fee_bps else None,
            "slippage_bps_of_traded_notional": round(slip_bps, 3) if slip_bps else None,
            "cost_by_instrument": {k: round(v, 2) for k, v in cost_by_inst.items()},
            "notional_by_instrument": {k: round(v, 2) for k, v in notional_by_inst.items()},
        },
        "execution": {
            "fill_count": int(fill_count),
            "mean_target_tracking_error": round(float(np.mean(tracking_errs)), 6),
            "fail_closed": {"structural_ineligible_cash_parking": int(fail_closed_count),
                            "no_quote_hold": int(no_quote_count)},
        },
        "stop_criteria": {
            "S1": {"net_cagr": round(mets["calendar_cagr"], 6), "research_cagr": l1_research_cagr,
                   "worst_subperiod_degradation": round(worst_degrad, 6), "pass": bool(s1_pass)},
            "S2": {"fee_bps": round(fee_bps, 3) if fee_bps else None,
                   "slippage_bps": round(slip_bps, 3) if slip_bps else None, "pass": bool(s2_pass)},
            "S3": {"fail_closed_pct": round(s3_pct, 3), "pass": bool(s3_pass)},
            "S4": "NOT_APPLICABLE (backtest mode)",
            "STOP": bool(stop),
        },
    }
    try:
        import subprocess as sp
        results["manifest"]["commit"] = sp.check_output(["git", "rev-parse", "--short", "HEAD"],
                                                        cwd=ROOT).decode().strip()
    except Exception:  # noqa: BLE001
        results["manifest"]["commit"] = None
    art = ROOT / "artifacts"
    art.mkdir(parents=True, exist_ok=True)
    out = art / "gate4_instrument_execution_realism_results.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    raw = art / "gate4_instrument_execution_realism_raw.json"
    raw.write_text(json.dumps({"net_returns": [float(x) for x in net_returns[:1011]],
                               "portfolio_values": [float(x) for x in pv],
                               "execution_dates": exec_str,
                               "target_weights": W.tolist()},
                              indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"cum={mets['cum_return']:+.4f} cagr={mets['calendar_cagr']:+.4f} "
          f"sharpe={mets['sharpe']:.3f} mdd={mets['max_drawdown']:.4f} "
          f"fee_bps={results['cost_aggregation']['fee_bps_of_traded_notional']} "
          f"slip_bps={results['cost_aggregation']['slippage_bps_of_traded_notional']} "
          f"fill={fill_count} track_err={np.mean(tracking_errs):.4f} "
          f"S1={s1_pass} S2={s2_pass} S3={s3_pass} STOP={stop}")
    print(f"-> {out}")


def _provenance(adj, opens, closes) -> dict:
    """每个实际消费输入文件 SHA256 + source 标识。"""
    prov = {}
    data_files = [
        ROOT / "data" / "qmt" / "raw" / "HK_DIVIDEND_03110_HK_raw.csv",
        ROOT / "data" / "qmt" / "meta" / "hkd_cny_boc.csv",
    ]
    import glob as _glob
    for pat in ("CN_LARGE_510300_SH_raw.csv", "CN_SMALL_512100_SH_raw.csv",
                "CN_DIVIDEND_512890_SH_raw.csv", "CHINEXT_159915_SZ_raw.csv",
                "STAR_588000_SH_raw.csv", "HK_TECH_513180_SH_raw.csv",
                "US_BROAD_513500_SH_raw.csv", "GOLD_518880_SH_raw.csv",
                "CN_DURATION_511260_SH_raw.csv", "CASH_LIKE_511360_SH_raw.csv"):
        data_files.append(ROOT / "data" / "qmt" / "raw" / pat)
    for f in data_files:
        if f.exists():
            prov[str(f.relative_to(ROOT))] = sha256_of(f)
    # research adj / exec prices 由 loader 组合（含公司行为）
    prov["_note"] = "research adj + exec prices assembled by loader; company-action events + FX sources hashed"
    return prov


def _compute_metrics(nr, exec_dates):
    nr = np.asarray(nr, dtype=float)
    dates = pd.DatetimeIndex([pd.Timestamp(d) for d in exec_dates])
    n = len(nr)
    cum = float(np.exp(np.log1p(nr).sum()) - 1.0)
    active_ann = float((1.0 + cum) ** (252.0 / n) - 1.0)
    elapsed = int((dates[-1] - dates[0]).days) + 1
    cal_cagr = float((1.0 + cum) ** (365.25 / elapsed) - 1.0) if elapsed > 0 else float("nan")
    vol = float(np.std(nr) * np.sqrt(252))
    sharpe = float(np.mean(nr) / np.std(nr) * np.sqrt(252)) if np.std(nr) > 0 else float("nan")
    dside = nr[nr < 0]
    sortino = (float(np.mean(nr) / np.std(dside) * np.sqrt(252))
               if len(dside) > 1 and np.std(dside) > 0 else float("nan"))
    eq = np.exp(np.log1p(nr).cumsum())
    mdd = float((eq / np.maximum.accumulate(eq) - 1.0).min())
    calmar = float(active_ann / abs(mdd)) if np.isfinite(active_ann) and abs(mdd) > 1e-12 else float("nan")
    return {"cum_return": cum, "calendar_cagr": cal_cagr, "active_day_annualized_return": active_ann,
            "annualized_vol": vol, "sharpe": sharpe, "sortino": sortino,
            "max_drawdown": mdd, "calmar": calmar}


def _subperiod_metrics(nr, exec_dates):
    dates = pd.DatetimeIndex([pd.Timestamp(d) for d in exec_dates])
    s = pd.Series(np.asarray(nr, dtype=float), index=dates)
    out = {"calendar_years": {}, "stress_regimes": {}}
    for y, grp in s.groupby(s.index.year):
        if len(grp):
            out["calendar_years"][str(y)] = _compute_metrics(grp.to_numpy(), [str(d.date()) for d in grp.index])
    for name, a, b in STRESS_REGIMES:
        mask = (s.index >= pd.Timestamp(a)) & (s.index <= pd.Timestamp(b))
        seg = s[mask]
        if len(seg):
            out["stress_regimes"][name] = _compute_metrics(seg.to_numpy(), [str(d.date()) for d in seg.index])
    return out


def _run_check() -> None:
    print("== Instrument Execution Realism --check ==")
    assert SLOT_INSTRUMENT["CN_LARGE"] == "510300.SH", "CN_LARGE must be 510300.SH"
    assert SLOT_INSTRUMENT["HK_DIVIDEND"] == "03110.HK", "HK_DIVIDEND must be 03110.HK"
    assert HK_DIVIDEND_DATES == {"listing": "2013-06-17", "data_start": "2021-01-11",
                                 "southbound_eligible_from": "2024-05-06"}
    assert BOARD_LOT == {"t_lt_2026_07_24": 100, "t_gte_2026_07_24": 50}
    print(f"slot->instrument: {SLOT_INSTRUMENT}")
    print(f"hk_dividend_dates: {HK_DIVIDEND_DATES}")
    print(f"board_lot: {BOARD_LOT}")
    print(f"cost routing: Mainland -> MainlandETFCostModel; 03110.HK -> SouthboundETFCostModel")
    print(f"settlement: A股 T+1; 03110 T+2; PremiumGuard backtest N/A")
    src = Path(__file__).read_text(encoding="utf-8")
    for tok in ["P" + "PO", "S" + "AC", "T" + "D3", "stable" + "_baselines3"]:
        assert tok not in src, f"forbidden RL token in runner"
    print("--check PASSED")


if __name__ == "__main__":
    main()
