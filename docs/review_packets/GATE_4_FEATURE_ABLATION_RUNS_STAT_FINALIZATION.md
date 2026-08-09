# GATE 4 FEATURE ABLATION RUNS — STAT FINALIZATION（B1-B5 统计严谨性修正）

> 评审（`GATE_4_FEATURE_ABLATION_RUNS_CORRECTIONS_REVIEWER_RESPONSE.md`）**TARGETED_STATISTICAL_FINALIZATION_REQUIRED**
> （B1-B5），`authorized_next: GATE_4_FEATURE_ABLATION_RUNS_STAT_FINALIZATION`。本 packet 关闭 B1-B5。
> handoff_id = **G4_FEATURE_ABLATION_RUNS_STAT_FINALIZATION_001**。

---

# 1. 修正内容（B1-B5）

```text
B1 global Test 隔离 → global_test_union = ∪ fold.test 决策日（475），从每个 screening/fit 数据集排除；
   screening = decision 日 ∩ 非 test 日 = 540 天（expanding 下 fold-local 不足够，因后 fold train 含前 fold test）。
B2 median-p→Holm/BH 无效 → block_permutation_p（block-shuffle null，null-centered）每特征一个有效 p，
   跨 6 特征 Holm/BH（族级控制）。
B3 median-of-CI 非聚合 CI → 报告 per-fold bootstrap CI（4 个独立 CI，无合成聚合置信水平）+
   block_len 敏感性 20/40/60。
B4 p_bs 非 null-centered → 移除；block_bootstrap_ci 仅描述性 percentile CI（无 p 值）。
B5 残差化 reduced F0 proxy（10 预测子：5 global + CN_LARGE per-asset 5，非完整 104 维 F0）→
   重标签 reduced_F0_market_proxy + 收窄结论。
```

# 2. 方法（全局 Test-free，无 RL/无策略）

```text
outcome = 市场等权前向收益（11 槽位复权 log 收益 t→t+1）
screening 面板 = 540 个从未出现在任何 fold test 的决策日
每特征：spearman(f, |fwd|) + tercile gap + per-fold bootstrap CI（block_len 20/40/60）+ block_permutation_p
Holm/BH 校正跨 6 特征（有效依赖感知 p）
残差化：reduced_F0_market_proxy fold-local cross-fit（train fit → val apply，global-test-excluded）
```

# 3. 结果（从 tracked artifact 生成：artifacts/gate4_feature_importance_stat_final.json）

## 3.1 F1 特征 screening（540 全局 Test-free 决策日）

| 特征 | ρ_\|ret\| | naive MWp | **block-perm p** | **Holm p** | BH q |
|---|---:|---:|---:|---:|---:|
| corr_pc1_share_60 | -0.090 | 0.036 | 0.044 | 0.264 | 0.264 |
| equity_bond_corr_change_20_60 | +0.015 | 0.633 | 0.723 | 1.000 | 0.771 |
| equity_gold_corr_change_20_60 | -0.041 | 0.711 | 0.302 | 0.905 | 0.453 |
| cn_us_corr_60 | +0.014 | 0.723 | 0.771 | 1.000 | 0.771 |
| equity_vol_ratio_20_60 | -0.063 | 0.109 | 0.126 | 0.629 | 0.378 |
| equity_downside_semivol_60 | +0.060 | 0.194 | 0.192 | 0.767 | 0.384 |

**有效 block-permutation Holm 校正后：全部 6 特征不显著（Holm ≥ 0.264，q ≥ 0.264）。**

## 3.2 vol_ratio per-fold bootstrap CI（block_len 20，4 个独立 CI）

| fold | n | 95% CI |
|---|---:|---|
| F1 | 360 | [-0.183, +0.031] |
| F2 | 420 | [-0.144, +0.047] |
| F3 | 480 | [-0.160, +0.026] |
| F4 | 540 | [-0.147, +0.016] |

**全部 4 个 CI 跨 0** —— 无正向风险关联。

## 3.3 block_len 敏感性（vol_ratio median endpoints）

| block_len | 中位 lo | 中位 hi |
|---|---:|---:|
| 20 | -0.153 | +0.028 |
| 40 | -0.148 | +0.029 |
| 60 | -0.135 | +0.037 |

**block_len 20/40/60 结果一致**（F1 含 60 日窗口，敏感性确认）。

## 3.4 reduced-F0-proxy fold-local cross-fit 残差化（train fit → val apply）

| 特征 | min ρ_resid | median ρ_resid |
|---|---:|---:|
| corr_pc1_share_60 | -0.152 | -0.105 |
| equity_bond_corr_change_20_60 | -0.096 | +0.086 |
| equity_gold_corr_change_20_60 | -0.253 | -0.085 |
| cn_us_corr_60 | -0.323 | -0.108 |
| equity_vol_ratio_20_60 | -0.285 | -0.018 |
| equity_downside_semivol_60 | -0.270 | -0.154 |

**5/6 median ρ_resid ≤ 0**（bond_corr 仅 +0.086）——移除 reduced 线性 F0 proxy 后无稳健正向单调残差关联。

# 4. 结论（收窄至证据支持的描述性陈述）

1. **无 F1 特征在有效依赖感知多重检验校正后显著**（全局 Test-free，Holm/BH ≥ 0.26）。
2. **vol_ratio 的 475-Test 关联未获独立证伪也未被证实**——Test-free 数据 ρ=-0.063（符号反）、
   per-fold CI 全跨 0；与先前 Test 面板（+0.187）矛盾，符号不稳定。
3. **reduced-F0 残差化**：仅支持"移除 reduced 线性 F0 proxy 后无稳健正向单调残差关联"，
   **不**支持"F1 冗余于完整 104 维 F0"（proxy 仅 10 预测子，未含全部 per-asset/weights）。
4. 这些是**描述性 negative evidence**，不是形式化的无预测力证明；F1 冻结候选集**保持不变**。

# 5. 边界与规避

```text
✓ 全局 Test 隔离（union 排除；540 天 Test-free）
✓ block permutation null p + Holm/BH（有效族级/FDR）
✓ per-fold bootstrap CI（无合成聚合 CI）+ block_len 敏感性
✓ reduced_F0_market_proxy 标签（B5 收窄）
✓ 无 RL 重训 / 10-seed / Optuna / sweep / F2/F3
✗ 不因 Test 结果增删特征；不做 Test-informed 选择推荐
✗ 不断言完整 F0 冗余；不断言独立证伪原 475-Test 关联
```

# 6. Pytest

```text
collected 194 items  →  194 passed（新增 6：block_permutation_p ×3、bootstrap 无 p_bs、全局隔离不相交、reduced proxy 标签）
```

# 7. Git Commit

`GATE_4_FEATURE_ABLATION_RUNS_STAT_FINALIZATION` 提交 SHA：**`6dd8b34`**

```text
src/china_etf/evaluation/factor_importance.py     ← +block_permutation_p；block_bootstrap_ci 移除 p_bs
scripts/gate4_feature_importance_stat_final.py    ← 全局 Test-free screening + per-fold CI + 敏感性 + 有效 Holm/BH
tests/test_feature_importance.py                  ← +6 测试
artifacts/gate4_feature_importance_stat_final.json ← 结果（tracked）
docs/review_packets/GATE_4_FEATURE_ABLATION_RUNS_STAT_FINALIZATION.md  ← 本 packet
docs/agent_state/CLAUDE_STATUS.yaml               ← 协议状态
```

---

## Approval Record

```yaml
gate: 4
handoff_id: G4_FEATURE_ABLATION_RUNS_STAT_FINALIZATION_001
packet: GATE_4_FEATURE_ABLATION_RUNS_STAT_FINALIZATION
status: READY_FOR_REVIEW

closed:
  B1_global_test_quarantine: true       # global_test_union (475) excluded; 540 Test-free screening days
  B2_valid_dependence_aware_p: true     # block_permutation_p per feature + Holm/BH across 6
  B3_per_fold_ci_no_aggregate: true     # per-fold bootstrap CI + block_len 20/40/60 sensitivity
  B4_p_bs_removed: true                 # bootstrap = descriptive percentile CI only
  B5_reduced_f0_proxy_label: true       # reduced_F0_market_proxy (10 pred); conclusion narrowed

findings:
  no_f1_feature_significant_test_free: true  # Holm p >= 0.264, q >= 0.264 all
  vol_ratio_test_signal_not_robust: true     # test-free rho -0.063 (sign flip), per-fold CI all cross 0
  reduced_proxy_no_incremental: true         # 5/6 median resid rho <= 0; bond_corr +0.086 weak

not_done:
  rl_retraining: false
  ten_seed_formal: false
  optuna_or_sweep: false
  f2_f3_real_macro: false
  test_informed_selection: false             # explicitly avoided
  feature_set_change: false                  # frozen F1 candidates unchanged
```

## END OF GATE 4 FEATURE ABLATION RUNS STAT FINALIZATION
