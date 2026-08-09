# CORRECTED F0 RL EXECUTION PREP — CORRECTIONS（H1-H7 harness 质量修正）

> 评审（`CORRECTED_F0_RL_EXECUTION_PREP_REVIEWER_RESPONSE.md`）**TARGETED_EXECUTION_HARNESS_CORRECTIONS_REQUIRED**
> （H1-H7），`authorized_next: CORRECTED_F0_RL_EXECUTION_PREP_CORRECTIONS`。harness 实现级修正，无训练。
> handoff_id = **CORRECTED_F0_RL_EXECUTION_PREP_CORRECTIONS_001**。

---

# 1. 修正内容（H1-H7）

```text
H1 共享构造路径：_construct_model 为单一 runtime 构造函数（显式 config 超参 + net + device + seed）；
   run_fold_rl_config 与 dry-run spy 都调用它（不再手动复制构造）。
H2 config_sha256 = 真 64-hex digest（load_protocol_config）；run 记录 digest（非 path）；测试断言 64-hex。
H3 fold 级 mask invariant：每 fold 校验 execution_dates == 该 fold 段（长度 118/118/118/121）；
   stitched 级：F1→F4 有序拼接 == 475 ordered mask；n_eval == fold 长度（fold 级）/ 475（stitched 级）。
H4 cost reconciliation auditable：sum(series.costs) == test.total_cost；证据缺失（costs/total_cost 缺）→ fail-closed。
H5 raw 完整性 + 精确身份：expected = algorithms × seeds × F1-F4（config 派生），无缺无多；
   每 fold 校验 execution_dates/net_returns/cash/actual_weights 长度兼容。
H6 GO/NO-GO seed 完整性：精确 seed 集 == cfg.seeds；全部决策指标 finite；≥2/3 阈值从 config 派生；
   不完整 → NO_GO/INCOMPLETE。
H7 真 Pareto dominance：RL 被 MaxDiv 主导 ⟺ RL 全部目标 ≤ MaxDiv 且至少一严格 <（高好方向）；
   混合（一维更优一维更差）→ not_dominated + underperforms_maxdiv_dimensions 报告每维。
```

# 2. 验证（真实 fold 长度 + 共享路径）

```text
pytest: collected 229 → 229 passed
  - H1: shared _construct_model spy 收到冻结超参 + net [256,256] + seed
  - H2: config_sha256 64-hex 确定性
  - H3: 真实 fold 长度 [118,118,118,121] pass；fold 长度错 fail；stitched 475 ordered mask
  - H4: cost 证据缺失 fail；sum(costs)==total_cost pass
  - H5: raw 缺失 fail；身份不匹配 fail
  - H6: seed 集不完整 → NO_GO/INCOMPLETE
  - H7: 混合 → not_dominated + underperforms_dims；全维更差 → dominated
runner --dry-run: 经共享 _construct_model → PPO/SAC/TD3 match=True（no learn，不训练）
config_sha256 = 46c56bc9a204…
```

# 3. 边界与规避

```text
✓ harness 质量修正 only：dry-run 构造 spy（无 learn / 无训练）
✓ 不跑 corrected 3-seed（CORRECTED_F0_RL_3SEED 未来独立执行门）
✓ 不 10-seed / Optuna / sweep / F2-F3 / Test-informed / 特征增减 / QMT / SOUTHBOUND
✓ 无 Test-based algorithm ranking
```

# 4. Git Commit

`CORRECTED_F0_RL_EXECUTION_PREP_CORRECTIONS` 提交 SHA：**`b17fe19`**

```text
src/china_etf/evaluation/rl_formal.py          ← H1-H7（共享构造、hash、fold/stitched mask、cost evidence、身份、seed、Pareto）
scripts/gate4_rl_formal_runner.py              ← dry-run 经共享 _construct_model
tests/test_rl_formal_protocol.py               ← H1-H7 测试
docs/review_packets/CORRECTED_F0_RL_EXECUTION_PREP_CORRECTIONS.md  ← 本 packet
docs/agent_state/CLAUDE_STATUS.yaml            ← 协议状态
```

---

## Approval Record

```yaml
gate: 4
handoff_id: CORRECTED_F0_RL_EXECUTION_PREP_CORRECTIONS_001
packet: CORRECTED_F0_RL_EXECUTION_PREP_CORRECTIONS
status: READY_FOR_REVIEW

closed:
  H1_shared_constructor_path: true      # _construct_model shared by run + dry-run spy
  H2_config_sha256_true_digest: true    # 64-hex; run + artifact consistent
  H3_fold_segment_and_stitched_mask: true  # [118,118,118,121] per fold; ordered 475 stitched
  H4_cost_reconciliation_evidence: true  # sum(costs)==total_cost; missing evidence fails closed
  H5_exact_identity_and_raw_completeness: true  # config-derived algos x seeds x F1-F4; raw lengths
  H6_seed_set_fail_closed: true          # exact seeds + finite + 2/3 from config; INCOMPLETE->NO_GO
  H7_true_pareto_dominance: true         # le_all + strict_lt_any; underperforms_dims report

binding_proof:
  dry_run_shared_path: {PPO: true, SAC: true, TD3: true}
  config_sha256: 46c56bc9a204
  pytest_229: true
  no_learn_called: true

not_done:
  rl_training: false
  corrected_f0_rl_3seed: false           # future execution gate
  ten_seed_execution: false
  optuna_or_sweep: false
  f2_f3_real_macro: false
  test_informed_selection: false
  feature_set_change: false
```

## END OF CORRECTED F0 RL EXECUTION PREP CORRECTIONS
