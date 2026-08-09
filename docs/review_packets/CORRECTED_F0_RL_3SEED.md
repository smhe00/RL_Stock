# CORRECTED F0 RL 3-SEED — 正式执行结果（36 runs，全部无 stop 违规）

> 评审（`CORRECTED_F0_RL_EXECUTION_PUBLICATION_SCHEMA_CLOSEOUT_REVIEWER_RESPONSE.md`）**APPROVED_FOR_CORRECTED_F0_RL_3SEED_EXECUTION**。
> 本 packet 报告 corrected F0 3-seed 正式执行结果。handoff_id = **CORRECTED_F0_RL_3SEED_001**。

---

# 1. 执行清单（冻结协议）

```text
observation: F0 dim 104 | algorithms: PPO/SAC/TD3 | seeds: 42/2026/7 | folds: F1-F4
nominal runs: 3×3×4 = 36 | train_passes: 20 | net: [256,256] | checkpoint: final endpoint
inputs: configs/rl_formal_protocol.yaml | path: run_fold_rl_config / shared constructor
Test mask: RESEARCH_BENCHMARK_TEST (475) | Test-informed selection: 未用（禁止）
并行：PPO(cpu) / SAC(gpu) / TD3(gpu) 3 进程
config_sha256: 46c56bc9a204…
```

# 2. 结果（从 tracked artifact 生成：artifacts/gate4_rl_formal_results.json + _raw.json）

## 2.1 per-algorithm（3-seed median，corrected 路径）

| 算法 | median 年化 | median Sharpe | median MaxDD | median Calmar | Sharpe≥1.64 seeds | GO/NO-GO |
|---|---:|---:|---:|---:|---:|---|
| **PPO** | 27.4% | 1.617 | -9.1% | 3.01 | 1/3 | **NO_GO** |
| **SAC** | 24.9% | 1.527 | -8.7% | 2.83 | 0/3 | **NO_GO** |
| **TD3** | 19.0% | 1.210 | -12.3% | 1.57 | 0/3 | **NO_GO** |

## 2.2 per-seed（完整 9 seed×algo）

```text
PPO: seed42 ret 0.277 sh 1.69 mdd -0.086 | seed2026 ret 0.274 sh 1.62 mdd -0.091 | seed7 ret 0.245 sh 1.57 mdd -0.091
SAC: seed42 ret 0.249 sh 1.53 mdd -0.088 | seed2026 ret 0.246 sh 1.55 mdd -0.087 | seed7 ret 0.250 sh 1.52 mdd -0.087
TD3: seed42 ret 0.222 sh 1.31 mdd -0.123 | seed2026 ret 0.150 sh 0.93 mdd -0.148 | seed7 ret 0.190 sh 1.21 mdd -0.121
```

## 2.3 GO/NO-GO + project level

```text
PPO NO_GO: median sharpe 1.617 < 1.64；median mdd -0.0910 < -0.0881；仅 1/3 seeds sharpe≥1.64（需 2）
SAC NO_GO: median ret 0.249 < 0.2687；median sharpe 1.527 < 1.64；0/3 seeds sharpe≥1.64
TD3 NO_GO: median ret 0.190 < 0.2687；median sharpe 1.210 < 1.64；median mdd -0.123 < -0.0881；0/3 seeds
project_level = NO_GO
Pareto vs MaxDiv: PPO/SAC/TD3 全部 dominated（sharpe/max_drawdown/calmar 三维均被 MaxDiv 主导）
```

## 2.4 Stop / invariant 状态

```text
stop_flags: {PPO: [], SAC: [], TD3: []}   # 36 runs 全无 NaN/neg-cash/save-load/non-finite
invariants: 全部通过（execution_dates==475、n_eval==475、cost 对账、fold 覆盖、36 runs）
config_sha256: 每 run == 顶层 == 46c56bc9a204
```

# 3. 关键观察（非结论）

1. **RL 未通过"超 EqualWeight 强基线"门槛**：PPO 最接近（median 年化 27.4% 超 26.9%，但 Sharpe 1.617 差 0.02、
   MaxDD 略差、仅 1/3 seeds 达标）；SAC/TD3 明确不达标。
2. **与 horse-race 结论一致**：多个优化器同样未稳超 EW（DeMiguel 论点再次验证）——估计误差侵蚀优化收益。
3. **三者均被 MaxDiv 风险前沿 Pareto 主导**：风险调整维度 RL 不占优。
4. **PPO 是相对最强 RL**：corrected 路径下 median 27.4%/1.62，但未达协议 GO 阈值。

# 4. 判定与后续

```text
project_level = NO_GO → 不进 CONDITIONAL_FORMAL_ROBUSTNESS 阶段（PROMISING 才授权）
PROMISING 不产生：不授权 10-seed / robustness / live / Optuna / 特征变更
RL 结果相对 benchmark hurdle 判定；不跨 algo 选 winner（无 Test-informed selection）
```

# 5. 边界与规避

```text
✓ 36 runs 全完成，无 stop/invariant 违规；finalize_publish 通过（published）
✓ 无 RL 重训 / 10-seed / Optuna / sweep / F2-F3 / Test-informed / 特征增减 / QMT / SOUTHBOUND
✓ 未改冻结协议/超参；并行仅编排（3 进程）
```

# 6. Git Commit

`CORRECTED_F0_RL_3SEED` 提交 SHA：**`de621a6`**

```text
scripts/gate4_rl_formal_3seed.py            ← 3-seed 执行 runner（并行 --algo / --aggregate）
artifacts/gate4_rl_formal_results.json      ← 结果（tracked）
artifacts/gate4_rl_formal_raw.json          ← 原始 series（tracked）
docs/review_packets/CORRECTED_F0_RL_3SEED.md  ← 本 packet
docs/agent_state/CLAUDE_STATUS.yaml          ← 协议状态
```

---

## Approval Record

```yaml
gate: 4
handoff_id: CORRECTED_F0_RL_3SEED_001
packet: CORRECTED_F0_RL_3SEED
status: READY_FOR_REVIEW

execution:
  runs_completed: 36/36
  stop_violations: 0
  invariants: pass
  config_sha256: 46c56bc9a204
  parallel: PPO(cpu) SAC/TD3(gpu)

results:
  PPO:  {median_ret: 0.274, median_sharpe: 1.617, median_mdd: -0.091, decision: NO_GO, seeds_pass: 1/3}
  SAC:  {median_ret: 0.249, median_sharpe: 1.527, median_mdd: -0.087, decision: NO_GO, seeds_pass: 0/3}
  TD3:  {median_ret: 0.190, median_sharpe: 1.210, median_mdd: -0.123, decision: NO_GO, seeds_pass: 0/3}
  project_level: NO_GO
  pareto_vs_maxdiv: all dominated

not_authorized_by_this_result:
  conditional_robustness_execution: false   # NO_GO；PROMISING 才考虑
  ten_seed_formal: false
  optuna_or_sweep: false
  qmt_live: false
  feature_change: false
```

## END OF CORRECTED F0 RL 3-SEED
