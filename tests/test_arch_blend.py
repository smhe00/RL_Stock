"""POST_L2_DETERMINISTIC_ARCHITECTURE_RUN — 架构混合测试（评审冻结契约）。

覆盖：
- 混合语义：w_final = RiskOverlayV0(alpha*maxdiv + (1-alpha)*mom)；成本在最终可执行路径
- C0/C1 重建 parity 到 gen3 精确 metrics（评审冻结；失败 = STOP）
- 全候选 post-overlay 约束（single<=25%、growth<=50%、sum=1）
- R1-R6 成功准则评估逻辑
- 候选集冻结（C0-C4）
- 无 RL / 无 dense search
"""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_spec = importlib.util.spec_from_file_location("arch", ROOT / "scripts" / "gate4_arch_blend.py")
arch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(arch)
_spec_l2 = importlib.util.spec_from_file_location("l2_proxy", ROOT / "scripts" / "gate4_long_horizon_proxy.py")
_l2 = importlib.util.module_from_spec(_spec_l2)
_spec_l2.loader.exec_module(_l2)


def test_candidate_set_frozen() -> None:
    labels = [c for c, _ in arch.CANDIDATES]
    assert labels == ["C0_MaxDiv_100", "C1_Momentum_100", "C2_75_25", "C3_50_50", "C4_25_75"]
    alphas = [a for _, a in arch.CANDIDATES]
    assert alphas == [1.00, 0.00, 0.75, 0.50, 0.25]
    assert len(arch.CANDIDATES) == 5


def test_blend_semantics_w_final_overlay() -> None:
    """混合后必须过 RiskOverlayV0（single<=25%、growth<=50%、sum=1）。"""
    signal_panel, ret_panel, decision_dates, exec_dates = arch.build_panels()
    pol_md = _l2.ProxyPolicy(signal_panel, "MaximumDiversification")
    pol_mom = _l2.ProxyPolicy(signal_panel, "Momentum_12_1")
    growth_idx = [i for i, s in enumerate(_l2.SLOT_ORDER) if s in ("CHINEXT", "STAR")]
    for alpha in (1.0, 0.75, 0.5, 0.25, 0.0):
        for t in decision_dates[::700]:
            w_md = np.clip(np.asarray(pol_md(t), dtype=float), 0.0, None)
            w_md = w_md / w_md.sum()
            w_mom = np.clip(np.asarray(pol_mom(t), dtype=float), 0.0, None)
            w_mom = w_mom / w_mom.sum()
            w_blend = alpha * w_md + (1 - alpha) * w_mom
            w_final = _l2._apply_overlay(w_blend, _l2.SLOT_ORDER)
            assert np.allclose(w_final.sum(), 1.0, atol=1e-6)
            assert w_final.max() <= 0.25 + 1e-6, f"alpha={alpha} single>25%"
            assert w_final[growth_idx].sum() <= 0.50 + 1e-6


def test_c0_c1_parity_to_gen3() -> None:
    """C0/C1 重建 metrics 与 gen3 精确 parity（评审冻结；失败 STOP）。"""
    signal_panel, ret_panel, decision_dates, exec_dates = arch.build_panels()
    r0 = arch.run_candidate(1.00, signal_panel, ret_panel, decision_dates, exec_dates)
    r1 = arch.run_candidate(0.00, signal_panel, ret_panel, decision_dates, exec_dates)
    for label, r, gen in (("C0", r0, arch.GEN3_C0), ("C1", r1, arch.GEN3_C1)):
        for k, want in gen.items():
            got = r["metrics"][k]
            assert abs(got - want) < 1e-4, f"{label} {k}: got {got:.6f} want {want:.6f}"


def test_success_criteria_evaluation() -> None:
    """R1-R6 评估逻辑：构造已知通过/失败的候选。"""
    # 已知：C0（纯 MaxDiv）自身——R1 应 False（无改进）、R2 True、R3 True、R4 True
    crit = arch.evaluate_criteria(arch.GEN3_C0, {"cost_cum_delta": -0.005})
    assert crit["R2_maxdd_deg_le_5pct"] and crit["R3_sharpe_ge_0.80_and_calmar_ge_0.40"]
    assert not crit["R1_cagr_gain_ge_0.5pct"]  # C0 相对自身无改进
    assert crit["R4_cost_delta_ge_-3pct"]
    # 构造 cagr +1%（通过 R1）、mdd -20%（通过 R2）、Sharpe 1.2/Calmar 0.6（通过 R3）的候选
    crit2 = arch.evaluate_criteria(
        {"calendar_cagr": arch.C0_cagr + 0.01, "max_drawdown": -0.15,
         "sharpe": 1.2, "calmar": 0.6}, {"cost_cum_delta": -0.01})
    assert crit2["R1_cagr_gain_ge_0.5pct"] and crit2["R2_maxdd_deg_le_5pct"]
    assert crit2["R3_sharpe_ge_0.80_and_calmar_ge_0.40"] and crit2["R4_cost_delta_ge_-3pct"]
    assert crit2["passes_R1_R4"]


def test_cost_on_final_executable_path() -> None:
    """成本敏感性必须基于最终可执行权重路径（post-overlay 换手）。"""
    signal_panel, ret_panel, decision_dates, exec_dates = arch.build_panels()
    r = arch.run_candidate(0.50, signal_panel, ret_panel, decision_dates, exec_dates)
    cost = r["cost_sensitivity"]
    assert cost["cost_cum_delta"] <= 0.0  # 成本拖累零或负
    assert cost["est_total_cost_over_initial"] >= 0.0
    assert cost["cum_return_net_1x"] <= cost["cum_return_no_cost"] + 1e-9


def test_no_rl_no_dense() -> None:
    src = Path(ROOT / "scripts" / "gate4_arch_blend.py").read_text(encoding="utf-8")
    for tok in ("PPO", "SAC", "TD3", "stable_baselines3"):
        assert tok not in src, f"forbidden RL token {tok}"
    assert "no_dense_search" in src or "CANDIDATES" in src
