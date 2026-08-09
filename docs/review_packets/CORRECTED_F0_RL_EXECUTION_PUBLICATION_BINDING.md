# CORRECTED F0 RL EXECUTION PUBLICATION BINDING — canonical 聚合绑定（P1-P3，无训练）

> 评审（`CORRECTED_F0_RL_EXECUTION_HARNESS_FINALIZATION_REVIEWER_RESPONSE.md`）**TARGETED_PUBLICATION_METRIC_BINDING_REQUIRED**
> （P1-P3），`authorized_next: CORRECTED_F0_RL_EXECUTION_PUBLICATION_BINDING`。publication-integrity closeout，**无训练**。
> handoff_id = **CORRECTED_F0_RL_EXECUTION_PUBLICATION_BINDING_001**。

---

# 1. 修正内容（P1-P3）

```text
P1 canonical 聚合：aggregate_raw_results 从 validated raw results 重算每 (algo,seed) 有序 F1→F4
   stitched active_day_annualized_return / sharpe / max_drawdown / calmar；GO/NO-GO 只信任 canonical；
   caller_stitched 仅诊断对比，mismatch → fail-closed（永不权威）。
P2 stop violations 派生：从 run 记录（save_load_deterministic_identical / nan_obs_or_reward /
   negative_cash_count / 非 finite net_returns）派生；字段缺失 → fail-closed。
P3 synthetic 用真实 folds + exact_test_mask（475，[118,118,118,121]），非 arbitrary bdate。
```

# 2. 关键实现（src/china_etf/evaluation/rl_formal.py）

```text
aggregate_raw_results(results, cfg, mask_dates) -> {algo: {seed: {active_day_annualized_return,
   sharpe, max_drawdown, calmar, stop_violations, n_seeds}}}
  - 有序 F1→F4 拼接 net_returns（len==475 断言）
  - active_ann = (1+prod(1+nr))**(252/475)-1；sharpe = mean/std*sqrt(252)；mdd = min(eq/cummax-1)；calmar
  - stop_violations 从 run 字段派生；save_load/nan/neg_cash 字段缺失 → InvariantViolation（fail-closed）
finalize_publish(results, config_envelope, mask_dates, caller_stitched=None)
  - config sha 一致性 → validate_runtime_invariants → aggregate_raw_results(canonical)
  - caller_stitched 逐字段对比（active_ann/sharpe/mdd per (algo,seed) atol），mismatch → raise
  - evaluate_go_nogo(canonical) → {config_sha256, go_nogo, canonical_stitched, results, published}
```

# 3. 验证（真实 mask synthetic + 测试，无训练）

```text
pytest: collected 243 → 243 passed
  - P1: 零 raw + 矛盾 caller（正 return）→ fail-closed（不 publish 为正 GO）
  - P1b: caller 与 canonical 一致 → publish 通过
  - P2: raw run save_load False → 派生 stop_violations>0 → 该 algo NO_GO；字段缺失 → fail-closed
  - P3: 真实 mask 长度 475 + canonical stitched len==475
runner --publish-synthetic: published=True config_sha256=46c56bc9a204 project_level=NO_GO
  （真实 mask，canonical 聚合，无 caller summary；synthetic，no training）
runner --dry-run: 共享 _construct_model，无 learn
```

# 4. 边界与规避

```text
✓ publication binding only：synthetic/dry-run 无 learn / 无训练
✓ caller summary 永不权威（仅诊断对比，mismatch fail-closed）
✓ 不跑 corrected 3-seed（CORRECTED_F0_RL_3SEED 未来独立执行门）
✓ 不 10-seed / Optuna / sweep / F2-F3 / Test-informed / 特征增减 / QMT / SOUTHBOUND
```

# 5. Git Commit

`CORRECTED_F0_RL_EXECUTION_PUBLICATION_BINDING` 提交 SHA：**`PENDING_SHA`**

```text
src/china_etf/evaluation/rl_formal.py          ← P1/P2（aggregate_raw_results + finalize_publish 绑定）
scripts/gate4_rl_formal_runner.py              ← P3（真实 mask synthetic）
tests/test_rl_formal_protocol.py               ← P1/P2/P3 测试
docs/review_packets/CORRECTED_F0_RL_EXECUTION_PUBLICATION_BINDING.md  ← 本 packet
docs/agent_state/CLAUDE_STATUS.yaml            ← 协议状态
```

---

## Approval Record

```yaml
gate: 4
handoff_id: CORRECTED_F0_RL_EXECUTION_PUBLICATION_BINDING_001
packet: CORRECTED_F0_RL_EXECUTION_PUBLICATION_BINDING
status: READY_FOR_REVIEW

closed:
  P1_canonical_stitched_aggregation: true   # raw results -> stitched metrics; caller mismatch fails closed
  P2_stop_conditions_derived_from_run: true # save_load/nan/neg_cash/non-finite; missing evidence fails closed
  P3_real_canonical_test_mask: true         # real folds + exact_test_mask [118,118,118,121] -> 475

binding_proof:
  publish_synthetic: {published: true, config_sha256: 46c56bc9a204, project_level: NO_GO, real_mask: true}
  pytest_243: true
  dry_run_no_learn: true

not_done:
  rl_training: false
  corrected_f0_rl_3seed: false           # future execution gate; NOT authorized
  ten_seed_execution: false
  optuna_or_sweep: false
  f2_f3_real_macro: false
  test_informed_selection: false
  feature_set_change: false
```

## END OF CORRECTED F0 RL EXECUTION PUBLICATION BINDING
