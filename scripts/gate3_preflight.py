"""GATE 3 PREFLIGHT — P4 Slot 映射 / P5 真实 11-Core 观测 / C3 精确 diff。

任一项失败 → STOP，不得训练。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from china_etf.contracts import EnvironmentMode  # noqa: E402
from china_etf.cost.mainland import MainlandETFCostModel  # noqa: E402
from china_etf.data.loader import (  # noqa: E402
    SLOT_MAP,
    load_execution_prices,
    load_research_adj,
    slot_manifest,
)
from china_etf.environment.portfolio_env import ChinaETFPortfolioEnv  # noqa: E402
from china_etf.execution.broker.mock import MockBroker  # noqa: E402
from china_etf.execution.order_generator import OrderGenerator  # noqa: E402
from china_etf.execution.premium import PremiumGuard  # noqa: E402
from china_etf.execution.tradability import TradabilityMask  # noqa: E402


def p4_manifest() -> pd.DataFrame:
    m = slot_manifest()
    print("\n===== P4 Slot→Research Series Manifest =====")
    print(m.to_string(index=False))
    assert len(m) == 11, "ActionDim 必须为 11（禁止静默 drop）"
    assert set(m["asset_slot"]) == set(SLOT_MAP.keys())
    return m


def p5_observations() -> None:
    print("\n===== P5 真实 11-Core 100 个连续观测 =====")
    adj = load_research_adj()
    opens, closes = load_execution_prices()
    assert len(adj.columns) == 11
    broker = MockBroker(
        tradability=TradabilityMask(),
        premium_guard=PremiumGuard(requires_protection=lambda i: i == "US_BROAD"),
        cost_model=MainlandETFCostModel(),
        open_prices=opens,
    )
    env = ChinaETFPortfolioEnv(
        slots=list(SLOT_MAP.keys()),
        adj_close=adj,
        open_prices=opens,
        close_prices=closes,
        initial_cash=1_000_000.0,
        broker=broker,
        order_generator=OrderGenerator(),
        slot_to_instrument={s: SLOT_MAP[s]["instrument"] for s in SLOT_MAP},
        mode=EnvironmentMode.METHOD_RESEARCH,
    )
    obs = env.reset()
    print(f"data: {adj.index[0].date()} -> {adj.index[-1].date()} | days={len(adj)} | warmup_idx={env._warmup_index}")
    stats = []
    for _ in range(100):
        obs, reward, done, info = env.step(np.zeros(11))
        if done:
            env.reset()
        stats.append(obs)
    arr = np.stack(stats)
    print(f"shape={arr.shape}")
    assert arr.shape[1] == 104, "obs 必须是 104 维"
    assert np.isfinite(arr).all(), "obs 必须全 finite"
    print(f"min={arr.min():.6f} max={arr.max():.6f} mean={arr.mean():.6f} std={arr.std():.6f}")
    # 锚点特征必须是真实计算值（11-Core 宇宙含 GOLD/CN_DURATION，禁止 fallback 补 0 路径）
    assert "GOLD" in adj.columns and "CN_DURATION" in adj.columns
    # 实际权重有效：0 ≤ w ≤ 1，Σw ≤ 1+ε
    w_block = arr[:, 8 * 11 : 8 * 11 + 11]
    assert (w_block >= -1e-9).all() and (w_block <= 1.0 + 1e-6).all()
    assert (w_block.sum(axis=1) <= 1.0 + 1e-6).all()
    print(f"actual weights: min={w_block.min():.4f} max={w_block.max():.4f} "
          f"sum_range=[{w_block.sum(axis=1).min():.4f},{w_block.sum(axis=1).max():.4f}]")
    print("P5 PASS")


def c3_exact_diff() -> None:
    print("\n===== C3 精确 diff（QMT raw+events TR vs QMT front）=====")
    from xtquant import xtdata

    from china_etf.data.adjustments import total_return_with_events

    checks = ["510300.SH", "512890.SH", "511260.SH", "515070.SH"]
    all_diffs: list[float] = []
    for code in checks:
        xtdata.download_history_data2([code], "1d", "20190101", "20260808", incrementally=True)
        raw = xtdata.get_market_data_ex(["close"], [code], "1d", "20190101", "20260808",
                                        dividend_type="none", fill_data=False)[code]["close"]
        front = xtdata.get_market_data_ex(["close"], [code], "1d", "20190101", "20260808",
                                          dividend_type="front", fill_data=False)[code]["close"]
        raw.index = pd.to_datetime(raw.index.astype(str), format="%Y%m%d")
        front.index = pd.to_datetime(front.index.astype(str), format="%Y%m%d")
        raw = raw[raw > 0].astype(float)
        front = front[front > 0].astype(float)
        ev = xtdata.get_divid_factors(code, "20190101", "20260808")
        if ev is None or len(ev) == 0:
            print(f"  {code}: no events")
            continue
        ev = ev.copy()
        ev["time"] = (pd.to_datetime(ev["time"], unit="ms", utc=True) + pd.Timedelta(hours=8)).dt.tz_localize(None).dt.normalize()
        ev = ev.set_index("time")
        cash = ev["interest"].reindex(raw.index).fillna(0.0)
        split = (1.0 + ev["stockBonus"] + ev["stockGift"]).reindex(raw.index).ffill().fillna(1.0)
        tr = total_return_with_events(raw, cash_distribution=cash, split_factor=split)
        fr = front / front.shift(1) - 1.0
        diffs = []
        print(f"  {code}:")
        for d in ev.index:
            if d in tr.index and d in fr.index:
                diff = float(tr.loc[d] - fr.loc[d])
                diffs.append(diff)
                print(f"    {d.date()}  TR={tr.loc[d]:+.6f} front={fr.loc[d]:+.6f} diff={diff:+.6f}")
        all_diffs.extend(abs(x) for x in diffs)
    print(f"\n  max_abs_diff={max(all_diffs):.6f}  median_abs_diff={float(np.median(all_diffs)):.6f}  n={len(all_diffs)}")
    print("  → 目标 ≤ 0.0001（1bp）。超限需证明来自 rounding（QMT interest 3 位小数 / 价格）或 provider 调整约定。")


if __name__ == "__main__":
    p4_manifest()
    p5_observations()
    c3_exact_diff()
    print("\nPREFLIGHT DONE")
