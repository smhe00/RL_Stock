# RL FORMAL PROTOCOL PREP — CORRECTIONS（P1-P9 协议/配置/测试修正）

> 评审（`RL_FORMAL_PROTOCOL_PREP_REVIEWER_RESPONSE.md`）**TARGETED_PROTOCOL_CORRECTIONS_REQUIRED**（P1-P9），
> `authorized_next: RL_FORMAL_PROTOCOL_PREP_CORRECTIONS`。纯协议/配置/测试修正，**无 RL 训练**。
> handoff_id = **RL_FORMAL_PROTOCOL_PREP_CORRECTIONS_001**。

---

# 1. 修正内容（P1-P9）

```text
P1 F0 rationale → 既有冻结基线契约（不消费描述性 F1 诊断；F1 保留 Gen-2 候选集）
P2 3-seed = CORRECTED_F0_RL_3SEED / research-benchmark GO-NO-GO；10-seed conditional/未授权（不删除）
P3 475 日 = RESEARCH_BENCHMARK_TEST（已反复观测）；GO = 值得进一步验证；预留 FUTURE_FINAL_FORWARD_HOLDOUT
P4 两层 benchmark：PRIMARY=EqualWeight（回报）；FRONTIER=MaxDiv（风险调整，Sharpe 2.77/MaxDD -3.4%/Calmar 5.38）；
   Pareto 报告；MaxDD hurdle 纳入 GO guardrail
P5 GO/NO-GO 分算法 + 项目级两阶段；禁 Test-based algo winner selection
P6 checkpoint = final_training_endpoint_only（无 search）
P7 有效 SB3 超参/软件/device 冻结于 configs/rl_formal_protocol.yaml（机器可读，runner/tests 消费）
P8 评估器不变量硬 stop：execution_dates==475、n_eval_steps==475、cost reconciliation、完整 fold/raw series
P9 metric 命名统一 active_day_annualized_return（stitched 含 val gaps，RL/非 RL 同定义）
```

# 2. 机器可读冻结配置（P7，canonical：configs/rl_formal_protocol.yaml）

```yaml
meta: {gate: RL_FORMAL_PROTOCOL_PREP_CORRECTIONS, observation: F0, observation_dim: 104,
       n_folds: 4, test_mask_label: RESEARCH_BENCHMARK_TEST, test_mask_count: 475,
       forward_holdout: FUTURE_FINAL_FORWARD_HOLDOUT}
seeds: [42, 2026, 7]
train_passes: 20
net_arch: [256, 256]
checkpoint_policy: final_training_endpoint_only
device: {PPO: cpu, SAC: cuda, TD3: cuda}
versions: {sb3: 2.8.0, torch: 2.7.1+cu118, gymnasium: 1.2.3, pandas: 3.0.5, numpy: 2.5.1}
algorithms:
  PPO: {learning_rate: 0.0003, n_steps: 2048, batch_size: 64, n_epochs: 10, gamma: 0.99,
        gae_lambda: 0.95, clip_range: 0.2, ent_coef: 0.0, vf_coef: 0.5, max_grad_norm: 0.5}
  SAC: {learning_rate: 0.0003, buffer_size: 1000000, learning_starts: 100, batch_size: 256,
        tau: 0.005, gamma: 0.99, train_freq: 1, gradient_steps: 1, ent_coef: auto, target_update_interval: 1}
  TD3: {learning_rate: 0.001, buffer_size: 1000000, learning_starts: 100, batch_size: 256,
        tau: 0.005, gamma: 0.99, train_freq: 1, gradient_steps: 1, policy_delay: 2,
        target_policy_noise: 0.2, target_noise_clip: 0.5}
benchmark:
  primary_return_hurdle: {name: EqualWeight, active_day_annualized_return: 0.2687, sharpe: 1.64, max_drawdown: -0.0881}
  risk_adjusted_frontier: {name: MaximumDiversification, active_day_annualized_return: 0.1832,
                           sharpe: 2.77, max_drawdown: -0.0340, calmar: 5.38}
hard_stop_invariants: [execution_dates_equal_475_mask, n_eval_steps_equal_475,
                       cost_reconciliation_pass, all_folds_present_no_duplicates, raw_series_complete]
```

# 3. 协议可执行性验证（scripts/gate4_rl_formal_protocol_check.py，读 config，无训练）

```text
config gate = RL_FORMAL_PROTOCOL_PREP_CORRECTIONS  observation=F0 obs_dim=104
exact_test_mask = 475  [2023-11-24 .. 2026-08-07]  label=RESEARCH_BENCHMARK_TEST
fold train/val/test：F1 300/60/118、F2 478/60/118、F3 656/60/118、F4 834/60/121
benchmark EW(primary) match=True；MaxDiv(frontier) match=True
hyperparams match SB3: {PPO: True, SAC: True, TD3: True}
hard_stop_invariants: 5  checkpoint=final_training_endpoint_only
rl_training_executed = False
```

# 4. Pytest

```text
collected 215 items  →  215 passed（test_rl_formal_protocol.py 15 个：config 冻结值、475 mask、
两层 benchmark、P7 超参匹配 SB3、P8 invariants、P5 完整 GO 规则、P9 命名）
```

# 5. 边界与规避

```text
✓ 协议/配置/测试修正 only：不训练/重训 RL；不跑 corrected 3-seed（未来独立执行门）
✓ 10-seed conditional/未授权保留；不 Optuna/sweep/F2-F3/Test-informed/特征增减
✓ F0 因既有冻结基线保留（P1）；F1 保留 Gen-2 候选集
```

# 6. Git Commit

`RL_FORMAL_PROTOCOL_PREP_CORRECTIONS` 提交 SHA：**`PENDING_SHA`**

```text
configs/rl_formal_protocol.yaml                    ← P7 机器可读冻结配置（canonical）
docs/features/RL_FORMAL_PROTOCOL.md                ← P1-P6/P9 修正
scripts/gate4_rl_formal_protocol_check.py          ← 读 config 验证
tests/test_rl_formal_protocol.py                   ← 15 契约测试
docs/review_packets/RL_FORMAL_PROTOCOL_PREP_CORRECTIONS.md  ← 本 packet
docs/agent_state/CLAUDE_STATUS.yaml                ← 协议状态
```

---

## Approval Record

```yaml
gate: 4
handoff_id: RL_FORMAL_PROTOCOL_PREP_CORRECTIONS_001
packet: RL_FORMAL_PROTOCOL_PREP_CORRECTIONS
status: READY_FOR_REVIEW

closed:
  P1_f0_rationale_baseline_contract: true
  P2_3seed_corrected_benchmark_10seed_conditional: true
  P3_research_benchmark_test_forward_holdout: true
  P4_two_tier_benchmark: true          # EW primary + MaxDiv frontier; Pareto reporting; MaxDD in GO
  P5_per_algo_project_go_nogo: true    # no Test-based winner selection
  P6_final_endpoint_checkpoint: true
  P7_machine_readable_config: true     # configs/rl_formal_protocol.yaml; hyperparams match SB3
  P8_hard_stop_invariants: true        # 5 invariants
  P9_active_day_annualized_return: true

verified:
  protocol_check_reads_config: true
  hyperparams_match_sb3: {PPO: true, SAC: true, TD3: true}
  pytest_215: true
  rl_training_executed: false

not_done:
  rl_training: false
  corrected_f0_rl_3seed: false         # future execution gate
  ten_seed_execution: false            # conditional / not authorized
  optuna_or_sweep: false
  f2_f3_real_macro: false
  test_informed_selection: false
  feature_set_change: false
```

## END OF RL FORMAL PROTOCOL PREP CORRECTIONS
