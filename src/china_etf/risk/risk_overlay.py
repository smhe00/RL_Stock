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


class RiskOverlayCE(RiskOverlayV0):
    """POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY — M1-M3 joint Euclidean projection.

    在 M0 的 legacy RiskOverlayV0（per-asset caps + growth 组 cap）基础上增加
    defensive 组 cap（CASH_LIKE+CN_DURATION），并以唯一确定性凸 QP 投影求解
    joint intersection（C1 long-only / C2 simplex / C3 per-slot caps /
    C4 growth 组 / C5 defensive 组）：
        min_w  0.5 * ||w - raw||_2^2   s.t. C1-C5
    方法: scipy.optimize.minimize(method='SLSQP')（命名唯一，无 fallback）；
    max_iter=200 / ftol=1e-12 / 终检 atol=1e-6；result.success 必须为 True，
    任一收敛/KKT/可行性检查失败 → InfeasibleConstraints（fail-closed）。

    语义: cap 作用于 rebalance target weights（同 RiskOverlayV0 V1）；actual 超限由
    下次再平衡纠正。M0 不经过本类（保持 legacy RiskOverlayV0 精确路径）。
    """

    def __init__(
        self,
        slots: list[str],
        *,
        caps: np.ndarray,
        growth_max: float = 0.50,
        growth_slots: tuple[str, ...] = ("CHINEXT", "STAR"),
        def_max: float,
        def_slots: tuple[str, ...] = ("CASH_LIKE", "CN_DURATION"),
    ) -> None:
        self.slots = list(slots)
        self.caps = np.asarray(caps, dtype=float)
        assert len(self.caps) == len(self.slots), "caps length must equal slots"
        self.cap_index = {s: i for i, s in enumerate(self.slots)}
        self.growth_idx = [self.cap_index[s] for s in growth_slots if s in self.cap_index]
        self.growth_max = float(growth_max)
        self.def_idx = [self.cap_index[s] for s in def_slots if s in self.cap_index]
        self.def_max = float(def_max)
        self.max_iter = 200
        self.ftol = 1e-12
        self.atol = 1e-6

    def apply(self, raw: pd.Series) -> pd.Series:
        import scipy.optimize as so
        v = np.asarray(raw.reindex(self.slots).values, dtype=float)
        v = np.clip(v, 0.0, None)
        n = len(self.slots)
        caps = self.caps
        # 可行性预检: per-slot caps 之和必须 >= 1
        if caps.sum() < 1.0 - 1e-9:
            raise InfeasibleConstraints(f"sum(caps)={caps.sum():.3f} < 1")

        def obj(w):
            return 0.5 * np.dot(w - v, w - v)

        def jac(w):
            return w - v

        # C2 simplex 等式（独立元素）；C4/C5 组不等式（各独立 LinearConstraint）
        eq_cons = {"type": "eq", "fun": lambda w: w.sum() - 1.0,
                   "jac": lambda w: np.ones(n)}
        constraints = [eq_cons]
        if self.growth_idx:
            A_growth = np.zeros((1, n))
            A_growth[0, self.growth_idx] = 1.0
            constraints.append(
                so.LinearConstraint(A_growth, lb=-np.inf, ub=self.growth_max))
        if self.def_idx:
            A_def = np.zeros((1, n))
            A_def[0, self.def_idx] = 1.0
            constraints.append(
                so.LinearConstraint(A_def, lb=-np.inf, ub=self.def_max))

        res = so.minimize(
            obj, x0=v.copy(), jac=jac, method="SLSQP",
            bounds=[(0.0, float(c)) for c in caps],
            constraints=constraints,
            options={"maxiter": self.max_iter, "ftol": self.ftol},
        )
        if not res.success:
            raise InfeasibleConstraints(
                f"SLSQP failed: success=False status={res.status} msg={str(res.message)[:120]}")
        w = np.asarray(res.x, dtype=float)
        # 最终同时可行性断言（final simultaneous assertions, fail-closed）
        if not np.isclose(w.sum(), 1.0, atol=self.atol):
            raise InfeasibleConstraints(f"projection sum={w.sum():.6f}")
        if (w < -1e-9).any() or (w > caps + self.atol).any():
            raise InfeasibleConstraints("projection violates per-slot caps")
        if self.growth_idx and w[self.growth_idx].sum() > self.growth_max + self.atol:
            raise InfeasibleConstraints("projection violates growth-group cap")
        if self.def_idx and w[self.def_idx].sum() > self.def_max + self.atol:
            raise InfeasibleConstraints("projection violates defensive-group cap")
        return pd.Series(w, index=self.slots)
