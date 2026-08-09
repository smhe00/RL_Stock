# GATE 4 FEATURE ABLATION — DIAGNOSTIC CLOSEOUT（退役确认性推断，仅描述性，D1-D3）

> 评审（`GATE_4_FEATURE_ABLATION_RUNS_STAT_FINALIZATION_CORRECTIONS_REVIEWER_RESPONSE.md`）**TARGETED_RESAMPLING_CLOSEOUT_REQUIRED**
> （D1-D3），`authorized_next: GATE_4_FEATURE_ABLATION_DIAGNOSTIC_CLOSEOUT`。按评审 preferred 收尾路径：
> **退役确认性 p/Holm/BH 与 bootstrap CI 主张，保留 transition-quarantined 描述性证据**。
> handoff_id = **G4_FEATURE_ABLATION_DIAGNOSTIC_CLOSEOUT_001**。

---

# 1. 修正内容（D1-D3）

```text
D1 block_len=60 permutation 在 [359,60,60,60] 段退化（60 日段=单块，洗牌恒等）→ 退役确认性 p/Holm/BH
   （不换小 block_len 取便利 p）
D2 fold bootstrap CI 在 compact array 跨 quarantined gap → 移除 bootstrap CI 证据
D3 结论收窄为描述性 negative evidence
```

本 closeout **仅保留描述性统计**：transition-quarantined 面板上的 point estimates / per-segment summaries /
reduced-F0-proxy cross-fit 残差。**无 p / Holm / BH / bootstrap CI**（`inferential_claims_retired=true`）。

# 2. 方法（transition-quarantined，仅描述性，无 RL/无策略）

```text
C1 隔离保留：exact_test_mask 475 执行日 → decision_dates 决策日排除；transition invariant + val_end assert 通过
outcome = 市场等权前向收益（11 槽位复权 log 收益 t→t+1）；screening = 539 天（无任何 Test transition）
每特征：spearman(f,|fwd|) / spearman(f,fwd) 点估计 + tercile |fwd| 均值 + gap（描述性）
       + per-segment spearman（contiguous_segments [359,60,60,60]，展示段内稳定性）
残差化：reduced_F0_market_proxy fold-local cross-fit（train fit → val apply，transition-excluded）
naive Mann-Whitney p 仅标注 EXPLORATORY（非确认性）
```

# 3. 描述性结果（从 tracked artifact 生成：artifacts/gate4_feature_importance_diagnostic_closeout.json）

## 3.1 F1 特征描述性摘要（539 transition-quarantined 决策日）

| 特征 | ρ_\|ret\| | ρ_ret | gap(low−high) | per-seg ρ_\|ret\| (min/max) |
|---|---:|---:|---:|---|
| corr_pc1_share_60 | -0.097 | +0.078 | +0.0008 | -0.448 / -0.108 |
| equity_bond_corr_change_20_60 | +0.015 | -0.024 | -0.0004 | -0.044 / +0.153 |
| equity_gold_corr_change_20_60 | -0.040 | -0.017 | +0.0002 | -0.220 / +0.042 |
| cn_us_corr_60 | 0.000 | +0.085 | +0.0000 | -0.305 / +0.000 |
| equity_vol_ratio_20_60 | -0.062 | -0.008 | +0.0004 | -0.112 / +0.109 |
| equity_downside_semivol_60 | +0.056 | +0.075 | -0.0007 | -0.052 / +0.060 |

**无任何特征展示大而稳的单调关联**：全部 ρ_\|ret\| ≤ |0.10|，per-segment ρ 符号跨段不稳定。

## 3.2 vol_ratio 未以同号复现

- Test-free ρ_\|ret\| = **-0.062**（先前的 475-Test +0.187 未复现，符号反）。

## 3.3 per-segment summaries（[359,60,60,60]，描述性）

- corr_pc1_share_60 是唯一全段同号（负，-0.448~-0.108）的特征，但 ρ 弱且为反向关联；
  其余特征 per-segment 符号跨段翻转 → 无稳定信号。

## 3.4 reduced-F0-proxy fold-local cross-fit 残差化（描述性 point ρ）

| 特征 | min ρ_resid | median ρ_resid |
|---|---:|---:|
| corr_pc1_share_60 | -0.144 | -0.109 |
| equity_bond_corr_change_20_60 | -0.084 | +0.090 |
| equity_gold_corr_change_20_60 | -0.251 | -0.080 |
| cn_us_corr_60 | -0.313 | -0.116 |
| equity_vol_ratio_20_60 | -0.296 | -0.019 |
| equity_downside_semivol_60 | -0.259 | -0.164 |

**5/6 median ρ_resid ≤ 0**（bond_corr 仅 +0.090）——移除 reduced 线性 F0 proxy 后无稳健正向单调残差关联（描述性）。

# 4. 结论（评审 §D3 措辞，描述性 negative evidence）

> On the transition-quarantined development data, none of the six frozen F1 features shows a large,
> stable monotonic association with next-day market absolute return; the previously observed Test
> vol-ratio association does not reproduce with the same sign.

这**不授权**删除 F1 特征或改变 RL 观察/网络；冻结 F1 候选集**保持不变**。先前的 475-Test 关联保持 exploratory。

# 5. 边界与规避

```text
✓ C1 transition 隔离保留（475 执行日 → 决策日排除；invariant + val_end assert）
✓ 确认性推断退役（无 p/Holm/BH/bootstrap CI；inferential_claims_retired=true）
✓ 仅描述性 point estimates / per-segment summaries / cross-fit 残差
✓ reduced_F0_market_proxy 标签（10 预测子非完整 F0）
✓ 无 RL 重训 / 10-seed / Optuna / sweep / F2/F3 / Test-informed / RL_FORMAL_PREP / CORRECTED_F0_RL_3SEED
✗ 不因 Test 结果增删特征；不做 Test-informed 选择推荐
```

# 6. Pytest

```text
collected 200 items  →  200 passed（新增 2：segment-shuffle 退化测试——单块段恒等、多块段置换值集不变；
C1 invariant / segments 测试保留）
```

# 7. Git Commit

`GATE_4_FEATURE_ABLATION_DIAGNOSTIC_CLOSEOUT` 提交 SHA：**`cad0d4b`**

```text
scripts/gate4_feature_importance_diagnostic_closeout.py  ← 描述性 closeout（无 inferential 统计）
tests/test_feature_importance.py                          ← +2 退化测试
artifacts/gate4_feature_importance_diagnostic_closeout.json ← 结果（tracked）
docs/review_packets/GATE_4_FEATURE_ABLATION_DIAGNOSTIC_CLOSEOUT.md  ← 本 packet
docs/agent_state/CLAUDE_STATUS.yaml                       ← 协议状态
```

---

## Approval Record

```yaml
gate: 4
handoff_id: G4_FEATURE_ABLATION_DIAGNOSTIC_CLOSEOUT_001
packet: GATE_4_FEATURE_ABLATION_DIAGNOSTIC_CLOSEOUT
status: READY_FOR_REVIEW

closed:
  D1_confirmatory_inference_retired: true  # no p/Holm/BH (block permutation degenerate on 60-day segs)
  D2_bootstrap_ci_removed: true            # descriptive point estimates only
  D3_conclusion_narrowed: true             # descriptive negative evidence wording

method:
  descriptive_only: true
  transition_quarantine_kept: true         # 475 exec -> decision excluded; invariant + val_end assert
  inferential_claims_retired: true

findings:
  no_large_stable_monotonic_f1: true       # all |rho_abs| <= 0.10; per-segment signs unstable
  vol_ratio_test_signal_not_reproduced: true  # test-free rho -0.062 (sign flip)
  reduced_proxy_no_incremental: true       # 5/6 median resid rho <= 0 (descriptive)

not_done:
  rl_retraining: false
  ten_seed_formal: false
  optuna_or_sweep: false
  f2_f3_real_macro: false
  test_informed_selection: false
  feature_set_change: false                # frozen F1 unchanged
  rl_formal_protocol_prep: false
  corrected_f0_rl_3seed: false
```

## END OF GATE 4 FEATURE ABLATION DIAGNOSTIC CLOSEOUT
