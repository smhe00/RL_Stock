# GATE 4 FEATURE ABLATION PREP — RE-AFFIRMATION (post non-RL horse-race finalization)

> 评审（`GATE_4_NON_RL_HORSE_RACE_FINALIZATION_REVIEWER_RESPONSE.md`）：**APPROVED**，
> `authorized_next: GATE_4_FEATURE_ABLATION_PREP`（仅 prep；**FEATURE_ABLATION_RUNS 仍 forbidden**，
> "feature ablation execution before preparation review"）。
> 本 packet = gate transition + prep 对最终化评估路径的重验证 + 请求 runs 授权。
> handoff_id = **G4_FEATURE_ABLATION_PREP_002**。

---

# 1. Gate Transition（消费 FINALIZATION 评审）

```text
consumed_handoff    = G4_NON_RL_HORSE_RACE_FINALIZATION_001（APPROVED）
authorized_next     = GATE_4_FEATURE_ABLATION_PREP
forbidden_next      = RL_RETRAINING / GATE_4_10_SEED_FORMAL / FEATURE_ABLATION_RUNS /
                      OPTUNA / HYPERPARAMETER_SWEEP
```

此前 prep 已完成并经 `G4_FEATURE_ABLATION_PREP_CORRECTIONS_001` 全项 PASS
（P1 native-calendar-first F2 / P2 VIX 因果 / P3 分位公式 / P4 spec 同步 / P5 F0 parity）。
随后 ROADMAP 重定向到 `GATE_4_NON_RL_HORSE_RACE`（全链路 APPROVED）。
现评审重新授权进入 prep 阶段，故本轮**只 prep 不 runs**。

# 2. Prep 资产零漂移

自上次审批提交 `a273b63`（G4_FEATURE_ABLATION_PREP_CORRECTIONS_001）以来：

```text
git diff --stat a273b63..HEAD -- src/china_etf/features/ docs/features/
                                scripts/gate4_ablation_prep.py tests/test_ablation_features.py
→ 空（无任何改动）
```

prep 实现（F1/F2/F3 builders、align_pit、FeaturePreprocessor ddof=1、F-A2、spec）
保持已审批状态，**未做任何代码修改**。

# 3. 对最终化评估路径的重验证（HEAD 744a092）

评估路径在 horse race 期间已 FINALIZATION（`2a8ea68`，F4A/F4B/F5/F6 全关）。
prep 通过同一 `build_env` / `WalkForwardRunner` / `RiskOverlay` / corporate-action /
exact Test mask（475）契约工作。在最终化代码上重跑验证：

**Full pytest（当前 HEAD）：**

```text
collected 162 items  →  162 passed in 61.50s（含 tests/test_ablation_features.py 全部）
```

**Deterministic feature-construction smoke（scripts/gate4_ablation_prep.py 重跑）：**

```text
F0: exog=93 obs=104 OK   F1: exog=99 obs=110 OK
F2: exog=99 obs=110 OK   F3: exog=105 obs=116 OK
F-A2: train_rows=507 val_rows=508  finite_train=True finite_val=True imputed_approx_zero=True
```

（输出 runs/gate4_ablation_prep_smoke.json，gitignored per EXECUTION_SPEC §55。）

# 4. 已冻结契约仍然成立（spec = canonical source）

```text
F-A1 downside_semivol = LPM2 around zero
F-A2 train-only imputation（val/test 只 transform；train 无可用观测 → fail-closed）
F2 native-calendar-first + PIT as-of 对齐（VIX strict_prev_session）
VIX 分位 = (rank-1)/(N-1)，ties average rank
FeaturePreprocessor ddof=1（F0 legacy parity）
ObsDim：F0 104 / F1 110 / F2 110 / F3 116 ≤ 120
```

# 5. 请求的下一步授权（本 packet 不执行）

请求评审授权 **FEATURE_ABLATION_RUNS**（按 FROZEN FEATURE_ABLATION_SPEC：
F0 baseline vs F1/F2/F3 多 fold，corrected 评估路径）。在授权前**不运行任何 ablation**。

F2 相关的 carry-forward（评审 P2 记录，非当前 blocker）：

```text
真实 F2 macro 数据获取 = 独立 FEATURE_DATA_READY 门（spec：数据固化本地，禁止运行时抓取）
真实 F2 run 前需 timezone-aware available_at + China decision_at + 单一归一化时区比较
F1/F3（内部特征，无外部数据）不依赖该 carry-forward
```

# 6. Git Commit

`GATE_4_FEATURE_ABLATION_PREP_REAFFIRMATION` 提交 SHA：**`eb8128f`**

```text
docs/review_packets/GATE_4_FEATURE_ABLATION_PREP_002.md  ← 本 packet（gate transition + 重验证）
docs/agent_state/CLAUDE_STATUS.yaml                       ← 协议状态
```

（无 src/scripts/ 代码改动——prep 零漂移，仅 doc。）

# 7. Not Done / Not Authorized

```text
✗ 不运行 feature ablation runs（等待授权）
✗ 不重训 RL（TD3/SAC/PPO）——RL 结果仍为 HISTORICAL_RL_PILOT_REFERENCE
✗ 不跑 10-seed formal / Optuna / hyperparameter sweep
✗ 不获取真实宏观数据（F2 FEATURE_DATA_READY 独立门）
✗ 不改 F0 观测 contract（equity_average_corr_60 命名 → RFC/ablation note 已记录）
```

---

## Approval Record

```yaml
gate: 4
handoff_id: G4_FEATURE_ABLATION_PREP_002
packet: GATE_4_FEATURE_ABLATION_PREP_002
status: READY_FOR_REVIEW

transition:
  consumed_handoff: G4_NON_RL_HORSE_RACE_FINALIZATION_001
  consumed_decision: APPROVED
  re_entered_phase: GATE_4_FEATURE_ABLATION_PREP

re_validated:
  prep_assets_zero_drift: true        # a273b63..HEAD 无改动
  full_pytest_162: true               # 61.50s
  prep_smoke_rerun: true              # F0/F1/F2/F3 维度 + F-A2 imputation 全 OK
  interface_compat_finalized_eval: true  # build_env / WalkForward / RiskOverlay / mask 475

requested:
  feature_ablation_runs_authorization: pending   # 本 packet 不执行

not_done:
  feature_ablation_runs: false
  rl_retraining: false
  ten_seed_formal: false
  real_macro_data_acquisition: false  # F2 FEATURE_DATA_READY 独立门
```

## END OF GATE 4 FEATURE ABLATION PREP RE-AFFIRMATION
