"""小型优化器（GATE_4_NON_RL_HORSE_RACE_CORRECTIONS）——numpy-only，无 scipy。

- simplex_lp: 两阶段 simplex（phase-1 人工变量 + phase-2 原始），解 min c'x s.t. Ax≤b, Aeq x=beq, x≥0。
  Bland 规则防循环。供 MinCVaR LP（N1）。
- qp_projected: 梯度投影解 long-only QP（供 ShrinkMV utility / MaxDiv DR）。
- waterfill_proj: long-only + sum=1 + caps 投影。
"""

from __future__ import annotations

import numpy as np

from ..risk.risk_overlay import RiskOverlayV0


def _phase1_simplex(A, b, c, basis, nv, m, max_iter=3000):
    """标准 tableau simplex：min c'x, A x = b, x≥0，初始可行基 basis。"""
    c = c.astype(float)
    A = A.astype(float)
    b = b.astype(float).ravel()
    basis = list(basis)
    obj = 0.0
    for it in range(max_iter):
        B = A[:, basis]
        try:
            Binv = np.linalg.inv(B)
        except np.linalg.LinAlgError:
            return None, None, False
        xB = Binv @ b
        if (xB < -1e-8).any():
            return None, None, False
        nonbasis = [j for j in range(nv) if j not in basis]
        N = A[:, nonbasis]
        cB = c[basis]
        red = c[nonbasis] - cB @ (Binv @ N)
        # 最负 reduced cost（Bland：取最小下标打破平局）
        entering = None
        min_red = -1e-10
        for k in range(len(nonbasis)):
            if red[k] < min_red:
                min_red = red[k]
                entering = k
        if entering is None:
            return xB, basis, True
        jq = nonbasis[entering]
        d = Binv @ A[:, jq]
        ratios = []
        for i in range(m):
            if d[i] > 1e-12:
                ratios.append((xB[i] / d[i], i, basis[i]))
        if not ratios:
            return None, None, False  # 无界
        # Bland：同比值取最小基下标
        ratio, ip, _ = min(ratios, key=lambda t: (t[0], t[2]))
        basis[ip] = jq
        obj = float(cB @ xB)
    return None, None, False  # 迭代上限


def simplex_lp(c, A=None, b=None, Aeq=None, beq=None, max_iter: int = 4000) -> dict:
    """两阶段 simplex：min c'x s.t. A x ≤ b, Aeq x = beq, x ≥ 0。

    返回 {"x": ndarray, "ok": bool, "iter": int, "obj": float, "basis": list}。
    """
    c = np.asarray(c, dtype=float).ravel()
    n = len(c)
    leq_cons = [] if A is None else list(A)
    leq_rhs = [] if b is None else list(np.asarray(b, dtype=float).ravel())
    eq_cons = [] if Aeq is None else list(Aeq)
    eq_rhs = [] if beq is None else list(np.asarray(beq, dtype=float).ravel())

    # 标准形：≤ → 加松弛；= → phase-1 人工变量
    m = len(leq_cons) + len(eq_cons)
    nvar = n + len(leq_cons) + len(eq_cons)  # x + 松弛 + 人工
    A_full = np.zeros((m, nvar))
    rhs = np.zeros(m)
    row = 0
    slack_start = n
    art_start = n + len(leq_cons)
    for Ai, bi in zip(leq_cons, leq_rhs):
        A_full[row, :n] = Ai
        A_full[row, slack_start + row] = 1.0
        rhs[row] = bi
        row += 1
    art_idx = []
    for Ai, bi in zip(eq_cons, eq_rhs):
        A_full[row, :n] = Ai
        A_full[row, art_start + (row - len(leq_cons))] = 1.0  # 人工变量系数 +1
        rhs[row] = bi
        art_idx.append(art_start + (row - len(leq_cons)))
        row += 1
    # rhs 可负？预处理：负行 × -1（若等式 rhs 负，翻转使 rhs ≥0 但人工系数变 -1 → 需处理）
    # 简化：要求 rhs ≥ 0（我们的 LP 构造保证；否则调用方翻转）
    if (rhs < 0).any():
        # 负 rhs 行：×-1，≤ 松弛系数 -1（仍合法）；= 人工系数 -1
        neg = rhs < 0
        A_full[neg] = -A_full[neg]
        rhs[neg] = -rhs[neg]
        for i in np.where(neg)[0]:
            # 对 ≤ 行，松弛系数由 +1 变 -1（保持 A x + s = b 形式，s 仍 ≥0 需 x 域外）——
            # 这里不处理 s≥0 约束（我们的 ≤ 行 rhs 均 ≥0，负行仅等式可能）
            pass

    # Phase-1：min Σ人工变量, 目标 c1 = [0]*nvar 除人工=1
    c1 = np.zeros(nvar)
    c1[art_idx] = 1.0
    basis = list(range(slack_start, slack_start + len(leq_cons))) + list(art_idx)
    xB, basis, ok1 = _phase1_simplex(A_full, rhs, c1, basis, nvar, m, max_iter)
    if not ok1 or xB is None:
        return {"x": np.zeros(n), "ok": False, "iter": 0, "obj": np.nan, "basis": []}
    # Phase-1 目标应 = 0（可行）；若 >0 不可行
    obj1 = float(c1[basis] @ (np.linalg.pinv(A_full[:, basis]) @ rhs))
    if obj1 > 1e-6:
        return {"x": np.zeros(n), "ok": False, "iter": 0, "obj": np.nan, "basis": []}
    # 人工变量出基（若仍在基）
    basis = [j for j in basis if j not in art_idx]
    # 基可能少于 m（退化）；补回非人工变量
    if len(basis) < m:
        for j in range(nvar):
            if j not in basis and j not in art_idx and len(basis) < m:
                col = A_full[:, j]
                if np.abs(col).max() > 1e-12:
                    basis.append(j)
    # Phase-2：min c（人工列目标 0，实际 c 只在前 n）
    c2 = np.zeros(nvar)
    c2[:n] = c
    xB, basis, ok2 = _phase1_simplex(A_full, rhs, c2, basis, nvar, m, max_iter)
    if not ok2 or xB is None:
        return {"x": np.zeros(n), "ok": False, "iter": 0, "obj": np.nan, "basis": []}
    x_full = np.zeros(nvar)
    for i, jb in enumerate(basis):
        x_full[jb] = xB[i]
    x_opt = x_full[:n]
    return {"x": x_opt, "ok": True, "iter": 0, "obj": float(c @ x_opt), "basis": basis}


def simplex_lp_eq(c: np.ndarray, Aeq: np.ndarray, beq: np.ndarray) -> dict:
    """等式的便捷包装（供 MinCVaR sum w=1）。"""
    return simplex_lp(c, Aeq=Aeq, beq=beq)


def qp_projected(grad_lin: np.ndarray, Q: np.ndarray, *,
                 initial: np.ndarray | None = None,
                 caps: np.ndarray | None = None,
                 growth_max: float = 0.50, growth_slots: tuple[int, ...] = (),
                 max_iter: int = 500, lr: float = 0.1, tol: float = 1e-8) -> np.ndarray:
    """梯度投影解 min 0.5 w'Q w - grad_lin'w s.t. w≥0, Σw=1, 0≤w≤caps, growth group cap。

    迭代内投影到 project 可行集（F4）。
    """
    n = len(grad_lin)
    if caps is None:
        caps = np.full(n, 1.0)
    w = np.full(n, 1.0 / n) if initial is None else np.asarray(initial, dtype=float).copy()
    w = waterfill_proj(w, n, caps, growth_max, growth_slots)
    for _ in range(max_iter):
        grad = Q @ w - grad_lin
        w_new = w - lr * grad
        w_new = waterfill_proj(w_new, n, caps, growth_max, growth_slots)
        if np.abs(w_new - w).max() < tol:
            return w_new
        w = w_new
    return w


def waterfill_proj(w: np.ndarray, n: int, caps: np.ndarray | None = None,
                   growth_max: float = 0.50, growth_slots: tuple[int, ...] = ()) -> np.ndarray:
    """long-only + sum=1 + single-slot caps + ChinaGrowth group cap（F4：project 可行集投影）。"""
    caps = np.full(n, 1.0) if caps is None else np.asarray(caps, dtype=float)
    if caps.sum() < 1.0 - 1e-9:
        raise ValueError(f"caps sum {caps.sum():.3f} < 1 (infeasible)")
    w = np.clip(np.asarray(w, dtype=float), 0.0, caps)
    if not np.isfinite(w).all() or w.sum() <= 1e-12:
        w = np.full(n, 1.0 / n)
    # waterfill 先满足单槽 caps（与 RiskOverlayV0 同投影）
    proj = RiskOverlayV0._waterfill(w, caps, total=1.0)
    if growth_slots:
        g = proj[list(growth_slots)].sum()
        if g > growth_max + 1e-9:
            scale = growth_max / max(g, 1e-12)
            proj[list(growth_slots)] *= scale
            non = [i for i in range(n) if i not in growth_slots]
            slack = 1.0 - proj.sum()
            if slack > 1e-9 and non:
                proj[non] = RiskOverlayV0._waterfill(proj[non], caps[non], total=proj[non].sum() + slack)
    if not np.isclose(proj.sum(), 1.0, atol=1e-6):
        raise ValueError(f"projection sum {proj.sum():.6f}")
    return proj
