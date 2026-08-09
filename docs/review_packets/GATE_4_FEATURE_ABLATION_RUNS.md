# GATE 4 FEATURE ABLATION RUNS — F1 因子重要性发现（非 RL，用户定向）

> **注记（CORRECTIONS）**：本 packet 及其 artifact 现标注为 **EXPLORATORY_TEST_SCREENING_ONLY**
> （评审 A1：Test panel 不用于特征选择）。见 `GATE_4_FEATURE_ABLATION_RUNS_CORRECTIONS.md`。
>
> 评审（`GATE_4_FEATURE_ABLATION_PREP_002_REVIEWER_RESPONSE.md`）**APPROVED**，授权 `GATE_4_FEATURE_ABLATION_RUNS`
> （按冻结 FEATURE_ABLATION_SPEC；禁 RL 重训 / 10-seed / sweep；F2 真实宏观 → FEATURE_DATA_READY 门）。
>
> **用户定向方法**：不训练 RL。用 corrected 评估路径重跑便宜非 RL 参考策略，叠加冻结 F1 特征
> 做**因子重要性发现**——找出对前向 OOS 结果携带信息的因子，作为后续 RL 输入维度/net 调整的**发现**。
> handoff_id = **G4_FEATURE_ABLATION_RUNS_001**。

---

# 1. 方法（用户定向，非 RL）

```text
参考策略（corrected 路径，run_fold_baseline）：
  EqualWeight / RiskParity_IVOL / MinimumVariance（各 4 folds，475 执行日）
F1 特征（冻结 FEATURE_ABLATION_SPEC，ablation_features.f1_features）：
  6 个内部特征，在决策日 t（执行日 t_next 前一日）取值，与净收益配对

每特征 × 每策略：
  spearman(f, fwd_ret)、spearman(f, |fwd_ret|)
  tercile 判别：low vs high 分位 fwd 波动均值差 + Mann-Whitney U 双侧 p
F0 基线残差化（EW 面板为参考轴）：
  OLS 去除 F0 已有 corr/vol 信息（10 预测子：5 global + CN_LARGE per-asset 关键 5）
  → 残差仍预测前向风险？→ 回答 "F1 是否超出 F0 已有信息"
跨策略 regime 响应：每特征 low/mid/high 分位内各策略 OOS Sharpe
```

无任何 RL 训练发生。

# 2. 结果（从 tracked artifact 生成：artifacts/gate4_feature_importance_results.json）

## 2.1 F1 特征重要性表（EW 面板为参考轴）

| 特征 | ρ_ret | ρ_\|ret\| | F0 残差 ρ_\|ret\| | MWp_\|ret\| | low 分位 \|fwd\| | high 分位 \|fwd\| |
|---|---:|---:|---:|---:|---:|---:|
| equity_vol_ratio_20_60 | +0.076 | **+0.187** | **+0.036** | **<0.001** | 0.0050 | 0.0091 |
| equity_downside_semivol_60 | -0.003 | +0.048 | -0.020 | 0.378 | 0.0069 | 0.0065 |
| cn_us_corr_60 | -0.004 | +0.002 | -0.025 | 0.667 | 0.0071 | 0.0066 |
| equity_gold_corr_change_20_60 | +0.012 | -0.034 | -0.057 | 0.603 | 0.0070 | 0.0059 |
| corr_pc1_share_60 | +0.001 | -0.071 | -0.024 | 0.586 | 0.0064 | 0.0073 |
| equity_bond_corr_change_20_60 | -0.065 | -0.064 | +0.021 | 0.116 | 0.0076 | 0.0057 |

## 2.2 三策略一致性（vol_ratio 是唯一显著者）

| 策略 | ρ_ret | ρ_\|ret\| | MWp_\|ret\| |
|---|---:|---:|---:|
| EqualWeight | +0.076 | +0.187 | <0.001 |
| RiskParity_IVOL | +0.074 | +0.185 | <0.001 |
| MinimumVariance | +0.073 | +0.165 | <0.001 |

## 2.3 regime 响应（vol_ratio）

| 分位 | n | \|fwd\| 均值 | EW Sharpe | RP Sharpe | MinVar Sharpe |
|---|---:|---:|---:|---:|---:|
| low | 158 | 0.0050 | **-0.49** | -0.20 | -0.34 |
| mid | 159 | 0.0057 | 2.60 | 2.76 | 2.81 |
| high | 158 | 0.0091 | 2.33 | 2.48 | 2.40 |

# 3. 关键发现（discovery，非结论）

1. **仅 `equity_vol_ratio_20_60` 有显著前向风险判别**：high 分位前向波动 ≈ low 的 **1.8×**
   （0.0091 vs 0.0050），Mann-Whitney p < 0.001，三策略一致。
2. **但 F0 残差化后增量基本消失**：ρ_\|ret\| 0.187 → **0.036**。F0 已含 `realized_vol_20/60` +
   `cn_large_vol_percentile_252`，vol 比信号已被覆盖 → **F1 的 vol_ratio 对 F0 冗余**。
3. **其余 5 个 F1 因子无前向信息**：全部 ρ≈0、MWp>0.1——corr 结构（PC1 share / bond/gold/US corr
   变化）与 downside semivol 在本 OOS 样本未显示预测力。
4. **regime 备注**：low vol_ratio 分位下三策略 Sharpe 均显著为负（-0.20~-0.49）——该 regime 前向
   收益偏负（|ρ_ret|=0.076 弱单调，主要为尾部），可能是风险偏好转换期，仅作观察。

# 4. 对后续 RL 输入维度/net 调整的**发现**（非决策）

```text
- F1 候选集整体与 F0 冗余：无证据支持整组加入 RL 观察（ObsDim 104 → 110）。
- vol_ratio 原始判别最强，但增量已被 F0 覆盖 → 单独加入也意义有限。
- 若坚持保留一个 F1 因子，equity_vol_ratio_20_60 是最不坏候选（原始 p<0.001），
  但需接受其对 F0 的低增量。
- 建议：后续 RL 观察维度优先维持 F0（104）或做极少量选择扩展；net 大小调整
  不应由 F1 特征驱动（本发现不支持）。
```

这些为**发现**，不构成模型选型结论；是否调整由评审/用户后续决定。

# 5. 边界与规避

```text
✗ 未训练 RL（PPO/TD3/SAC）——遵守 RL_RETRAINING forbidden
✗ 未跑 10-seed / Optuna / sweep
✗ 未做 F2/F3（真实宏观数据 → FEATURE_DATA_READY 门）
✗ 未做模型选型结论；重要性为 screening 发现
环境变更：venv 新增 scipy 1.18（统计分析用，Mann-Whitney/Spearman）
```

# 6. Pytest

```text
collected 178 items  →  178 passed（新增 tests/test_feature_importance.py 16 个：
tercile 边界/tie/短N、Spearman 单调/NaN/常量、判别 gap+MWp、决策日对齐、OLS 残差、
已知单调信号符号/排序）
```

# 7. Git Commit

`GATE_4_FEATURE_ABLATION_RUNS` 提交 SHA：**`f0d471c`**

```text
src/china_etf/evaluation/factor_importance.py        ← 统计 helper（scipy-backed）
scripts/gate4_feature_importance.py                  ← 因子重要性发现脚本（非 RL）
tests/test_feature_importance.py                     ← 16 测试
artifacts/gate4_feature_importance_results.json      ← 结果（tracked）
docs/review_packets/GATE_4_FEATURE_ABLATION_RUNS.md  ← 本 packet
docs/agent_state/CLAUDE_STATUS.yaml                  ← 协议状态
```

---

## Approval Record

```yaml
gate: 4
handoff_id: G4_FEATURE_ABLATION_RUNS_001
packet: GATE_4_FEATURE_ABLATION_RUNS
status: READY_FOR_REVIEW

method:
  user_directed: non-RL F1 factor-importance discovery   # 不训练 RL
  reference_strategies: [EqualWeight, RiskParity_IVOL, MinimumVariance]
  f1_features: 6 internal (frozen FEATURE_ABLATION_SPEC)
  statistics: spearman + tercile discrimination + Mann-Whitney + F0 OLS residualization

findings:
  vol_ratio_significant_raw: true            # MWp<0.001, high/low fwd vol ~1.8x
  vol_ratio_increment_over_F0: small         # resid rho_abs 0.036 (~raw 0.187 gone)
  other_five_f1_weak: true                   # all rho~0, MWp>0.1
  f0_redundancy: F1 candidates largely redundant with F0 corr/vol

not_done:
  rl_retraining: false
  ten_seed_formal: false
  optuna_or_sweep: false
  f2_f3_real_macro: false                    # FEATURE_DATA_READY gate
  model_selection_conclusion: false          # findings only
```

## END OF GATE 4 FEATURE ABLATION RUNS
