# GATE 4 PRECHECK — Reviewer Response (REVISED SCOPE)
## FinRL-X 中国 ETF 项目 — Track A 境内 ETF 化后的 Walk-Forward 前审查

**Reviewed artifact:** `GATE_4_PRECHECK.md`  
**Review date:** 2026-08-08  
**Revision reason:** Track A 暂缓直接港股通 Instrument，避免 Gate 4 在 Southbound/QMT/HKD 细节上继续投入。  
**Decision:** `TARGETED_CORRECTIONS_REQUIRED_BEFORE_3_SEED_PILOT`  
**Gate 4 preparation:** `SUBSTANTIALLY_PASS`  
**3-seed pilot authorization:** `NOT YET AUTHORIZED`  
**10-seed formal run:** `NOT AUTHORIZED`

---

# 1. Reviewer Scope Decision — Track A 暂停直接港股通执行

Reviewer 接受新的工程收敛原则：

> **暂停直接港股通 Instrument，不暂停港股/美股资产暴露。**

当前唯一真正引入 HKEX / Southbound / HKD / QMT 港股能力依赖的 Core Instrument 是：

```text
HK_DIVIDEND → 03110.HK
```

而：

```text
HK_TECH  → 513180.SH
US_BROAD → 513500.SH
```

虽然底层分别暴露于香港科技和美国股票，但它们都是境内上市、人民币交易 ETF。

因此从 Gate 4 起：

```text
03110.HK
→ DEFER_TO_GATE6 / SECONDARY_TRACK
```

不再作为 Track A 主 Instrument。

---

# 2. Track A 新 Instrument Mapping

保持 11 个 Asset Slots 不变：

| Asset Slot | Track A Instrument |
|---|---|
| CN_LARGE | 510300 |
| CN_SMALL | 512100 |
| CN_DIVIDEND | 512890 |
| CHINEXT | 159915 |
| STAR | 588000 |
| HK_TECH | 513180 |
| **HK_DIVIDEND** | **513690** |
| US_BROAD | 513500 |
| GOLD | 518880 |
| CN_DURATION | 511260 |
| CASH_LIKE | 511360 |

即：

```text
HK_DIVIDEND:
03110.HK
→
513690.SH
```

---

# 3. 为什么不把 HK_DIVIDEND Slot 删除

原系统核心原则继续冻结：

```text
Asset Slot != ETF Instrument
```

RL 学的是：

```text
economic exposure
```

而不是具体代码。

因此不做：

```text
ActionDim 11 → 10
```

也不改：

```text
ObsDim
ActionTransform
RiskOverlay
TD3/SAC/PPO architecture
```

这样可以避免因为一个执行载体变化而重做 Gate 3。

新的映射正是 InstrumentSelector 分层设计的用途。

---

# 4. 513690 Track A 角色

513690 为：

```text
博时恒生港股通高股息率 ETF
上海证券交易所上市
人民币交易
```

官方资料显示：

```text
fund contract effective : 2021-05-11
SSE listing date        : 2021-05-20
trading currency        : CNY
```

其经济暴露与 03110 并非完全相同，但均可归于：

```text
HK high-dividend / value equity
```

因此可以作为 `HK_DIVIDEND` Asset Slot 的境内执行 wrapper。

---

# 5. 513690 ≠ 03110 — 必须做 Mapping Validation

不得在文档中写：

```text
513690 == 03110
```

二者跟踪指数和成分规则不同。

Track A 启动前只要求做一个轻量 wrapper-equivalence audit。

至少报告共同区间：

```text
daily return correlation
annualized volatility
max drawdown
annualized return
tracking / style divergence
```

建议再报告：

```text
rolling 120D correlation median / min
```

目标不是证明两者完全一致，而是证明：

> 513690 足以代表 `HK_DIVIDEND` 这一经济风险 Slot。

如果长期相关性明显失效，则重新评估 Slot wrapper，而不是改 RL action space。

---

# 6. Southbound 相关工作正式移出 Gate 4

以下项目不再阻塞 Gate 4：

```text
03110 QMT quote availability
03110 QMT order support
Southbound board lot
Southbound same-day reversal
HKD broker cash handling
Southbound broker commission
Southbound regulatory fee schedule
03110 dividend payment settlement
03110 Southbound eligibility history
```

已有研究成果不删除，保留为未来证据。

状态：

```text
03110 research data:
PARTIALLY VALIDATED / PRESERVE

03110 execution:
DEFERRED

Southbound execution:
DEFERRED_TO_GATE6
```

---

# 7. F1/F2 Southbound Fee Work — Preserve, But Remove From Gate 4 Critical Path

本轮已经做出的 Southbound fee schedule 与 conservative commission scenario 保留：

```text
HKEX trading fee
SFC levy
AFRC levy
settlement fee
ETF stamp-duty exemption
broker commission conservative scenario
```

但从现在开始：

```text
NOT REQUIRED FOR TRACK_A_GATE4
```

未来 Gate 6 或 Southbound secondary track 重新启用时再做 account verification。

不要继续为 Gate 4 深挖这些细节。

---

# 8. Observation Index Proof — APPROVED

当前 obs：

```text
0:88      per-asset exogenous
88:99     actual portfolio weights
99:104    global exogenous
```

因此：

```text
EXOGENOUS = 0..87 + 99..103
WEIGHTS   = 88..98
```

4 个显式测试已经证明：

```text
market/global normalized
weights unchanged
```

正式关闭。

无需 RL rerun。

---

# 9. C3 Research Return Reconstruction — APPROVED

本轮已经证明：

```text
QMT front
```

不适合作为稳定 Source of Truth。

正式研究序列继续采用：

```text
raw market price
+
point-in-time corporate actions
→ research total-return series
```

其中累计 split / unit-conversion + cash distribution 的修正方向批准。

状态：

```text
C3 = CLOSED
```

---

# 10. 03110 H1 — Preserve as Completed Research, No Longer Gate 4 Dependency

03110 官方分派：

```text
2025-09-24  1.60 HKD/unit
2025-03-25  0.27 HKD/unit
2024-09-24  1.36 HKD/unit
```

已足以证明：

```text
Sina qfq 对 03110 实际未处理 dividend
```

以及：

```text
raw + official distributions
```

才是正确研究方向。

这项工作保留，但从 Track A 移出。

状态：

```text
H1 = CLOSED_FOR_RESEARCH
H1 = NOT_REQUIRED_FOR_TRACK_A_EXECUTION
```

---

# 11. 新 BLOCKER-0：先完成 03110 → 513690 的 Track A Migration

3-seed pilot 前必须完成以下最小迁移：

```text
InstrumentSelector:
HK_DIVIDEND → 513690

data loader:
加载 513690 raw + corporate actions

features:
重新生成 HK_DIVIDEND research series

execution:
使用 513690 raw tradable prices

cost model:
使用 Mainland ETF cost path
```

不得让 Track A 中残留：

```text
03110 price
HKD/CNY
Southbound fee
HKEX calendar
```

---

# 12. Track A Effective Start 必须重新计算

不要直接继承原：

```text
effective_obs_start = 2022-05-18
```

因为替换 Instrument 后，11 个 Core 的 common-valid start 可能发生变化。

必须重新计算：

```text
raw common start
252-day warmup completion
first fully finite observation
last valid market row
last valid decision date
```

并报告：

```text
effective_obs_start
decision_days
```

如果仍然是 2022-05-18，可以保留，但必须由新 11-Instrument universe 重新证明。

---

# 13. 513690 数据最小验收

3-seed pilot 前只需要完成：

```text
raw OHLC availability
volume / turnover availability
corporate-action event coverage
finite features after warmup
no abnormal return spikes caused by adjustments
```

以及：

```text
513690 vs 03110 wrapper-equivalence audit
```

不需要展开 Southbound 交易模拟。

---

# 14. Corporate Action Accounting 仍然是 Gate 4 Blocker

即使去掉 03110，Corporate Action Accounting 不能删除。

因为境内 ETF 也会：

```text
cash dividend
unit conversion / fund-share conversion
```

因此仍然必须区分：

```text
research_total_return_series
execution_raw_price_series
corporate_action_stream
```

正式回测禁止用 adjusted synthetic price 成交。

---

# 15. Track A 双价格 Contract

正式 Gate 4：

```text
features / historical returns
→ total-return-consistent research series

orders / fills
→ raw market OHLC

portfolio valuation
→ raw prices + corporate-action accounting
```

Portfolio equity：

$$
V_t =
Cash_t
+
Receivable_t
+
\sum_i Quantity_{i,t} P^{raw}_{i,t}
$$

---

# 16. 境内 ETF Cash Distribution Accounting

现金分红：

### Ex-date

```text
create dividend entitlement / receivable
raw market price mechanically drops
portfolio equity should not suffer artificial loss
```

### Cash payment date

```text
receivable ↓
broker cash ↑
portfolio equity should not jump again
```

如果项目决定为了 Gate 4 简化成：

```text
ex-date accrual + receivable
```

这是推荐路径。

不要简单：

```text
ex-date directly add spendable cash
```

除非明确作为近似并证明对结果不敏感。

---

# 17. 建议使用境内 ETF 官方分红做 E2E Fixture

不再要求用 03110 做 Gate 4 E2E。

可以优先使用：

```text
513690
```

官方分红事件作为 fixture。

上海证券交易所公开资料显示 513690 2025 年存在现金分红，因此适合作为：

```text
ex-date
→ receivable
→ payment-date
```

的境内 ETF 端到端验证。

也可以增加 510300 作为第二个 fixture。

---

# 18. Corporate Action Required Tests

正式 pilot 前至少：

```text
test_execution_uses_raw_price_not_total_return_price

test_ex_dividend_creates_receivable

test_dividend_receivable_not_spendable_before_payment

test_dividend_payment_moves_receivable_to_cash_without_pnl_jump

test_ex_dividend_reward_has_no_artificial_loss

test_unit_conversion_preserves_portfolio_value

test_walkforward_uses_dual_price_contract
```

重点：

```text
全部可以在 Mainland ETF universe 内完成
```

不需要再依赖 03110。

---

# 19. BLOCKER-1：Walk-Forward 必须是 Train → Validation → Test

原 Execution Spec 冻结：

```text
Train
→ Validation
→ Test
```

当前 packet 是：

```text
Train
→ Test
```

需要修正。

即使 Gate 4 暂时不做 Optuna，Validation contract 仍必须存在，以避免未来：

```text
model selection
early stopping
hyperparameter choice
reward choice
```

污染 Test。

---

# 20. 推荐 Fold Structure

保留当前 4 个 OOS Test window 的思路。

建议每个原 Train window 最后：

```text
60 trading days
```

切成 Validation。

结构：

```text
F1: Train core ≈300D + Val 60D + Test ≈177D
F2: expanding Train + Val 60D + Test ≈177D
F3: expanding Train + Val 60D + Test ≈177D
F4: expanding Train + Val 60D + Test to data end
```

具体日期必须重新由：

```text
new 513690-based Track A trading calendar
```

计算。

不要沿用旧日期硬编码。

---

# 21. Fold Isolation Rules

每 fold：

```text
TRAIN
  fit scaler
  fit policy

VALIDATION
  transform only
  no scaler update
  no test use

TEST
  model/scaler fully frozen
```

下一 fold：

```text
refit scaler
retrain model
```

---

# 22. BLOCKER-2：t → t+1 Boundary 必须显式隔离

环境语义仍然是：

```text
decision at t close
→ execute at t+1 open
```

因此：

```text
Train last decision
```

不得使用：

```text
Validation first-day execution/mark
```

同理：

```text
Validation last decision
```

不得使用：

```text
Test first-day price
```

---

# 23. Segment Semantics

正式定义：

```text
calendar_rows
decision_rows
terminal_mark_row
```

例如：

```text
177 calendar rows
→ 176 valid decisions
```

Run manifest 不要把它们混称为 `days`。

至少增加：

```text
data_end
last_decision_date
last_execution_mark_date
```

---

# 24. Boundary Required Tests

```text
test_train_last_decision_does_not_use_validation_price

test_validation_last_decision_does_not_use_test_price

test_test_decision_count_equals_calendar_rows_minus_one

test_fold_segment_terminal_mark_semantics
```

---

# 25. BLOCKER-3：Training Budget 按 Fold 长度冻结

不推荐固定：

```text
12,000 timesteps / fold
```

因为 expanding fold 的 train length 不同，会导致：

```text
早期 fold 对同一历史重复训练更多遍
```

推荐：

```text
TRAIN_PASSES = 20
total_timesteps = train_decision_steps × TRAIN_PASSES
```

每个 run manifest 记录：

```text
train_decision_steps
train_passes
total_timesteps
```

如果 Agent 要坚持 fixed timesteps，需要在 packet 中给出 RFC 理由。

---

# 26. Baseline Architecture — PASS FOR PILOT

当前：

```text
Equal Weight
Risk Parity
Minimum Variance
Momentum
```

通过同一：

```text
TargetWeight
→ inverse ActionTransform
→ ActionTransform
→ RiskOverlay
→ execution
```

路径，方向正确。

增加：

```text
test_baseline_target_action_roundtrip
```

即可。

---

# 27. Gate 4 正式结果前仍需补的 Baselines

以下不阻塞 3-seed pilot：

```text
Mean-Variance
Trend + Risk Parity
```

但在最终：

```text
GATE_4_CORE_WALKFORWARD.md
```

之前应实现，或 RFC 说明删去理由。

正式 baseline set 建议：

```text
Equal Weight
Risk Parity
Minimum Variance
Mean-Variance
Momentum
Trend + Risk Parity
```

---

# 28. Normalized Evaluation Rollout — APPROVED

本轮发现 Gate 3 sanity eval 使用 raw observation 而 policy 训练在 normalized obs 上，这是正确发现。

Gate 4 新：

```text
evaluation/rollout.py
```

统一使用训练同构的 normalization path，批准。

建议增加：

```text
test_training_and_evaluation_share_same_observation_transform
```

旧 Gate 3 reward / weight 数字只能标记：

```text
SANITY APPROXIMATE
```

---

# 29. 当前 WalkForwardRunner Smoke — PASS AS MECHANICS

已有：

```text
EW smoke
TD3 2000-step smoke
save/load deterministic
fold-isolated scaler
normalized OOS rollout
```

作为 mechanics proof 足够。

不要解释：

```text
TD3 vs EW
```

收益差。

---

# 30. 新 Gate 4 主路径

新的执行路线冻结为：

```text
G4.P0
03110 → 513690 Track A migration

G4.P1
513690 data + wrapper-equivalence audit

G4.P2
recompute common valid horizon

G4.P3
Mainland-only corporate-action accounting

G4.P4
Train / Validation / Test + t+1 boundary

G4.P5
mechanics smoke

G4.P6
3-seed pilot

G4.P7
10-seed formal
```

---

# 31. 明确禁止继续投入的 Gate 4 工作

Claude Code 在当前阶段不要继续做：

```text
03110 QMT market-data debugging
03110 QMT order capability
HKD broker cash accounting
Southbound order simulator
Southbound lot/reversal behavior
Southbound broker-account fee audit
03110 live premium
Southbound tax/account settlement details
```

这些统一留到：

```text
Gate 6 / Secondary Southbound Track
```

---

# 32. Gate 4 Revised Decision Table

| Item | Decision |
|---|---|
| Observation index | PASS |
| QMT front deprecation | PASS |
| Research TR reconstruction | PASS |
| 03110 historical distribution research | PRESERVE / DEFER |
| Southbound execution | DEFER TO GATE 6 |
| Southbound fees | PRESERVE / NOT GATE4 BLOCKER |
| `HK_DIVIDEND → 513690` | **NEW REQUIRED MIGRATION** |
| 513690 wrapper-equivalence | **REQUIRED BEFORE PILOT** |
| Track A effective horizon | **RECOMPUTE** |
| Mainland corporate-action accounting | **BLOCKER** |
| Train/Validation/Test | **BLOCKER** |
| t→t+1 fold boundary | **BLOCKER** |
| training budget rule | **FREEZE BEFORE PILOT** |
| runner smoke | PASS |
| normalized rollout | PASS |
| 3-seed pilot | NOT YET AUTHORIZED |
| 10-seed formal | NOT AUTHORIZED |

---

# 33. Required Next Packet

请生成：

```text
docs/review_packets/GATE_4_PILOT_READY.md
```

包含：

## A. Scope migration

```text
HK_DIVIDEND → 513690
03110 → DEFERRED
```

## B. 513690 evidence

```text
official identity/listing
raw data availability
corporate actions
feature completeness
wrapper-equivalence vs 03110
```

## C. Recomputed Track A horizon

```text
effective_obs_start
data_end
last_decision_date
decision count
```

## D. Dual-price contract

```text
research total-return series
execution raw prices
corporate-action events
```

## E. Mainland ETF corporate-action accounting

## F. Train / Validation / Test folds

## G. t→t+1 boundary proof

## H. Training budget rule

## I. Baseline inverse-action roundtrip test

## J. train/eval normalization-equivalence test

## K. exact pytest output

## L. mechanics smoke

## M. revised compute budget

## N. git commit

---

# 34. Authorization After `GATE_4_PILOT_READY`

如果以上全部通过，下一步直接授权：

```text
4 folds
× TD3 / SAC / PPO
× seeds 42 / 2026 / 7
× 1x cost
```

即：

```text
36 RL trainings
```

目标只评估：

```text
runner stability
seed dispersion
fold dispersion
accounting integrity
runtime
```

不是最终算法排名。

---

# 35. Cost Sensitivity

3-seed pilot：

```text
1x only
```

10-seed formal：

```text
1x
2x
3x
```

但现在 Track A 已全部采用境内上市 ETF wrapper，因此成本敏感性统一从：

```text
Mainland ETF execution path
```

计算。

---

# 36. Pilot Stop Conditions

任何：

```text
negative cash
NaN/Inf
fold leakage
test scaler update
test-informed model choice
corporate-action artificial PnL
adjusted price used as execution fill
reward/accounting mismatch
RiskOverlay invariant failure
save/load nondeterminism
03110/HKD/Southbound state leaked into Track A
```

必须 STOP。

---

# 37. Carry-Forward Register

```text
C1 03110 same-day reversal:
DEFERRED → Gate 6

C2 Proxy PIT:
OPEN → before Track B use

C3 Research total-return reconstruction:
CLOSED

H1 03110 distribution research:
CLOSED / PRESERVED

F1 Southbound regulatory PIT:
PRESERVED / DEFERRED

F2 Southbound broker commission:
PRESERVED AS CONSERVATIVE SCENARIO / DEFERRED

M1 HK_DIVIDEND Track A wrapper migration:
NEW BLOCKER → before 3-seed pilot

M2 513690 wrapper-equivalence:
NEW BLOCKER → before 3-seed pilot

CA1 Mainland ETF corporate-action accounting:
BLOCKER → before 3-seed pilot

WF1 Validation segment:
BLOCKER → before 3-seed pilot

WF2 t+1 segment boundary:
BLOCKER → before 3-seed pilot

TB1 fold training-budget semantics:
FREEZE → before 3-seed pilot
```

---

# 38. Reviewer Approval Record

```yaml
gate: 4
packet: GATE_4_PRECHECK
revision: TRACK_A_MAINLAND_LISTED_ETF_ONLY
decision: TARGETED_CORRECTIONS_REQUIRED_BEFORE_3_SEED_PILOT
date: 2026-08-08

track_a_policy:
  direct_hkex_instruments: false
  southbound_execution: deferred_to_gate6
  action_dim: 11

instrument_mapping:
  HK_DIVIDEND:
    previous: 03110.HK
    track_a: 513690.SH
    previous_instrument_status: deferred

approved:
  observation_index: true
  c3_research_return: true
  qmt_front_deprecation: true
  normalized_rollout: true
  runner_mechanics: true

preserve_but_defer:
  03110_research_validation: true
  southbound_fee_schedule: true
  southbound_commission_scenario: true
  hkd_execution_accounting: true
  qmt_hk_order_capability: true

blockers_before_pilot:
  migrate_hk_dividend_to_513690: true
  validate_513690_wrapper: true
  recompute_track_a_horizon: true
  mainland_corporate_action_accounting: true
  train_validation_test_contract: true
  next_day_fold_boundary: true
  training_budget_semantics: true

permissions:
  patch_track_a_mapping: true
  fetch_validate_513690: true
  recompute_horizon: true
  implement_mainland_corporate_actions: true
  revise_walkforward_folds: true
  rerun_mechanics_smoke: true

  work_on_03110_execution: false
  work_on_southbound_gate4: false
  three_seed_pilot: false
  ten_seed_formal: false
  optuna: false
  theme_sleeve: false
  qmt_live: false

required_next_packet:
  GATE_4_PILOT_READY.md
```

---

# 39. Agent Next Instruction

```text
1. Preserve all passed Gate 0–3 and Gate 4 Precheck work.

2. Stop all direct 03110 / Southbound execution work for Gate 4.

3. Change Track A InstrumentSelector:
      HK_DIVIDEND → 513690.SH

4. Keep:
      ActionDim = 11
      existing asset-slot semantics
      existing RL architecture.

5. Load and validate 513690:
      raw prices
      liquidity
      corporate actions
      finite features.

6. Perform a lightweight 513690 vs 03110 wrapper-equivalence audit.

7. Recompute the 11-instrument common valid horizon and 252-day warmup.

8. Ensure Track A has no:
      HKD
      HKEX instrument
      Southbound fee
      03110 execution state.

9. Implement/verify Mainland ETF dual-price + corporate-action accounting.

10. Revise WalkForwardRunner to:
       Train → Validation → Test.

11. Prove t→t+1 transitions do not cross segment boundaries.

12. Freeze training budget:
       recommended fixed train passes.

13. Add required regression tests.

14. Run tests + mechanics smoke only.

15. Do NOT run 3-seed pilot yet.

16. Generate:
       docs/review_packets/GATE_4_PILOT_READY.md

17. STOP and return to Reviewer / ChatGPT.
```

---

## END OF REVISED REVIEWER RESPONSE
