"""POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN_CORRECTION_003 — MaxDiv 可执行 instrument 路径（评审 7 项修正）。

评审（POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN_CORRECTION_002_REVIEWER_RESPONSE.md）
EXECUTION_REALISM_RUN_CORRECTION_002_INVALID_CORRECTION_003_REQUIRED → 本脚本为 CORRECTION_003。

CORRECTION_003 7 项忠实性修正：
  1. 03110.HK 可执行价格路径：从 sina_qfq（HKD 本地，QMT raw 全零不可用）构建 opens/closes
     ["03110.HK"]（CNY，冻结 T-1 HKD/CNY 仅用于换算/sizing）；Southbound 传 HKD 本地价 +
     transaction_date + fx_to_base=T-1 FX；eligible 后 03110 真实成交（不再是 no_quote=550）。
  2. maxdiv_weights：canonical 复现 = action_transform.transform(action,t) → risk_overlay.apply()
     ，与已接受 L1 post_risk_weights 精确一致（1011×11 max diff 0.0）。
  3. S1 每子期研究 CAGR：从已接受 L1 artifact sub_periods（cum + n_days）计算每段研究 CAGR，
     非复用全期 0.094154；net CAGR 在同边界执行日段计算；worst 段判 S1。
  4. S3 按冻结 fail-closed 定义：结构不可交易停泊 ∪ 无报价，distinct 决策日 / 1011。
  5. 公司行为时序：t_next 开盘前应用（settle 派息 → 份额折算 → 除息计提，基于开盘前持仓），
     与 canonical env 一致；open 估值/sizing 之前。
  6. HK T+2 用 03110.HK session 日历（sina_qfq index = HK 交易日），非 SH exec index + 2；
     应收款按 release 日期入 ledger，release date <= t_next 才释放。
  7. Provenance 单一 manifest：全部实际消费输入（Mainland QMT raw + sina_qfq + FX + CA 事件）
     + 已接受 L1 research artifact（SHA256 + commit）绑定。

冻结契约（不变）：MaxDiv 120/0.5；11 真实 ETF（HK_DIVIDEND=03110.HK 执行）；L1 窗口 1011 日；
03110 三日期；date-effective lot 100->50 @2026-07-24；same_day UNKNOWN；A股 T+1（卖出当日可买，
T+1 才可取现——A 股 T+0 buying power）/ 03110 T+2 session；PremiumGuard N/A；S1/S2/S3 阈值；
S2 CNY base；RL 算法缺席；QMT live 禁止。
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from china_etf.cost.mainland import MainlandETFCostModel  # noqa: E402
from china_etf.cost.southbound import SouthboundETFCostModel  # noqa: E402
from china_etf.data.corporate_actions import (  # noqa: E402
    CONSERVATIVE_PAY_LAG_BD, CorporateActionEvent, _settle_for, load_corporate_actions,
)
from china_etf.data.loader import (  # noqa: E402
    META, SLOT_MAP, load_execution_prices, load_fx_hkd_cny, load_research_adj,
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
# L1 已接受 artifact 的 phase 名（边界一致：weak=382 / strong=629 执行日）
STRESS_REGIMES = [("2022H2-2023_weak_equity", "2022-06-09", "2023-12-29"),
                  ("2024-2026_strong_equity", "2024-01-02", "2026-08-07")]
L1_RESEARCH_ARTIFACT = ROOT / "artifacts" / "gate4_long_horizon_nonrl_results.json"
L1_RAW_ARTIFACT = ROOT / "artifacts" / "gate4_long_horizon_nonrl_raw.json"
L1_MAXDIV_KEY = "MaximumDiversification"
SINA_HK_FILE = ROOT / "data" / "qmt" / "raw" / "HK_DIVIDEND_03110_HK_sina_qfq.csv"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _fx_t_minus_1(fx: pd.Series, t: pd.Timestamp) -> float:
    """T-1 HKD/CNY（冻结保守时序）：最近一次严格早于 t 的 FX 观测。"""
    prior = fx[fx.index < t]
    return float(prior.iloc[-1]) if len(prior) else float("nan")


def _t1_fx_applicable(fx: pd.Series, dates) -> pd.Series:
    """对每个 date 返回其 T-1 可用 HKD/CNY（与 _fx_t_minus_1 逐日一致，向量化）。"""
    shifted = fx.shift(1, freq="D")  # index +1 日，value = 前一交易日 FX
    return shifted.reindex(dates, method="ffill")


def _load_hk_marks(fx: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.DatetimeIndex]:
    """03110.HK HKD 本地执行价（sina_qfq；QMT raw 全零不可用）+ T-1 FX 换算 CNY 序列。

    返回 (opens_hkd, closes_hkd, opens_cny, closes_cny, hk_cal)。
    注意：akshare stock_hk_daily(adjust='qfq') 对 03110 返回即 raw（H1 已验证 qfq==raw），
    故分红需由 divid_events/03110.HK.csv 官方事件单独计提（_load_exec_ca）。
    """
    hk = pd.read_csv(SINA_HK_FILE)
    dc = next(c for c in ("date", "index", "time") if c in hk.columns)
    hk[dc] = pd.to_datetime(hk[dc].astype(str))
    hk = hk.set_index(dc).sort_index()
    opens_hkd = hk["open"].astype(float)
    closes_hkd = hk["close"].astype(float)
    fx_t1 = _t1_fx_applicable(fx, hk.index)
    ok = fx_t1.notna() & (fx_t1 > 0)
    opens_cny = (opens_hkd * fx_t1).where(ok)
    closes_cny = (closes_hkd * fx_t1).where(ok)
    return opens_hkd, closes_hkd, opens_cny, closes_cny, hk.index.normalize()


def _load_exec_ca() -> dict:
    """可执行路径 CA 事件 = load_corporate_actions()（SLOT_MAP 境内 10 工具）+ 03110.HK 官方事件。"""
    ca = load_corporate_actions()
    path = META / "divid_events" / "03110.HK.csv"
    if path.exists():
        df = pd.read_csv(path)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            events: list[CorporateActionEvent] = []
            for _, r in df.iterrows():
                ex = pd.Timestamp(r["date"])
                action = str(r.get("action_type", "CASH_DIVIDEND")).strip() or "CASH_DIVIDEND"
                unit = float(r.get("unit_factor", 1.0)) if pd.notna(r.get("unit_factor")) else 1.0
                cash = float(r.get("interest", 0.0)) if pd.notna(r.get("interest")) else 0.0
                pay_raw = r.get("pay_date") if "pay_date" in df.columns else None
                pay = (pd.Timestamp(pay_raw) if pay_raw is not None and pd.notna(pay_raw)
                       and str(pay_raw).strip() else None)
                settle, source = _settle_for(action, ex, pay, CONSERVATIVE_PAY_LAG_BD)
                events.append(CorporateActionEvent(
                    instrument="03110.HK", action_type=action, ex_date=ex, unit_factor=unit,
                    cash_per_share=cash, pay_date=pay, settle_date=settle, source=source))
            if events:
                ca["03110.HK"] = events
    return ca


def load_all() -> dict:
    """加载全部执行数据。opens/closes 加入 03110.HK（CNY，T-1 FX 换算）；保留 HKD 本地价。"""
    adj = load_research_adj()
    opens, closes = load_execution_prices()
    fx = load_fx_hkd_cny()
    opens_hkd, closes_hkd, opens_cny, closes_cny, hk_cal = _load_hk_marks(fx)
    opens["03110.HK"] = opens_cny
    closes["03110.HK"] = closes_cny
    ca = _load_exec_ca()
    return {"adj": adj, "opens": opens, "closes": closes, "fx": fx,
            "opens_hkd": opens_hkd, "closes_hkd": closes_hkd, "ca": ca,
            "hk_cal": hk_cal}


def _build_env(adj, opens, closes, ca):
    """canonical env（与 L1 runner build_env 一致；仅用于目标权重复现）。"""
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
    return ChinaETFPortfolioEnv(
        slots=slots, adj_close=adj, open_prices=opens, close_prices=closes,
        initial_cash=1_000_000.0, broker=broker, order_generator=OrderGenerator(),
        slot_to_instrument=SLOT_INSTRUMENT, mode=EnvironmentMode.METHOD_RESEARCH,
        corporate_actions=ca)


def maxdiv_weights(adj, opens, closes, decision_dates, ca=None) -> np.ndarray:
    """canonical MaxDiv 目标权重 = action_transform.transform -> risk_overlay.apply（post_risk）。

    与已接受 L1 artifact post_risk_weights 精确一致（parity 测试全 1011 日）。
    """
    env = _build_env(adj, opens, closes, ca)
    pol = maximum_diversification_policy(env, lookback=120, shrinkage=0.5)
    cal = env.calendar
    W = []
    for t in decision_dates:
        env._i = cal.index(t)
        action = pol(None)
        raw = env.action_transform.transform(np.asarray(action, dtype=float), t).weights
        post = env.risk_overlay.apply(raw)
        W.append(np.asarray(post.values, dtype=float))
    return np.asarray(W)


def _hk_settle_date(hk_cal: pd.DatetimeIndex, t_next: pd.Timestamp):
    """HK T+2 结算日 = t_next 起第 2 个 HK 交易日（session 日历）。t_next 非 HK 交易日返回 None。"""
    try:
        pos = hk_cal.get_loc(t_next)
    except KeyError:
        return None
    if pos + SETTLEMENT_T["HK"] >= len(hk_cal):
        return None
    return hk_cal[pos + SETTLEMENT_T["HK"]]


def _apply_ca_at(t_next, positions, accrued_div, cash, fx, div_accrual, unit_conv, div_settle) -> float:
    """t_next 公司行为（canonical 顺序，open 估值/sizing 之前）：settle 派息 -> 份额折算 -> 计提。

    计提基于 t_next 开盘前持仓（= 上一执行日收盘后持仓），单位换算先于计提（canonical env 同序）。
    """
    for inst in list(div_settle.get(t_next, ())):
        if accrued_div.get(inst, 0.0) > 0:
            cash += accrued_div[inst]
            accrued_div[inst] = 0.0
    for (ex_date, inst) in [k for k in list(unit_conv) if k[0] == t_next]:
        if positions.get(inst, 0.0) > 0:
            positions[inst] *= unit_conv[(ex_date, inst)]
        del unit_conv[(ex_date, inst)]
    for (ex_date, inst) in [k for k in list(div_accrual) if k[0] == t_next]:
        cps = div_accrual[(ex_date, inst)]
        if positions.get(inst, 0.0) > 0 and cps > 0:
            if inst in HK_INST:
                fx_t1 = _fx_t_minus_1(fx, t_next)
                cps_cny = cps * fx_t1 if np.isfinite(fx_t1) else cps
            else:
                cps_cny = cps
            accrued_div[inst] = accrued_div.get(inst, 0.0) + positions[inst] * cps_cny
        del div_accrual[(ex_date, inst)]
    return cash


def _simulate(data: dict, W: np.ndarray | None = None) -> dict:
    """可执行 MaxDiv 全期模拟（不写文件）。返回完整 results dict。"""
    adj, opens, closes, fx = data["adj"], data["opens"], data["closes"], data["fx"]
    opens_hkd, closes_hkd = data["opens_hkd"], data["closes_hkd"]
    ca, hk_cal = data["ca"], data["hk_cal"]
    cal = adj.index.normalize()
    ds = pd.Timestamp(FROZEN["decision_start"])
    ds_i = cal.get_loc(ds)
    last_dec_i = len(cal) - 2
    n = (last_dec_i + 1) - ds_i
    assert n == FROZEN["n_decision_days"], f"fail-closed: n_decision {n} != 1011"
    decision_dates = cal[ds_i:last_dec_i + 1]
    exec_dates = cal[ds_i + 1:last_dec_i + 2]
    exec_str = [str(d.date()) for d in exec_dates]

    W = W if W is not None else maxdiv_weights(adj, opens, closes, decision_dates, ca=ca)

    slots = list(SLOT_INSTRUMENT.keys())
    initial_cash = 1_000_000.0
    cash = initial_cash
    positions = {inst: 0.0 for inst in SLOT_INSTRUMENT.values()}
    receivables: dict[pd.Timestamp, float] = {}  # release_date -> amount（date-keyed）
    window_end = exec_dates[-1] + pd.Timedelta(days=1)
    fees_total = 0.0
    slippage_total = 0.0
    traded_notional_cny = 0.0
    fill_count = 0
    structural_days: set[int] = set()
    no_quote_days: set[int] = set()
    tracking_errs = []
    cost_by_inst = {inst: 0.0 for inst in SLOT_INSTRUMENT.values()}
    notional_by_inst = {inst: 0.0 for inst in SLOT_INSTRUMENT.values()}
    nav_close = []
    hk_attempts = 0
    hk_fills = 0
    hk_notional = 0.0
    hk_feasible_days = 0
    inst_to_slot = {v: k for k, v in SLOT_INSTRUMENT.items()}

    div_accrual = {}
    unit_conv = {}
    div_settle = {}
    for inst, evs in (ca or {}).items():
        for ev in evs:
            if ev.cash_per_share and ev.cash_per_share > 0:
                div_accrual[(ev.ex_date, inst)] = ev.cash_per_share
                div_settle.setdefault(ev.settle_date, set()).add(inst)
            if ev.unit_factor and ev.unit_factor != 1.0:
                unit_conv[(ev.ex_date, inst)] = ev.unit_factor
    accrued_div = {inst: 0.0 for inst in SLOT_INSTRUMENT.values()}

    hk_slot_idx = list(SLOT_INSTRUMENT.values()).index("03110.HK")

    for i, t in enumerate(decision_dates):
        t_next = exec_dates[i]
        # 1. 释放到期结算款（date-keyed；HK = 03110 session T+2）
        for rd in list(receivables):
            if rd <= t_next:
                cash += receivables.pop(rd)
        # 2. 公司行为（open 估值/sizing 之前，canonical 顺序）
        cash = _apply_ca_at(t_next, positions, accrued_div, cash, fx,
                            div_accrual, unit_conv, div_settle)
        # 3. open/close 估值 + fresh-quote
        open_marks = {}
        close_marks = {}
        fresh = {}
        for inst in SLOT_INSTRUMENT.values():
            os_ = opens.get(inst)
            cs_ = closes.get(inst)
            ov = cv = float("nan")
            fresh_i = False
            if os_ is not None:
                v = os_[os_.index <= t_next]
                if len(v) and np.isfinite(float(v.iloc[-1])) and float(v.iloc[-1]) > 0:
                    ov = float(v.iloc[-1])
                if t_next in os_.index:
                    e = os_.loc[t_next]
                    if pd.notna(e) and np.isfinite(float(e)) and float(e) > 0:
                        fresh_i = True
            if cs_ is not None:
                v = cs_[cs_.index <= t_next]
                if len(v):
                    cv = float(v.iloc[-1])
            open_marks[inst] = ov
            close_marks[inst] = cv
            fresh[inst] = fresh_i
        # 4. 停泊（03110 pre-eligible -> CASH_LIKE；结构 fail-closed）
        w_adj = W[i].copy()
        cash_idx = list(SLOT_INSTRUMENT.values()).index("511360.SH")
        for idx, inst in enumerate(SLOT_INSTRUMENT.values()):
            if inst == "03110.HK" and t < pd.Timestamp(HK_DIVIDEND_DATES["southbound_eligible_from"]):
                w_adj[cash_idx] += w_adj[idx]
                w_adj[idx] = 0.0
                structural_days.add(i)
        w_adj = w_adj / w_adj.sum()
        # 5. target_qty（open 价）
        total_open_val = cash + sum(receivables.values()) + sum(accrued_div.values())
        for inst, pos in positions.items():
            om = open_marks.get(inst, float("nan"))
            if np.isfinite(om):
                total_open_val += pos * om
        target_qty = {}
        for idx, inst in enumerate(SLOT_INSTRUMENT.values()):
            om = open_marks.get(inst, float("nan"))
            if not np.isfinite(om) or om <= 0 or not fresh[inst]:
                target_qty[inst] = positions[inst]
                if w_adj[idx] > 1e-9:
                    no_quote_days.add(i)
                continue
            q = w_adj[idx] * total_open_val / om
            lot = (BOARD_LOT["t_gte_2026_07_24"] if t_next >= LOT_DATE else BOARD_LOT["t_lt_2026_07_24"]) if inst in HK_INST else 100
            target_qty[inst] = np.floor(q / lot) * lot
            if inst == "03110.HK" and q >= lot:
                hk_feasible_days += 1
        # 6. sells 先（open 价；需当日报价；HK -> HKD 本地价 + T-1 FX 成本 + session T+2 应收）
        for inst in SLOT_INSTRUMENT.values():
            diff = target_qty[inst] - positions[inst]
            if diff < -1e-9:
                sell_qty = min(-diff, positions[inst])
                om = open_marks.get(inst, float("nan"))
                if not np.isfinite(om) or om <= 0 or not fresh[inst]:
                    no_quote_days.add(i)
                    continue
                fx_t1 = _fx_t_minus_1(fx, t_next)
                if inst in SOUTHBOUND_INST:
                    hk_attempts += 1
                    if not (np.isfinite(fx_t1) and fx_t1 > 0):
                        no_quote_days.add(i)
                        continue
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
                    rel = _hk_settle_date(hk_cal, t_next)
                    rd = rel if rel is not None else window_end
                    receivables[rd] = receivables.get(rd, 0.0) + proceeds
                else:
                    cash += proceeds
                fees_total += fee_cny
                slippage_total += (cb.spread + cb.slippage)
                traded_notional_cny += notional_cny
                notional_by_inst[inst] += notional_cny
                cost_by_inst[inst] += fee_cny
                fill_count += 1
                if inst == "03110.HK":
                    hk_fills += 1
                    hk_notional += notional_cny
        # 7. buys（open 价；需当日报价；已结算现金）
        for inst in SLOT_INSTRUMENT.values():
            diff = target_qty[inst] - positions[inst]
            if diff > 1e-9:
                om = open_marks.get(inst, float("nan"))
                if not np.isfinite(om) or om <= 0 or not fresh[inst]:
                    no_quote_days.add(i)
                    continue
                fx_t1 = _fx_t_minus_1(fx, t_next)
                if inst in SOUTHBOUND_INST:
                    hk_attempts += 1
                    if not (np.isfinite(fx_t1) and fx_t1 > 0):
                        no_quote_days.add(i)
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
                    if inst == "03110.HK":
                        hk_fills += 1
                        hk_notional += notional_cny
        # 8. post-fill close NAV（新持仓 + 已结算现金 + 未结算应收 + 未派分红）
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
    pv_full = np.concatenate([[initial_cash], pv])
    net_returns = np.diff(pv_full) / np.maximum(pv_full[:-1], 1e-12)
    assert len(net_returns) == FROZEN["n_decision_days"]
    mets = _compute_metrics(net_returns, exec_str)
    sub = _subperiod_metrics(net_returns, exec_str)
    fee_bps = fees_total / traded_notional_cny * 1e4 if traded_notional_cny else None
    slip_bps = slippage_total / traded_notional_cny * 1e4 if traded_notional_cny else None
    fail_closed_days = structural_days | no_quote_days
    overlap_days = structural_days & no_quote_days
    s3_pct = len(fail_closed_days) / len(decision_dates) * 100
    s1_segments = _s1_subperiods(net_returns, exec_str)
    worst_degrad = min(v["degradation"] for v in s1_segments.values())
    s1_pass = worst_degrad >= -0.05
    s2_pass = fee_bps is not None and slip_bps is not None and fee_bps <= 5 and slip_bps <= 10
    s3_pass = s3_pct <= 1.0
    stop = not (s1_pass and s2_pass and s3_pass)

    prov = _provenance()
    results = {
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
            "fail_closed": {"structural_ineligible_cash_parking": int(len(structural_days)),
                            "no_quote_days": int(len(no_quote_days)),
                            "distinct_fail_closed_days": int(len(fail_closed_days)),
                            "s3_fail_closed_pct": round(s3_pct, 3)},
            "hk_dividend_diagnostic": _hk_diagnostic(W, decision_dates, total_open_val,
                                                     hk_attempts, hk_fills, hk_notional,
                                                     hk_feasible_days, hk_slot_idx),
        },
        "stop_criteria": {
            "S1": {"worst_subperiod_degradation": round(worst_degrad, 6), "pass": bool(s1_pass)},
            "S2": {"fee_bps": round(fee_bps, 3) if fee_bps else None,
                   "slippage_bps": round(slip_bps, 3) if slip_bps else None, "pass": bool(s2_pass)},
            "S3": {"fail_closed_pct": round(s3_pct, 3),
                   "structural_days": int(len(structural_days)),
                   "no_quote_days": int(len(no_quote_days)),
                   "overlap_days": int(len(overlap_days)),
                   "pass": bool(s3_pass)},
            "S4": "NOT_APPLICABLE (backtest mode)",
            "STOP": bool(stop),
        },
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
            "settlement": {"A_SHARE_T": 1, "HK_T": 2,
                           "session_calendar": "A股: SH exec session T+1 buying-power (T+0 same-day reuse, T+1 withdrawal); 03110: 03110.HK tradable-session calendar T+2"},
            "premium_guard": "INSTRUMENT_BACKTEST = NOT_EVALUABLE_HISTORICALLY (N/A)",
            "hk_price_source": "sina_qfq (akshare stock_hk_daily qfq==raw for 03110; QMT raw all-zero unavailable)",
            "no_rl": True,
            "data_provenance": prov,
            "l1_research_reference": {
                "results_artifact": str(L1_RESEARCH_ARTIFACT.relative_to(ROOT)),
                "results_sha256": sha256_of(L1_RESEARCH_ARTIFACT),
                "raw_artifact": str(L1_RAW_ARTIFACT.relative_to(ROOT)),
                "raw_sha256": sha256_of(L1_RAW_ARTIFACT),
            },
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "provenance_count": int(len(prov)),
        },
    }
    try:
        results["manifest"]["commit"] = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT).decode().strip()
    except Exception:  # noqa: BLE001
        results["manifest"]["commit"] = None
    return results


def main() -> None:
    if "--check" in sys.argv:
        _run_check()
        return
    data = load_all()
    results = _simulate(data)
    art = ROOT / "artifacts"
    art.mkdir(parents=True, exist_ok=True)
    out = art / "gate4_instrument_execution_realism_results.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    cal = data["adj"].index.normalize()
    ds_i = cal.get_loc(pd.Timestamp(FROZEN["decision_start"]))
    last_dec_i = len(cal) - 2
    decision_dates = cal[ds_i:last_dec_i + 1]
    exec_dates = cal[ds_i + 1:last_dec_i + 2]
    W = maxdiv_weights(data["adj"], data["opens"], data["closes"], decision_dates, ca=data["ca"])
    raw = art / "gate4_instrument_execution_realism_raw.json"
    raw.write_text(json.dumps({
        "execution_dates": [str(d.date()) for d in exec_dates],
        "target_weights": W.tolist(),
        "stop_criteria": results["stop_criteria"],
    }, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    m = results["metrics"]
    c = results["cost_aggregation"]
    e = results["execution"]
    s = results["stop_criteria"]
    print(f"cum={m['cum_return']:+.4f} cagr={m['calendar_cagr']:+.4f} "
          f"sharpe={m['sharpe']:.3f} mdd={m['max_drawdown']:.4f} "
          f"fee_bps={c['fee_bps_of_traded_notional']} slip_bps={c['slippage_bps_of_traded_notional']} "
          f"fill={e['fill_count']} track_err={e['mean_target_tracking_error']:.4f} "
          f"S1={s['S1']['pass']} S2={s['S2']['pass']} S3={s['S3']['pass']} STOP={s['STOP']}")
    print(f"hk_diagnostic={e['hk_dividend_diagnostic']}")
    print(f"-> {out}")


def _price_hkd(opens_hkd: pd.Series, inst, t_next, price_cny, fx_t1):
    """03110 T+1 open HKD 本地价（fresh 下为精确当日）；缺失时 CNY 价 ÷ T-1 FX 反推。"""
    v = opens_hkd[opens_hkd.index <= t_next]
    if len(v):
        return float(v.iloc[-1])
    return price_cny / fx_t1 if fx_t1 > 0 else float("nan")


def _hk_diagnostic(W, decision_dates, total_open_val, attempts, fills, notional,
                   feasible_days, hk_slot_idx) -> dict:
    """03110 post-2024-05-06 执行诊断（评审要求：attempted orders / feasible lots / fills / notional）。"""
    eligible = decision_dates >= pd.Timestamp(HK_DIVIDEND_DATES["southbound_eligible_from"])
    w_eligible = W[eligible][:, hk_slot_idx]
    return {
        "post_eligible_days": int(eligible.sum()),
        "mean_target_weight": round(float(w_eligible.mean()), 6) if len(w_eligible) else None,
        "max_target_weight": round(float(w_eligible.max()), 6) if len(w_eligible) else None,
        "dates_target_notional_ge_one_board_lot": int(feasible_days),
        "attempted_orders": int(attempts),
        "actual_fills": int(fills),
        "traded_notional_cny": round(notional, 2),
        "note": "descriptive only; instrument/strategy unchanged",
    }


def _research_cagr_segments() -> dict[str, float]:
    """已接受 L1 research artifact 每子期研究 CAGR = (1+cum)^(252/n_days) - 1（同边界）。"""
    ref = json.loads(L1_RESEARCH_ARTIFACT.read_text(encoding="utf-8"))
    sp = ref["methods"][L1_MAXDIV_KEY]["sub_periods"]
    out = {}
    for y, v in sp["calendar_years"].items():
        out[f"year_{y}"] = (1 + v["cum_return"]) ** (252 / v["n_days"]) - 1
    for ph, v in sp["phases"].items():
        if ph == "split_label":
            continue
        out[ph] = (1 + v["cum_return"]) ** (252 / v["n_days"]) - 1
    return out


def _s1_subperiods(net_returns, exec_dates) -> dict:
    """每子期 net CAGR vs 已接受 L1 研究 CAGR（同边界）；worst 段判 S1。"""
    dates = pd.DatetimeIndex([pd.Timestamp(d) for d in exec_dates])
    s = pd.Series(np.asarray(net_returns, dtype=float), index=dates)
    ref = _research_cagr_segments()
    out = {}
    for y, grp in s.groupby(s.index.year):
        seg = f"year_{y}"
        if len(grp) >= 2 and seg in ref:
            net_cagr = _cagr_of(grp.to_numpy())
            out[seg] = {"net_cagr": round(net_cagr, 6),
                        "research_cagr": round(ref[seg], 6),
                        "degradation": round(net_cagr - ref[seg], 6),
                        "n_days": int(len(grp))}
    for name, a, b in STRESS_REGIMES:
        mask = (s.index >= pd.Timestamp(a)) & (s.index <= pd.Timestamp(b))
        seg = s[mask]
        if len(seg) >= 2 and name in ref:
            net_cagr = _cagr_of(seg.to_numpy())
            out[name] = {"net_cagr": round(net_cagr, 6),
                         "research_cagr": round(ref[name], 6),
                         "degradation": round(net_cagr - ref[name], 6),
                         "n_days": int(len(seg))}
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
    """全部实际消费输入 SHA256（Mainland QMT raw + 513690 research raw + sina_qfq + FX + CA 事件）。"""
    prov = {}
    raw = ROOT / "data" / "qmt" / "raw"
    meta = ROOT / "data" / "qmt" / "meta"
    files = []
    for slot, meta_slot in SLOT_MAP.items():
        inst = meta_slot["instrument"]
        files.append(raw / f"{slot}_{inst.replace('.', '_')}_raw.csv")
    files.append(SINA_HK_FILE)
    files.append(meta / "hkd_cny_boc.csv")
    for ev in (meta / "divid_events").glob("*.csv"):
        files.append(ev)
    for f in files:
        if f.exists():
            prov[str(f.relative_to(ROOT))] = sha256_of(f)
    return prov


def _run_check() -> None:
    print("== Instrument Execution Realism CORRECTION_003 --check ==")
    assert SLOT_INSTRUMENT["CN_LARGE"] == "510300.SH", "CN_LARGE must be 510300.SH"
    assert SLOT_INSTRUMENT["HK_DIVIDEND"] == "03110.HK", "HK_DIVIDEND must be 03110.HK"
    assert HK_DIVIDEND_DATES == {"listing": "2013-06-17", "data_start": "2021-01-11",
                                 "southbound_eligible_from": "2024-05-06"}
    assert BOARD_LOT == {"t_lt_2026_07_24": 100, "t_gte_2026_07_24": 50}
    assert L1_RESEARCH_ARTIFACT.exists(), "L1 research artifact missing"
    assert L1_RAW_ARTIFACT.exists(), "L1 raw artifact missing"
    assert SINA_HK_FILE.exists(), "03110 sina_qfq missing"
    hk = pd.read_csv(SINA_HK_FILE)
    dc = next(c for c in ("date", "index", "time") if c in hk.columns)
    hk[dc] = pd.to_datetime(hk[dc].astype(str))
    hk = hk.set_index(dc)
    el = hk.loc[hk.index >= "2024-05-06"]
    assert int((el["open"].astype(float) > 0).sum()) > 500, "03110 marks must be finite post-eligibility"
    print(f"slot->instrument: {SLOT_INSTRUMENT}")
    print(f"hk_dividend_dates: {HK_DIVIDEND_DATES}")
    print(f"board_lot: {BOARD_LOT}")
    print(f"03110 sina_qfq finite open post-2024-05-06: {int((el['open'].astype(float) > 0).sum())}")
    print(f"cost routing: Mainland -> MainlandETFCostModel; 03110.HK -> SouthboundETFCostModel")
    print(f"settlement: A股 T+1 (T+0 buying power); 03110 T+2 (03110.HK session calendar)")
    src = Path(__file__).read_text(encoding="utf-8")
    for tok in ["P" + "PO", "S" + "AC", "T" + "D3", "stable" + "_baselines3"]:
        assert tok not in src, f"forbidden RL token in runner"
    print("--check PASSED")


if __name__ == "__main__":
    main()
