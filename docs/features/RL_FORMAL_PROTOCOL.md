# RL Formal Protocol — FROZEN（RL_FORMAL_PROTOCOL_PREP_CORRECTIONS）

> 评审（`RL_FORMAL_PROTOCOL_PREP_REVIEWER_RESPONSE.md`）TARGETED_PROTOCOL_CORRECTIONS_REQUIRED（P1-P9）已闭环。
> 本文件是 corrected F0 RL 正式实验的 **canonical frozen 契约**；**机器可读配置**见 `configs/rl_formal_protocol.yaml`（P7）。
> **协议 prep only：不训练/重训 RL；不跑 corrected F0 3-seed**（CORRECTED_F0_RL_3SEED 是未来独立执行门）。

## 状态

```text
observation = F0（104 维）——作为**既有冻结基线契约**保留（P1）；不因描述性 F1 诊断而选/删
F1 = 独立 Gen-2 研究候选集；描述性诊断不证明 F1 无价值，也不用于选择 F0（P1）
F2/F3 = 真实宏观数据（FEATURE_DATA_READY 门后），正式实验排除
下一 3-seed 定位 = CORRECTED_F0_RL_3SEED / research-benchmark GO-NO-GO（P2）
10-seed = conditional / 未授权（FEATURE_ABLATION_SPEC 冻结保留；本协议不删除，P2）
RL_RETRAINING / CORRECTED_F0_RL_3SEED / OPTUNA / SWEEP = FORBIDDEN（本 prep 门）
```

## 1. 目标

```text
在 corrected 评估路径上，F0 RL 策略在 RESEARCH_BENCHMARK_TEST（exact 475 执行日）上是否表现
出超越非 RL 基准的增量价值（值得进一步验证，非最终泛化证明，P3）。
```

## 2. 算法（P7 冻结于 configs/rl_formal_protocol.yaml）

```text
PPO / SAC / TD3（stable-baselines3）
net_arch = [256, 256]；TRAIN_PASSES = 20
device = PPO: cpu；SAC / TD3: cuda
全部有效构造超参 = configs/rl_formal_protocol.yaml algorithms（SB3 默认，机器可读冻结）
reward = log(V_{t+1}^net / V_t^net)（已扣全部成本）
```

## 3. 训练预算（walkforward TB1）

```text
每 fold 预算 = TRAIN_PASSES × train_decision_steps（非固定 timesteps/fold）
train_decision_steps = len(train_env.calendar) - 1 - warmup_index（末行 = terminal mark）
folds = 4（expanding train core + val 60d + test）
```

## 4. Seed 政策（P2）

```text
下一 run seeds = {42, 2026, 7}（3 seeds，pilot 集；确定性可审计）
总 runs = 3 algos × 3 seeds × 4 folds = 36
定位 = CORRECTED_F0_RL_3SEED / research-benchmark GO-NO-GO（非最终统计阶段）
10-seed = conditional / 未授权（保留，不删除）；10-seed 执行需未来独立授权
```

## 5. Model selection（P6）

```text
checkpoint_policy = final_training_endpoint_only（无 checkpoint search，无后验自由度）
validation-only：跨 seed 报告 median；禁止用 Test 选 seed / checkpoint / 超参 / algo（P5）
```

## 6. Test mask（P3）

```text
RESEARCH_BENCHMARK_TEST = exact_test_mask(folds, calendar=adj.index)["test_dates"] = 475 执行日
（历史 475 日已被 pilot/horse-race/feature-diagnostic 反复观测 → 研究基准，非 pristine final holdout）
stitched OOS = 按 fold 序拼接 test net_returns（fold 间 val gaps 不计）
mask parity assert：n_eval_steps == 475 且 execution_dates == mask test_dates
FUTURE_FINAL_FORWARD_HOLDOUT = 未来未见期，用于最终确认（P3 预留）
```

## 7. Corrected 评估语义（E1/E2/E3，horse-race FINALIZATION 后）

```text
E1：fold 边界 test 段在 val_end 重置记账（现金+零持仓，保留特征历史），首执行 test_start open
E2：cost reconciliation（Σcosts == fees delta）；total_turnover / total_cost / traded 精确求和
E3：RiskOverlay 诊断（risk_overlay_intervention_rate, mean_l1_raw_to_post）
1x Mainland cost；corporate actions（settle/折算/计提，value-neutral）；t-close → t+1-open 执行
```

## 8. Benchmark hurdle（P4 两层）

```text
PRIMARY RETURN HURDLE = EqualWeight（PROMISING_GO 依据，回报维度）：
  active_day_annualized_return 0.2687 / Sharpe 1.64 / MaxDD -0.0881（corrected 路径 artifact）
RISK-ADJUSTED FRONTIER REFERENCE = MaximumDiversification（风险调整前沿，Pareto 报告）：
  active_day_annualized_return 0.1832 / Sharpe 2.77 / MaxDD -0.0340 / Calmar 5.38
必须报告 RL 是否被确定性前沿在 Sharpe / MaxDD / Calmar 上 Pareto 主导；
不清除 EqualWeight 即断言 RL 整体优越。
MaxDD hurdle 纳入 GO guardrail（§10）——EqualWeight MaxDD -0.0881。
```

## 9. Metrics（P9 命名统一）

```text
stitched 序列含 validation gaps → 年化一律用 active_day_annualized_return =
  (1 + cumulative_return) ** (252 / n_steps) - 1（RL 与非 RL 同定义；不混用 calendar CAGR）
oos_cum_return, active_day_annualized_return, annualized_vol, sharpe, sortino, max_drawdown, calmar,
mean_turnover, total_turnover, total_cost, cost_over_initial_value, actual_traded_notional,
n_eval_steps, risk_overlay_intervention_rate, risk_overlay_mean_l1_raw_to_post,
nan_obs_or_reward, negative_cash_count
```

## 10. GO/NO-GO（P5 分算法 + 项目级两阶段）

```text
【per-algorithm】（对 PPO、SAC、TD3 各自）：
  GO = 无 stop/invariant 违规 AND median(seed Sharpe) ≥ 1.64 AND median(seed CAGR) ≥ 0.2687
       AND ≥2/3 seeds 的 Sharpe ≥ 1.64 AND median(seed MaxDD) ≥ -0.0881（点估计，3-seed 不声明统计显著）
  NO-GO = 任何 stop/invariant 违规，或未达任一条件
【project-level】：
  至少 1 个算法 per-algorithm GO → project = PROMISING（值得进一步验证）
  0 个算法 GO → project = NO-GO（不推进）
  禁止 Test-based 算法 winner selection（不得用 Test 选单算法推进；若仅 1 算法通过，
  后续推进的 selection 必须 validation-only 且先于 Test 消费冻结）
  冻结通过后行为：通过算法进入 conditional formal robustness stage（10-seed，未来独立授权，P2）
```

## 11. Artifacts

```text
artifacts/gate4_rl_formal_results.json   主结果（tracked）
artifacts/gate4_rl_formal_raw.json       原始 series（tracked）
runs/                                    gitignored（EXECUTION_SPEC §55）
```

## 12. Stop / hard-stop invariants（P8）

```text
stop conditions（复用 pilot check_stop_conditions）：
  nan_obs_or_reward > 0 / negative_cash_count > 0 / save_load 失败 / oos 非 finite
hard-stop invariants（fail-closed，P8）：
  execution_dates == 475 mask（parity）
  n_eval_steps == 475
  cost reconciliation pass
  全部 folds 存在且无重复；raw series 完整
```

## 13. 范围与隔离

```text
observation = F0（104 维）；F1 保留为 Gen-2 候选集（不删除、不因诊断选/删，P1）
F2/F3 真实宏观 → FEATURE_DATA_READY 门
禁止：RL 重训 / 10-seed 执行 / Optuna / sweep / Test-informed 选择 / 特征增减 / QMT_LIVE / SOUTHBOUND
```

## 冻结声明

```text
此协议于 RL_FORMAL_PROTOCOL_PREP_CORRECTIONS（2026-08-09）冻结，独立于任何未来 Test 结果。
机器可读配置（configs/rl_formal_protocol.yaml）为 canonical 输入。
hurdle 参数（§8/§10）可在评审批准下调整；其余契约冻结。
协议执行（CORRECTED_F0_RL_3SEED）需独立评审授权。
```

## 变更记录

- 2026-08-09（RL_FORMAL_PROTOCOL_PREP）：初始冻结。
- 2026-08-09（RL_FORMAL_PROTOCOL_PREP_CORRECTIONS）：P1-P9 闭环——F0 rationale（既有冻结基线）、
  3-seed 定位 corrected benchmark + 10-seed conditional、RESEARCH_BENCHMARK_TEST + forward holdout、
  两层 benchmark（EW primary + MaxDiv frontier）、分算法 GO/NO-GO、final-endpoint checkpoint、
  机器可读 config（configs/rl_formal_protocol.yaml）、hard-stop invariants、active_day_annualized_return 命名。
