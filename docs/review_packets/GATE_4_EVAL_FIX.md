# GATE 4 EVAL FIX

> Reviewer：`GATE_4_3_SEED_PILOT = PASS_AS_MECHANICS`（`GATE_4_3_SEED_PILOT_REVIEWER_RESPONSE.md`），
> `NEXT = GATE_4_EVAL_FIX`。本 packet 关闭 E1/E2/E3 三个评估路径 blocker + benchmark mask +
> fallback pay-date sensitivity + 特征 spec 冻结。handoff_id = **G4_EVAL_FIX_001**。

---

# 1. E1 Segment Accounting-Reset Implementation

**问题**：`_rollout_segment` 从 warmup 用最终策略 replay 历史到段边界才记录 → test 起点组合是合成状态。

**修复**：
- `portfolio_env.reset(at_date=None)`：`at_date` 提供时从该决策日（段边界前一交易日收盘）开始，
  accounting 重置为初始现金+零持仓；`at_date` 必须 ≥ warmup_index（保留 252D 特征历史，不截断）。
- `roll_out(..., reset_at)`：`env.reset(at_date=reset_at)`；记录条件改为 `st.t_next >= eval_start`
  （执行日 ≥ 段首，使段首 transition——决策于边界收盘、执行于段首 open——计入评估）。
- `_rollout_segment`：Validation → `reset_at=train_end`；Test → `reset_at=val_end`；
  `run_fold_baseline` 同样在 `val_end` 重置。

# 2. Validation/Test Predecision / First-Fill / First-Metric Timeline

```text
Validation:
  feature history : retained（env 数据到 val_end，特征滚动用 ≤t 数据）
  accounting reset: train_end close（现金+零持仓）
  decision         : train_end close
  first execution  : val_start open
  first evaluated transition: val_start

Test:
  feature history : retained（env 数据到 test_end）
  accounting reset: val_end close（现金+零持仓）
  decision         : val_end close
  first execution  : test_start open
  first evaluated transition: test_start
```

每段 manifest 暴露（评审要求）：`segment_predecision_date` / `segment_first_execution_date` /
`segment_first_metric_date` / `initial_cash` / `initial_positions`。

# 3. E2 Cost Reconciliation

**问题**：`prev_fees=0` 而 `fees_paid` 累计 → 首个 test step_cost 含 pre-test 费用
（PPO turnover 0.054 却 cost/initial 2.38% 的假象）。

**修复**：E1 段独立记账后费用从段边界归零；`prev_fees` 初始化为 reset 后 `fees_paid`。
`roll_out` 返回前 **assert `sum(test_step_cost) == fees_at_segment_end - fees_at_segment_start`**。
新增指标：

```text
mean_turnover_l1 / total_turnover_l1
estimated_one_way_traded_fraction = total_turnover_l1 / 2
actual_traded_notional / actual_traded_notional_over_initial_equity
total_cost / total_cost_over_traded_notional / cost_over_initial_equity
```

**修复效果（smoke 实测）**：PPO F1 cost_over_initial_equity 由旧假象 2.38% → **0.115%**
（与 Mainland ~3.5bp 单边成本 × 换手量级一致）。E2 对账 assert 全部通过。

# 4. Corrected Turnover / Cost Diagnostics

| algo（F1 smoke） | cost/initial equity | total_cost_over_traded_notional | 说明 |
|---|---:|---:|---|
| TD3 | 1.018% | ~3.5bp 量级 | 低 passes 未收敛，turnover 高 |
| SAC | 0.095% | ~3.5bp 量级 | 换手低 |
| PPO | 0.115% | ~3.5bp 量级 | 换手低 |

`total_cost_over_traded_notional` ≈ 3.5bp（佣金 0.5bp + spread 1bp + slippage 2bp），与 Mainland V1 一致；
成本/换手量级一致（`test_cost_turnover_order_of_magnitude_consistent`）。

# 5. E3 RiskOverlay Reconciliation

**澄清**：E3 报告的 TD3 F1 `intervention=43.6% / mean_l1≈1e-16` 矛盾实为 **packet 文档误写**
（§12 把 PPO 的 ~1e-16 错填进 TD3 行）；代码实际 `mean_l1=0.112` 与 43.6% 自洽。
但仍按要求加固：

```text
raw_single_core_violation_rate / raw_china_growth_violation_rate
post_single_core_at_cap_rate / post_china_growth_at_cap_rate
post_constraint_violation_rate   （应恒 0）
```

cap 用 RiskOverlay 实际值（`env.risk_overlay.caps` / `growth_max`，非硬编码 0.25/0.50）。
**Reconciliation assert**：`if overlay_intervened>0: mean_l1 >= intervention_rate × 1e-6`，否则报错，
杜绝不可能报告。smoke 中 TD3 干预 47.5% 时 mean_l1 合理、assert 通过。

# 6. Exact Stitched Test-Mask Proof

`evaluation/benchmark.py::exact_test_mask(folds, calendar)`：

```text
strategy_stitched_steps = 475    benchmark_stitched_steps = 475
exact_test_date_count   = 475    first_test_date = 2023-11-24  last_test_date = 2026-08-07
excluded_validation_dates = 240（4 folds val 段）
```

assert 步数相等。措辞改用 **`stitched OOS active-day annualized return`**（承认非连续日历，明确排除 val gap）。

# 7. Executable 510300 Buy-and-Hold Baseline Smoke

`benchmark.py::cn_large_buy_hold_net_return`：raw open 首 test 日全仓买入 + 公司行为记账 + 1x 成本 +
exact Test mask（不走 RiskOverlay，100% CN_LARGE）。

```text
CN_LARGE_EXECUTABLE_NET_BUY_HOLD: cum=+35.30%（474 执行日），首日成本=350 CNY
```
标签：`510300_EXECUTABLE_NET_BUY_HOLD`（对照研究 TR 参考 `510300_RESEARCH_TR_REFERENCE`，两者分开标注）。
注意：buy-hold +35.3% 用可执行路径（首日 open + 成本 + CA），与研究 TR 口径不同，正式对比必须用可执行口径。

# 8. OOS Fallback Pay-Date Official-Date or Sensitivity Plan

**官方日期解析尝试**：akshare `fund_announcement_dividend_em` 仅返回公告标题，无结构化 record/ex/pay 日期，
不可靠 → 采用评审选项 2（settlement-delay sensitivity）。

`scripts/gate4_settlement_sensitivity.py`（+3T/+5T/+7T）：

```text
baselines（EW/RP/MV/Momentum × 4 folds）stitched_cum 跨 lag 最大差异: 0.00024（0.024pp）
RL 代表（PPO|42 F2，训一次模型，3 lag 各 eval）cum 跨 lag 差异: 0.00000
verdict: IMMATERIAL
```

**理论依据**：settle_date 只影响现金时点（应收款与现金均 1:1 计入 portfolio_value），决策 obs 不含 cash
→ settle lag 不影响 RL 权重路径与 equity。RL cum 三 lag 逐位一致证实。
**结论**：7 个 OOS fallback 事件（settle ex+3/5/7T）对正式 OOS 结果影响可忽略，**无需补官方日期**
（评审选项 2 满足）；若 10-seed 仍想确认，可对全部事件补官方 pay-date（非阻塞）。

# 9. Frozen F0/F1/F2/F3 Feature Spec

`docs/features/FEATURE_ABLATION_SPEC.md`（冻结，独立于 Test 结果）：

```text
F0 当前：ObsDim 104
F1 Risk/Corr：corr_pc1_share_60 / equity_bond_corr_change_20_60 / equity_gold_corr_change_20_60 /
             cn_us_corr_60 / equity_vol_ratio_20_60 / equity_downside_semivol_60（ObsDim 110）
F2 Macro：vix_prev_close_percentile_252 / vix_prev_close_change_5 / usd_cny_return_20 /
         cgb10y_yield_change_20 / dr007_zscore_60 / a_share_turnover_zscore_20（ObsDim 110）
F3 = F1+F2（ObsDim 116 ≤ 120）
strict PIT：China EOD 决策只用前一日完成的 US session VIX；外部数据固化本地。
禁止大 TA bundle。ablation runs NOT authorized（spec 仅冻结）。
```

# 10. Full Pytest

```text
collected 121 items  →  121 passed（新增 tests/test_eval_fix.py 12 个，含 E1×6/E2×3/E3×1/mask×1/buy-hold×1）
```

# 11. Corrected Seed42 Mechanics/Regression Smoke

`scripts/gate4_eval_fix.py`（F1，3 algos × 低 passes；**不重跑全部 36**）：

```text
E1 verified: 三 algo first_execution=2023-11-24(test_start)，n_eval=118=test 段行数
TD3 18.1s  cum=-1.0%  nan=0 neg_cash=0  intervention=47.5%
SAC 22.8s  cum=+4.1%  nan=0 neg_cash=0  intervention=0
PPO 35.3s  cum=+4.0%  nan=0 neg_cash=0  intervention=0
E2 对账 assert 全通过（total_cost == fees delta）
E3 诊断 + reconciliation assert 通过
benchmark mask 步数相等（475=475），buy-hold +35.3%
```

# 12. Old-vs-New Metric Delta（Diagnostic Only）

```text
旧（E1/E2 修复前，3-seed pilot）: test 段起点 = retroactive replay 合成组合；
  test 首 step_cost 含 pre-test 费用（PPO F3 cost/init 假象 2.38%）。
新（修复后）: test 段起点 = val_end 现金+零持仓；成本只含段内（PPO cost/init 0.115%）。
net_return 序列变化：每段多 1 个 transition（test_start 执行日）→ stitched 步数 +4（471→475）。
```

此 delta 仅诊断说明，**不重跑 36 正式结果**；10-seed formal 将使用修复后 runner 生成新证据。

# 13. Git Commit

`GATE_4_EVAL_FIX` 提交 SHA：**`dcb1287`**

```text
src/china_etf/environment/portfolio_env.py   ← E1 reset(at_date)
src/china_etf/evaluation/rollout.py          ← E1/E2/E3（reset_at, 成本对账, 诊断, reconciliation）
src/china_etf/evaluation/walkforward.py      ← 段边界 reset_at + manifest
src/china_etf/evaluation/benchmark.py        ← exact mask + buy-hold（新）
src/china_etf/data/corporate_actions.py      ← pay_lag_bdays 参数化（sensitivity）
tests/test_eval_fix.py                       ← E1/E2/E3/mask 回归（新）
tests/test_walkforward.py                    ← t_next 语义更新
docs/features/FEATURE_ABLATION_SPEC.md       ← F0/F1/F2/F3 spec 冻结（新）
scripts/gate4_eval_fix.py                    ← 修复后 smoke（新）
scripts/gate4_settlement_sensitivity.py      ← fallback sensitivity（新）
docs/agent_state/CLAUDE_STATUS.yaml          ← 协议状态（新）
docs/review_packets/GATE_4_EVAL_FIX.md       ← 本 packet
```

---

## Approval Record

```yaml
gate: 4
handoff_id: G4_EVAL_FIX_001
packet: GATE_4_EVAL_FIX
status: READY_FOR_REVIEW

closed:
  E1_segment_accounting_reset: true
  E2_segment_cost_reconciliation: true
  E3_overlay_diagnostics_reconciliation: true
  benchmark_exact_test_mask: true      # 475=475
  executable_510300_buy_hold: true     # +35.3% (net, 1x cost, CA)
  fallback_paydate_sensitivity: true   # IMMATERIAL (baseline 0.024pp, RL 0)
  feature_ablation_spec_frozen: true   # F0/F1/F2/F3, runs not authorized

requested_review:
  - E1/E2/E3 correctness
  - benchmark mask parity
  - fallback sensitivity sufficiency
  - feature spec freeze
```

## END OF GATE 4 EVAL FIX
