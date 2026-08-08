"""RiskOverlayV0（EXECUTION_SPEC §36/§59；Reviewer BLOCKER-2）。

Core-only 硬约束：
  long_only、无杠杆（sum=1）、single_core_max=0.25、
  china_growth_max=0.50（CHINEXT+STAR 组）。

投影：bounded simplex（water filling），非 naive clip+renormalize；
约束不可行 → 抛 InfeasibleConstraints（不静默放松）。
语义：cap 作用于 rebalance 时 target weights（V1；actual 因市场波动超限由下次再平衡纠正）。
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class InfeasibleConstraints(Exception):
    pass


class RiskOverlayV0:
    def __init__(
        self,
        slots: list[str],
        *,
        single_core_max: float = 0.25,
        china_growth_max: float = 0.50,
        growth_slots: tuple[str, ...] = ("CHINEXT", "STAR"),
    ) -> None:
        self.slots = list(slots)
        self.caps = np.full(len(self.slots), float(single_core_max))
        self.cap_index = {s: i for i, s in enumerate(self.slots)}
        self.growth_idx = [self.cap_index[s] for s in growth_slots if s in self.cap_index]
        self.growth_max = float(china_growth_max)

    def apply(self, raw: pd.Series) -> pd.Series:
        v = np.asarray(raw.reindex(self.slots).values, dtype=float)
        v = np.clip(v, 0.0, None)
        caps = self.caps.copy()
        # 可行性
        if caps.sum() < 1.0 - 1e-9:
            raise InfeasibleConstraints(f"sum(caps)={caps.sum():.3f} < 1")
        group_cap = sum(min(caps[i], self.growth_max) for i in self.growth_idx)
        if len(self.growth_idx) and group_cap < 0.0 - 1e-9:
            raise InfeasibleConstraints("growth group min > china_growth_max")
        w = self._waterfill(v, caps, total=1.0)
        if self.growth_idx:
            g = w[self.growth_idx].sum()
            if g > self.growth_max + 1e-9:
                scale = self.growth_max / g
                w[self.growth_idx] *= scale
                slack = 1.0 - w.sum()
                non = [i for i in range(len(self.slots)) if i not in self.growth_idx]
                if slack > 1e-9 and non:
                    w[non] = self._waterfill(w[non], caps[non], total=w[non].sum() + slack)
        # 终检
        if not np.isclose(w.sum(), 1.0, atol=1e-6):
            raise InfeasibleConstraints(f"projection sum={w.sum():.6f}")
        if (w < -1e-9).any() or (w > caps + 1e-6).any():
            raise InfeasibleConstraints("projection violates per-asset caps")
        if self.growth_idx and w[self.growth_idx].sum() > self.growth_max + 1e-6:
            raise InfeasibleConstraints("projection violates china_growth_max")
        return pd.Series(w, index=self.slots)

    @staticmethod
    def _waterfill(values: np.ndarray, caps: np.ndarray, total: float) -> np.ndarray:
        """bounded simplex：min ||w - values||₂ s.t. 0≤w≤caps, Σw=total。"""
        if total > caps.sum() + 1e-9 or total < -1e-9:
            raise InfeasibleConstraints(f"total={total:.3f} > sum(caps)={caps.sum():.3f}")
        lo, hi = float(values.min()) - 1.0, float(values.max())

        def f(lam: float) -> float:
            return float(np.minimum(np.maximum(values - lam, 0.0), caps).sum())

        for _ in range(80):
            mid = (lo + hi) / 2.0
            if f(mid) > total:
                lo = mid
            else:
                hi = mid
        w = np.minimum(np.maximum(values - hi, 0.0), caps).astype(float)
        diff = total - w.sum()
        for i in np.argsort(-w):
            room = caps[i] - w[i]
            if room <= 1e-12:
                continue
            add = min(diff, room)
            w[i] += add
            diff -= add
            if diff <= 1e-10:
                break
        if diff > 1e-5:
            raise InfeasibleConstraints(f"waterfill residual diff={diff:.2e}")
        return w
