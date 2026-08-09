# CORRECTED F0 RL EXECUTION PUBLICATION SCHEMA CLOSEOUT — canonical schema 桥接（S1-S3，无训练）

> 评审（`CORRECTED_F0_RL_EXECUTION_PUBLICATION_BINDING_REVIEWER_RESPONSE.md`）**TARGETED_CANONICAL_SCHEMA_BRIDGE_REQUIRED**
> （S1-S3），`authorized_next: CORRECTED_F0_RL_EXECUTION_PUBLICATION_SCHEMA_CLOSEOUT`。schema 桥接修正，**无训练**。
> handoff_id = **CORRECTED_F0_RL_EXECUTION_PUBLICATION_SCHEMA_CLOSEOUT_001**。

---

# 1. 修正内容（S1-S3）

```text
S1 schema 统一：aggregate_raw_results 输出 pivot 为 algo-centric
   {algo: {seed_keys, active_day_annualized_return: {seed}, sharpe: {seed}, max_drawdown: {seed},
           calmar_median, stop_violations, per_seed}}
   匹配 evaluate_go_nogo 契约 → GO/NO-GO 实际消费 canonical 指标（不再看到空 maps）。
S2 正收益端到端：构造正收益 raw returns（finite variance、非零 drawdown、清空 EW hurdle）→
   raw → validate → aggregate → evaluate → finalize_publish → GO + project PROMISING。
S3 stop-flip 端到端：同正收益 + save_load False → 该 algo NO_GO（raw-derived stop 翻转 GO→NO_GO）。
```

# 2. 关键实现（src/china_etf/evaluation/rl_formal.py）

```text
aggregate_raw_results(results, cfg, mask_dates) -> algo-centric canonical（S1）
  - 每 (algo,seed)：有序 F1→F4 net_returns 重算 active_ann/sharpe/max_drawdown/calmar
  - calmar_median = median(seed calmars)（Pareto 可用）
  - stop_violations = sum(seed 派生)（evaluator 读取）
  - per_seed 审计细节
finalize_publish: config sha 一致性 → validate_invariants → aggregate（algo-centric）→
  caller 对比（algo-centric schema，mismatch fail-closed）→ evaluate_go_nogo(canonical)
```

# 3. 端到端验证（synthetic raw returns，无训练）

```text
pytest: collected 246 → 246 passed
  - S2: 正收益 raw → finalize_publish → ≥1 algo GO + project PROMISING（proves canonical consumption）
  - S3: 同正收益 + save_load False → 该 algo NO_GO（raw-derived stop 翻转）
  - S1: evaluator 收到 canonical 指标 == 从 raw F1→F4 重算值（数值一致）
  - 保留 P1-P3 / F1-F6 / E1-E4 / H1-H7 测试
runner --publish-synthetic: published=True config_sha256=46c56bc9a204 project_level=NO_GO
  （真实 475 mask，canonical 聚合；synthetic，no training）
runner --dry-run: 共享 _construct_model，无 learn
```

# 4. 边界与规避

```text
✓ schema closeout only：synthetic/dry-run 无 learn / 无训练
✓ 未改冻结阈值/算法/seeds/特征/预算/Test 选择规则
✓ caller summary 永不权威（mismatch fail-closed）
✓ 不跑 corrected 3-seed（CORRECTED_F0_RL_3SEED 未来独立执行门）
✓ 不 10-seed / Optuna / sweep / F2-F3 / Test-informed / 特征增减 / QMT / SOUTHBOUND
```

# 5. Git Commit

`CORRECTED_F0_RL_EXECUTION_PUBLICATION_SCHEMA_CLOSEOUT` 提交 SHA：**`PENDING_SHA`**

```text
src/china_etf/evaluation/rl_formal.py          ← S1（aggregate pivot algo-centric + caller 对比）
tests/test_rl_formal_protocol.py               ← S2/S3 端到端 + 数值一致
docs/review_packets/CORRECTED_F0_RL_EXECUTION_PUBLICATION_SCHEMA_CLOSEOUT.md  ← 本 packet
docs/agent_state/CLAUDE_STATUS.yaml            ← 协议状态
```

---

## Approval Record

```yaml
gate: 4
handoff_id: CORRECTED_F0_RL_EXECUTION_PUBLICATION_SCHEMA_CLOSEOUT_001
packet: CORRECTED_F0_RL_EXECUTION_PUBLICATION_SCHEMA_CLOSEOUT
status: READY_FOR_REVIEW

closed:
  S1_canonical_schema_bridge: true    # aggregate algo-centric == evaluate_go_nogo contract
  S2_positive_raw_to_go_e2e: true     # positive returns -> GO + PROMISING through full chain
  S3_stop_flip_e2e: true              # save_load False flips GO -> NO_GO

binding_proof:
  publish_synthetic: {published: true, config_sha256: 46c56bc9a204, project_level: NO_GO, real_mask: true}
  pytest_246: true
  dry_run_no_learn: true
  frozen_contract_unchanged: true     # thresholds/algorithms/seeds/features/budget unchanged

not_done:
  rl_training: false
  corrected_f0_rl_3seed: false        # future execution gate; NOT authorized
  ten_seed_execution: false
  optuna_or_sweep: false
  f2_f3_real_macro: false
  test_informed_selection: false
  feature_set_change: false
```

## END OF CORRECTED F0 RL EXECUTION PUBLICATION SCHEMA CLOSEOUT
