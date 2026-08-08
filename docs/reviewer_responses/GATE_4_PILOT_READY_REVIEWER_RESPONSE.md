# GATE 4 PILOT READY — Reviewer Response
## FinRL-X 中国 ETF 项目 — 3-Seed Pilot 放行前最终审查

**Reviewed artifact:** `GATE_4_PILOT_READY.md`  
**Review date:** 2026-08-08  
**Decision:** `TARGETED_FINAL_CORRECTIONS_REQUIRED_BEFORE_3_SEED_PILOT`  
**Gate 4 preparation:** `PASS_WITH_FINAL_DATA_CORRECTIONS`  
**3-seed pilot authorization:** `NOT YET AUTHORIZED`  
**Expected next state after correction:** `AUTHORIZE_G4_3_3_SEED_PILOT`

---

# 1. Executive Decision

本 packet 已经完成绝大多数 Gate 4 pilot 前置工作。

以下项目批准：

```text
HK_DIVIDEND → 513690 migration
ActionDim = 11 unchanged
Track A Mainland-listed ETF only
dual-price architecture
corporate-action accounting architecture
Train → Validation → Test
t→t+1 fold boundary isolation
fold-isolated scaler
normalized train/eval path
fixed train-pass budget
runner mechanics smoke
102 tests
```

因此不需要再重构环境、action、risk、runner。

但是 Reviewer 独立复核后发现 3 个需要在正式 3-seed pilot 前关闭的 data/accounting correctness 项：

```text
P1  03110 wrapper-audit annualized return is implausible / likely miscomputed
P2  cash-dividend payment date cannot default to ex_date + 2T for formal Track A
P3  512100 real unit-conversion event must be represented as direct factor=0.36555,
    not inferred from stockBonus/stockGift semantics
```

另有一个文档口径修正：

```text
P4  "decision_days=1015" 实际更像 calendar rows；需与 rows-1 transition 语义统一
```

这些都是 targeted fixes。

---

# 2. M1 `HK_DIVIDEND → 513690` — APPROVED

当前：

```text
HK_DIVIDEND:
03110.HK → deferred
513690.SH → Track A wrapper
```

批准。

继续保持：

```text
Asset Slot != Instrument
ActionDim = 11
```

正确。

不要求重新跑 Gate 3。

---

# 3. Track A Mainland-Listed ETF Scope — APPROVED

新的 Track A：

```text
510300
512100
512890
159915
588000
513180
513690
513500
518880
511260
511360
```

全部为境内上市 ETF。

因此 Gate 4 不再需要：

```text
HKD broker cash
HKEX execution
Southbound commission
Southbound order capability
03110 QMT live quote
```

这些继续 defer Gate 6。

---

# 4. P1 BLOCKER — Wrapper Audit 中 `03110 annualized return = 57.4%` 明显异常

当前 packet 报告：

```text
common period: 2021-05-20 → 2026-08-07

513690 annualized return = +18.2%
03110  annualized return = +57.4%
```

这个结果不能直接接受。

Reviewer 复核 Global X 官方 performance：

```text
3110 listed class:
2021 calendar return = +7.09%
2022                 = -7.28%
2023                 = -3.29%
2024                 = +31.36%
2025                 = +34.88%

since inception cumulative return
(as of 2026-07-28) = +181.69%
```

Global X 另有官方研究指出：

```text
underlying index 10-year annualized return to Apr-2026 ≈ 11.5%
```

因此：

> `03110 annualized return = 57.4%` 不可能被直接解释成正常的几何年化收益。

这可能来自：

```text
annualization formula error
FX conversion error
dividend double counting
calendar/intersection misalignment
raw+TR reconstruction issue
```

---

# 5. Required Wrapper Audit Fix

重新运行：

```text
scripts/gate4_513690_wrapper_audit.py
```

必须明确输出以下不同指标，不要混用：

```text
cumulative_total_return
CAGR
arithmetic_mean_daily_return × 252
annualized_volatility
max_drawdown
daily_return_correlation
tracking_error
rolling_120D_corr_median
rolling_120D_corr_min
```

正式 `annualized_return` 建议统一定义为几何 CAGR：

```text
CAGR = (TR_end / TR_start) ** (365.2425 / elapsed_calendar_days) - 1
```

而不是：

```text
mean(daily_return) * 252
```

---

# 6. 03110 CNY Total-Return Conversion 必须再证明一次

如果 03110 audit 使用 CNY series：

```text
TR_CNY_t
=
TR_HKD_t
× FX_HKDCNY_t
/ FX_HKDCNY_0
```

不要：

```text
先把价格转换一次 FX
再把 dividend/TR index 再乘一次 FX
```

否则会 double-count currency effect。

重新 audit 后增加 assertion：

```text
03110 reconstructed total return
approximately matches
Global X official NAV total-return scale
```

不要求逐日完全相同，但：

```text
multi-year CAGR / cumulative return
```

必须在合理量级。

---

# 7. M2 Wrapper Decision 暂时改为 `CONDITIONALLY_PASS`

当前：

```text
corr = 0.832
rolling median = 0.861
rolling min = 0.583
```

本身足以支持：

```text
same economic sleeve, different wrapper/index
```

但是因为 03110 return series / annualization 存在异常，当前 M2 不能标记完全 CLOSED。

修复后：

如果：

```text
daily corr remains >= ~0.75
rolling median remains strong
```

并且总收益量级正常，

则：

```text
M2 = CLOSED
```

不需要追求 513690 与 03110 完全一致。

---

# 8. P2 BLOCKER — `pay_date = ex_date + 2T` 不能作为正式历史结算事实

当前 corporate-action loader：

```text
pay_date missing
→ ex_date + 2 trading days
```

Reviewer 复核 513690 官方公告：

### 2025 distribution

```text
record date : 2025-12-16
ex-date     : 2025-12-17
pay date    : 2025-12-22
```

即：

```text
ex-date → pay-date
= 3 trading days
```

而不是 +2T。

### 2024 distribution

```text
record date : 2024-12-16
ex-date     : 2024-12-17
pay date    : 2024-12-20
```

同样不是统一 +2T。

因此当前 F4 smoke：

```text
513690 2025-12-17 dividend
```

若使用 fallback，会让 dividend receivable 提前变成可用现金。

虽然对 portfolio equity 影响很小，但会对：

```text
available cash
rebalance feasibility
execution path
```

造成轻微 optimistic bias。

---

# 9. Required Pay-Date Policy

正式 Gate 4 Track A 推荐：

```text
known historical event
→ use official payment date

unknown payment date
→ NEVER settle earlier than confirmed date
```

对于历史回测，Track A 事件数量很有限，应尽量补齐真实：

```text
record_date
ex_date
pay_date
cash_per_share
```

不建议正式 pilot 继续使用：

```text
ex_date + 2T
```

作为默认历史事实。

---

# 10. Safe Fallback

如果个别事件确实拿不到 pay_date：

推荐：

```text
pay_date = UNKNOWN
receivable remains non-spendable
```

直到保守 fallback，例如：

```text
ex_date + 5 trading days
```

并：

```text
source = CONSERVATIVE_FALLBACK
```

这比提前给钱更安全。

但正式 Track A 中的重要 cash distributions 优先补官方日期。

---

# 11. Required Payment-Date Tests

增加：

```text
test_513690_2025_official_payment_date
test_513690_2024_official_payment_date
test_unknown_payment_date_never_settles_early
```

然后重跑 F4 mechanics smoke。

不需要 RL 训练。

---

# 12. Corporate Action Entitlement Semantics — APPROVED

当前顺序：

```text
settle payment
unit conversion
accrue dividend based on pre-open holdings
execute t+1 open orders
mark close
```

对于 cash dividend：

```text
pre-open ex-date holding
```

等价于前一个 record-date close 持仓，在当前 daily-only execution contract 下方向正确。

建议代码/文档显式写：

```text
eligible_qty = record-date-close position
```

而不是仅写：

```text
pre-trade qty
```

避免未来 intraday execution 扩展后语义混乱。

这不是 pilot blocker。

---

# 13. P3 BLOCKER — 512100 真实基金份额合并必须直接表示为 `0.36555`

当前 packet 写：

```text
unit_factor = 1 + stockBonus + stockGift
（送股/折算）
```

这个 contract 对普通股票：

```text
bonus shares / capitalization
```

可以成立。

但是不能自动代表 ETF 的：

```text
fund-unit consolidation
```

Reviewer 复核官方 512100 公告：

```text
record date      : 2022-09-01
unit merge date  : 2022-09-02
merge ratio      : 0.36555
```

即：

```text
old_qty
→ old_qty × 0.36555
```

而不是：

```text
1 + stockBonus + stockGift
```

---

# 14. 为什么这个问题是 Pilot Blocker

512100 的 2022-09-02 合并：

```text
位于当前 Track A 有效历史区间内
```

因此如果 event loader 没有把真实：

```text
unit_factor = 0.36555
```

送入 accounting，

会直接污染：

```text
F1 training data / portfolio accounting
```

而不仅是理论测试问题。

---

# 15. Required CorporateAction Schema

建议明确区分：

```text
CASH_DIVIDEND
STOCK_BONUS
UNIT_SPLIT
UNIT_CONSOLIDATION
```

例如：

```python
CorporateActionEvent(
    instrument="512100.SH",
    action_type="UNIT_CONSOLIDATION",
    effective_date="2022-09-02",
    unit_factor=0.36555,
    source="official_fund_announcement",
)
```

不要试图从：

```text
stockBonus
stockGift
```

猜 ETF consolidation ratio。

---

# 16. Required Real-Event Regression

必须增加：

```text
test_512100_20220902_real_unit_consolidation_factor

test_512100_20220902_quantity_changes_by_036555

test_512100_20220902_portfolio_value_continuity

test_512100_20220902_fill_uses_raw_post_conversion_price
```

最好直接用历史 raw data fixture。

---

# 17. Dual-Price Contract — APPROVED

当前：

```text
research returns
→ raw + corporate actions TR

orders / fills
→ raw OHLC

valuation
→ raw market value + receivable
```

批准。

这是正式 Gate 4 的正确 contract。

---

# 18. Portfolio Accounting Identity — APPROVED

继续冻结：

$$
V_t
=
Cash_t
+
DividendReceivable_t
+
\sum_i Qty_{i,t} P^{raw}_{i,t}
$$

测试：

```text
ex-dividend no artificial loss
payment no artificial gain
unit conversion value neutral
```

方向正确。

---

# 19. Train → Validation → Test — APPROVED

新的：

```text
Train core
→ Validation 60D
→ Test
```

结构批准。

Validation 当前不用于选参也没有问题。

它作为未来：

```text
model selection
early stopping
hyperparameter tuning
```

的隔离层即可。

---

# 20. Fold Boundary Semantics — APPROVED

当前已经明确：

```text
calendar rows
decision rows
terminal mark row
```

并测试：

```text
Train does not consume Val first-day price
Val does not consume Test first-day price
Test decisions = rows - 1
```

通过。

这一项正式关闭。

---

# 21. P4 DOCUMENTATION FIX — `decision_days=1015`

Packet 同时写：

```text
decision_days = 1015
```

但后面又正确写：

```text
121 test rows
→ 120 decisions
```

且：

```text
300 train rows
→ 299 train_decision_steps
```

因此全区间的：

```text
1015
```

更像：

```text
calendar_rows
```

而不是 complete `t→t+1` decisions。

请改成明确字段：

```text
track_a_calendar_rows = 1015
track_a_max_full_transitions = 1014
```

如果实际有别的终止语义，就按代码真实值填。

不要继续把 rows 和 decisions 混称。

这是文档/manifest correction，不阻塞代码架构。

---

# 22. Training Budget — APPROVED

当前：

```text
TRAIN_PASSES = 20

total_timesteps
=
train_decision_steps × 20
```

批准。

当前：

```text
F1 299 → 5,980
F2 477 → 9,540
F3 655 → 13,100
F4 833 → 16,660
```

比固定 12k/fold 更适合 expanding window。

正式 run manifest 继续保存：

```text
train_decision_steps
train_passes
total_timesteps
```

---

# 23. Baseline Roundtrip — APPROVED

```text
w
→ a = 2w-1
→ ActionTransform
→ w
```

对于 feasible baseline target 已验证。

批准。

---

# 24. Normalization Train/Eval Equivalence — APPROVED

当前已证明：

```text
same raw state
+ same train-fit scaler
→ same transformed observation
```

正式关闭 Gate 3 遗留的 eval normalization bug。

---

# 25. Mechanics Smoke — PASS, BUT RERUN AFTER P2/P3

当前 F4：

```text
EW
TD3 × 2 passes
save/load
Val/Test rollout
corporate action event
```

作为 runner smoke 通过。

但由于：

```text
513690 pay_date fallback
```

需要修复，因此更正后重新运行一次：

```text
mechanics smoke only
```

不需要再训练完整 20 passes。

---

# 26. 513690 Liquidity — Minor Documentation Improvement

Packet 当前给：

```text
latest-day volume / amount
```

建议换成 Gate 1 已冻结的：

```text
ADV20
ADV60
```

至少在正式 Gate 4 报告中出现。

不阻塞 3-seed pilot。

---

# 27. Cost Sensitivity — Important Carry-Forward Before 10 Seeds

Packet 当前估计：

```text
1x / 2x / 3x
→ ×3 retrain
```

Reviewer 不建议默认这么做。

正式 cost sensitivity 的主定义应该是：

```text
train policy under frozen base-cost environment
then re-evaluate same trained policy under:
1x
2x
3x execution cost
```

这样测试的是：

> 已训练策略对真实交易成本恶化的鲁棒性。

如果每个 cost scenario 都重新训练：

```text
2x-specific policy
3x-specific policy
```

那回答的是另一个问题：

> 策略在已知不同成本制度下重新优化后的最优结果。

两个实验都可以做，但不能混称。

---

# 28. Recommended Formal Cost Protocol

10-seed 正式阶段建议：

### Primary

```text
train = 1x cost
evaluate = 1x / 2x / 3x
NO retraining
```

### Optional secondary

```text
retrain at 2x / 3x
```

如果后来有研究价值再做。

因此当前：

```text
26–28h estimate
```

大概率过高。

这个问题不阻塞 3-seed pilot。

---

# 29. Mean-Variance / Trend+RiskParity — Carry-Forward

仍然按上一轮：

```text
not required for 3-seed pilot
```

但正式：

```text
GATE_4_CORE_WALKFORWARD
```

之前补齐或 RFC 删除。

---

# 30. Gate 4 Pilot-Ready Final Decision Table

| Item | Decision |
|---|---|
| 03110 → 513690 migration | PASS |
| ActionDim=11 | PASS |
| Mainland-only Track A | PASS |
| 513690 identity/data | PASS |
| wrapper correlation | CONDITIONALLY PASS |
| wrapper annualized return calculation | **BLOCKER P1** |
| Track A horizon | PASS, terminology fix |
| Dual-price contract | PASS |
| Dividend receivable accounting | PASS |
| Real dividend pay dates | **BLOCKER P2** |
| Unit conversion architecture | PASS CONCEPT |
| 512100 real 0.36555 event ingestion | **BLOCKER P3** |
| Train/Val/Test | PASS |
| t→t+1 boundary | PASS |
| Fixed train passes | PASS |
| Baseline roundtrip | PASS |
| Normalization equivalence | PASS |
| Mechanics smoke | PASS, rerun after fix |
| 3-seed pilot | **NOT YET AUTHORIZED** |
| 10-seed formal | NOT AUTHORIZED |

---

# 31. Required Final Correction Packet

不需要再生成大 packet。

请生成一个很短的：

```text
docs/review_packets/GATE_4_PILOT_READY_FINAL_FIX.md
```

只报告：

```text
1. corrected 513690/03110 wrapper audit
2. 03110 CNY TR sanity vs Global X official performance
3. exact official pay_date handling
4. 513690 2024/2025 payment-date regression
5. explicit 512100 2022-09-02 unit_factor=0.36555
6. real-event portfolio-value regression
7. calendar_rows vs decision_rows terminology fix
8. updated pytest count
9. rerun mechanics smoke
10. git commit
```

不要再扩 scope。

---

# 32. What Claude Code Should NOT Do

本轮不要：

```text
run 3 seeds
run 10 seeds
add new algorithms
add Optuna
revisit Southbound
revisit 03110 execution
change ActionTransform
change RiskOverlay
change neural networks
redesign folds
```

只做上述 3 个 correctness fix。

---

# 33. Expected Authorization

如果下一 packet 证明：

```text
P1 wrapper return fixed
P2 exact/conservative non-early payment dates fixed
P3 512100 real consolidation factor fixed
```

且 tests + smoke 通过，

Reviewer 下一步将直接：

```text
GATE_4_3_SEED_PILOT = AUTHORIZED
```

不再增加新的 pre-pilot 方法学工作。

---

# 34. Pilot Scope After Approval

```text
4 folds
×
TD3 / SAC / PPO
×
seeds = 42, 2026, 7
×
base 1x cost
```

即：

```text
36 RL trainings
```

外加 deterministic baselines。

Pilot 目标仍然只是：

```text
reproducibility
seed dispersion
fold dispersion
runtime
accounting integrity
runner stability
```

禁止做最终 winner conclusion。

---

# 35. Reviewer Approval Record

```yaml
gate: 4
packet: GATE_4_PILOT_READY
decision: TARGETED_FINAL_CORRECTIONS_REQUIRED_BEFORE_3_SEED_PILOT
date: 2026-08-08

approved:
  mainland_track_a_scope: true
  instrument_migration: true
  action_dim_11: true
  dual_price_contract: true
  accounting_architecture: true
  train_validation_test: true
  fold_boundary_isolation: true
  fixed_train_passes: true
  baseline_roundtrip: true
  normalization_equivalence: true
  runner_mechanics: true

final_blockers:
  P1_wrapper_return_audit: true
  P2_real_dividend_payment_dates: true
  P3_real_512100_unit_consolidation: true

documentation_fix:
  calendar_rows_vs_decision_rows: true

permissions:
  correct_wrapper_audit: true
  patch_payment_dates: true
  patch_unit_conversion_event: true
  rerun_tests: true
  rerun_mechanics_smoke: true

  three_seed_pilot: false
  ten_seed_formal: false
  optuna: false
  southbound_execution: false

required_next_packet:
  GATE_4_PILOT_READY_FINAL_FIX.md
```

---

# 36. Agent Next Instruction

```text
1. Preserve all current Gate 4 architecture.

2. Fix wrapper audit:
      distinguish CAGR from arithmetic annualized mean.
      validate 03110 CNY total-return scale against Global X official data.
      confirm no FX or dividend double count.

3. Patch historical cash-dividend pay dates:
      use official dates where available.
      no ex_date+2T early settlement in formal Track A.

4. Add official regressions:
      513690 2024 pay date
      513690 2025 pay date.

5. Patch 512100 real unit consolidation:
      effective date 2022-09-02
      unit_factor = 0.36555
      direct UNIT_CONSOLIDATION event.
      do not infer this ratio from stockBonus/stockGift.

6. Add real-event quantity/value/fill tests.

7. Rename global horizon counters:
      calendar rows
      full transitions / decision rows.

8. Rerun full pytest.

9. Rerun mechanics smoke only.

10. Generate:
      GATE_4_PILOT_READY_FINAL_FIX.md

11. STOP.

12. Return to Reviewer / ChatGPT.

Do NOT run the 3-seed pilot yet.
```

---

## END OF REVIEWER RESPONSE
