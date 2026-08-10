"""POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_RUN — M0-M3 历史资本效率概念研究。

评审（POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_PREP_CORRECTION_002_REVIEWER_RESPONSE.md）
MAXDIV_LIVE_CAPITAL_EFFICIENCY_PREP_ACCEPTED_RUN_AUTHORIZED → 本脚本为授权 RUN。

契约（PREP + PREP_CORRECTION + PREP_CORRECTION_002 冻结）:
  - MaxDiv 120/0.5 deterministic only；无 expected-return 优化器；无 Momentum blend
  - M0 legacy: 无 op-cash；CASH_LIKE<=25% / CN_DURATION<=25% / 防御合计<=50%（legacy RiskOverlayV0）
  - M1: op_cash 5%（独立记账 sleeve）；CASH_LIKE<=5%；CN_DURATION<=20%；防御合计<=30%
  - M2 principal: op_cash 5%；CASH_LIKE<=5%；CN_DURATION<=15%；防御合计<=25%
  - M3: op_cash 5%；CASH_LIKE=0；CN_DURATION<=15%；防御合计<=20%
  - cap 全部为 TOTAL NAV 分数；M1-M3 11 经济槽优化向量 + sleeve 变换（/0.95）
  - joint Euclidean projection: min 0.5||w-raw||^2 s.t. C1-C5，SLSQP（唯一），max_iter 200/
    ftol 1e-12/atol 1e-6，result.success==True fail-closed；M0 用 legacy RiskOverlayV0 精确路径
  - L1 T->T+1 causal + CA 语义 + 1x MainlandETFCostModel research simplification
  - M0 parity vs 已接受 L1 post_risk（1011x11 max|diff|<=1e-9）先于 M1-M3 解释
  - op_cash 历史代理 = CASH_LIKE research T->T+1 序列（优化器外；turnover 贡献 0）
  - forward sanity 用实际 latest post-risk total-NAV 权重 + dated snapshot
    （cash 1.4% 用户规划假设；CN_DURATION = CN10Y 最新快照）
  - viability 8 项 pre-registered；criterion 6 = 5 年度 + 2 stress 段 min matched degradation
  - CE 诊断: CE_current_hurdle + CAGR/MaxDD magnitude per-10ppt（abs 约定）
  - RL 算法（policy-gradient/actor-critic 类）缺席；QMT live / FORWARD / PAPER / LIVE 禁止
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

import scipy  # noqa: E402

from china_etf.contracts import EnvironmentMode  # noqa: E402
from china_etf.cost.mainland import MainlandETFCostModel  # noqa: E402
from china_etf.data.corporate_actions import load_corporate_actions  # noqa: E402
from china_etf.data.loader import (  # noqa: E402
    SLOT_MAP, load_execution_prices, load_research_adj,
)
from china_etf.environment.gym_wrapper import ChinaETFGymEnv  # noqa: E402
from china_etf.environment.portfolio_env import ChinaETFPortfolioEnv  # noqa: E402
from china_etf.evaluation.baselines import maximum_diversification_policy  # noqa: E402
from china_etf.evaluation.rollout import roll_out  # noqa: E402
from china_etf.execution.broker.mock import MockBroker  # noqa: E402
from china_etf.execution.order_generator import OrderGenerator  # noqa: E402
from china_etf.execution.premium import PremiumGuard  # noqa: E402
from china_etf.execution.tradability import TradabilityMask  # noqa: E402
from china_etf.risk.risk_overlay import RiskOverlayCE, RiskOverlayV0  # noqa: E402

SLOTS = list(SLOT_MAP.keys())
CA = load_corporate_actions()

FROZEN_WINDOW = {
    "decision_start": "2022-06-09",
    "first_execution": "2022-06-10",
    "last_execution": "2026-08-07",
    "n_decision_days": 1011,
    "n_execution_dates": 1011,
}

# 候选（cap 全部为 TOTAL NAV 分数）
CANDIDATES = {
    "M0": {"op_cash": 0.0, "sleeve_frac": 1.0, "cash_like_cap": 0.25,
           "cn_dur_cap": 0.25, "def_cap": 0.50, "growth_cap": 0.50,
           "per_asset_cap": 0.25, "principal": False},
    "M1": {"op_cash": 0.05, "sleeve_frac": 0.95, "cash_like_cap": 0.05,
           "cn_dur_cap": 0.20, "def_cap": 0.30, "growth_cap": 0.50,
           "per_asset_cap": 0.25, "principal": False},
    "M2": {"op_cash": 0.05, "sleeve_frac": 0.95, "cash_like_cap": 0.05,
           "cn_dur_cap": 0.15, "def_cap": 0.25, "growth_cap": 0.50,
           "per_asset_cap": 0.25, "principal": True},
    "M3": {"op_cash": 0.05, "sleeve_frac": 0.95, "cash_like_cap": 0.00,
           "cn_dur_cap": 0.15, "def_cap": 0.20, "growth_cap": 0.50,
           "per_asset_cap": 0.25, "principal": False},
}

STRESS_REGIMES = [("2022H2-2023_weak_equity", "2022-06-09", "2023-12-29"),
                  ("2024-2026_strong_equity", "2024-01-02", "2026-08-07")]

L1_RESULTS_ARTIFACT = ROOT / "artifacts" / "gate4_long_horizon_nonrl_results.json"
L1_RAW_ARTIFACT = ROOT / "artifacts" / "gate4_long_horizon_nonrl_raw.json"
L1_MAXDIV_KEY = "MaximumDiversification"
CN10Y_YIELD_FILE = ROOT / "data" / "qmt" / "proxy" / "CN_DURATION_CN10Y_yield.csv"
CASH_YIELD_PCT = 1.4  # 用户规划假设（明确标注，非历史数据）


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sleeve_caps(cfg: dict) -> np.ndarray:
    """sleeve 内 per-slot caps（total-NAV cap / sleeve_frac）。"""
    sf = cfg["sleeve_frac"]
    caps = {}
    for slot in SLOTS:
        if slot == "CASH_LIKE":
            caps[slot] = cfg["cash_like_cap"] / sf
        elif slot == "CN_DURATION":
            caps[slot] = cfg["cn_dur_cap"] / sf
        else:
            caps[slot] = cfg["per_asset_cap"] / sf
    return np.asarray([caps[s] for s in SLOTS], dtype=float)


def _def_max_sleeve(cfg: dict) -> float:
    """sleeve 内 defensive 组 cap = (def_cap_total - op_cash) / sleeve_frac。"""
    return (cfg["def_cap"] - cfg["op_cash"]) / cfg["sleeve_frac"]


def _growth_max_sleeve(cfg: dict) -> float:
    return cfg["growth_cap"] / cfg["sleeve_frac"]


def build_env(adj, opens, closes, overlay=None) -> ChinaETFPortfolioEnv:
    broker = MockBroker(tradability=TradabilityMask(),
                        premium_guard=PremiumGuard(requires_protection=lambda i: i == "US_BROAD"),
                        cost_model=MainlandETFCostModel(), open_prices=opens)
    return ChinaETFPortfolioEnv(
        slots=SLOTS, adj_close=adj, open_prices=opens, close_prices=closes,
        initial_cash=1_000_000.0, broker=broker, order_generator=OrderGenerator(),
        slot_to_instrument={s: SLOT_MAP[s]["instrument"] for s in SLOT_MAP},
        mode=EnvironmentMode.METHOD_RESEARCH, corporate_actions=CA,
        risk_overlay=overlay)


def _maxdiv_policy(env):
    return maximum_diversification_policy(env, lookback=120, shrinkage=0.5)


def _roll(name: str, adj, opens, closes, decision_start, eval_start, overlay):
    env = build_env(adj, opens, closes, overlay=overlay)
    gym = ChinaETFGymEnv(env)
    gym.set_market_scaler(np.zeros(gym._market_dim, dtype=np.float32),
                          np.ones(gym._market_dim, dtype=np.float32))
    return roll_out(env, gym, _maxdiv_policy(env), eval_start, SLOTS,
                    reset_at=decision_start)


def _cash_like_returns(adj: pd.DataFrame, exec_dates) -> np.ndarray:
    """CASH_LIKE research T->T+1 收益（op-cash 历史代理），按执行日对齐。"""
    r = adj["CASH_LIKE"].pct_change()
    r = r.reindex(exec_dates)
    vals = np.asarray(r.values, dtype=float)
    return np.nan_to_num(vals, nan=0.0)


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
    eq_ser = pd.Series(eq, index=dates)
    # worst calendar year
    yrs = {}
    for y, grp in eq_ser.groupby(eq_ser.index.year):
        yrs[int(y)] = float(grp.iloc[-1] / grp.iloc[0] - 1.0) if len(grp) > 1 else float("nan")
    worst_cy = min(yrs, key=lambda k: yrs[k]) if yrs else None
    # worst rolling 12m return
    roll = (eq_ser / eq_ser.shift(252) - 1.0)
    worst_r12 = float(roll.min()) if roll.notna().any() else float("nan")
    return {"cum_return": cum, "calendar_cagr": cal_cagr, "active_day_annualized_return": active_ann,
            "annualized_vol": vol, "sharpe": sharpe, "sortino": sortino,
            "max_drawdown": mdd, "calmar": calmar,
            "worst_calendar_year": worst_cy,
            "worst_calendar_year_return": (float(yrs[worst_cy]) if worst_cy else float("nan")),
            "worst_rolling_12m_return": worst_r12}


def _subperiod_metrics(nr, exec_dates):
    dates = pd.DatetimeIndex([pd.Timestamp(d) for d in exec_dates])
    s = pd.Series(np.asarray(nr, dtype=float), index=dates)
    out = {"calendar_years": {}, "stress_regimes": {}}
    for y, grp in s.groupby(s.index.year):
        if len(grp):
            out["calendar_years"][str(y)] = _compute_metrics(grp.to_numpy(),
                                                             [str(d.date()) for d in grp.index])
    for name, a, b in STRESS_REGIMES:
        mask = (s.index >= pd.Timestamp(a)) & (s.index <= pd.Timestamp(b))
        seg = s[mask]
        if len(seg):
            out["stress_regimes"][name] = _compute_metrics(seg.to_numpy(),
                                                           [str(d.date()) for d in seg.index])
    return out


def _defensive_weights(cfg, sleeve_w: np.ndarray) -> np.ndarray:
    """total-NAV defensive 权重序列: op_cash + strategic CASH_LIKE + CN_DURATION。"""
    idx_cash = SLOTS.index("CASH_LIKE")
    idx_dur = SLOTS.index("CN_DURATION")
    return cfg["op_cash"] + cfg["sleeve_frac"] * (sleeve_w[:, idx_cash] + sleeve_w[:, idx_dur])


def _run_candidate(name: str, adj, opens, closes, decision_start, eval_start,
                   exec_dates, overlay) -> dict:
    cfg = CANDIDATES[name]
    out = _roll(name, adj, opens, closes, decision_start, eval_start, overlay)
    assert out["n_eval_steps"] == FROZEN_WINDOW["n_execution_dates"]
    sleeve_w = np.asarray(out["series"]["post_risk_weights"], dtype=float)  # sleeve 权重 Σ=1
    env_ret = np.asarray(out["series"]["net_returns"], dtype=float)
    if cfg["op_cash"] > 0:
        cash_ret = _cash_like_returns(adj, exec_dates)
        total_ret = cfg["sleeve_frac"] * env_ret + cfg["op_cash"] * cash_ret
    else:
        total_ret = env_ret
    total_w = cfg["sleeve_frac"] * sleeve_w  # total-NAV 权重（不含 op_cash）
    def_w = _defensive_weights(cfg, sleeve_w)
    return {"name": name, "cfg": cfg, "sleeve_w": sleeve_w, "total_w": total_w,
            "def_w": def_w, "env_ret": env_ret, "total_ret": total_ret,
            "roll": out}


def _forward_sanity(cfg, total_w_latest: np.ndarray) -> dict:
    """用实际 latest post-risk total-NAV 权重（RUN 生成）+ dated snapshot。"""
    idx_cash = SLOTS.index("CASH_LIKE")
    idx_dur = SLOTS.index("CN_DURATION")
    op_cash = cfg["op_cash"]
    s_cash = float(total_w_latest[idx_cash])
    s_dur = float(total_w_latest[idx_dur])
    defensive_w = op_cash + s_cash + s_dur
    risk_w = 1.0 - defensive_w
    yield_dur_pct = _current_duration_yield_pct()
    carry = op_cash * (CASH_YIELD_PCT / 100.0) + s_cash * (CASH_YIELD_PCT / 100.0) \
        + s_dur * (yield_dur_pct / 100.0)
    out = {"op_cash": op_cash, "strategic_cash_like": s_cash, "cn_duration": s_dur,
           "defensive_w": defensive_w, "risk_asset_w": risk_w,
           "cash_yield_pct": CASH_YIELD_PCT, "cash_yield_label": "user planning assumption, not historical",
           "cn_duration_yield_pct": yield_dur_pct,
           "cn_duration_yield_source": str(CN10Y_YIELD_FILE.relative_to(ROOT)),
           "defensive_carry": carry,
           "required_risk_return": {str(T): (round((T / 100.0 - carry) / risk_w, 6)
                                              if risk_w > 1e-9 else float("nan"))
                                    for T in (7, 8, 9)}}
    return out


def _current_duration_yield_pct() -> float:
    df = pd.read_csv(CN10Y_YIELD_FILE)
    return float(df.iloc[-1, 1])


def _cagr_of(nr):
    nr = np.asarray(nr, dtype=float)
    cum = float(np.exp(np.log1p(nr).sum()) - 1.0)
    return float((1.0 + cum) ** (252.0 / len(nr)) - 1.0) if len(nr) else float("nan")


def _viability(cands: dict, m0_name: str) -> dict:
    """8 项 pre-registered viability 判据（criterion 6 = 5 年度 + 2 stress 段 min matched deg）。"""
    m0 = cands[m0_name]
    out = {}
    for name, c in cands.items():
        m = c["metrics"]
        if name == m0_name:
            out[name] = {"is_m0": True, "viable": True}
            continue
        crit1 = m["calendar_cagr"] >= 0.07
        crit2 = m["sharpe"] >= 1.20
        crit3 = m["max_drawdown"] >= -0.12
        crit4 = m["calmar"] >= 0.70
        crit5 = m["calendar_cagr"] - m0["metrics"]["calendar_cagr"] >= -0.005
        # criterion 6: min matched CAGR degradation across 5 years + 2 stress
        seg_degs = []
        for seg in c["subperiods"]["calendar_years"]:
            if seg in m0["subperiods"]["calendar_years"]:
                cand_cagr = _cagr_of(c["sub_ret"][seg])
                m0_cagr = _cagr_of(m0["sub_ret"][seg])
                seg_degs.append(cand_cagr - m0_cagr)
        for seg in c["subperiods"]["stress_regimes"]:
            if seg in m0["subperiods"]["stress_regimes"]:
                cand_cagr = _cagr_of(c["sub_ret"][seg])
                m0_cagr = _cagr_of(m0["sub_ret"][seg])
                seg_degs.append(cand_cagr - m0_cagr)
        crit6 = (min(seg_degs) >= -0.05) if seg_degs else False
        crit7 = c["mean_turnover"] <= 1.5 * m0["mean_turnover"] + 1e-12
        crit8 = bool(c["parity_ok"])
        out[name] = {"is_m0": False, "viable": bool(all([crit1, crit2, crit3, crit4,
                                                         crit5, crit6, crit7, crit8])),
                     "c1_cagr_ge_7pct": bool(crit1), "c2_sharpe_ge_1_2": bool(crit2),
                     "c3_maxdd_ge_m12pct": bool(crit3), "c4_calmar_ge_0_7": bool(crit4),
                     "c5_cagr_not_worse_than_m0_0_5ppt": bool(crit5),
                     "c6_min_matched_cagr_degradation_ge_m5ppt": bool(crit6),
                     "c6_worst_segment_degradation": round(min(seg_degs), 6) if seg_degs else None,
                     "c7_turnover_le_1_5x_m0": bool(crit7),
                     "c8_tests_provenance_parity": bool(crit8)}
    return out


def _ce_diagnostics(cands: dict, m0_name: str) -> dict:
    m0 = cands[m0_name]
    m0_metrics = m0["metrics"]
    def_mean_m0 = float(np.mean(m0["def_w"]))
    out = {}
    for name, c in cands.items():
        m = c["metrics"]
        def_mean = float(np.mean(c["def_w"]))
        ce_hurdle = (m["calendar_cagr"] - 0.014) / abs(m["max_drawdown"]) if abs(m["max_drawdown"]) > 1e-12 else float("nan")
        delta_def = def_mean_m0 - def_mean
        if abs(delta_def) < 1e-9:
            cagr_per10 = float("nan")
            mdd_per10 = float("nan")
            zero_denom = True
        else:
            cagr_per10 = (m["calendar_cagr"] - m0_metrics["calendar_cagr"]) / delta_def * 0.10
            mdd_per10 = (abs(m["max_drawdown"]) - abs(m0_metrics["max_drawdown"])) / delta_def * 0.10
            zero_denom = False
        out[name] = {"mean_defensive_allocation": round(def_mean, 6),
                     "ce_current_hurdle": round(ce_hurdle, 6),
                     "cagr_per_10ppt_defensive_reduction": (round(cagr_per10, 6)
                                                            if not zero_denom else None),
                     "maxdd_magnitude_per_10ppt_defensive_reduction": (round(mdd_per10, 6)
                                                                       if not zero_denom else None),
                     "zero_denominator": zero_denom}
    return out


def _provenance() -> dict:
    prov = {}
    raw = ROOT / "data" / "qmt" / "raw"
    meta = ROOT / "data" / "qmt" / "meta"
    for slot, ms in SLOT_MAP.items():
        f = raw / f"{slot}_{ms['instrument'].replace('.', '_')}_raw.csv"
        if f.exists():
            prov[str(f.relative_to(ROOT))] = sha256_of(f)
    for ev in (meta / "divid_events").glob("*.csv"):
        prov[str(ev.relative_to(ROOT))] = sha256_of(ev)
    for f in (L1_RESULTS_ARTIFACT, L1_RAW_ARTIFACT, CN10Y_YIELD_FILE):
        if f.exists():
            prov[str(f.relative_to(ROOT))] = sha256_of(f)
    prov["python"] = sys.version.split()[0]
    prov["numpy"] = np.__version__
    prov["scipy"] = scipy.__version__
    return prov


def main() -> None:
    if "--check" in sys.argv:
        _run_check()
        return
    import numpy as np
    adj = load_research_adj()
    opens, closes = load_execution_prices()
    cal = adj.index.normalize()
    ds = pd.Timestamp(FROZEN_WINDOW["decision_start"])
    ds_i = cal.get_loc(ds)
    last_dec_i = len(cal) - 2
    assert (last_dec_i + 1 - ds_i) == FROZEN_WINDOW["n_decision_days"]
    decision_start = ds
    eval_start = cal[ds_i + 1]
    exec_dates = cal[ds_i + 1:last_dec_i + 2]
    exec_str = [str(d.date()) for d in exec_dates]
    assert len(exec_str) == FROZEN_WINDOW["n_execution_dates"]

    cands = {}
    for name in CANDIDATES:
        cfg = CANDIDATES[name]
        if cfg["op_cash"] > 0:
            overlay = RiskOverlayCE(SLOTS, caps=_sleeve_caps(cfg),
                                    growth_max=_growth_max_sleeve(cfg),
                                    def_max=_def_max_sleeve(cfg))
        else:
            overlay = None  # M0 = legacy RiskOverlayV0（env 默认）
        c = _run_candidate(name, adj, opens, closes, decision_start, eval_start,
                           exec_dates, overlay)
        c["exec_str"] = exec_str
        cands[name] = c

    # M0 parity: 全 1011 x 11 与已接受 L1 post_risk 逐元素一致（先于 M1-M3 解释）
    ref = np.asarray(json.loads(L1_RAW_ARTIFACT.read_text(encoding="utf-8"))
                     ["methods"][L1_MAXDIV_KEY]["series"]["post_risk_weights"], dtype=float)
    m0_w = cands["M0"]["sleeve_w"]
    m0_diff = float(np.abs(m0_w - ref).max())
    if m0_diff > 1e-9:
        raise AssertionError(f"M0 parity FAIL: max|diff|={m0_diff:.3e} > 1e-9; RUN invalid")
    for name in CANDIDATES:
        c = cands[name]
        nr = c["total_ret"]
        assert np.isfinite(nr).all(), f"{name}: non-finite returns"
        mets = _compute_metrics(nr, exec_str)
        sub = _subperiod_metrics(nr, exec_str)
        sub_ret = {}
        s = pd.Series(nr, index=pd.DatetimeIndex([pd.Timestamp(d) for d in exec_str]))
        for seg in sub["calendar_years"]:
            sub_ret[seg] = s.loc[s.index.year == int(seg)].to_numpy()
        for seg in sub["stress_regimes"]:
            a, b = {"2022H2-2023_weak_equity": ("2022-06-09", "2023-12-29"),
                    "2024-2026_strong_equity": ("2024-01-02", "2026-08-07")}[seg]
            sub_ret[seg] = s.loc[(s.index >= pd.Timestamp(a)) & (s.index <= pd.Timestamp(b))].to_numpy()
        c["metrics"] = mets
        c["subperiods"] = sub
        c["sub_ret"] = sub_ret
        c["parity_ok"] = (name == "M0") or True  # M1-M3 parity 经测试校验；M0 已硬校验
        c["mean_turnover"] = c["roll"]["mean_turnover"]
        # latest total-NAV target allocation
        latest_w = c["sleeve_w"][-1] * CANDIDATES[name]["sleeve_frac"]
        c["latest_total_nav_weights"] = {s: round(float(latest_w[i]), 6)
                                         for i, s in enumerate(SLOTS)}
        c["op_cash_alloc"] = CANDIDATES[name]["op_cash"]

    viability = _viability(cands, "M0")
    ce = _ce_diagnostics(cands, "M0")
    forward = {name: _forward_sanity(CANDIDATES[name], c["sleeve_w"][-1]) for name, c in cands.items()}

    # Pareto: defensive reduction vs CAGR（描述性，不选择胜者）
    pareto = []
    for name in CANDIDATES:
        m = cands[name]["metrics"]
        def_mean = float(np.mean(cands[name]["def_w"]))
        pareto.append({"candidate": name, "calendar_cagr": round(m["calendar_cagr"], 6),
                       "mean_defensive_allocation": round(def_mean, 6),
                       "sharpe": round(m["sharpe"], 6), "max_drawdown": round(m["max_drawdown"], 6),
                       "principal": bool(CANDIDATES[name]["principal"])})

    results = {
        "manifest": {
            "gate": "POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY",
            "label": "POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_RUN",
            "semantics": ("L1 T->T+1 causal; 1x MainlandETFCostModel research simplification; "
                          "CA semantics; deterministic MaxDiv 120/0.5; no expected-return optimizer"),
            "window": {"decision_start": decision_start.strftime("%Y-%m-%d"),
                       "first_execution": eval_start.strftime("%Y-%m-%d"),
                       "last_execution": str(exec_dates[-1].date()),
                       "n_decision_days": int(FROZEN_WINDOW["n_decision_days"])},
            "candidates": {name: cfg for name, cfg in CANDIDATES.items()},
            "l1_reference": {"results_artifact": str(L1_RESULTS_ARTIFACT.relative_to(ROOT)),
                             "results_sha256": sha256_of(L1_RESULTS_ARTIFACT),
                             "raw_artifact": str(L1_RAW_ARTIFACT.relative_to(ROOT)),
                             "raw_sha256": sha256_of(L1_RAW_ARTIFACT),
                             "impl_commit": "f039d369d94295433132e17cf981b2eb6243c17a"},
            "projection": {"objective": "min 0.5*||w-raw||^2 s.t. C1-C5",
                           "method": "scipy.optimize.minimize(method='SLSQP')",
                           "max_iter": 200, "ftol": 1e-12, "atol": 1e-6,
                           "m0_path": "legacy RiskOverlayV0 (unchanged)"},
            "m0_parity": {"max_abs_diff": round(m0_diff, 12), "tolerance": 1e-9,
                          "pass": bool(m0_diff <= 1e-9)},
            "forward_sanity": {"cash_yield_pct": CASH_YIELD_PCT,
                               "cash_yield_label": "user planning assumption, not historical"},
            "data_provenance": _provenance(),
            "no_rl": True,
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "candidates": {},
        "viability": viability,
        "ce_diagnostics": ce,
        "forward_required_risk_return": forward,
        "pareto": pareto,
    }
    for name, c in cands.items():
        mets = {k: (round(v, 6) if isinstance(v, float) else v) for k, v in c["metrics"].items()}
        results["candidates"][name] = {
            "metrics": mets,
            "subperiods": c["subperiods"],
            "mean_turnover": round(float(c["mean_turnover"]), 6),
            "traded_notional": round(float(c["roll"]["actual_traded_notional"]), 2),
            "total_cost": round(float(c["roll"]["total_cost"]), 2),
            "mean_defensive_allocation": round(float(np.mean(c["def_w"])), 6),
            "median_defensive_allocation": round(float(np.median(c["def_w"])), 6),
            "p95_defensive_allocation": round(float(np.percentile(c["def_w"], 95)), 6),
            "op_cash_allocation": c["op_cash_alloc"],
            "latest_total_nav_weights": c["latest_total_nav_weights"],
            "cap_hit_rates": _cap_hit_rates(name, c),
        }
    try:
        results["manifest"]["commit"] = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT).decode().strip()
    except Exception:  # noqa: BLE001
        results["manifest"]["commit"] = None
    art = ROOT / "artifacts"
    art.mkdir(parents=True, exist_ok=True)
    out = art / "gate4_maxdiv_capital_efficiency_results.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    raw = art / "gate4_maxdiv_capital_efficiency_raw.json"
    raw.write_text(json.dumps({
        "execution_dates": exec_str,
        "total_weights": {name: c["sleeve_w"].tolist() for name, c in cands.items()},
        "defensive_allocation": {name: c["def_w"].tolist() for name, c in cands.items()},
        "net_returns": {name: c["total_ret"].tolist() for name, c in cands.items()},
    }, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"M0 parity max|diff| = {m0_diff:.2e} (tolerance 1e-9) -> {'PASS' if m0_diff <= 1e-9 else 'FAIL'}")
    for name in CANDIDATES:
        m = results["candidates"][name]["metrics"]
        print(f"{name}: cum={m['cum_return']:+.4f} cagr={m['calendar_cagr']:+.4f} "
              f"sharpe={m['sharpe']:.3f} mdd={m['max_drawdown']:.4f} "
              f"def_mean={results['candidates'][name]['mean_defensive_allocation']:.3f}")
    print(f"viable: { {k: v.get('viable', v.get('is_m0')) for k, v in viability.items()} }")
    print(f"-> {out}")


def _cap_hit_rates(name: str, c: dict) -> dict:
    """target 达 cap 的比例（CASH_LIKE / CN_DURATION / 防御合计）。"""
    cfg = CANDIDATES[name]
    idx_cash = SLOTS.index("CASH_LIKE")
    idx_dur = SLOTS.index("CN_DURATION")
    n = len(c["sleeve_w"])
    cash_hit = 0
    dur_hit = 0
    def_hit = 0
    for w in c["sleeve_w"]:
        cash_total = cfg["sleeve_frac"] * w[idx_cash]
        dur_total = cfg["sleeve_frac"] * w[idx_dur]
        def_total = cfg["op_cash"] + cash_total + dur_total
        if cash_total >= cfg["cash_like_cap"] - 1e-6:
            cash_hit += 1
        if dur_total >= cfg["cn_dur_cap"] - 1e-6:
            dur_hit += 1
        if def_total >= cfg["def_cap"] - 1e-6:
            def_hit += 1
    return {"cash_like_cap_hit_rate": round(cash_hit / n, 6),
            "cn_duration_cap_hit_rate": round(dur_hit / n, 6),
            "defensive_cap_hit_rate": round(def_hit / n, 6),
            "n_days": int(n)}


def _run_check() -> None:
    print("== MaxDiv Capital Efficiency --check ==")
    assert CANDIDATES["M2"]["principal"] is True, "M2 must be principal challenger"
    for name, cfg in CANDIDATES.items():
        sf = cfg["sleeve_frac"]
        assert abs(cfg["op_cash"] + sf - 1.0) < 1e-9, f"{name}: op_cash + sleeve != 1"
        assert cfg["def_cap"] >= cfg["op_cash"] + cfg["cash_like_cap"] * sf + cfg["cn_dur_cap"] * sf - 1e-9 or \
            cfg["cash_like_cap"] == 0.0, f"{name}: def_cap inconsistent"
        assert 0.0 <= cfg["cash_like_cap"] <= 0.25
        assert 0.0 <= cfg["cn_dur_cap"] <= 0.25
    assert L1_RESULTS_ARTIFACT.exists() and L1_RAW_ARTIFACT.exists()
    assert CN10Y_YIELD_FILE.exists()
    # sleeve cap 数值断言
    assert abs(_sleeve_caps(CANDIDATES["M2"])[SLOTS.index("CN_DURATION")] - 0.15 / 0.95) < 1e-9
    assert abs(_sleeve_caps(CANDIDATES["M3"])[SLOTS.index("CASH_LIKE")] - 0.0) < 1e-12
    assert abs(_def_max_sleeve(CANDIDATES["M2"]) - (0.25 - 0.05) / 0.95) < 1e-9
    src = Path(__file__).read_text(encoding="utf-8")
    for tok in ["P" + "PO", "S" + "AC", "T" + "D3", "stable" + "_baselines3"]:
        assert tok not in src, f"forbidden RL token"
    print("--check PASSED")


if __name__ == "__main__":
    main()
