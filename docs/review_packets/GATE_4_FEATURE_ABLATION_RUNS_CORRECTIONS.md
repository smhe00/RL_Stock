# GATE 4 FEATURE ABLATION RUNS — CORRECTIONS（Train/Val-only 因子 screening，A1-A5）

> 评审（`GATE_4_FEATURE_ABLATION_RUNS_REVIEWER_RESPONSE.md`）**REVISIONS_REQUIRED**（A1-A5），
> `authorized_next: GATE_4_FEATURE_ABLATION_RUNS_CORRECTIONS`。本 packet 关闭 A1-A5。
> handoff_id = **G4_FEATURE_ABLATION_RUNS_CORRECTIONS_001**。

---

# 1. 修正内容（A1-A5）

```text
A1 Test-informed screening   → 原 475-Test artifact 保留为 EXPLORATORY_TEST_SCREENING_ONLY（不删不改），
                               本分析只用 Train/Val，不用于特征选择/RL 输入设计。
A2 非 RL 子门                → 明确为 non-RL screening/diagnostic 子门；无 canonical RL F0-vs-F1 模型
                               ablation 执行（RL retraining forbidden）。
A3 iid 显著性                → block bootstrap（block_len=20 预声明，移动块）95% CI + Holm/BH-FDR 多重检验。
A4 full-Test 残差化          → Train/Val-only + fold-local cross-fit（train fit → val apply）。
A5 composite score           → 弃用；各指标分开报告（rho、gap、p、CI）。
```

# 2. 方法（fold-local，TEST 隔离，无 RL/无策略）

```text
outcome = 市场等权前向收益（11 槽位复权 log 收益，决策日 t → t+1）
每 fold：screening 决策日 = 该 fold 自身 train∪val（不含自身 test）；folds 间 expanding
  train 天然重叠 → fold-local 是唯一无泄漏的隔离方式
统计：Spearman(f, |fwd|)、tercile gap、Mann-Whitney p、block bootstrap CI（每 fold → 跨 fold 汇总）
残差化：fold-local cross-fit（train 区间 fit F1~F0 OLS → val 区间 apply → 残差 vs val |fwd|）
```

# 3. 结果（从 tracked artifact 生成：artifacts/gate4_feature_importance_corrections.json）

## 3.1 F1 特征 Train/Val screening（fold-local，TEST quarantined）

| 特征 | med ρ_\|ret\| | med gap | med MWp | Holm p | bootstrap 95% CI |
|---|---:|---:|---:|---:|---|
| corr_pc1_share_60 | -0.071 | +0.0003 | 0.127 | 0.760 | [-0.162, +0.011] |
| equity_bond_corr_change_20_60 | -0.043 | +0.0006 | 0.409 | 1.000 | [-0.128, +0.050] |
| equity_gold_corr_change_20_60 | -0.022 | +0.0004 | 0.733 | 1.000 | [-0.109, +0.056] |
| cn_us_corr_60 | -0.048 | +0.0010 | 0.140 | 0.760 | [-0.142, +0.044] |
| equity_vol_ratio_20_60 | **+0.018** | -0.0008 | 0.765 | 1.000 | [-0.087, +0.122] |
| equity_downside_semivol_60 | +0.056 | -0.0006 | 0.196 | 0.785 | [-0.027, +0.140] |

**全部 6 特征：Holm 校正 p ≥ 0.76，bootstrap CI 全部含 0 —— 无一个在 Train/Val 上显著。**

## 3.2 vol_ratio 逐 fold（Test 信号不稳健的实证）

| fold | ρ_\|ret\| | MWp | n |
|---|---:|---:|---:|
| F1 | -0.065 | 0.072 | 360 |
| F2 | +0.019 | 0.971 | 538 |
| F3 | +0.016 | 0.966 | 716 |
| F4 | +0.048 | 0.563 | 894 |
| **median** | **+0.018** | 0.765 | — |

Test 面板上 vol_ratio 的显著（ρ=+0.187, p<0.001）在 Train/Val 上**消失且符号跨 fold 不稳定**（-0.065~+0.048）——样本特定现象，非稳健 OOS 信号。

## 3.3 fold-local cross-fit 残差化（train fit → val apply）

| 特征 | min ρ_resid | median ρ_resid |
|---|---:|---:|
| corr_pc1_share_60 | -0.110 | -0.084 |
| equity_bond_corr_change_20_60 | -0.103 | +0.096 |
| equity_gold_corr_change_20_60 | -0.235 | -0.091 |
| cn_us_corr_60 | -0.389 | -0.107 |
| equity_vol_ratio_20_60 | -0.285 | -0.059 |
| equity_downside_semivol_60 | -0.195 | -0.163 |

**全部 median ρ_resid ≤ 0 —— F1 特征去除 F0 后无正向增量前向信息。**

# 4. 结论（发现，非决策）

1. **Train/Val 隔离下无 F1 特征显著**——F1 候选集（corr/vol/PC1）在修正统计下无稳健前向信号。
2. **原 Test 面板的 vol_ratio 显著是样本特定**：Train/Val 中 ρ 符号跨 fold 不稳定、CI 含 0——
   评审对 Test-informed 的担忧被实证支持。
3. **cross-fit 残差化无增量**：F1 不提供超出 F0 的前向信息。
4. **无 RL 模型 ablation 执行**；本结果为 exploratory/diagnostic，**不驱动特征选择或 RL 输入维度/net 调整**。

# 5. 边界与规避

```text
✓ TEST 完全隔离（fold-local；fold k+1 的 train 含 fold k 的 test 是 expanding 设计，非泄漏）
✓ 原 475-Test artifact 保留未改（EXPLORATORY_TEST_SCREENING_ONLY）
✓ block bootstrap（block_len=20）+ Holm/BH-FDR
✓ 无 RL 重训 / 10-seed / Optuna / sweep / F2/F3 真实宏观
✗ 不做 Test-informed 特征选择/RL 维度/net 推荐
```

# 6. Pytest

```text
collected 188 items  →  188 passed（新增 10：bootstrap CI ×3、Holm/BH ×4、cross-fit ×2、fold-local 隔离 ×1）
```

# 7. Git Commit

`GATE_4_FEATURE_ABLATION_RUNS_CORRECTIONS` 提交 SHA：**`520d13a`**

```text
src/china_etf/evaluation/factor_importance.py     ← +block_bootstrap_ci / holm_adjust / bh_fdr
scripts/gate4_feature_importance_corrections.py   ← Train/Val-only fold-local screening
tests/test_feature_importance.py                  ← +10 测试
artifacts/gate4_feature_importance_corrections.json ← 结果（tracked）
docs/review_packets/GATE_4_FEATURE_ABLATION_RUNS_CORRECTIONS.md  ← 本 packet
docs/agent_state/CLAUDE_STATUS.yaml               ← 协议状态
```

---

## Approval Record

```yaml
gate: 4
handoff_id: G4_FEATURE_ABLATION_RUNS_CORRECTIONS_001
packet: GATE_4_FEATURE_ABLATION_RUNS_CORRECTIONS
status: READY_FOR_REVIEW

closed:
  A1_test_quarantine: true          # Test artifact preserved as EXPLORATORY; screening on Train/Val only
  A2_non_rl_screening_subgate: true # no canonical RL F0-vs-F1 ablation; RL retraining forbidden
  A3_timeseries_uncertainty: true   # block bootstrap (block_len=20) CI + Holm/BH-FDR
  A4_fold_local_cross_fit: true     # train fit -> val apply residualization
  A5_no_composite_score: true       # metrics reported separately

findings:
  no_f1_feature_significant_train_val: true   # Holm p >= 0.76 all, bootstrap CI all contain 0
  vol_ratio_test_signal_not_robust: true      # Test rho 0.187 -> Train/Val median 0.018, sign unstable
  cross_fit_no_incremental_info: true         # all median resid rho <= 0

not_done:
  rl_retraining: false
  ten_seed_formal: false
  optuna_or_sweep: false
  f2_f3_real_macro: false
  test_informed_selection: false              # explicitly avoided
```

## END OF GATE 4 FEATURE ABLATION RUNS CORRECTIONS
