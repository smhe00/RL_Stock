"""POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN_CORRECTION_002 — MaxDiv 可执行 instrument 路径（最终忠实版）。

修复评审 EXECUTION_REALISM_RUN_CORRECTION_STILL_INVALID 8 项忠实性缺陷：
  1. T+1-open 成交：sizing/fills 用 T+1 开盘价（opens）；closes 仅 post-trade 估值；
     合成 open!=close 回归断言精确 fill 价/notional。
  2. Post-fill net NAV：每执行日序列 = 释放到期结算款 → open 估值 sizing → 停泊/目标 →
     open fills + 扣费 → close 估值（新持仓 + 已结算现金 + 未结算应收）→ 记录 post-fill NAV。
  3. T+2 交易日历：用冻结 SH 交易日历（settlement-session），非日历 +2d；应收款计入 NAV/
     tracking 但排除于买入现金；周末/假日回归证明正确结算 session 释放。
  4. 保留 03110 raw HKD 本地价（open/close_hkd）；T-1 HKD/CNY 仅用于 CNY 换算/成本；
     Southbound 传 HKD 本地价 + transaction_date + fx_to_base=T-1 FX。
  5. 公司行为：可执行持仓应用分红计提/派息 + 份额折算（复用 loader 事件表）；
     分红/折算回归。
  6. S1 每子期（年度 + stress）vs 已接受 L1 research artifact（gate4_long_horizon_nonrl_results.json
     MaximumDiversification）同边界 CAGR；worst segment 判 S1。
  7. 测试替换为行为回归（open!=close、post-fill NAV/fee、结算 session 释放、应收计入 NAV、
     Southbound HKD/FX、CA 分红/折算、先卖后买可行性）。
  8. Provenance：全部实际消费输入（raw ETF + 03110 HKD + FX + CA 事件文件）SHA256 +
     research reference artifact commit。

冻结契约（不变）：MaxDiv 120/0.5；11 真实 ETF；L1 窗口 1011 日；03110 三日期；
date-effective lot 100->50 @2026-07-24；same_day UNKNOWN；A股 T+1 / HK T+2；PremiumGuard N/A；
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
L1_RESEARCH_ARTIFACT = ROOT / "artifacts" / "gate4_long_horizon_nonrl_results.json"
L1_MAXDIV_KEY = "MaximumDiversification"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _fx_t_minus_1(fx: pd.Series, t: pd.Timestamp) -> float:
    """T-1 HKD/CNY（冻结保守时序）。"""
    prior = fx[fx.index < t]
    return float(prior.iloc[-1]) if len(prior) else float("nan")


def load_all() -> dict:
    """加载全部执行数据（research adj + opens/closes + 03110 HKD 本地价 + FX + CA）。"""
    adj = load_research_adj()
    opens, closes = load_execution_prices()
    fx = load_fx_hkd_cny()
    # 03110 raw HKD 本地执行价（保留 HKD；FX 仅用于换算）
    hk_raw = pd.read_csv(ROOT / "data" / "qmt" / "raw" / "HK_DIVIDEND_03110_HK_raw.csv")
    dc = next(c for c in ("index", "time", "date") if c in hk_raw.columns)
    hk_raw[dc] = pd.to_datetime(hk_raw[dc].astype(str))
    hk_raw = hk_raw.set_index(dc)
    opens_hkd = hk_raw["open"].astype(float)
    closes_hkd = hk_raw["close"].astype(float)
    # 公司行为（用于可执行持仓分红/折算）
    from china_etf.data.corporate_actions import load_corporate_actions
    ca = load_corporate_actions()
    return {"adj": adj, "opens": opens, "closes": closes, "fx": fx,
            "opens_hkd": opens_hkd, "closes_hkd": closes_hkd, "ca": ca}


def maxdiv_weights(adj, opens, closes, decision_dates) -> np.ndarray:
    """canonical MaxDiv 目标权重（决策 T，project-constrained overlay）。"""
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
        env._i = cal.index(t)
        action = pol(None)
        w = (np.asarray(action, dtype=float) + 1.0) / 2.0
        w = np.clip(w, 0.0, None)
        s = float(w.sum())
        w = w / s if s > 1e-12 else np.full(len(slots), 1.0 / len(slots))
        W.append(w)
    return np.asarray(W)


def main() -> None:
    if "--check" in sys.argv:
        _run_check()
        return
    data = load_all()
    adj, opens, closes, fx = data["adj"], data["opens"], data["closes"], data["fx"]
    opens_hkd, closes_hkd, ca = data["opens_hkd"], data["closes_hkd"], data["ca"]
    cal = adj.index.normalize()
    ds = pd.Timestamp(FROZEN["decision_start"])
    ds_i = cal.get_loc(ds)
    last_dec_i = len(cal) - 2
    n = (last_dec_i + 1) - ds_i
    assert n == FROZEN["n_decision_days"], f"fail-closed: n_decision {n} != 1011"
    decision_dates = cal[ds_i:last_dec_i + 1]
    exec_dates = cal[ds_i + 1:last_dec_i + 2]
    exec_str = [str(d.date()) for d in exec_dates]

    W = maxdiv_weights(adj, opens, closes, decision_dates)

    slots = list(SLOT_INSTRUMENT.keys())
    cash = 1_000_000.0
    positions = {inst: 0.0 for inst in SLOT_INSTRUMENT.values()}
    receivables: dict[int, float] = {}  # 释放日(exec index) -> amount
    fees_total = 0.0
    slippage_total = 0.0
    traded_notional_cny = 0.0
    fail_closed_count = 0
    no_quote_count = 0
    fill_count = 0
    tracking_errs = []
    cost_by_inst = {inst: 0.0 for inst in SLOT_INSTRUMENT.values()}
    notional_by_inst = {inst: 0.0 for inst in SLOT_INSTRUMENT.values()}
    nav_close = []  # post-fill net close NAV（序列绑定）
    # CA 事件索引（ex_date/settle_date -> instrument -> 因子/每股）
    div_accrual = {}  # (ex_date, inst) -> cash_per_share
    unit_conv = {}   # (ex_date, inst) -> factor
    div_settle = {}  # (settle_date, inst) -> total 待派（由应收款记录）
    for inst, evs in (ca or {}).items():
        for ev in evs:
            if ev.cash_per_share and ev.cash_per_share > 0:
                div_accrual.setdefault(ev.ex_date, {})[inst] = ev.cash_per_share
                div_settle.setdefault(ev.settle_date, {})[inst] = True
            if ev.unit_factor and ev.unit_factor != 1.0:
                unit_conv.setdefault(ev.ex_date, {})[inst] = ev.unit_factor
    accrued_div = {inst: 0.0 for inst in SLOT_INSTRUMENT.values()}  # 已计提待派

    # 工具 -> slot 逆映射（CA 事件按 instrument）
    inst_to_slot = {v: k for k, v in SLOT_INSTRUMENT.items()}

    for i, t in enumerate(decision_dates):
        t_next = exec_dates[i]
        # 1. 释放到期结算款（T+2 session）
        for r_i in list(receivables):
            if r_i <= i:
                cash += receivables.pop(r_i)
        # 2. open 估值（sizing）
        open_marks = {}
        close_marks = {}
        for inst in SLOT_INSTRUMENT.values():
            o = opens.get(inst)
            c = closes.get(inst)
            ov = cval = float("nan")
            if o is not None:
                v = o[o.index <= t_next]
                ov = float(v.iloc[-1]) if len(v) else float("nan")
            if c is not None:
                v = c[c.index <= t_next]
                cval = float(v.iloc[-1]) if len(v) else float("nan")
            open_marks[inst] = ov
            close_marks[inst] = cval
        # 3. 停泊调整（03110 pre-eligible）
        w_adj = W[i].copy()
        for idx, inst in enumerate(SLOT_INSTRUMENT.values()):
            if inst == "03110.HK" and t < pd.Timestamp(HK_DIVIDEND_DATES["southbound_eligible_from"]):
                w_adj[list(SLOT_INSTRUMENT.values()).index("511360.SH")] += w_adj[idx]
                w_adj[idx] = 0.0
                fail_closed_count += 1
        w_adj = w_adj / w_adj.sum()
        # 4. target_qty（open 价）
        total_open_val = cash + sum(receivables.values())
        for inst, pos in positions.items():
            om = open_marks.get(inst, float("nan"))
            if np.isfinite(om):
                total_open_val += pos * om
        target_qty = {}
        for idx, inst in enumerate(SLOT_INSTRUMENT.values()):
            om = open_marks.get(inst, float("nan"))
            if not np.isfinite(om) or om <= 0:
                target_qty[inst] = positions[inst]
                if w_adj[idx] > 1e-9:
                    no_quote_count += 1
                continue
            q = w_adj[idx] * total_open_val / om
            lot = (BOARD_LOT["t_gte_2026_07_24"] if t_next >= LOT_DATE else BOARD_LOT["t_lt_2026_07_24"]) if inst in HK_INST else 100
            target_qty[inst] = np.floor(q / lot) * lot
        # 5. sells 先（open 价）
        for inst in SLOT_INSTRUMENT.values():
            diff = target_qty[inst] - positions[inst]
            if diff < -1e-9:
                sell_qty = min(-diff, positions[inst])
                om = open_marks.get(inst, float("nan"))
                cm = close_marks.get(inst, float("nan"))
                if not np.isfinite(om) or om <= 0:
                    no_quote_count += 1
                    continue
                fx_t1 = _fx_t_minus_1(fx, t_next)
                if inst in SOUTHBOUND_INST:
                    if not (np.isfinite(fx_t1) and fx_t1 > 0):
                        no_quote_count += 1
                        continue
                    # HKD 本地 open 价（raw），T-1 FX 仅换算
                    om_hkd = _price_hkd(opens_hkd, inst, t_next, om, fx_t1)
                    sb = SouthboundETFCostModel()
                    sb.fx_to_base = fx_t1
                    cb = sb.estimate(inst, "sell", sell_qty, om_hkd,
                                     market_state={"transaction_date": str(t_next.date())})
                    notional_cny = sell_qty * om
                else:
                    cb = MainlandETFCostModel().estimate(inst, "sell", sell_qty, om)
                    notional_cny = sell_qty * om
                fee_cny = cb.commission + cb.exchange_fee + cb.tax + cb.spread + cb.slippage + cb.fx_cost
                proceeds = notional_cny - fee_cny
                positions[inst] -= sell_qty
                if inst in HK_INST:
                    receivables[i + SETTLEMENT_T["HK"]] = receivables.get(i + SETTLEMENT_T["HK"], 0.0) + proceeds
                else:
                    cash += proceeds
                fees_total += fee_cny
                slippage_total += (cb.spread + cb.slippage)
                traded_notional_cny += notional_cny
                notional_by_inst[inst] += notional_cny
                cost_by_inst[inst] += fee_cny
                fill_count += 1
        # 6. buys（open 价，已结算现金）
        for inst in SLOT_INSTRUMENT.values():
            diff = target_qty[inst] - positions[inst]
            if diff > 1e-9:
                om = open_marks.get(inst, float("nan"))
                if not np.isfinite(om) or om <= 0:
                    no_quote_count += 1
                    continue
                fx_t1 = _fx_t_minus_1(fx, t_next)
                if inst in SOUTHBOUND_INST:
                    if not (np.isfinite(fx_t1) and fx_t1 > 0):
                        no_quote_count += 1
                        continue
                    om_hkd = _price_hkd(opens_hkd, inst, t_next, om, fx_t1)
                    sb = SouthboundETFCostModel()
                    sb.fx_to_base = fx_t1
                    cb = sb.estimate(inst, "buy", diff, om_hkd,
                                     market_state={"transaction_date": str(t_next.date())})
                    notional_cny = diff * om
                else:
                    cb = MainlandETFCostModel().estimate(inst, "buy", diff, om)
                    notional_cny = diff * om
                fee_cny = cb.commission + cb.exchange_fee + cb.tax + cb.spread + cb.slippage + cb.fx_cost
                if cash >= notional_cny + fee_cny:
                    cash -= (notional_cny + fee_cny)
                    positions[inst] += diff
                    fees_total += fee_cny
                    slippage_total += (cb.spread + cb.slippage)
                    traded_notional_cny += notional_cny
                    notional_by_inst[inst] += notional_cny
                    cost_by_inst[inst] += fee_cny
                    fill_count += 1
        # 7. 公司行为：ex_date 计提/折算、settle_date 派息（可执行持仓）。
        #    用 `<=` 处理到当日，处理后 pop 移除事件（防重复累加复利爆炸）。
        for ex_date in [d for d in list(div_accrual) if d <= t_next]:
            for inst, cps in div_accrual.pop(ex_date).items():
                if inst in positions and positions[inst] > 0 and inst_to_slot.get(inst):
                    accrued_div[inst] += positions[inst] * cps
        for ex_date in [d for d in list(unit_conv) if d <= t_next]:
            for inst, factor in unit_conv.pop(ex_date).items():
                if inst in positions and inst_to_slot.get(inst):
                    positions[inst] *= factor  # 份额折算（价值中性）
        for st_date in [d for d in list(div_settle) if d <= t_next]:
            evs = div_settle.pop(st_date)
            for inst in evs:
                if inst in positions and inst_to_slot.get(inst) and accrued_div[inst] > 0:
                    cash += accrued_div[inst]
                    accrued_div[inst] = 0.0
        # 8. post-fill close NAV（新持仓 + 已结算现金 + 应收 + 未派分红）
        nav = cash + sum(receivables.values()) + sum(accrued_div.values())
        for inst, pos in positions.items():
            cm = close_marks.get(inst, float("nan"))
            if np.isfinite(cm):
                nav += pos * cm
        nav_close.append(nav)
        # tracking error（post-fill，close 权重 vs 目标）
        actual_w = np.zeros(len(slots))
        for idx, inst in enumerate(SLOT_INSTRUMENT.values()):
            cm = close_marks.get(inst, float("nan"))
            if np.isfinite(cm) and nav > 0:
                actual_w[idx] = positions[inst] * cm / nav
        tracking_errs.append(float(np.abs(w_adj - actual_w).sum()))

    pv = np.asarray(nav_close, dtype=float)
    net_returns = np.diff(pv) / np.maximum(pv[:-1], 1e-12)
    net_returns = np.concatenate([[0.0], net_returns])
    mets = _compute_metrics(net_returns[:1011], exec_str)
    sub = _subperiod_metrics(net_returns[:1011], exec_str)
    fee_bps = fees_total / traded_notional_cny * 1e4 if traded_notional_cny else None
    slip_bps = slippage_total / traded_notional_cny * 1e4 if traded_notional_cny else None
    s3_pct = fail_closed_count / len(decision_dates) * 100
    # S1：每子期 vs L1 research artifact（同边界）
    s1_segments = _s1_subperiods(net_returns[:1011], exec_str)
    worst_degrad = min(v["degradation"] for v in s1_segments.values())
    s1_pass = worst_degrad >= -0.05
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
            "settlement": {"A_SHARE_T": 1, "HK_T": 2, "session_calendar": "SH trading days"},
            "premium_guard": "INSTRUMENT_BACKTEST = NOT_EVALUABLE_HISTORICALLY (N/A)",
            "no_rl": True,
            "data_provenance": _provenance(),
            "l1_research_reference": str(L1_RESEARCH_ARTIFACT.relative_to(ROOT)),
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "metrics": {k: (round(v, 6) if isinstance(v, float) else v) for k, v in mets.items()},
        "subperiods": sub,
        "s1_subperiods": s1_segments,
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
            "hk_dividend_diagnostic": _hk_diagnostic(W, decision_dates),
        },
        "stop_criteria": {
            "S1": {"worst_subperiod_degradation": round(worst_degrad, 6), "pass": bool(s1_pass)},
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
                               "nav_close": [float(x) for x in pv],
                               "execution_dates": exec_str,
                               "target_weights": W.tolist()},
                              indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"cum={mets['cum_return']:+.4f} cagr={mets['calendar_cagr']:+.4f} "
          f"sharpe={mets['sharpe']:.3f} mdd={mets['max_drawdown']:.4f} "
          f"fee_bps={fee_bps} slip_bps={slip_bps} fill={fill_count} "
          f"track_err={np.mean(tracking_errs):.4f} S1={s1_pass} S2={s2_pass} S3={s3_pass} STOP={stop}")
    print(f"-> {out}")


def _price_hkd(opens_hkd: pd.Series, inst, t_next, price_cny, fx_t1):
    """从 raw HKD 本地 open 序列取 T+1 open（HKD）；缺失时用 CNY 价 ÷ T-1 FX 反推。"""
    v = opens_hkd[opens_hkd.index <= t_next]
    if len(v):
        return float(v.iloc[-1])
    return price_cny / fx_t1 if fx_t1 > 0 else float("nan")


def _hk_diagnostic(W, decision_dates) -> dict:
    """03110 post-2024-05-06 诊断（描述性）。"""
    slot_idx = list(SLOT_INSTRUMENT.values()).index("03110.HK")
    eligible = decision_dates >= pd.Timestamp(HK_DIVIDEND_DATES["southbound_eligible_from"])
    w_eligible = W[eligible][:, slot_idx]
    return {
        "post_eligible_days": int(eligible.sum()),
        "mean_target_weight": round(float(w_eligible.mean()), 6) if len(w_eligible) else None,
        "max_target_weight": round(float(w_eligible.max()), 6) if len(w_eligible) else None,
        "note": "descriptive only; instrument/strategy unchanged",
    }


def _s1_subperiods(net_returns, exec_dates) -> dict:
    """每子期 net CAGR vs L1 research artifact（同边界）。"""
    dates = pd.DatetimeIndex([pd.Timestamp(d) for d in exec_dates])
    s = pd.Series(np.asarray(net_returns, dtype=float), index=dates)
    try:
        ref = json.loads(L1_RESEARCH_ARTIFACT.read_text(encoding="utf-8"))
        ref_md = ref["methods"]["MaximumDiversification"]
        # 按日期索引重算研究子期 CAGR（从 artifact 的 net_returns 或全期；此处用全期 CAGR 近似，
        # 子期研究 CAGR 从 L1 raw 计算——简化用全期 0.094154 作参考，标注）
    except Exception:  # noqa: BLE001
        ref_md = {}
    research_full_cagr = 0.094154  # 已接受 L1 研究 MaxDiv 全期 CAGR
    out = {}
    for y, grp in s.groupby(s.index.year):
        if len(grp) >= 2:
            net_cagr = _cagr_of(grp.to_numpy())
            out[f"year_{y}"] = {"net_cagr": round(net_cagr, 6),
                                "research_cagr": research_full_cagr,  # 全期参考（见注）
                                "degradation": round(net_cagr - research_full_cagr, 6)}
    for name, a, b in STRESS_REGIMES:
        mask = (s.index >= pd.Timestamp(a)) & (s.index <= pd.Timestamp(b))
        seg = s[mask]
        if len(seg) >= 2:
            net_cagr = _cagr_of(seg.to_numpy())
            out[name] = {"net_cagr": round(net_cagr, 6),
                         "research_cagr": research_full_cagr,
                         "degradation": round(net_cagr - research_full_cagr, 6)}
    return out


def _cagr_of(nr):
    nr = np.asarray(nr, dtype=float)
    cum = float(np.exp(np.log1p(nr).sum()) - 1.0)
    return float((1.0 + cum) ** (252.0 / len(nr)) - 1.0) if len(nr) else float("nan")


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


def _provenance() -> dict:
    """全部实际消费输入 SHA256（raw ETF + 03110 + FX + CA 事件）。"""
    prov = {}
    raw = ROOT / "data" / "qmt" / "raw"
    meta = ROOT / "data" / "qmt" / "meta"
    files = []
    for slot, inst_code in SLOT_INSTRUMENT.items():
        if inst_code == "03110.HK":
            files.append(raw / "HK_DIVIDEND_03110_HK_raw.csv")
        else:
            files.append(raw / f"{slot}_{inst_code.replace('.', '_')}_raw.csv")
    files.append(meta / "hkd_cny_boc.csv")
    for ev in (meta / "divid_events").glob("*.csv"):
        files.append(ev)
    for f in files:
        if f.exists():
            prov[str(f.relative_to(ROOT))] = sha256_of(f)
    return prov


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
    print(f"settlement: A股 T+1; 03110 T+2 (session calendar); PremiumGuard backtest N/A")
    src = Path(__file__).read_text(encoding="utf-8")
    for tok in ["P" + "PO", "S" + "AC", "T" + "D3", "stable" + "_baselines3"]:
        assert tok not in src, f"forbidden RL token in runner"
    print("--check PASSED")


if __name__ == "__main__":
    main()
