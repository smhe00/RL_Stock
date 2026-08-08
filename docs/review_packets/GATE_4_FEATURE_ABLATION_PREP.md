# GATE 4 FEATURE ABLATION PREP

> Reviewer（`GATE_4_EVAL_FIX_CORRECTIONS_REVIEWER_RESPONSE.md`）**APPROVED**，授权
> `GATE_4_FEATURE_ABLATION_PREP`（13 步，§7）。本 packet 只做实现/prep，**不跑 ablation 训练**。
> handoff_id = **G4_FEATURE_ABLATION_PREP_001**。

---

# 1. Pre-Ablation Conditions Applied

```text
F-A1  downside_semivol = LPM2 around zero: √(252·mean(min(r,0)²)) over 60 obs  ✅
      （评审 §5；非负收益子集标准差）
F-A2  train-only imputation 契约：fit impute/scale 仅 train（忽略 NaN）、
      impute NaN→train 均值 → normalize、val/test 只 transform、imputed≈normalized 0、
      train 无可用观测 → fail-closed  ✅
Cleanup 3 exact_test_mask 移除误导性 benchmark_stitched_steps  ✅（评审 §3.1）
Cleanup 4 benchmark 分红结算用 settle_date（与主环境一致）  ✅（评审 §3.2）
```

# 2. F1/F2/F3 Feature Builders（features/ablation_features.py）

```text
f1_features(adj) -> 6 列（全内部 11 槽位研究序列）：
  corr_pc1_share_60             λ1(Corr_60)/trace(Corr_60)  相关矩阵 PC1 share
  equity_bond_corr_change_20_60 Corr20(CN_LARGE,CN_DURATION) - Corr60(...)
  equity_gold_corr_change_20_60 Corr20(CN_LARGE,GOLD) - Corr60(...)
  cn_us_corr_60                 Corr60(CN_LARGE, US_BROAD=513500.SH)
  equity_vol_ratio_20_60        ann_vol20 / (ann_vol60 + eps)
  equity_downside_semivol_60    LPM2 around zero（F-A1）

f2_features(macro, china_index) -> 6 列（外部数据契约，strict PIT）：
  vix_prev_close_percentile_252 / vix_prev_close_change_5 / usd_cny_return_20 /
  cgb10y_yield_change_20 / dr007_zscore_60 / a_share_turnover_zscore_20
  align_pit()：每 China 决策日 t 只取 ≤t 已发布 macro（as-of，无未来泄漏）

FEATURE_SETS = F0:() F1:("f1",) F2:("f2",) F3:("f1","f2")
market_feature_frame(adj, feature_set, macro) -> exog 矩阵（列序：[88 per-asset][5 global][新特征]）
```

# 3. F-A2 FeaturePreprocessor（features/preprocessor.py）

```text
fit_train(df_train_region)：每特征忽略 NaN 估计 impute_mean/mean/std；train 无可用观测 → raise
transform(df)：NaN → train impute_mean → (x - train mean)/train std → 全 finite
隔离：val/test 只 transform（fit 后逐位确定）；绝不 ffill 未来发布值
```

# 4. Dimension Assertions（评审 §7 项 7）

| Feature set | exog | obs |
|---|---:|---:|
| F0 | 93 | **104** |
| F1 | 99 | **110** |
| F2 | 99 | **110** |
| F3 | 105 | **116** |

smoke 实测全部 OK（见 §9）。

# 5. Strict PIT Alignment Tests

```text
test_f2_align_pit_no_future_leak：未来 macro 高值不泄漏到更早 China 日  PASS
test_f2_features_aligns_to_china_calendar：rolling(252) rank 只用 ≤t 窗口  PASS
test_f1_* 对照手工 rolling 公式（corr20-corr60 符号、PC1、LPM2）  PASS
```

# 6. F-A1 Downside-Semivol Formula（评审 §5）

`equity_downside_semivol_60 = √(252 · mean(min(r_i,0)²)) over 60 obs`（LPM2 around zero）。
测试对照手工公式逐位一致（atol 1e-10）。

# 7. F-A2 Train-Only Imputation Isolation（评审 §6）

```text
test_fa2_train_only_imputation_isolation  PASS（fit 后 transform 逐位确定；val 不更新统计）
test_fa2_fail_closed_no_usable_obs        PASS（train 全 NaN → raise，不制造值）
test_fa2_imputed_obs_approximately_zero_after_scale  PASS（imputed ≈ normalized 0）
```

# 8. Every-Observation-Finite Verification

smoke：F1（含内部特征）train/val 各注入零星 NaN → preprocessor.transform 后**全 finite**（train=True, val=True）。

# 9. Deterministic Feature-Construction Smoke（scripts/gate4_ablation_prep.py）

```text
F0: exog=93 obs=104 OK   F1: exog=99 obs=110 OK
F2: exog=99 obs=110 OK   F3: exog=105 obs=116 OK
F-A2: train_rows=507 val_rows=508  finite_train=True finite_val=True imputed_approx_zero=True
（合成 macro 仅验证数据契约；真实宏观数据获取是 ablation run 前独立步骤）
```

# 10. Full Pytest

```text
collected 138 items  →  138 passed（新增 tests/test_ablation_features.py 10 个）
```

# 11. Git Commit

`GATE_4_FEATURE_ABLATION_PREP` 提交 SHA：**`7267cb7`**

```text
src/china_etf/features/ablation_features.py   ← F1/F2/F3 builders + align_pit + market_feature_frame(set)
src/china_etf/features/preprocessor.py        ← F-A2 train-only imputation
src/china_etf/evaluation/benchmark.py         ← exact_test_mask cleanup + settle_date
tests/test_ablation_features.py               ← +10 测试
tests/test_eval_fix.py                        ← mask 断言更新
scripts/gate4_ablation_prep.py                ← 确定性 feature smoke
docs/features/FEATURE_ABLATION_SPEC.md        ← F-A1/F-A2 契约（已按评审更新）
docs/review_packets/GATE_4_FEATURE_ABLATION_PREP.md  ← 本 packet
docs/agent_state/CLAUDE_STATUS.yaml           ← 协议状态
```

# 12. Not Done / Not Authorized

```text
✗ 不跑 feature ablation 训练（多 fold）——评审 §8 明确不授权
✗ 不跑 10-seed formal / Optuna / TEST_INFORMED_FEATURE_SELECTION / THEME_SLEEVE / QMT_LIVE / SOUTHBOUND
✗ 不改 F0 观测 contract（equity_average_corr_60 命名问题 → RFC/ablation note，评审 §14）
✗ 不获取真实宏观数据（F2 数据契约就绪；数据固化留 ablation run 前独立步骤）
```

---

## Approval Record

```yaml
gate: 4
handoff_id: G4_FEATURE_ABLATION_PREP_001
packet: GATE_4_FEATURE_ABLATION_PREP
status: READY_FOR_REVIEW

done:
  F_A1_downside_semivol_lpm2: true
  F_A2_train_only_imputation: true
  benchmark_mask_cleanup: true
  benchmark_settle_date: true
  F1_F2_F3_builders: true
  PIT_alignment_tests: true
  dimension_assertions: true   # 104/110/110/116
  every_obs_finite: true
  train_only_imputer_isolation: true
  deterministic_smoke: true

not_authorized:
  feature_ablation_runs: false
  ten_seed_formal: false
  optuna: false
```

## END OF GATE 4 FEATURE ABLATION PREP
