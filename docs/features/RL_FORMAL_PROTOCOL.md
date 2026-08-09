# RL Formal Protocol — FROZEN（RL_FORMAL_PROTOCOL_PREP）

> 评审（`GATE_4_FEATURE_ABLATION_DIAGNOSTIC_CLOSEOUT_REVIEWER_RESPONSE.md`）APPROVED，
> `authorized_next: RL_FORMAL_PROTOCOL_PREP`。本文件是 corrected F0 RL 正式实验的 **canonical frozen 契约**。
> **协议 prep only：不训练/重训 RL；不跑 corrected F0 3-seed**（CORRECTED_F0_RL_3SEED 是未来独立执行门）。

## 状态

```text
observation = F0（104 维）——feature-ablation（已 APPROVED）无 F1 稳健增益，F1 不加入
F2/F3 = 真实宏观数据（FEATURE_DATA_READY 门后），正式实验排除
10-seed = REMOVED_FROM_ACTIVE_ROADMAP
RL_RETRAINING / CORRECTED_F0_RL_3SEED / OPTUNA / SWEEP = FORBIDDEN（本 prep 门）
```

## 1. 目标

```text
在 corrected 评估路径上，F0 RL 策略在 exact 475-Test mask 上是否超越 benchmark hurdle（EqualWeight）。
```

## 2. 算法（冻结 pilot 配置）

```text
PPO / SAC / TD3（stable-baselines3）
net_arch        = [256, 256]
TRAIN_PASSES    = 20
device          = PPO: cpu；SAC / TD3: cuda
reward          = log(V_{t+1}^net / V_t^net)（已扣全部成本）
```

## 3. 训练预算（walkforward TB1）

```text
每 fold 预算 = TRAIN_PASSES × train_decision_steps（非固定 timesteps/fold）
train_decision_steps = len(train_env.calendar) - 1 - warmup_index（末行 = terminal mark）
folds = 4（expanding train core + val 60d + test）
```

## 4. Seed 政策

```text
seeds = {42, 2026, 7}（3 seeds，pilot 一致；seed 分散度已验证低）
总 runs = 3 algos × 3 seeds × 4 folds = 36
10-seed = REMOVED（不做）
```

## 5. Validation-only model selection

```text
- 跨 seed 报告 median（不选单 best seed）
- 禁止用 Test 选 seed / checkpoint / 超参
- 若执行多 checkpoint：按 VAL 指标选（非 Test）
```

## 6. Exact Test mask

```text
exact_test_mask(folds, calendar=adj.index)["test_dates"] = 475 执行日
stitched OOS = 按 fold 序拼接 test net_returns（fold 间非连续，val gaps 不计）
mask parity assert：n_eval_steps == 475 且 execution_dates == mask test_dates
```

## 7. Corrected 评估语义（E1/E2/E3，horse-race FINALIZATION 后）

```text
E1：fold 边界 test 段在 val_end 重置记账（现金+零持仓，保留特征历史），首执行 test_start open
E2：cost reconciliation（Σcosts == fees delta）；total_turnover / total_cost / traded 精确求和
E3：RiskOverlay 诊断（risk_overlay_intervention_rate, mean_l1_raw_to_post）
1x Mainland cost；corporate actions（settle/折算/计提，value-neutral）；t-close → t+1-open 执行
```

## 8. Benchmark hurdle（GO/NO-GO 参照；参数化，评审可调）

```text
参照 = EqualWeight（corrected 路径，artifacts/gate4_non_rl_horse_race_results.json）：
  CAGR = 0.2687（active-day annualized）
  Sharpe = 1.64
  MaxDD = -0.0881
```

## 9. Metrics（per fold test + stitched）

```text
oos_cum_return, cagr, annualized_vol, sharpe, sortino, max_drawdown, calmar,
mean_turnover, total_turnover, total_cost, cost_over_initial_value,
actual_traded_notional, n_eval_steps,
risk_overlay_intervention_rate, risk_overlay_mean_l1_raw_to_post,
nan_obs_or_reward, negative_cash_count
```

## 10. GO/NO-GO criteria

```text
GO   = 无 stop-condition 违规 AND
       median(seed Sharpe) ≥ hurdle Sharpe (1.64) AND
       median(seed CAGR)  ≥ hurdle CAGR  (0.2687) AND
       ≥2/3 seeds 的 Sharpe ≥ hurdle Sharpe（点估计；3-seed 不声明统计显著）
NO-GO = 任何 stop 违规，或未达上述任一条件
```

## 11. Artifacts

```text
artifacts/gate4_rl_formal_results.json   主结果（tracked）
artifacts/gate4_rl_formal_raw.json       原始 series（tracked）
runs/                                    gitignored（EXECUTION_SPEC §55）
```

## 12. Stop conditions（复用 pilot check_stop_conditions）

```text
nan_obs_or_reward > 0          → stop
negative_cash_count > 0        → stop
save_load_deterministic 失败   → stop
oos_cum_return 非 finite       → stop
```

## 13. 范围与隔离

```text
observation = F0（104 维）；F1 不加入（ablation 无稳健增益）；F2/F3 真实宏观 → FEATURE_DATA_READY 门
RL 结果仅相对 benchmark hurdle 判定；不做跨 algo 选 winner 结论
禁止：RL 重训 / 10-seed / Optuna / sweep / Test-informed 特征选择 / 特征增减 / QMT_LIVE / SOUTHBOUND
```

## 冻结声明

```text
此协议于 RL_FORMAL_PROTOCOL_PREP（2026-08-09）冻结，独立于任何未来 Test 结果。
hurdle 参数（§8/§10）可在评审批准下调整；其余契约冻结。
协议执行（CORRECTED_F0_RL_3SEED）需独立评审授权。
```

## 变更记录

- 2026-08-09（RL_FORMAL_PROTOCOL_PREP）：初始冻结。
