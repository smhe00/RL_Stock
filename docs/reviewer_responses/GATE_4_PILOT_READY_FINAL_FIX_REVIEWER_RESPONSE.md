# GATE 4 PILOT READY — FINAL REVIEWER RESPONSE
## FinRL-X 中国 ETF 项目 — 3-Seed Walk-Forward Pilot Authorization

**Reviewed artifact:** `GATE_4_PILOT_READY_FINAL_FIX.md`  
**Review date:** 2026-08-08  
**Decision:** `GATE_4_3_SEED_PILOT = AUTHORIZED`  
**10-seed formal run:** `NOT YET AUTHORIZED`

---

# 1. Final Decision

本轮 P1 / P2 / P3 / P4 已达到 3-seed pilot 所需的 correctness threshold。

Reviewer 决定：

```text
GATE_4_PRECHECK = PASS
GATE_4_PILOT_READY = PASS
GATE_4_3_SEED_PILOT = AUTHORIZED
GATE_4_10_SEED_FORMAL = NOT YET AUTHORIZED
```

不再增加新的 pre-pilot blocker。

下一步允许正式执行：

```text
4 walk-forward folds
×
TD3 / SAC / PPO
×
3 seeds: 42 / 2026 / 7
×
1x base cost
```

共：

```text
36 RL training runs
```

并运行 deterministic baselines。

---

# 2. P1 Wrapper Return Audit — CLOSED

原 packet 中：

```text
03110 annualized return = 57.4%
```

的问题已经正确定位为：

```text
4.87-year cumulative return
被误标成 annualized return
```

当前指标已明确拆分：

```text
513690 cumulative total return       = +18.15%
03110 CNY cumulative total return    = +57.39%
03110 HKD cumulative total return    = +50.96%

513690 CAGR                          = 3.25%
03110 CNY CAGR                       = 9.09%

513690 arithmetic annualized mean    = 5.41%
03110 arithmetic annualized mean     = 10.98%
```

定义清晰。

批准。

---

# 3. 03110 Independent Sanity — CLOSED

Global X 官方截至 2026-07-28：

```text
Listed Class Since-Inception cumulative return
= +181.69%
```

当前重建：

```text
2013 inception → 2026-07-28
HKD total return
= +179.78%
```

差异：

```text
-1.91 percentage points
```

对于：

```text
raw market price + official cash distributions
```

相对于：

```text
official NAV total-return
```

这一独立重建方式，量级吻合度已经足以证明：

```text
no major dividend double count
no major FX double count
no catastrophic adjustment error
```

因此 P1 正式关闭。

---

# 4. FX Conversion Contract — APPROVED

当前：

```text
TR_CNY_t
=
TR_HKD_t
× FX_t / FX_0
```

并满足：

```text
1 + CNY cumulative return
≈
(1 + HKD cumulative return)
×
(1 + FX cumulative move)
```

这个归一化方式正确。

03110 已退出 Track A，因此这里只作为：

```text
wrapper audit / research cross-check
```

保留。

---

# 5. M2 `513690` Wrapper Decision — CLOSED

共同窗口：

```text
daily return corr              = 0.832
rolling 120D corr median       = 0.861
rolling 120D corr minimum      = 0.583
annualized tracking error      = 11.18%
```

Reviewer 认可：

```text
513690 != 03110
```

但两者足够属于：

```text
HK_DIVIDEND economic sleeve
```

因此：

```text
HK_DIVIDEND → 513690.SH
```

作为 Track A 境内 wrapper 正式批准。

不要求重新设计 Asset Slot 或 ActionDim。

---

# 6. P2 513690 Official Dividend Payment Dates — CLOSED

正式事件：

```text
2024:
record   2024-12-16
ex-date  2024-12-17
pay-date 2024-12-20

2025:
record   2025-12-16
ex-date  2025-12-17
pay-date 2025-12-22
```

已进入 CorporateActionEvent。

因此：

```text
ex-date → receivable
official pay-date → broker cash
```

正确。

原：

```text
ex_date + 2T
```

默认已删除。

P2 关闭。

---

# 7. Unknown Payment-Date Fallback — ACCEPTED FOR PILOT

当前：

```text
unknown pay-date
→ ex-date + 5 trading days
→ source = CONSERVATIVE_FALLBACK
```

允许用于 3-seed pilot。

但注意：

```text
+5T
```

并不能数学上保证永远晚于真实 pay-date。

因此在 pilot packet 中必须额外记录：

```text
corporate_action_events_total
official_pay_date_events
fallback_pay_date_events
fallback_events_in_test_windows
```

这不是 pilot blocker。

但在 10-seed formal 前：

> 如果仍有会影响 OOS test 的 fallback cash event，应优先补官方 pay-date，或明确做 settlement-delay sensitivity。

---

# 8. P3 512100 Unit Consolidation — CLOSED

官方事实：

```text
record date             = 2022-09-01
official consolidation  = 2022-09-02
consolidation ratio     = 0.36555
first resumed trading   = 2022-09-05
```

当前实现：

```text
action_type = UNIT_CONSOLIDATION
unit_factor = 0.36555
```

正确。

不再通过：

```text
1 + stockBonus + stockGift
```

推导 ETF 份额合并。

P3 关闭。

---

# 9. 2022-09-02 vs 2022-09-05 — Reviewer Interpretation

官方 Corporate Action 的法律/基金事件日期：

```text
official_effective_date = 2022-09-02
```

但：

```text
2022-09-02 ETF suspended
2022-09-05 first post-consolidation tradable raw-price bar
```

在当前：

```text
daily tradable-bar environment
```

中，把 quantity conversion 应用于：

```text
2022-09-05 pre-open
```

用于与 post-consolidation raw price 对齐，是合理的 backtest implementation。

因此这不阻塞 pilot。

但建议未来 schema 最终明确两个字段：

```text
official_effective_date = 2022-09-02
accounting_apply_date   = 2022-09-05
```

不要让：

```text
event date = 2022-09-05
```

在文档层被误解为官方合并日。

这是 metadata refinement，不需要 pilot 前再修改架构。

---

# 10. Real 512100 Regression — APPROVED

当前真实事件证明：

```text
qty_after = qty_before × 0.36555

post-consolidation raw price ≈ 2.7
pre-consolidation raw price  ≈ 1.0

portfolio value:
no ×2.76 false gain
no -63% false loss
```

并证明 fill 使用：

```text
post-consolidation raw tradable price
```

批准。

---

# 11. P4 Rows / Decisions Terminology — CLOSED

当前：

```text
track_a_calendar_rows       = 1015
track_a_max_full_transitions = 1014
```

与：

```text
segment decisions = calendar rows - 1
```

一致。

以后统一使用：

```text
calendar_rows
decision_steps
full_transitions
terminal_mark_row
```

不要再用模糊的：

```text
days
```

同时表示两种语义。

---

# 12. Track A Horizon — APPROVED

当前：

```text
effective_obs_start = 2022-06-06
data_end            = 2026-08-07
calendar_rows       = 1015
max_full_transitions = 1014
```

批准作为 Gate 4 Track A limited-history OOS evidence base。

结论仍必须标记：

```text
LIMITED-HISTORY REAL-INSTRUMENT OOS
```

不得宣传为长期 alpha 证明。

---

# 13. Corporate-Action Accounting — APPROVED FOR PILOT

正式 contract：

```text
Research:
raw + PIT corporate actions
→ total-return-consistent series

Execution:
raw market prices only

Accounting:
cash
+ dividend receivable
+ raw-price market value
```

批准。

继续冻结：

$$
V_t
=
Cash_t
+
DividendReceivable_t
+
\sum_i Qty_{i,t} P_{i,t}^{raw}
$$

---

# 14. Walk-Forward Structure — APPROVED

正式 pilot 使用：

```text
Train core
→ Validation 60D
→ Test
```

4-fold expanding。

Scaler：

```text
fit Train only
freeze Validation/Test
```

模型：

```text
Train only
Validation diagnostic
Test fully frozen
```

Gate 4 pilot 不允许根据 Test 调整任何参数。

---

# 15. Fold Boundary — APPROVED

已验证：

```text
Train last transition
does not consume Validation first price

Validation last transition
does not consume Test first price

Test:
decision_steps = calendar_rows - 1
```

通过。

---

# 16. Training Budget — APPROVED

正式 pilot 冻结：

```text
TRAIN_PASSES = 20
```

各 fold：

```text
F1: 299 × 20 = 5,980
F2: 477 × 20 = 9,540
F3: 655 × 20 = 13,100
F4: 833 × 20 = 16,660
```

同一个 fold 内：

```text
TD3
SAC
PPO
```

使用相同 Environment-step budget。

禁止 pilot 中临时改变训练步数。

---

# 17. Hyperparameters — FREEZE DURING PILOT

pilot 继续使用当前 Gate 3 / Gate 4 已冻结配置：

```text
TD3 / SAC / PPO
net_arch = [256,256]
```

不要：

```text
Optuna
manual tuning from pilot Test
per-algorithm cherry-picking
reward redesign
action redesign
```

---

# 18. 3-Seed Pilot — AUTHORIZED

正式授权：

```text
folds:
F1 / F2 / F3 / F4

algorithms:
TD3
SAC
PPO

seeds:
42
2026
7

cost:
1x base cost

train_passes:
20
```

共：

```text
4 × 3 × 3
=
36 RL trainings
```

---

# 19. Deterministic Baselines Required in the Same Packet

当前至少运行：

```text
Equal Weight
Risk Parity
Minimum Variance
Momentum
```

必须：

```text
same folds
same execution path
same corporate-action accounting
same 1x cost
```

Baseline 不需要按 seed 重复。

---

# 20. Pilot Metrics — Mandatory

每个：

```text
algorithm × seed × fold
```

必须记录：

### Performance

```text
cumulative net return
annualized return / CAGR
annualized volatility
Sharpe
Sortino
max drawdown
Calmar
```

### Portfolio behavior

```text
average turnover
total turnover
average number of active assets
max single-asset weight
HHI
```

### Risk overlay

```text
intervention rate
mean L1(raw, post-risk)
single-core cap hit rate
ChinaGrowth cap hit rate
```

### Execution/accounting

```text
transaction cost
cost / gross return
minimum broker cash
negative-cash count
corporate-action events applied
fallback pay-date event count
```

### Stability

```text
NaN/Inf count
save/load deterministic
episode completion
```

---

# 21. Aggregate Across Seeds Correctly

正式报告不能只展示：

```text
best seed
```

每个算法至少报告：

```text
median across seeds
mean across seeds
std across seeds
min / max across seeds
```

建议对核心指标：

```text
OOS CAGR
Sharpe
MaxDD
turnover
```

同时给：

```text
seed-level raw results
```

---

# 22. Aggregate Across Folds Carefully

不要把 4 个 fold 的 Sharpe 简单平均后称为：

```text
overall Sharpe
```

正式 pilot 建议同时给：

### Fold-level table

```text
F1 / F2 / F3 / F4
```

### Stitched OOS equity curve

按时间顺序拼接：

```text
F1 Test
→ F2 Test
→ F3 Test
→ F4 Test
```

然后在 stitched daily return series 上重新计算：

```text
overall OOS CAGR
overall OOS volatility
overall OOS Sharpe
overall OOS MaxDD
```

这是主要 overall metric。

---

# 23. Seed-Level Stitched OOS

对每个：

```text
algorithm × seed
```

分别生成：

```text
stitched OOS return series
```

然后比较 3 个 seeds。

不要先把 weights/returns 跨 seed 平均再计算 Sharpe。

---

# 24. Pilot Interpretation Rules

这个 pilot 的目的：

```text
reproducibility
seed sensitivity
fold sensitivity
runner robustness
algorithm pathological behavior detection
runtime calibration
```

不是决定最终 winner。

因此本轮禁止结论：

```text
TD3 is the best strategy
SAC should be deployed
PPO has proven alpha
```

允许结论：

```text
TD3 unstable across seeds
PPO has lower seed dispersion
SAC turnover is materially higher
all algorithms fail / pass sanity
```

---

# 25. Pilot Stop Conditions

任一情况出现：

```text
NaN/Inf
negative broker cash beyond numerical tolerance
fold leakage
Validation/Test scaler update
Test-informed tuning
adjusted price used as fill
corporate-action accounting discontinuity
unexpected ×2 / ×3 price/quantity PnL
RiskOverlay invariant failure
save/load mismatch
03110/HKD/Southbound execution leaks into Track A
```

必须：

```text
STOP
```

不要继续烧剩余 runs。

---

# 26. Early Stop Rule for Batch Execution

建议执行顺序：

```text
seed 42
all 4 folds
all 3 algorithms
```

先完成第一组。

若：

```text
12 trainings
```

机制全部正常，再跑：

```text
seed 2026
seed 7
```

这样如果存在系统性问题，只浪费约 1/3 compute。

这是 execution optimization，不改变实验设计。

---

# 27. No Algorithm-Specific Recovery

如果某算法某 seed：

```text
performance terrible
```

但：

```text
no numerical / accounting error
```

不能单独：

```text
change learning rate
increase steps
rerun until good
```

差结果也是正式 pilot evidence。

只有真正的：

```text
software / numerical failure
```

才能修复后整套一致重跑。

---

# 28. Cost Sensitivity — DEFER TO FORMAL

3-seed pilot：

```text
1x cost only
```

不要跑 2x / 3x。

正式 10-seed 时 primary protocol 推荐：

```text
train at 1x
evaluate same trained policy at:
1x
2x
3x
```

不默认重新训练 2x/3x policy。

---

# 29. Baseline Carry-Forward

以下仍不阻塞 3-seed pilot：

```text
Mean-Variance
Trend + Risk Parity
```

但必须在：

```text
GATE_4_CORE_WALKFORWARD
```

正式 10-seed 结论之前：

```text
implement
or
RFC-remove
```

---

# 30. Minor Carry-Forward: Payment-Date Fallback Inventory

pilot packet 中新增一个表：

| Field | Value |
|---|---:|
| total cash-dividend events | ... |
| official pay-date events | ... |
| conservative fallback events | ... |
| fallback events inside OOS tests | ... |

如果：

```text
fallback events inside OOS tests > 0
```

不自动判失败。

但必须列出：

```text
instrument
ex-date
fallback settle-date
cash/share
```

供正式 10-seed 前决定是否补官方数据。

---

# 31. Minor Carry-Forward: Official vs Accounting Date

512100 保存：

```text
official_effective_date = 2022-09-02
accounting_apply_date   = 2022-09-05
```

建议最终 schema 明确。

Pilot 可沿当前实现运行，不需要再停。

---

# 32. Required Next Packet

3-seed pilot 完成后输出：

```text
docs/review_packets/GATE_4_3_SEED_PILOT.md
```

必须包含：

```text
1. exact run manifest
2. git commit
3. package/version snapshot
4. fold definitions
5. training timesteps by fold
6. algorithm/seed run-completion matrix
7. baseline results
8. per-fold per-seed RL results
9. stitched OOS per seed
10. seed dispersion
11. turnover/cost
12. RiskOverlay diagnostics
13. corporate-action diagnostics
14. fallback pay-date inventory
15. runtime
16. failed/retried runs with reason
17. no-ranking disclaimer
18. pytest output
```

然后：

```text
STOP
```

返回 Reviewer。

---

# 33. Authorization Boundary

现在允许：

```text
3-seed pilot
```

现在仍不允许：

```text
10-seed formal run
20-seed run
Optuna
hyperparameter search
theme sleeve
Track B
Track C formal claim
QMT paper/live
Southbound execution
algorithm winner declaration
```

---

# 34. Approval Record

```yaml
gate: 4
packet: GATE_4_PILOT_READY_FINAL_FIX
decision: APPROVED_FOR_3_SEED_PILOT
date: 2026-08-08

final_fixes:
  P1_wrapper_return_audit: PASS
  P2_real_dividend_payment_dates: PASS
  P3_512100_unit_consolidation: PASS
  P4_rows_decisions_terminology: PASS

track_a:
  mainland_listed_etf_only: true
  action_dim: 11
  hk_dividend_wrapper: 513690.SH
  direct_hkex_execution: false

authorization:
  three_seed_pilot: true
  ten_seed_formal: false
  optuna: false
  theme_sleeve: false
  qmt_live: false

pilot:
  folds: 4
  algorithms:
    - TD3
    - SAC
    - PPO
  seeds:
    - 42
    - 2026
    - 7
  train_passes: 20
  cost: 1x
  rl_training_runs: 36

required_next_packet:
  GATE_4_3_SEED_PILOT.md
```

---

# 35. Agent Next Instruction

```text
1. Mark GATE_4_PILOT_READY_FINAL_FIX as APPROVED.

2. Freeze current code/config/data semantics.

3. Run the authorized 3-seed pilot only:

      4 folds
      × TD3 / SAC / PPO
      × seeds 42 / 2026 / 7
      × TRAIN_PASSES=20
      × 1x cost.

4. Run Equal Weight / Risk Parity / Minimum Variance / Momentum
   on identical OOS folds and execution/accounting path.

5. Execute seed 42 batch first.
   If all 12 RL trainings pass numerical/accounting invariants,
   continue seeds 2026 and 7.

6. Do not tune based on pilot Test results.

7. Record all required performance / turnover / cost /
   RiskOverlay / corporate-action / fallback-pay-date diagnostics.

8. Build stitched OOS return series separately for each
   algorithm × seed.

9. Do not select or declare a winning algorithm.

10. If any STOP condition occurs, stop the batch and report.

11. Generate:
      docs/review_packets/GATE_4_3_SEED_PILOT.md

12. STOP.

13. Return to Reviewer / ChatGPT.

Do NOT start 10-seed formal experiments.
```

---

## END OF REVIEWER RESPONSE
