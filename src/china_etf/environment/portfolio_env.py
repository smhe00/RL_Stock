"""ChinaETFPortfolioEnv（EXECUTION_SPEC §32/§34；Reviewer §16.8）。

Gate 2 范围：11 Core、action dim=11、long-only、无杠杆、无 Theme Sleeve。
时序：T 日收盘决策 → T+1 开盘成交（禁止同日收盘成交）。
Reward V1 (R0)：r_t = log(V_{t+1}^{net} / V_t^{net})，已扣全部成本。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..accounting import PortfolioAccounting
from ..contracts import (
    EnvironmentMode,
    TargetAssetWeights,
    TargetInstrumentWeights,
    softmax_weights,
)
from ..execution.broker.mock import MockBroker
from ..execution.order_generator import OrderGenerator


@dataclass
class EnvStep:
    t: pd.Timestamp
    t_next: pd.Timestamp
    value_before: float
    value_after: float
    net_return: float
    reward: float
    fees_paid: float
    fills: list = field(default_factory=list)


class ChinaETFPortfolioEnv:
    def __init__(
        self,
        *,
        slots: list[str],
        adj_close: pd.DataFrame,  # columns=slot, 复权收盘（研究收益）
        open_prices: dict[str, pd.Series],  # instrument -> 原始开盘价（执行）
        close_prices: dict[str, pd.Series],  # instrument -> 原始收盘价（执行/现金）
        initial_cash: float,
        broker: MockBroker,
        order_generator: OrderGenerator,
        slot_to_instrument: dict[str, str],
        mode: str = EnvironmentMode.METHOD_RESEARCH,
        min_history: int = 252,
    ) -> None:
        self.slots = list(slots)
        self.action_dim = len(self.slots)
        self.adj = adj_close
        self.open_prices = open_prices
        self.close_prices = close_prices
        self.broker = broker
        self.order_generator = order_generator
        self.slot_to_instrument = slot_to_instrument
        self.mode = mode
        self.min_history = min_history
        # 研究模式不启用实时 PremiumGuard（历史无 IOPV）；PAPER/LIVE fail-closed
        self.broker.premium_enforced = mode in (EnvironmentMode.PAPER, EnvironmentMode.LIVE)
        self.accounting = PortfolioAccounting(initial_cash=initial_cash)
        self.calendar = sorted(adj_close.index)
        # 预计算特征（一次性；warm-up 与 step 均使用预计算帧，避免重复滚动）
        from ..features.etf_features import global_features, per_asset_features

        self._per_features = {
            s: per_asset_features(self.adj[s]) for s in self.slots
        }
        self._global_feat = global_features(self.adj)
        self._i = 0
        self._warmup_index = self._find_warmup_index()
        self._weights = pd.Series(np.zeros(len(slots)), index=slots)

    def reset(self) -> np.ndarray:
        self._i = int(self._warmup_index)
        self.accounting = PortfolioAccounting(initial_cash=self.accounting.cash)
        self._weights = pd.Series(np.zeros(len(self.slots)), index=self.slots)
        return self._observe(self.calendar[self._i])

    def _find_warmup_index(self) -> int:
        """Reviewer §21/§22：warm-up 期后 observation 必须全 finite；禁止 NaN 静默填 0。"""
        per_ok = pd.DataFrame({s: self._per_features[s].notna().all(axis=1) for s in self.slots})
        global_ok = self._global_feat.notna().all(axis=1)
        ok = per_ok.all(axis=1) & global_ok
        for i in range(max(0, self.min_history - 1), len(self.calendar)):
            if bool(ok.iloc[i]):
                return i
        raise ValueError(
            f"no fully-finite observation within calendar (slots={len(self.slots)}, "
            f"min_history={self.min_history}, calendar_len={len(self.calendar)})"
        )

    def _actual_weights(self, t: pd.Timestamp) -> pd.Series:
        """Reviewer §7/§8：observation 必须用实际持仓权重（实际成交后），而非 target。
        cash 隐含在残差 1 - Σw_actual。"""
        marks = self._close_marks(t)
        snap = self.accounting.snapshot(t, marks, self._fx())
        v = snap.portfolio_value
        out = pd.Series(0.0, index=self.slots, dtype=float)
        for slot in self.slots:
            inst = self.slot_to_instrument[slot]
            if inst in snap.positions and v > 0:
                out[slot] = snap.positions[inst] * marks.get(inst, 0.0) / v
        return out

    def _observe(self, t: pd.Timestamp) -> np.ndarray:
        actual = self._actual_weights(t)
        parts: list[np.ndarray] = []
        for s in self.slots:
            parts.append(self._per_features[s].loc[t].values)
        parts.append(actual.values)
        parts.append(self._global_feat.loc[t].values)
        obs = np.concatenate(parts).astype(float)
        if not np.isfinite(obs).all():
            raise ValueError(f"observation contains non-finite values at {t}")
        return obs

    def step(self, raw_action: np.ndarray) -> tuple[np.ndarray, float, bool, dict]:
        if self._i >= len(self.calendar) - 1:
            return self._observe(self.calendar[-1]), 0.0, True, {}
        t = self.calendar[self._i]
        t_next = self.calendar[self._i + 1]
        weights = softmax_weights(raw_action, self.slots)
        self._weights = weights
        v_before = self.accounting.snapshot(t, self._close_marks(t), self._fx()).portfolio_value

        target_asset = TargetAssetWeights(decision_time=t, weights=weights)
        inst_w = pd.Series(
            {self.slot_to_instrument[s]: w for s, w in weights.items()},
        )
        target_inst = TargetInstrumentWeights(decision_time=t, weights=inst_w)
        close_marks = self._close_marks(t)
        orders = self.order_generator.plan(
            target_inst, accounting=self.accounting, close_prices=close_marks
        )
        fills = self.broker.execute_plan(
            orders, execution_date=t_next, accounting=self.accounting
        )
        v_after = self.accounting.snapshot(t_next, self._close_marks(t_next), self._fx()).portfolio_value
        net_return = v_after / v_before - 1.0
        reward = float(np.log(v_after / v_before))
        step = EnvStep(
            t=t,
            t_next=t_next,
            value_before=v_before,
            value_after=v_after,
            net_return=net_return,
            reward=reward,
            fees_paid=self.accounting.fees_paid,
            fills=fills,
        )
        self._i += 1
        return self._observe(t_next), reward, self._i >= len(self.calendar) - 1, {"step": step}

    def _close_marks(self, t: pd.Timestamp) -> dict[str, float]:
        out: dict[str, float] = {}
        for inst, series in self.close_prices.items():
            valid = series[series.index <= t]
            if not valid.empty:
                out[inst] = float(valid.iloc[-1])
        return out

    def _fx(self) -> dict[str, float]:
        return {inst: 1.0 for inst in self.close_prices}
