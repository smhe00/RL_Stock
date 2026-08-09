# CORRECTED F0 RL EXECUTION HARNESS FINALIZATION — 最终 fail-closed 修正（F1-F6，无训练）

> 评审（`CORRECTED_F0_RL_EXECUTION_PREP_CORRECTIONS_REVIEWER_RESPONSE.md`）**TARGETED_HARNESS_FINALIZATION_REQUIRED**
> （F1-F6），`authorized_next: CORRECTED_F0_RL_EXECUTION_HARNESS_FINALIZATION`。最终 prep/closeout，narrow fail-closed，**无训练**。
> handoff_id = **CORRECTED_F0_RL_EXECUTION_HARNESS_FINALIZATION_001**。

---

# 1. 修正内容（F1-F6）

```text
F1 algo_name/algo_cls 匹配校验：_construct_model 开头不匹配 → FormalConfigError（构造/训练前）
F2 缺失 n_eval_steps 即 fail-closed（不再 if is not None 跳过）
F3 raw_series_complete 扩展：execution_dates/net_returns/costs/cash 长度 == fold_len；
   actual_weights/raw_weights/post_risk_weights 每行宽度 == 11（action_dim）；缺失 → fail
F4 GO/NO-GO：每 metric map（active_day_annualized_return/sharpe/max_drawdown）keys == 精确 cfg.seeds；
   每 seed 三指标 finite；缺 seed → INCOMPLETE/NO_GO；project_level 仅当算法集 == config 才输出，缺 algo → INCOMPLETE
F5 Pareto：全部冻结维度（Sharpe/MaxDD/Calmar）finite 才做 dominance；否则 UNAVAILABLE/INCOMPLETE
F6 finalize_publish：顶层 config_sha256 == 每 run sha == 当前 frozen digest（mismatch → 不 publish）；
   validate_runtime_invariants 先行 → 仅通过后 evaluate_go_nogo → 返回 publish-ready payload
```

# 2. 验证（pytest + synthetic publication，无训练）

```text
pytest: collected 238 → 238 passed
  - F1: algo_name/class 不匹配 → FormalConfigError
  - F2: n_eval_steps 缺失 → invariant 失败
  - F3: weight row width != 11 → fail；raw 缺失 → fail
  - F4: metric map 缺 seed key → NO_GO/INCOMPLETE；project 缺 algo → INCOMPLETE
  - F5: Calmar NaN → Pareto UNAVAILABLE/INCOMPLETE
  - F6: run sha != top → 不 publish；invariants+hash 通过 → published payload
runner --publish-synthetic: published=True config_sha256=46c56bc9a204 project_level=NO_GO
  （synthetic no-training 结果走 finalize_publish：hash 一致 + invariants + GO/NO-GO）
runner --dry-run: PPO/SAC/TD3 match（共享 _construct_model，无 learn）
```

# 3. 边界与规避

```text
✓ harness finalization only：dry-run/synthetic 无 learn / 无训练
✓ 不跑 corrected 3-seed（CORRECTED_F0_RL_3SEED 未来独立执行门，本评审不授权）
✓ 不 10-seed / Optuna / sweep / F2-F3 / Test-informed / 特征增减 / QMT / SOUTHBOUND
✓ 无 Test-based algorithm ranking
```

# 4. Git Commit

`CORRECTED_F0_RL_EXECUTION_HARNESS_FINALIZATION` 提交 SHA：**`PENDING_SHA`**

```text
src/china_etf/evaluation/rl_formal.py          ← F1-F6（algo 匹配、n_eval、raw 完整性、metric seed、Pareto finite、finalize_publish）
scripts/gate4_rl_formal_runner.py              ← --publish-synthetic（F6 dry-run）
tests/test_rl_formal_protocol.py               ← F1-F6 测试
docs/review_packets/CORRECTED_F0_RL_EXECUTION_HARNESS_FINALIZATION.md  ← 本 packet
docs/agent_state/CLAUDE_STATUS.yaml            ← 协议状态
```

---

## Approval Record

```yaml
gate: 4
handoff_id: CORRECTED_F0_RL_EXECUTION_HARNESS_FINALIZATION_001
packet: CORRECTED_F0_RL_EXECUTION_HARNESS_FINALIZATION
status: READY_FOR_REVIEW

closed:
  F1_algo_name_class_mismatch_rejected: true   # FormalConfigError before construction
  F2_missing_n_eval_steps_fail_closed: true
  F3_raw_series_length_and_weight_shape: true  # 7 arrays + width 11
  F4_metric_seed_keys_and_project_completeness: true  # exact seeds + all algos for project status
  F5_pareto_requires_all_finite: true          # else UNAVAILABLE/INCOMPLETE
  F6_artifact_config_provenance_and_publication_order: true  # sha consistency -> invariants -> go_nogo -> publish

publication_proof:
  publish_synthetic: {published: true, config_sha256: 46c56bc9a204, project_level: NO_GO}
  pytest_238: true
  dry_run_no_learn: true

not_done:
  rl_training: false
  corrected_f0_rl_3seed: false           # future execution gate; NOT authorized by this review
  ten_seed_execution: false
  optuna_or_sweep: false
  f2_f3_real_macro: false
  test_informed_selection: false
  feature_set_change: false
```

## END OF CORRECTED F0 RL EXECUTION HARNESS FINALIZATION
