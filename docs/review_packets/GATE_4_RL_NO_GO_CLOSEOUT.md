# GATE 4 RL NO-GO CLOSEOUT — 决策收尾（文档 only）

> 评审（`CORRECTED_F0_RL_3SEED_REVIEWER_RESPONSE.md`）**FORMAL_NO_GO_ACCEPTED_RL_ROBUSTNESS_NOT_AUTHORIZED**，
> `authorized_next: GATE_4_RL_NO_GO_CLOSEOUT`。文档/决策收尾 only，无代码/训练变更。
> handoff_id = **GATE_4_RL_NO_GO_CLOSEOUT_001**。

---

# 1. 归档：接受的形式 NO_GO 结果

```text
执行：corrected F0 3-seed（36/36 runs，PPO/SAC/TD3 × seeds 42/2026/7 × folds F1-F4）
config_sha256: 46c56bc9a204
stop/invariant: 0 违规；finalize_publish 通过（published）
artifacts: artifacts/gate4_rl_formal_results.json + _raw.json（tracked）
```

| 算法 | median 年化 | median Sharpe | median MaxDD | Sharpe≥1.64 seeds | GO/NO-GO |
|---|---:|---:|---:|---:|---|
| PPO | 27.4% | 1.617 | -9.1% | 1/3 | NO_GO |
| SAC | 24.9% | 1.527 | -8.7% | 0/3 | NO_GO |
| TD3 | 19.0% | 1.210 | -12.3% | 0/3 | NO_GO |

**project_level = NO_GO**（三者均被 MaxDiv 风险前沿 Pareto 主导）。

# 2. 经济对比（RL vs 确定性基准）

| 参照 | active-ann | Sharpe | MaxDD | Calmar |
|---|---:|---:|---:|---:|
| EqualWeight（回报 hurdle） | 26.9% | 1.64 | -8.8% | 3.05 |
| MaxDiv（风险调整前沿） | 18.3% | **2.77** | **-3.4%** | **5.38** |
| PPO（RL best） | 27.4% | 1.62 | -9.1% | 3.01 |
| SAC | 24.9% | 1.53 | -8.7% | 2.83 |
| TD3 | 19.0% | 1.21 | -12.3% | 1.57 |

- **EqualWeight 是强回报基线**：PPO 年化略超但 Sharpe/MaxDD/seed 一致性未达标；多数优化器/RL 未稳超
  （DeMiguel 论点：估计误差侵蚀优化收益）。
- **MaxDiv 是清晰的风险调整前沿**：RL 三者均被其 Sharpe/MaxDD/Calmar 三维 Pareto 主导。

# 3. Roadmap 状态

```text
F0 PPO/SAC/TD3 分支：CLOSED for formal robustness（NO_GO）
CONDITIONAL_FORMAL_ROBUSTNESS：不授权（需 PROMISING）
GATE_4_10_SEED_FORMAL：不授权
确定性策略（非 RL：MaxDiv / EqualWeight 等）：保持为当前 benchmark/fallback 路径
```

# 4. 未来研究假设（仅新 pre-registered 实验）

```text
不得在同一 RESEARCH_BENCHMARK_TEST（475）上重训/调参/改特征（Test-informed 禁止）。
任何新假设（如 RL 架构 / 特征集 / reward / 数据 regime）须：
  1. 作为独立 pre-registered 实验设计；
  2. 需要新的 untouched forward 期 或 单独授权的新数据 regime；
  3. 先冻结协议经评审授权再执行。
```

# 5. 边界与规避

```text
✓ 文档/决策 only：无代码 / 无 RL 训练 / 无调参 / 无特征变更 / 无部署
✓ 不 10-seed / CONDITIONAL_ROBUSTNESS / Optuna / sweep / Test-informed / F2-F3 / QMT_LIVE / SOUTHBOUND
✓ 确定性策略保持 fallback，不启动新优化/live
```

# 6. Git Commit

`GATE_4_RL_NO_GO_CLOSEOUT` 提交 SHA：**`PENDING_SHA`**

```text
docs/DECISIONS.md                    ← D-022 NO_GO 决策记录
docs/review_packets/GATE_4_RL_NO_GO_CLOSEOUT.md  ← 本 packet
docs/agent_state/CLAUDE_STATUS.yaml  ← 协议状态
```

---

## Approval Record

```yaml
gate: 4
handoff_id: GATE_4_RL_NO_GO_CLOSEOUT_001
packet: GATE_4_RL_NO_GO_CLOSEOUT
status: READY_FOR_REVIEW

accepted:
  formal_no_go: true                # PPO/SAC/TD3 均未过 EW hurdle
  archived_artifacts: true          # gate4_rl_formal_results.json/_raw.json + config_sha256 46c56bc9a204
  economic_comparison: true         # vs EqualWeight + MaxDiv
  roadmap_f0_rl_closed: true        # CLOSED for formal robustness
  future_hypotheses_pre_registered_only: true  # 需新 forward 期或独立数据 regime
  deterministic_strategies_remain_fallback: true  # MaxDiv/EW benchmark path

not_authorized:
  conditional_robustness: false
  ten_seed: false
  rl_retraining_on_test: false
  test_informed_iteration: false
  live_execution: false
```

## END OF GATE 4 RL NO-GO CLOSEOUT
