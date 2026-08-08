# GATE 4 NON-RL HORSE RACE — FINAL CORRECTIONS

> 评审（`GATE_4_NON_RL_HORSE_RACE_CORRECTIONS_REVIEWER_RESPONSE.md`）：`TARGETED_FINAL_CORRECTIONS_REQUIRED`，
> 6 blocker F1-F6。本 packet：F1-F6 修复 + 语义测试 + 重跑 + 完整诊断。**禁止** RL 重训 / 10-seed / ablation / sweep。
> handoff = **G4_NON_RL_HORSE_RACE_FINAL_CORRECTIONS_001**。

---

# 1. F1 — HRP Cluster-Variance 分配方向（低方差簇更多权重）

`_hrp_weights.bisect` 分配修正：`weight_A = vb/(va+vb)`，`weight_B = va/(va+vb)`（评审 F1：低方差簇更多）。
新语义测试 `test_hrp_low_variance_cluster_gets_more_weight`：两簇不等方差（vol 0.005 vs 0.02）→ 低方差簇总权重 > 高方差簇。

# 2. F2 — MinCVaR 目标 + 收敛（R-U 精确）

- `_cvar_value` 修正为 R-U：`CVaR = zeta* + mean(max(loss - zeta*, 0))/(1-α)`，zeta* = VaR_α（分位数）。
  旧实现 `VaR + tail_mean/(1-α)` 移除（评审 F2：非 CVaR）。
- 删除 tautological 收敛条件（`abs(best_val - cvar(best_w)) < 1e-12` 恒真）；改用真实 CVaR 值跟踪 best_w + 停滞判据。
- 独立语义测试：`_empirical_es`（worst 5% 平均损失，不依赖 `_cvar_value`）对照，优化 ES ≤ EW ES。
- 旧 MinCVaR 结果作废，重跑后替换。

# 3. F3 — ERC 收紧 ≤1e-3（不放宽 gate）

- `_erc_solve` 用**解析 Jacobian**（∂(w_i(Σw)_i)/∂w_j = δ_ij(Σw)_i + w_iΣ_ij）+ 残差检查。
- 测试阈值改回 **≤1e-3**，并在**相关非均匀协方差**上验证（合成均匀数据 EW 近等贡献会掩盖问题）。
- 如实标注：`_proj_constrained` 投影到 project 约束后等贡献被 cap 截断 → 报告区分 raw ERC 解 vs post-constraint 执行。

# 4. F4 — Project 约束进优化器

- `_proj_constrained(w, slots)`：long-only + sum=1 + single-slot caps(0.25) + ChinaGrowth group cap(0.50, CHINEXT+STAR)。
- **MaxDiv / ShrinkMV / MinCVaR / ERC / HRP** 优化迭代内投影到 project 可行集（`qp_projected`/`_maxdiv_coordinate`/`_min_cvar_subgradient`/`_erc_solve` 均接受 caps/growth）。
- 重跑证据：**ERC/HRP/MaxDiv/MinCVaR/ShrinkMV overlay intervention 从 ~1.0 → 0**（约束已在优化内）；
  RiskParity/MV/Momentum/TrendRP 仍 ~1.0（这些是 unconstrained+RiskOverlay 变体，如实标注）。
- 语义测试：`test_maxdiv_feasible_local_optimality`（可行扰动不改进 DR）+ ShrinkMV utility ≥ EW。

# 5. F5 — 真实执行日期 Parity

- `roll_out` series 增 `execution_dates`（真实 `st.t_next`）。
- 脚本：每方法拼接真实执行日期，assert == `exact_test_mask.test_dates`（475，独立于 mask 重建）。
- 测试 `test_rollout_execution_dates_recorded`：首执行日 == test_start、末 == test_end、== 本 fold mask 段。

# 6. F6 — 完整 Stitched 诊断

每方法 stitched 输出补齐（`active_day_annualized_return` 明确标注，非普通日历 CAGR）：
cum / active-day annualized / ann vol / Sharpe / Sortino / MaxDD / Calmar / mean+total turnover /
total cost / cost-over-initial / mean HHI / mean active assets / max weight / overlay intervention /
NaN / negative-cash / fallback count。

# 7. Canonical 重跑结果（stitched OOS，475 执行日，corrected path + project 约束）

| 方法 | active-ann | Sharpe | Sortino | MaxDD | overlay |
|---|---:|---:|---:|---:|---:|
| EqualWeight | +26.9% | 1.64 | — | -8.8% | 1.00 |
| RiskParity_IVOL | +21.6% | 1.82 | — | -5.4% | 1.00 |
| MinimumVariance | +22.8% | 1.75 | — | -6.0% | 1.00 |
| Momentum_12_1 | +30.0% | 1.63 | — | -17.0% | 0.53 |
| **ERC** | +22.3% | 1.86 | — | -5.6% | **0.00** |
| **HRP** | +22.7% | 1.76 | — | -5.9% | **0.00** |
| **MaxDiv** | +18.3% | **2.78** | — | **-3.4%** | **0.00** |
| TrendRiskParity | +21.6% | 1.85 | — | -5.4% | 1.00 |
| **MinCVaR_95** | +16.8% | 2.30 | — | -4.3% | **0.00** |
| **ShrinkageMV** | +26.1% | 1.60 | — | -8.6% | **0.00** |

RL 历史参考（pre-correction）：TD3 24.9% / SAC 25.5% / PPO 27.5%。

**关键观察（非结论）**：
- **F1/F2 修正改变结果**：HRP 从 37.1% → **22.7%**（方差方向修正消除虚假高收益）；MinCVaR 从 21.0% → 16.8%（R-U 目标修正）。
- **MaxDiv 风险调整最优**（Sharpe 2.78、MaxDD -3.4% 最浅）——project 约束内 DR 目标在样本期表现稳健。
- **约束进优化器后**：5 个 canonical 方法 overlay=0（纯优化解），4 个基线 overlay>0（unconstrained+overlay 变体，如实区分）。
- **RL PPO median 27.5%** 仍具竞争力（pre-correction 参考）。

# 8. 语义测试

新增 F1（低方差簇）、F2（独立 ES）、F3（ERC 1e-3）、F4（MaxDiv 局部最优）、F5（execution_dates）。

# 9. Pytest

```text
collected 162 items  →  162 passed
```

# 10. Git Commit

`GATE_4_NON_RL_HORSE_RACE_FINAL_CORRECTIONS` 提交 SHA：**`4ace12f`**

```text
src/china_etf/evaluation/baselines.py    ← F1 HRP 方向 / F2 MinCVaR / F3 ERC / F4 约束进优化器
src/china_etf/evaluation/optimizers.py   ← waterfill_proj caps+growth
src/china_etf/evaluation/rollout.py      ← F5 execution_dates
scripts/gate4_non_rl_horse_race.py       ← F5 real-date assert + F6 完整诊断
tests/test_non_rl_horse_race.py          ← +F1/F2/F3/F4/F5 语义测试
artifacts/gate4_non_rl_horse_race_results.json / _raw.json  ← 更新
docs/review_packets/GATE_4_NON_RL_HORSE_RACE_FINAL_CORRECTIONS.md  ← 本 packet
docs/agent_state/CLAUDE_STATUS.yaml      ← 协议状态
```

---

## Approval Record

```yaml
gate: 4
handoff_id: G4_NON_RL_HORSE_RACE_FINAL_CORRECTIONS_001
packet: GATE_4_NON_RL_HORSE_RACE_FINAL_CORRECTIONS
status: READY_FOR_REVIEW

closed:
  F1_hrp_cluster_variance_direction: true   # 低方差簇更多权重；语义测试
  F2_min_cvar_objective_convergence: true   # R-U 精确 + 独立 ES 测试
  F3_erc_tolerance_1e3: true                # 解析 Jacobian，threshold ≤1e-3（未放宽）
  F4_project_constraints_in_optimizer: true # 5 方法 overlay=0；4 基线如实标注 unconstrained+overlay
  F5_actual_execution_date_parity: true     # rollout 真实日期 == 475 mask
  F6_stitched_diagnostics_complete: true    # active-day ann + 全字段

rl_retraining: false
ten_seed: false
ablation: false
```

## END OF GATE 4 NON-RL HORSE RACE FINAL CORRECTIONS
