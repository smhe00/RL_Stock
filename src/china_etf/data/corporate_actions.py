"""公司行为事件流（GATE_4_PILOT_READY CA1）——境内 ETF 双价 contract 的执行侧事件。

- 现金分红：ex_date 记应收款（基于除息日开盘前持仓）；pay_date 应收款 → 现金。
- 份额折算/送股：eff_date 持仓数量 ×= unit_factor（avg_cost /= factor），价值不变。

派息日近似（评审 §16）：事件 CSV 无 pay_date 时默认 `ex_date + pay_lag_bdays` 交易日
（mainland 交割惯例，默认 2）。文档标注为近似；`test_dividend_receivable_not_spendable_before_payment`
证明应收款在 pay_date 前不可用于购买。
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .loader import META, SLOT_MAP


@dataclass(frozen=True)
class CorporateActionEvent:
    instrument: str
    ex_date: pd.Timestamp  # 除息/折算生效日
    pay_date: pd.Timestamp | None  # 现金派发日（None → 用 ex_date+lag 近似）
    cash_per_share: float  # 每份现金（instrument 币种，mainland=CNY）
    unit_factor: float  # 1 + stockBonus + stockGift（送股/折算后每旧份对应新份数；1.0=无）


def _default_pay_date(ex_date: pd.Timestamp, pay_lag_bdays: int) -> pd.Timestamp:
    return ex_date + pd.offsets.BDay(pay_lag_bdays)


def load_corporate_actions(pay_lag_bdays: int = 2) -> dict[str, list[CorporateActionEvent]]:
    """读 data/qmt/meta/divid_events/{code}.csv → 按 instrument 索引的事件列表。

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
            cash = float(r.get("interest", 0.0)) if pd.notna(r.get("interest", None)) else 0.0
            unit = 1.0
            for k in ("stockBonus", "stockGift"):
                v = r.get(k, 0.0)
                unit += float(v) if pd.notna(v) else 0.0
            pay_raw = r.get("pay_date") if "pay_date" in df.columns else None
            pay = (
                pd.Timestamp(pay_raw)
                if pay_raw is not None and pd.notna(pay_raw)
                else _default_pay_date(ex, pay_lag_bdays)
            )
            events.append(
                CorporateActionEvent(
                    instrument=inst, ex_date=ex, pay_date=pay,
                    cash_per_share=float(cash), unit_factor=float(unit),
                )
            )
        if events:
            out[inst] = events
    return out
