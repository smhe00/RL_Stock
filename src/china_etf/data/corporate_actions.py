"""公司行为事件流（GATE_4_PILOT_READY CA1；FINAL_FIX P2/P3）——境内 ETF 双价 contract 执行侧。

事件类型（显式，不推断）：
  CASH_DIVIDEND      现金分红：ex_date 按除息日开盘前持仓（= record-date close）计提应收款
  UNIT_SPLIT         份额拆分/送股（factor > 1）：qty ×= factor，价值中性
  UNIT_CONSOLIDATION 份额合并/折算（factor < 1，如 512100 0.36555）：qty ×= factor，价值中性

派息日政策（FINAL_FIX P2）：
  - 已知历史事件 → 官方 pay_date（513690 2024-12-20 / 2025-12-22）
  - 未知 pay_date → 绝不提前结算：settle_date = ex_date + 5 交易日（CONSERVATIVE_FALLBACK），
    receivable 在保守结算日前不可花。
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .loader import META, SLOT_MAP

CONSERVATIVE_PAY_LAG_BD = 5  # 未知派息日的保守结算滞后（交易日）


@dataclass(frozen=True)
class CorporateActionEvent:
    instrument: str
    action_type: str  # CASH_DIVIDEND | UNIT_SPLIT | UNIT_CONSOLIDATION
    ex_date: pd.Timestamp  # 生效日（除息/折算；与 raw 行情跳变日一致）
    unit_factor: float  # 送股/折算因子（1.0=无）
    cash_per_share: float  # 每份现金（instrument 币种，mainland=CNY）
    pay_date: pd.Timestamp | None  # 官方派息日（None = 未知，用保守 fallback）
    settle_date: pd.Timestamp  # 实际结算日 = pay_date 或 ex_date + CONSERVATIVE_PAY_LAG_BD
    source: str  # official_fund_announcement | CONSERVATIVE_FALLBACK


def _settle_for(action_type: str, ex_date: pd.Timestamp, pay_date: pd.Timestamp | None) -> tuple[pd.Timestamp, str]:
    """结算日与来源。

    - UNIT_SPLIT / UNIT_CONSOLIDATION：无现金结算，settle_date=ex_date，来源=官方公告。
    - CASH_DIVIDEND：官方 pay_date 优先；未知 → ex+5T 保守 fallback（source=CONSERVATIVE_FALLBACK）。
    """
    if action_type != "CASH_DIVIDEND":
        return ex_date, "official_fund_announcement"
    if pay_date is not None:
        return pay_date, "official_fund_announcement"
    return ex_date + pd.offsets.BDay(CONSERVATIVE_PAY_LAG_BD), "CONSERVATIVE_FALLBACK"


def load_corporate_actions() -> dict[str, list[CorporateActionEvent]]:
    """读 data/qmt/meta/divid_events/{code}.csv → 按 instrument 索引的事件列表。

    CSV 列：date, action_type, unit_factor, interest, stockBonus, stockGift, pay_date(可选)。
    只加载 SLOT_MAP 当前 instrument（Track A = mainland 路径；03110 已 defer）。
    """
    out: dict[str, list[CorporateActionEvent]] = {}
    for slot, meta in SLOT_MAP.items():
        inst = meta["instrument"]
        path = META / "divid_events" / f"{inst}.csv"
        if not path.exists():
            continue
        df = pd.read_csv(path)
        if "date" not in df.columns:
            continue
        df["date"] = pd.to_datetime(df["date"])
        events: list[CorporateActionEvent] = []
        for _, r in df.iterrows():
            ex = pd.Timestamp(r["date"])
            action = str(r.get("action_type", "CASH_DIVIDEND")).strip() or "CASH_DIVIDEND"
            unit = float(r.get("unit_factor", 1.0)) if pd.notna(r.get("unit_factor")) else 1.0
            cash = float(r.get("interest", 0.0)) if pd.notna(r.get("interest")) else 0.0
            pay_raw = r.get("pay_date") if "pay_date" in df.columns else None
            pay = pd.Timestamp(pay_raw) if pay_raw is not None and pd.notna(pay_raw) and str(pay_raw).strip() else None
            settle, source = _settle_for(action, ex, pay)
            events.append(
                CorporateActionEvent(
                    instrument=inst, action_type=action, ex_date=ex,
                    unit_factor=unit, cash_per_share=float(cash),
                    pay_date=pay, settle_date=settle, source=source,
                )
            )
        if events:
            out[inst] = events
    return out
