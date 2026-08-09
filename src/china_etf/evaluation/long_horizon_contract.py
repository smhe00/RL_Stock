"""GATE_4_LONG_HORIZON_NON_RL — L1 冻结契约（PREP 冻结 + 评审 hard guard #1）。

窗口 parity fail-closed：L1 runner 从真实加载数据推导决策/执行窗口，
再断言与冻结契约精确一致；任何差异 → 停止并返回 blocker/revision packet
（不得静默平移区间/天数）。评审 GATE_4_LONG_HORIZON_NON_RL_PREP_REVIEWER_RESPONSE.md
guard #1（窗口）、#3（方法集）、#4（canonical 参数）。

单段 T→T+1 语义（真实 11 ETF 工具，无 pre-launch backfill）：
  decision_start（reset_at） = first_all_finite + 252 交易日 = 2022-06-09
  first_execution            = 2022-06-10（契约 start）
  last_decision              = 2026-08-06
  last_execution             = 2026-08-07（契约 end；数据末日）
  n_decision_days = 1011, n_execution_dates = 1011
"""

from __future__ import annotations

import pandas as pd

WARMUP_LOOKBACK = 252  # 最长 lookback（Momentum 12-1 = 252）

FROZEN_CONTRACT = {
    "label": "REAL_INSTRUMENT_LONG_HORIZON_DIAGNOSTIC",
    "decision_start_date": "2022-06-09",
    "start_execution_date": "2022-06-10",
    "last_decision_date": "2026-08-06",
    "end_execution_date": "2026-08-07",
    "n_decision_days": 1011,
    "n_execution_dates": 1011,
}

METHOD_NAMES_FROZEN = [
    "HS300_ref",
    "EqualWeight",
    "MaximumDiversification",
    "MinimumVariance",
    "RiskParity_IVOL",
    "Momentum_12_1",
]

# canonical 参数（评审 guard #3/#4：原样复用当前源码，无 lookback/shrinkage tuning）
CANONICAL_PARAMS = {
    "MaximumDiversification": {"lookback": 120, "shrinkage": 0.5},
    "MinimumVariance": {"lookback": 120, "shrinkage": 0.5},
    "RiskParity_IVOL": {"lookback": 60},
    "Momentum_12_1": {"lookback": 252, "skip": 21},
}


class ContractParityError(RuntimeError):
    """窗口/天数与冻结契约不一致 → stop condition（guard #1）。"""


def derive_window(adj: pd.DataFrame) -> dict:
    """从实际 adj 推导 L1 决策/执行窗口（不用旧 475-day mask）。"""
    first_all_finite = adj.dropna(how="any").index[0]
    p = adj.index.get_loc(first_all_finite)
    decision_start = adj.index[p + WARMUP_LOOKBACK]
    first_execution = adj.index[p + WARMUP_LOOKBACK + 1]
    last_execution = adj.index[-1]
    last_decision = adj.index[-2]
    return {
        "first_all_finite": first_all_finite,
        "decision_start": decision_start,
        "first_execution": first_execution,
        "last_decision": last_decision,
        "last_execution": last_execution,
        "n_decision_days": int(((adj.index >= decision_start) & (adj.index <= last_decision)).sum()),
        "n_execution_dates": int(((adj.index >= first_execution) & (adj.index <= last_execution)).sum()),
    }


def check_contract(adj: pd.DataFrame) -> dict:
    """derive + assert parity；失败 raise ContractParityError（stop condition）。"""
    w = derive_window(adj)
    checks = [
        ("decision_start", str(w["decision_start"].date()), FROZEN_CONTRACT["decision_start_date"]),
        ("first_execution", str(w["first_execution"].date()), FROZEN_CONTRACT["start_execution_date"]),
        ("last_decision", str(w["last_decision"].date()), FROZEN_CONTRACT["last_decision_date"]),
        ("last_execution", str(w["last_execution"].date()), FROZEN_CONTRACT["end_execution_date"]),
        ("n_decision_days", w["n_decision_days"], FROZEN_CONTRACT["n_decision_days"]),
        ("n_execution_dates", w["n_execution_dates"], FROZEN_CONTRACT["n_execution_dates"]),
    ]
    problems = [f"{k}={got} != {want}" for k, got, want in checks if got != want]
    if problems:
        raise ContractParityError("L1 window parity fail-closed: " + "; ".join(problems))
    return w
