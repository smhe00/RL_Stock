# GATE 4 3-SEED PILOT

> Reviewer 授权：`GATE_4_3_SEED_PILOT = AUTHORIZED`（2026-08-08，`GATE_4_PILOT_READY_FINAL_FIX_REVIEWER_RESPONSE.md` §18）。
> 4 folds × TD3/SAC/PPO × seeds 42/2026/7 × TRAIN_PASSES=20 × 1x cost = **36 RL trainings** + 4 deterministic baselines。
> 本 packet 按评审 §32 的 18 项清单提交；pilot 只评估 reproducibility / seed+fold dispersion /
> runner robustness / accounting integrity / runtime，**不声明算法 winner**（评审 §24）。

**生成时间**：2026-08-08。**状态**：结果待正式 run 完成后填充（run 进行中）。

---

# 1. Exact Run Manifest

```text
gate            : 4_3_SEED_PILOT
folds           : F1 / F2 / F3 / F4（4-fold expanding，train core 300 + val 60 + test）
algorithms      : TD3 / SAC / PPO（SB3 2.8.0，MlpPolicy，net_arch=[256,256]）
seeds           : 42 / 2026 / 7
train_passes    : 20（评审 §16 冻结）
total_timesteps : Σ(train_decision_steps × 20)（逐 fold，见 §5）
cost            : 1x（Mainland ETF 执行路径）
corporate-actions: 启用（官方派息日 + 512100 UNIT_CONSOLIDATION + 保守 fallback）
eval            : Validation（60D，transform-only）+ Test（frozen）
scaler          : train-only，逐 fold refit
rl_training_runs: 36
```

# 2. Git Commit

`GATE_4_3_SEED_PILOT` 提交 SHA：**（commit 后填写）**

包含：

```text
docs/review_packets/GATE_4_3_SEED_PILOT.md    ← 本 packet
docs/review_packets/GATE_4_PILOT_READY_FINAL_FIX_REVIEWER_RESPONSE.md  ← 授权输入（存档）
scripts/gate4_3seed_pilot.py                  ← pilot runner
src/china_etf/evaluation/rollout.py           ← series + 富 metrics（评审 §20）
runs/gate4_3seed_pilot_results.json           ← 主结果
runs/gate4_3seed_pilot_raw.json               ← 原始 series
```

# 3. Package / Version Snapshot

```text
stable_baselines3 : 2.8.0
torch             : 2.7.1+cu118（Pascal/1060）
gymnasium         : 1.2.3
pandas / numpy    : 2.x / 2.x
python            : 3.12
```

# 4. Fold Definitions

| Fold | Train（含） | Val | Test |
|---|---|---|---|
| F1 | 2022-06-06 → 2023-08-23（300 决策） | 2023-08-24 → 2023-11-23（60） | 2023-11-24 → 2024-05-23（118） |
| F2 | 2022-06-06 → 2024-05-23（478） | 2024-05-24 → 2024-08-16（60） | 2024-08-19 → 2025-02-18（118） |
| F3 | 2022-06-06 → 2025-02-18（656） | 2025-02-19 → 2025-05-19（60） | 2025-05-20 → 2025-11-10（118） |
| F4 | 2022-06-06 → 2025-11-10（834） | 2025-11-11 → 2026-02-04（60） | 2026-02-05 → 2026-08-07（121） |

Track A：`effective_obs_start=2022-06-06`，`calendar_rows=1015`，`max_full_transitions=1014`。

# 5. Training Timesteps by Fold（train_decision_steps × 20）

| Fold | train_decision_steps | total_timesteps |
|---|---:|---:|
| F1 | 299 | 5,980 |
| F2 | 477 | 9,540 |
| F3 | 655 | 13,100 |
| F4 | 833 | 16,660 |
| **合计** | 2,264 | **45,280 / algo-seed** |

同一 fold 内 TD3/SAC/PPO 使用相同 Environment-step budget（评审 §16）。

# 6. Algorithm / Seed Run-Completion Matrix

（正式 run 完成后填充：36 格 pass/fail + reason。）

# 7. Baseline Results（同 folds/执行/记账路径，不重复 seed）

（正式 run 完成后填充：EW / RiskParity / MinVariance / Momentum × 4 folds。）

# 8. Per-Fold Per-Seed RL Results

（正式 run 完成后填充：algo × seed × fold → cum/CAGR/Sharpe/MaxDD/turnover/cost/NaN/neg-cash/save-load。）

# 9. Stitched OOS per Seed

（正式 run 完成后填充：每 algo×seed 按 F1→F4 拼接 test net_returns → stitched CAGR/vol/Sharpe/MaxDD。）

# 10. Seed Dispersion

（正式 run 完成后填充：每 algo 跨 3 seeds 的 median/mean/std/min/max of {stitched CAGR, Sharpe, MaxDD, mean turnover}。）

# 11. Turnover / Cost

（正式 run 完成后填充：mean_turnover / total_cost / cost_over_initial_value，baseline vs RL。）

# 12. RiskOverlay Diagnostics

（正式 run 完成后填充：intervention_rate / mean L1(raw,post) / single_core_cap_hit / china_growth_cap_hit。）

# 13. Corporate-Action Diagnostics

（正式 run 完成后填充：events applied、receivable accrue/settle 生效、512100 折算连续性验证。）

# 14. Fallback Pay-Date Inventory（评审 §7/§30）

**pilot 使用官方 pay_date（513690 2024-12-20 / 2025-12-22）；未知 → ex+5T CONSERVATIVE_FALLBACK。**

```text
total_cash_events                 : 24
official_pay_date_events          : 2（513690 2024/2025）
conservative_fallback_events      : 22
fallback_events_in_test_windows   : 7
```

fallback 落入 OOS test 窗口的事件（>0，不自动判失败，但列出供 10-seed 前决定是否补官方）：

| instrument | ex-date | settle-date | cash/share | fold |
|---|---|---|---|---|
| 510300.SH | 2024-01-18 | 2024-01-25 | 0.069 | F1 |
| 510300.SH | 2025-06-18 | 2025-06-25 | 0.088 | F3 |
| 512100.SH | 2025-01-15 | 2025-01-22 | 0.037 | F2 |
| 513690.SH | 2023-12-22 | 2023-12-29 | 0.007 | F1 |
| 511260.SH | 2025-09-23 | 2025-09-30 | 1.360 | F3 |
| 511260.SH | 2026-03-25 | 2026-04-01 | 0.6711 | F4 |
| 511260.SH | 2026-06-25 | 2026-07-02 | 1.2686 | F4 |

注：以上为保守结算滞后（ex+5T）。10-seed formal 前建议为这些事件补官方 pay-date，
或做 settlement-delay sensitivity（评审 §30）。

# 15. Runtime

（正式 run 完成后填充：per-seed 组时长 + 总时长 + 单 run 平均。）

# 16. Failed / Retried Runs

（正式 run 完成后填充：fail + reason；无 fail 则注明。）

# 17. No-Ranking Disclaimer

本 pilot **不** 用于判定 TD3 / SAC / PPO 孰优。只评估 runner 稳定性、seed/fold 分散度、
会计完整性、运行时校准（评审 §24）。若某算法某 seed 表现差但无数值/记账错误，该差结果
是正式 evidence，**不得** 据此调参重跑（评审 §27）。

# 18. Pytest Output

```text
collected 109 items  →  109 passed（roll_out 扩展后无回归）
```

---

## Approval Record（待 run 完成后回填结果）

```yaml
gate: 4
packet: GATE_4_3_SEED_PILOT
status: RUNNING → SUBMITTED
stop_conditions: (见 §16)
stitched_oos / seed_dispersion: (见 §9/§10)
```

## END OF GATE 4 3-SEED PILOT
