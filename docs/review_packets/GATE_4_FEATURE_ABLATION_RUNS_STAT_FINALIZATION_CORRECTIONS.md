# GATE 4 FEATURE ABLATION RUNS — STAT FINALIZATION CORRECTIONS（C1-C5 过渡语义 + 依赖感知重采样）

> **注记（DIAGNOSTIC_CLOSEOUT）**：本 packet 的确认性 p/Holm/BH 与 bootstrap CI 被评审 D1/D2 判定
> 非有效确认性推断（block_len=60 permutation 在 60 日段退化；bootstrap 跨 gap）。最终版本退役确认性
> 推断、仅保留描述性证据，见 `GATE_4_FEATURE_ABLATION_DIAGNOSTIC_CLOSEOUT.md`。
>
> 评审（`GATE_4_FEATURE_ABLATION_RUNS_STAT_FINALIZATION_REVIEWER_RESPONSE.md`）**TARGETED_TRANSITION_AND_RESAMPLING_CORRECTIONS_REQUIRED**
> （C1-C5），`authorized_next: GATE_4_FEATURE_ABLATION_RUNS_STAT_FINALIZATION_CORRECTIONS`。本 packet 关闭 C1-C5。
> handoff_id = **G4_FEATURE_ABLATION_RUNS_STAT_FINALIZATION_CORRECTIONS_001**。

---

# 1. 修正内容（C1-C5）

```text
C1 Test 隔离按决策日（非执行日）：exact_test_mask["test_dates"]（475 执行日）→ decision_dates 映射到前序决策日
   （475 决策日）→ 排除该 union。transition-based invariant：无诊断 t→t+1 的 t+1 在执行 mask 中（assert 通过）；
   val_end 逐 fold 断言已排除。→ screening = 539 天（原 540 含边界泄漏，修正后 -1）。
C2 block_permutation_p（with-replacement bootstrap）→ segment-aware 无替换 contiguous-block permutation
   （段内不重叠块洗牌），p = (1 + count(|T_null| >= |T_obs|)) / (B + 1)，clamp [0,1]。
C3 resampling 不跨 quarantined gap：contiguous_segments 按原始 adj.index 邻接分段，段内块洗牌；4 段 [359,60,60,60]。
C4 fold CI 重标签 fold-specific nested-panel descriptive CI（expanding/nested，非独立，不合成聚合 CI）。
C5 inferential p 预声明保守主尺度 block_len=60（F1 含 60 日窗口），报告 20/40/60 敏感性；Holm/BH 用 60。
```

# 2. 方法（transition-quarantined，segment-aware，无 RL/无策略）

```text
outcome = 市场等权前向收益（11 槽位复权 log 收益 t→t+1）
excluded = decision_dates(exact_test_mask test_dates)   # 475 决策日
screen   = decision_days - excluded                     # 539 天（无任何 Test transition）
每特征：spearman(f, |fwd|) + tercile gap + naive MWp（描述性）
       + per-fold nested descriptive CI（block_len 20/40/60）
       + segment_block_permutation_p（block_len 20/40/60；primary=60）→ Holm/BH
残差化：reduced_F0_market_proxy fold-local cross-fit（train fit → val apply，排除 excluded）
```

# 3. 结果（从 tracked artifact 生成：artifacts/gate4_feature_importance_stat_final_corrections.json）

## 3.1 F1 特征 screening（539 transition-quarantined 决策日）

| 特征 | ρ_\|ret\| | p(20) | p(40) | **p(60)** | **Holm(60)** | BH q(60) |
|---|---:|---:|---:|---:|---:|---:|
| corr_pc1_share_60 | -0.097 | 0.006 | 0.014 | 0.027 | **0.162** | 0.162 |
| equity_bond_corr_change_20_60 | +0.015 | 0.700 | 0.678 | 0.712 | 1.000 | 0.855 |
| equity_gold_corr_change_20_60 | -0.040 | 0.342 | 0.309 | 0.359 | 1.000 | 0.538 |
| cn_us_corr_60 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| equity_vol_ratio_20_60 | -0.062 | 0.169 | 0.073 | 0.271 | 1.000 | 0.538 |
| equity_downside_semivol_60 | +0.056 | 0.160 | 0.121 | 0.238 | 1.000 | 0.538 |

**全部 6 特征在预声明保守主尺度（block_len=60）的 segment-aware permutation Holm/BH 下不显著（Holm ≥ 0.162，q ≥ 0.162）。**

注：corr_pc1_share_60 在较小 block_len（20/40）名义 p 较小（0.006/0.014），但 p(60)=0.027 且 Holm 校正后 0.162——不构成稳健显著性；ρ 为负（-0.097，反向关联）。

## 3.2 vol_ratio 再次不稳健

- Test-free ρ = **-0.062**（符号反），p(60) = 0.271，Holm 1.000——先前的 475-Test +0.187 关联未在 transition-quarantined 数据上复现。

## 3.3 segment-aware 邻接段（C3）

```text
contiguous_segments: 4 段, sizes=[359, 60, 60, 60]
（排除 475 决策日后，expanding train 中较长连续区 + 各 val 段独立成段；段内无 gap）
```

## 3.4 per-fold nested descriptive CI（C4，非独立，不合成聚合）

| fold | n | block_len 60 95% CI（vol_ratio） |
|---|---:|---|
| F1 | 360 | [-0.184, +0.024] |
| F2 | 420 | [-0.152, +0.053] |
| F3 | 480 | [-0.166, +0.032] |
| F4 | 539 | [-0.148, +0.018] |

**4 个 nested-panel descriptive CI 全部跨 0**（fold-specific，非独立，仅描述性）。

## 3.5 reduced-F0-proxy fold-local cross-fit 残差化（train fit → val apply，transition-excluded）

| 特征 | min ρ_resid | median ρ_resid |
|---|---:|---:|
| corr_pc1_share_60 | -0.144 | -0.109 |
| equity_bond_corr_change_20_60 | -0.084 | +0.090 |
| equity_gold_corr_change_20_60 | -0.251 | -0.080 |
| cn_us_corr_60 | -0.313 | -0.116 |
| equity_vol_ratio_20_60 | -0.296 | -0.019 |
| equity_downside_semivol_60 | -0.259 | -0.164 |

**5/6 median ρ_resid ≤ 0**（bond_corr 仅 +0.090）——移除 reduced 线性 F0 proxy 后无稳健正向单调残差关联。

# 4. 结论（描述性 negative evidence）

1. **无 F1 特征在保守依赖感知多重检验下显著**（transition-quarantined，segment-aware permutation，block_len=60 primary）。
2. **vol_ratio 的 475-Test 关联未获支持**（Test-free ρ=-0.062 符号反，p=0.271）。
3. **reduced-F0 残差化无增量**（5/6 median ρ_resid ≤ 0）；仅支持"移除 reduced 线性 F0 proxy 后无稳健正向单调残差关联"。
4. 这是**描述性证据**，非形式化无预测力证明；F1 冻结候选集**保持不变**，不驱动特征增减或 RL 架构变化。

# 5. 边界与规避

```text
✓ Test-transition 隔离（475 执行日 → 475 决策日排除；invariant + val_end assert 通过）
✓ segment-aware 无替换块 permutation（不跨 gap）
✓ 预声明保守主尺度 block_len=60 + 20/40 敏感性
✓ per-fold nested descriptive CI（非独立措辞）
✓ reduced_F0_market_proxy 标签（10 预测子非完整 F0）
✓ 无 RL 重训 / 10-seed / Optuna / sweep / F2/F3 / RL_FORMAL_PREP / CORRECTED_F0_RL_3SEED
✗ 不因 Test 结果增删特征；不做 Test-informed 选择推荐
```

# 6. Pytest

```text
collected 198 items  →  198 passed（新增 4：contiguous_segments ×2、segment permutation 无跨 gap、
C1 transition invariant；旧 block_permutation_p 测试更新为 segment 版）
```

# 7. Git Commit

`GATE_4_FEATURE_ABLATION_RUNS_STAT_FINALIZATION_CORRECTIONS` 提交 SHA：**`4cc590f`**

```text
src/china_etf/evaluation/factor_importance.py     ← +contiguous_segments / segment_block_permutation_p；移除 block_permutation_p
scripts/gate4_feature_importance_stat_final_corrections.py  ← C1-C5 修正
tests/test_feature_importance.py                  ← +4 测试（段/permutation/invariant）
artifacts/gate4_feature_importance_stat_final_corrections.json ← 结果（tracked）
docs/review_packets/GATE_4_FEATURE_ABLATION_RUNS_STAT_FINALIZATION_CORRECTIONS.md  ← 本 packet
docs/agent_state/CLAUDE_STATUS.yaml               ← 协议状态
```

---

## Approval Record

```yaml
gate: 4
handoff_id: G4_FEATURE_ABLATION_RUNS_STAT_FINALIZATION_CORRECTIONS_001
packet: GATE_4_FEATURE_ABLATION_RUNS_STAT_FINALIZATION_CORRECTIONS
status: READY_FOR_REVIEW

closed:
  C1_transition_quarantine: true     # 475 exec -> 475 decision excluded; invariant + val_end assert
  C2_segment_block_permutation: true # in-segment non-overlapping block shuffle; |T| two-sided p
  C3_no_cross_gap_resampling: true   # contiguous_segments 4 segs [359,60,60,60]
  C4_nested_panel_ci_wording: true   # fold-specific nested descriptive CI, no independence claim
  C5_block_len_60_primary: true      # predeclared conservative scale; 20/40 sensitivity table

findings:
  no_f1_feature_significant: true    # Holm(60) >= 0.162, q(60) >= 0.162 all
  vol_ratio_not_robust: true         # test-free rho -0.062, p(60) 0.271, sign flip
  corr_pc1_nominal_only: true        # p(20/40) small but p(60)=0.027, Holm 0.162; rho negative
  reduced_proxy_no_incremental: true # 5/6 median resid rho <= 0

not_done:
  rl_retraining: false
  ten_seed_formal: false
  optuna_or_sweep: false
  f2_f3_real_macro: false
  test_informed_selection: false
  feature_set_change: false          # frozen F1 unchanged
  rl_formal_protocol_prep: false
  corrected_f0_rl_3seed: false
```

## END OF GATE 4 FEATURE ABLATION RUNS STAT FINALIZATION CORRECTIONS
