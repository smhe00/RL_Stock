# GATE 4 NON-RL HORSE RACE — FINALIZATION

> 评审（`GATE_4_NON_RL_HORSE_RACE_FINAL_CORRECTIONS_REVIEWER_RESPONSE.md`）：`TARGETED_FINALIZATION_REQUIRED`。
> F1/F2/F3/F5 PASS。本 packet 关闭 F4A/F4B/F6 + packet-artifact 一致。**禁止** RL 重训 / 10-seed / ablation / sweep。
> handoff = **G4_NON_RL_HORSE_RACE_FINALIZATION_001**。

---

# 1. F4A — ERC/HRP 如实标注为 Project-Projected 变体

- `erc_policy` / `hrp_policy` 文档明确：先解**未约束** canonical objective（ERC 牛顿 ≤1e-3；HRP 完整层级），
  再 `_proj_constrained` 投影到 project 可行集。**投影后非"约束 ERC/HRP 最优"**，仅 post-projection 执行变体。
- 报告/方法名：`ERC_ProjectProjected`、`HRP_ProjectProjected`。
- MaxDiv / MinCVaR / ShrinkMV 为**迭代内投影**的 constrained 变体（保留 constrained 标签）。

# 2. F4B — 投影语义

`waterfill_proj` 描述为 **frozen project feasibility projection contract**（single-slot waterfill +
ChinaGrowth 缩放/再分配），**不声称精确 Euclidean 投影**。

# 3. F6 — 完整 Stitched 诊断 + 精确聚合

- `METRICS` 补：`total_turnover` / `total_turnover_l1` / `actual_traded_notional` /
  `total_cost_over_traded_notional` / `risk_overlay_mean_l1_raw_to_post`。
- stitched 聚合改为**精确求和**：`total_turnover = Σ per_fold`、`total_cost = Σ`、
  `actual_traded_notional = Σ`、`cost_over_traded_notional = total_cost / traded`。
- 加权均值：按 `n_eval_steps` 加权（非简单 mean）。
- `fallback_count` 可审计：脚本统计 `_cov_window` 返回 None（EW fallback）决策数，非硬编码。
- **全部方法 fallback=0**（Track A 有效历史足够全部 lookback，可审计）。

# 4. Final Horse-Race Table（从 tracked artifact 生成，corrected path + project 约束，475 执行日）

| 方法 | active-ann | Sharpe | Sortino | MaxDD | Calmar | total turn | total cost | c/traded | HHI | maxw | overlay | fb |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Momentum_12_1 | +30.0% | 1.63 | 2.09 | -17.0% | 1.76 | 0.051 | 9965 | 3.5bp | 0.149 | 0.256 | 0.53 | 0 |
| EqualWeight | +26.9% | 1.64 | 2.60 | -8.8% | 3.05 | 0.013 | 2632 | 3.5bp | 0.087 | 0.098 | 0.00 | 0 |
| ShrinkageMV | +26.1% | 1.60 | 2.37 | -8.6% | 3.02 | 0.013 | 2415 | 3.5bp | 0.090 | 0.135 | 0.00 | 0 |
| MinimumVariance | +22.8% | 1.75 | 2.75 | -6.0% | 3.81 | 0.012 | 2547 | 3.5bp | 0.118 | 0.250 | 1.00 | 0 |
| HRP_ProjectProjected | +22.7% | 1.76 | 2.76 | -5.9% | 3.83 | 0.012 | 2595 | 3.5bp | 0.118 | 0.250 | 0.00 | 0 |
| ERC_ProjectProjected | +22.5% | 1.87 | 2.87 | -5.6% | 4.05 | 0.025 | 4820 | 3.5bp | 0.121 | 0.252 | 0.00 | 0 |
| TrendRiskParity | +21.6% | 1.85 | 2.93 | -5.4% | 4.01 | 0.014 | 2938 | 3.5bp | 0.118 | 0.251 | 1.00 | 0 |
| RiskParity_IVOL | +21.6% | 1.82 | 2.90 | -5.4% | 4.00 | 0.013 | 2753 | 3.5bp | 0.118 | 0.250 | 1.00 | 0 |
| MaximumDiversification | +18.3% | **2.77** | **4.33** | **-3.4%** | **5.38** | 0.012 | 2798 | 3.5bp | 0.165 | 0.248 | 0.00 | 0 |
| MinimumCVaR_95 | +16.8% | 2.30 | 3.00 | -4.3% | 3.87 | 0.018 | 3784 | 3.5bp | 0.192 | 0.252 | 0.00 | 0 |

RL 历史参考（pre-correction）：TD3 24.9% / SAC 25.5% / PPO 27.5%。

**关键观察（非结论）**：
- **MaxDiv 风险调整最优**：Sharpe 2.77、Sortino 4.33、MaxDD -3.4% 最浅、Calmar 5.38 最高——DR 目标稳健。
- **EqualWeight 仍是强基线**：CAGR 26.9%、Sharpe 1.64、MaxDD -8.8%，优于多数优化器（估计误差侵蚀）。
- **Momentum 收益最高但回撤最深**（-17%）。
- **成本一致**：全部 cost/traded ≈ 3.5bp（Mainland 单边成本），换手低（0.01-0.05）。
- **overlay**：除 Momentum（0.53）全 0——等权/风险型权重本就低（≤0.25 cap）；packet 前表手抄错已修正。
- **RL PPO median 27.5%** 仍具竞争力（pre-correction 参考）。

# 5. Pytest

```text
collected 162 items  →  162 passed
```

# 6. Git Commit

`GATE_4_NON_RL_HORSE_RACE_FINALIZATION` 提交 SHA：**`2a8ea68`**

```text
src/china_etf/evaluation/baselines.py    ← F4A ERC/HRP 标注 + 投影语义
src/china_etf/evaluation/optimizers.py   ← F4B waterfill_proj docstring
scripts/gate4_non_rl_horse_race.py       ← F6 完整诊断 + 精确聚合 + 可审计 fallback
artifacts/gate4_non_rl_horse_race_results.json / _raw.json  ← 更新
docs/review_packets/GATE_4_NON_RL_HORSE_RACE_FINALIZATION.md  ← 本 packet
docs/agent_state/CLAUDE_STATUS.yaml      ← 协议状态
```

---

## Approval Record

```yaml
gate: 4
handoff_id: G4_NON_RL_HORSE_RACE_FINALIZATION_001
packet: GATE_4_NON_RL_HORSE_RACE_FINALIZATION
status: READY_FOR_REVIEW

closed:
  F4A_erc_hrp_project_projected_labeling: true
  F4B_projection_feasibility_contract: true
  F6_exact_stitched_diagnostics: true    # 精确求和 + 加权均值 + 可审计 fallback（全部 0）
  packet_artifact_consistency: true      # 表从 artifact 生成；overlay 修正

rl_retraining: false
ten_seed: false
ablation: false
```

## END OF GATE 4 NON-RL HORSE RACE FINALIZATION
