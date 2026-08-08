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

**36/36 全部 pass，0 fail，无 stop-condition 违规。**

| algo \ seed | 42 | 2026 | 7 |
|---|---|---|---|
| TD3 | ✅ F1-F4 | ✅ F1-F4 | ✅ F1-F4 |
| SAC | ✅ F1-F4 | ✅ F1-F4 | ✅ F1-F4 |
| PPO | ✅ F1-F4 | ✅ F1-F4 | ✅ F1-F4 |

每 run 均满足：`nan_obs_or_reward=0`、`negative_cash_count=0`、`save_load_deterministic_identical=True`、
RiskOverlay 无异常、无调整后价格成交（评审 §25 全部 stop 条件未触发）。

# 7. Baseline Results（同 folds/执行/记账路径，不重复 seed）

| Baseline | F1 | F2 | F3 | F4 | stitched 累计 | stitched CAGR |
|---|---:|---:|---:|---:|---:|---:|
| EqualWeight | +4.5% | +23.2% | +20.0% | +1.6% | +56.9% | +27.0% |
| RiskParity | +4.8% | +18.4% | +14.9% | +1.5% | +44.7% | +21.7% |
| MinimumVariance | +4.8% | +19.2% | +16.4% | +1.5% | +47.5% | +23.0% |
| Momentum | +12.3% | +16.2% | +22.9% | +2.8% | +64.7% | +30.4% |

# 8. Per-Fold Per-Seed RL Results（test 段累计净收益）

| algo \ seed | F1 | F2 | F3 | F4 |
|---|---|---|---|---|
| TD3 \| 42 | +1.1% | +24.3% | +22.6% | -1.7% |
| TD3 \| 2026 | +3.8% | +25.1% | +24.5% | +8.7% |
| TD3 \| 7 | +0.6% | +20.8% | +17.7% | +3.5% |
| SAC \| 42 | +4.4% | +24.2% | +17.5% | +0.3% |
| SAC \| 2026 | +4.6% | +22.8% | +18.5% | -2.8% |
| SAC \| 7 | +4.4% | +23.9% | +14.5% | +6.0% |
| PPO \| 42 | +4.7% | +24.0% | +20.0% | +1.1% |
| PPO \| 2026 | +4.7% | +24.5% | +17.9% | +2.7% |
| PPO \| 7 | +3.9% | +22.3% | +18.5% | +1.2% |

（每 run 均 `nan=0, neg_cash=0, save_load=True`。）

# 9. Stitched OOS per Seed（F1→F4 拼接 test net_returns）

| algo \ seed | 累计 | CAGR | 年化波动 | Sharpe | MaxDD |
|---|---:|---:|---:|---:|---:|
| TD3 \| 42 | +51.4% | +24.9% | 12.6% | 1.49 | -10.5% |
| TD3 \| 2026 | +75.7% | +35.2% | 14.7% | 1.62 | -12.3% |
| TD3 \| 7 | +48.1% | +23.4% | 12.6% | 1.47 | -13.9% |
| SAC \| 42 | +52.8% | +25.5% | 12.1% | 1.57 | -8.9% |
| SAC \| 2026 | +48.0% | +23.3% | 12.3% | 1.44 | -13.1% |
| SAC \| 7 | +57.0% | +27.3% | 12.7% | 1.61 | -8.8% |
| PPO \| 42 | +57.4% | +27.5% | 11.6% | 1.69 | -8.4% |
| PPO \| 2026 | +57.8% | +27.7% | 12.3% | 1.61 | -9.3% |
| PPO \| 7 | +52.4% | +25.3% | 11.6% | 1.61 | -9.1% |

# 10. Seed Dispersion（跨 3 seeds）

| algo | OOS CAGR median (mean/std/min/max) | OOS Sharpe median (mean/std/min/max) | MaxDD median | mean turnover |
|---|---|---|---|---|
| TD3 | 0.249 (0.278 / 0.053 / 0.234 / 0.352) | 1.49 (1.53 / 0.07 / 1.47 / 1.62) | -12.3% | 0.26 |
| SAC | 0.255 (0.254 / 0.016 / 0.233 / 0.273) | 1.57 (1.54 / 0.07 / 1.44 / 1.61) | -8.9% | 0.18 |
| PPO | 0.275 (0.268 / 0.011 / 0.253 / 0.277) | 1.61 (1.63 / 0.04 / 1.61 / 1.69) | -9.1% | 0.05 |

**seed 分散度关键观察**：三算法跨 3 seed 的 Sharpe std 仅 0.04-0.07、CAGR std 仅 0.01-0.05，
**种子敏感性很低（结果稳定）**；PPO 分散度最低（最稳），TD3 最高但也可接受。

# 11. Turnover / Cost

| 策略 | mean turnover | cost/初始值（单折，PPO F3 例） | total_cost（PPO F3 例） |
|---|---:|---:|---:|
| PPO（median） | 0.054 | 2.38% | 28,101 CNY |
| SAC（median） | 0.176 | — | — |
| TD3（median） | 0.260 | — | — |
| Momentum | — | — | — |

**换手率排序**：PPO（0.05）≪ SAC（0.18）< TD3（0.26）——PPO 换手最低、成本最低；TD3 换手最高。
PPO F3 单折成本 2.38% 初始值 / 折，10-seed 需在正式报告聚合全折总成本。

# 12. RiskOverlay Diagnostics

| algo | intervention_rate | mean L1(raw→post) | single_core_cap_hit | china_growth_cap_hit |
|---|---|---|---|---|
| TD3 | F1 43.6% / F2 7.7% / F3-F4 0% | ~1e-16 | 0 | 0 |
| SAC | F3 11.1% / F4 2.5% / 其余 0% | ~1e-16 | 0 | 0 |
| PPO | 全 0% | ~1e-16 | 0 | 0 |

**含义**：TD3 早期（F1）曾触及 25% 单资产 cap（43.6% 干预率），后随训练趋于温和；SAC/PPO 几乎不触发。
全部 run `single_core_cap_hit=0`、`china_growth_cap_hit=0`、无 RiskOverlay 异常（评审 §3.3 的
"干预率升高再研究 action semantics"条件未触发，V2 动作域下护栏状态健康）。

# 13. Corporate-Action Diagnostics

- 全 pilot 使用双价 contract：研究序列（raw+官方事件 TR）+ 执行 raw OHLC + raw 估值 + 应收款。
- 513690 官方派息（2024-12-20 / 2025-12-22）在 test 窗口正确结算（`test_513690_2024/2025_official_payment_date` PASS）。
- 512100 2022-09-05 UNIT_CONSOLIDATION（factor 0.36555）跨 F1 train 正确折算，价值连续
  （4 个真实事件回归 PASS，含 `test_512100_20220902_portfolio_value_continuity`）。
- 保守 fallback 事件（ex+5T，22 个）全部 `source=CONSERVATIVE_FALLBACK`，不提前结算。
- **所有 run `negative_cash_count=0`**，应收款→现金结算路径无会计断裂。

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

```text
seed 42   : 54.4 min（TD3 4折 + SAC 4折 + PPO 4折）
seed 2026 : 53.9 min
seed 7    : 52.6 min
baselines : ~3 min
总计      : ~2h42m（36 RL runs + 4 baselines，单 GPU 1060）
单 run 平均: ~4.3 min（TD3 均值 260s / SAC 335s / PPO 177s，随 fold 线性增长）
```

10-seed 正式（120 runs，顺序）预计 ~9h；双进程并行（SAC 独占 GPU + TD3/PPO/baseline）预计 ~5h。

# 16. Failed / Retried Runs

**0 fail，0 retry。** 36/36 runs 全部一次性通过，无异常、无数值错误、无记账错误。
（与 §6 completion matrix 一致；评审 §27 的"软件/数值故障才允许重跑"未触发。）

# 17. No-Ranking Disclaimer

本 pilot **不** 用于判定 TD3 / SAC / PPO 孰优。只评估 runner 稳定性、seed/fold 分散度、
会计完整性、运行时校准（评审 §24）。若某算法某 seed 表现差但无数值/记账错误，该差结果
是正式 evidence，**不得** 据此调参重跑（评审 §27）。

**观察（非结论）**：三算法均通过 sanity；PPO seed 分散度最低、换手最低；TD3 seed 分散度最高
（TD3|2026 的 +35.2% CAGR vs TD3|7 的 +23.4%，范围较宽）。这些属于 runner 稳定性观测，
不是算法排名依据。

本 pilot **不** 用于判定 TD3 / SAC / PPO 孰优。只评估 runner 稳定性、seed/fold 分散度、
会计完整性、运行时校准（评审 §24）。若某算法某 seed 表现差但无数值/记账错误，该差结果
是正式 evidence，**不得** 据此调参重跑（评审 §27）。

# 18. Pytest Output

```text
collected 109 items  →  109 passed（roll_out 扩展后无回归）
```

---

# 附：与同期沪深300（510300，含分红 TR）基准对比

同期 510300 基准（2023-11-24 → 2026-08-07，stitched）：**累计 +50.2%，CAGR +24.1%，Sharpe +1.16，MaxDD -13.7%**。

| 策略（stitched OOS median 跨 3 seeds） | CAGR | Sharpe | MaxDD | vs 基准 CAGR |
|---|---:|---:|---:|---:|
| **PPO** | **+27.5%** | **1.61** | -9.1% | **+3.4pp** |
| SAC | +25.5% | 1.57 | -8.9% | +1.4pp |
| TD3 | +24.9% | 1.49 | -12.3% | +0.8pp |
| Momentum（baseline） | +30.4% | — | — | +6.3pp |
| EqualWeight | +27.0% | — | — | +2.9pp |
| **510300 基准** | +24.1% | 1.16 | -13.7% | — |

**观察（非结论）**：三 RL 算法 stitched OOS 的 CAGR 中位数（24.9-27.5%）**略高于**同期沪深300（24.1%），
Sharpe（1.49-1.61）明显高于基准（1.16），MaxDD（-8.9%~-12.3%）浅于基准（-13.7%）。
RL 组合通过 11 槽位分散配置获得相近收益 + 更低回撤/波动。但样本仅 474 OOS 交易日、3 seeds，
差距在统计上不足以支撑"RL 优于沪深300"结论——须 10-seed formal（120 runs）才可评估置信区间。
Momentum baseline 的 CAGR 最高（+30.4%）提示简单动量在样本期有优势，正式对比必须含全部 baselines。

---

## Approval Record

```yaml
gate: 4
packet: GATE_4_3_SEED_PILOT
status: SUBMITTED_FOR_REVIEW
date: 2026-08-09

completion: 36/36 pass, 0 fail, 0 retry
stop_conditions: none triggered
seed_dispersion: low (Sharpe std 0.04-0.07 across 3 seeds)
stitched_oos_cagr_median: TD3 24.9% / SAC 25.5% / PPO 27.5%
benchmark_510300_stitched: CAGR 24.1% / Sharpe 1.16 / MaxDD -13.7%
runtime: ~2h42m (36 RL + baselines, single GTX 1060)

pilot_goal:
  reproducibility: pass
  seed_sensitivity: low
  fold_sensitivity: observable (F2 strong, F4 weak)
  runner_robustness: pass
  accounting_integrity: pass (0 NaN, 0 neg-cash, CA settlement correct)
  runtime_calibration: pass

no_ranking: true
10_seed_formal: not_authorized
```

## END OF GATE 4 3-SEED PILOT
