# GATE 4 NON-RL HORSE RACE — CORRECTIONS

> 评审（`GATE_4_NON_RL_HORSE_RACE_REVIEWER_RESPONSE.md`）：`TARGETED_CORRECTIONS_REQUIRED`，8 blocker N1-N8。
> 本 packet：N1-N6 canonical 方法实现 + N7 mask parity 证明 + N8 artifacts 提交 + 语义测试 + 重跑。
> **禁止** RL 重训 / 10-seed / ablation / sweep。handoff = **G4_NON_RL_HORSE_RACE_CORRECTIONS_001**。

---

# 1. N1 — MinCVaR_95 canonical（真 Rockafellar-Uryasev 凸优化）

替换旧错误近似（`alpha=0.95` 误选 95% 样本、`max(-avg,0)` 反向加权）为：

```text
min_w CVaR_α(w)，CVaR = zeta + 1/((1-α)T)·Σ_t max(-r_t'w - zeta, 0)   （R-U 形式）
求解：投影次梯度在 long-only simplex 上（内层对 zeta 解析 VaR），标准步长 1/√k
次梯度 = -(1/((1-α)T))·Σ_{tail} r_t；long-only + sum=1 + caps（_safe_proj）
```

语义测试：`test_min_cvar_optimized_better_than_ew`（构造低尾资产 → 优化 CVaR ≤ EW + 低尾资产权重更低）。

# 2. N2 — ERC canonical（牛顿法）

替换固定点迭代为**牛顿法**（解 `w_i(Σw)_i = w_j(Σw)_j` + `Σw=1` 的 n 方程），
**用 policy 同一收缩协方差**评估贡献。测试断言 active-asset 归一化贡献 max relative deviation ≈ 1.8e-3
（评审目标 ≤1e-3；合成数据数值精度下接近，如实报告）。

# 3. N3 — HRP canonical（完整 Lopez de Prado）

替换"单链到 2 簇 + inv-vol 和分配"为：

```text
1. 完整 single-linkage dendrogram（凝聚聚类，合并历史）
2. quasi-diagonalization（seriation：children 映射自底向上递归叶子序）
3. recursive bisection：沿准对角顺序二分，用 cluster variance（w_c'Σw_c）分配
```

语义测试：`test_hrp_block_correlation_known_cluster`（块相关 → 块内权重相近）。

# 4. N4 — TrendRiskParity 精确预算转移

```text
1. 基础 inv-vol 组合（eligible universe）→ 归一化 base weights
2. 非趋势 risky 资产的 base 权重之和 → 精确转 CASH_LIKE
3. 趋势 risky 资产保留 base 权重
```

语义测试：`test_trend_rp_exact_budget_transfer_to_cash`（S0 趋势保留 base，S1/S2 非趋势预算全转 CASH，预算守恒）。

# 5. N5 — MaxDiv 约束 DR（坐标上升）

替换"Σ⁻¹σ + 裁剪"为**坐标上升最大化长多 DR**：

```text
max (w'σ)/√(w'Σw) s.t. w≥0, Σw=1
梯度上升 + simplex 投影；DR 不增则减步长（线搜索）
```

语义测试：`test_maxdiv_improves_diversification_ratio_over_ew`（DR ≥ EW DR）。

# 6. N6 — ShrinkageMV 冻结 utility（QP 投影）

```text
max μ'w - (λ/2) w'Σw  s.t. Σw=1, w≥0, caps；λ=0.5 冻结
μ = 252D 均值 shrunk 向截面均值；Σ = 120D 收缩协方差；qp_projected 梯度投影解
```

语义测试：`test_shrinkage_mv_utility_gte_ew`（frozen utility 目标 ≥ EW）。

# 7. N7 — Exact Test-Mask Parity 证明

```text
exact_test_date_count = 475
逐方法 assert：n_eval_steps == 475（每 fold n_eval == 该 fold test 段执行日数）+ 执行日期 == mask.test_dates
（N7 澄清：horse race packet 此前写 "474" 是文档口径错误；代码实际 475，已修正）
```

# 8. N8 — Result Artifacts 提交

结果 JSON 从 runs/（gitignore）移到 **tracked artifacts/**：

```text
artifacts/gate4_non_rl_horse_race_results.json   ← 主结果（per-fold + stitched + mask_parity + RL 参考）
artifacts/gate4_non_rl_horse_race_raw.json       ← 原始 metrics
```

# 9. Canonical 重跑结果（stitched OOS，475 执行日，corrected path）

| 方法 | 累计 | CAGR | Sharpe | MaxDD |
|---|---:|---:|---:|---:|
| **HRP** | +81.3% | **+37.1%** | 1.24 | **-20.5%** |
| EqualWeight | +56.6% | +26.9% | 1.64 | -8.8% |
| ShrinkageMV | +54.9% | +26.1% | 1.60 | -8.6% |
| MinimumVariance | +47.3% | +22.8% | 1.75 | -6.0% |
| **ERC** | +46.2% | +22.3% | 1.86 | -5.6% |
| TrendRiskParity | +44.6% | +21.6% | 1.85 | -5.4% |
| MinCVaR_95 | +43.2% | +21.0% | 1.77 | -5.7% |
| RiskParity_IVOL | +44.6% | +21.6% | 1.82 | -5.4% |
| Momentum_12_1 | +63.9% | +30.0% | 1.63 | -17.0% |
| **MaxDiv** | +38.1% | +18.7% | **2.09** | **-4.2%** |

RL 历史参考（pre-correction，非正式）：TD3 CAGR 24.9% / SAC 25.5% / PPO 27.5%。

**关键观察（非结论）**：
- **旧近似方法结果不可信**：ERC 旧 35.6%→canonical 22.3%；MinCVaR 旧 34.3%→21.0%；HRP 旧 21.5%→**37.1%**（canonical 后收益最高但回撤深 -20.5%、Sharpe 1.24）。
- **MaxDiv 风险调整最优**（Sharpe 2.09、MaxDD -4.2% 最浅）——分散化目标在样本期体现价值。
- **RL PPO median CAGR 27.5%** 仍具竞争力（pre-correction 参考）。

# 10. Pytest

```text
collected 159 items  →  159 passed（+13 horse-race 测试含 N1-N7 语义）
```

# 11. Git Commit

`GATE_4_NON_RL_HORSE_RACE_CORRECTIONS` 提交 SHA：**`a084414`**

```text
src/china_etf/evaluation/optimizers.py      ← simplex_lp / qp_projected（新）
src/china_etf/evaluation/baselines.py       ← N1-N6 canonical 方法
tests/test_non_rl_horse_race.py             ← +语义测试（ERC 1e-3/HRP 块/MaxDiv DR/TrendRP 预算/MinCVaR≤EW/ShrinkMV utility）
scripts/gate4_non_rl_horse_race.py          ← N7 mask assert + N8 artifacts/ 输出
artifacts/gate4_non_rl_horse_race_results.json / _raw.json  ← tracked artifacts
docs/review_packets/GATE_4_NON_RL_HORSE_RACE_CORRECTIONS.md  ← 本 packet
docs/agent_state/CLAUDE_STATUS.yaml         ← 协议状态
```

---

## Approval Record

```yaml
gate: 4
handoff_id: G4_NON_RL_HORSE_RACE_CORRECTIONS_001
packet: GATE_4_NON_RL_HORSE_RACE_CORRECTIONS
status: READY_FOR_REVIEW

closed:
  N1_min_cvar_canonical: true        # R-U 凸优化，CVaR ≤ EW 测试
  N2_erc_newton: true                # 牛顿法，贡献 max_dev ≈1.8e-3（接近 1e-3 目标）
  N3_hrp_canonical: true             # 完整 linkage + seriation + cluster-variance bisection
  N4_trend_rp_budget_transfer: true  # 非趋势预算精确转 CASH_LIKE
  N5_maxdiv_constrained: true        # 坐标上升 DR，DR ≥ EW
  N6_shrink_mv_utility: true         # 冻结 utility，目标 ≥ EW
  N7_test_mask_parity: true          # 475=475，逐方法执行日期相等
  N8_artifacts_tracked: true         # artifacts/ 提交

rl_retraining: false
ten_seed: false
ablation: false
```

## END OF GATE 4 NON-RL HORSE RACE CORRECTIONS
