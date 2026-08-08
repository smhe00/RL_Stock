# GATE 2 Corrections — Reviewer Final Response
## FinRL-X 中国 ETF 项目 — Environment & Accounting 最终验收

**Reviewed artifact:** `GATE_2_CORRECTIONS.md`  
**Review date:** 2026-08-08  
**Decision:** `APPROVED_WITH_GATE3_PREFLIGHT_CONDITIONS`  
**Gate 2 status:** `APPROVED`  
**Gate 3 authorization:** `AUTHORIZED`  
**Gate 3 training permission:** `CONDITIONAL ON PREFLIGHT PASS`

---

# 1. Final Decision

本次 `GATE_2_CORRECTIONS.md` 已经实质关闭上一轮 Reviewer 定义的三个 Gate-3 blocker：

1. Southbound ETF fee model 的印花税错误已经修正；
2. Observation 的 current weights 已明确来自 actual holdings；
3. Environment 已增加 end-to-end transition test。

同时新增并通过了：

- overnight old-position timing；
- spread/slippage no-double-count；
- CostBreakdown base-currency convention；
- METHOD_RESEARCH / INSTRUMENT_BACKTEST / PAPER / LIVE mode；
- observation warm-up / finite check；
- real-data corporate-action adjustment checks。

因此：

```text
GATE_2 = APPROVED
GATE_3 = AUTHORIZED
```

不需要再生成一轮 Gate 2 correction packet。

但 Gate 3 在执行任何：

```text
TD3.fit()
SAC.fit()
PPO.fit()
```

之前，必须先完成本文件定义的：

```text
GATE_3_PREFLIGHT
```

如果任一硬性 Preflight 失败：

```text
STOP
DO NOT TRAIN
```

并回报 Reviewer。

---

# 2. Southbound ETF Fee Correction — PASS

当前修正：

```text
Stock Connect ETF stamp duty = 0
HKEX trading fee = 0.00565%
SFC levy = 0.00270%
AFRC levy = 0.00015%
```

方向正确。

对于 Gate 2 示例：

```text
notional = 300,000 HKD
commission = 15
trading fee = 16.95
SFC levy = 8.10
AFRC levy = 0.45
settlement = 6
spread = 30
slippage = 60
stamp duty = 0
```

得到：

```text
total = 136.50 HKD
```

测试已覆盖。

Reviewer 批准。

---

# 3. FeeRule Metadata — PASS, WITH CARRY-FORWARD F1

新增：

```text
FeeRule
effective_from
effective_to
source
applies_to
```

方向正确。

但当前报告写：

```text
MainlandETFCostModel / SouthboundETFCostModel
effective_from = 2026-08-08
```

需要注意：

> `2026-08-08` 是当前模型/审计快照日期，不一定是每条官方费率真正生效日期。

例如：

```text
HKEX 0.00565% trading fee
```

并不是 2026-08-08 才生效。

因此后续建议区分：

```text
rule_effective_from
```

与：

```text
model_observed_at
```

---

## 3.1 Gate 3 当前允许

Gate 3 RL Sanity 可以明确使用：

```text
CURRENT_FEE_SCENARIO
observed_at = 2026-08-08
```

因为 Gate 3 不做性能结论。

---

## 3.2 Gate 4 前必须完成 F1

在正式 Walk-Forward / Cost Stress 之前：

```text
F1 = POINT_IN_TIME_FEE_RULES
```

至少冻结：

- Mainland broker commission inclusion；
- Mainland exchange fee inclusion；
- Southbound broker commission；
- HKEX trading fee historical effective date；
- SFC levy historical effective date；
- AFRC levy historical effective date；
- settlement fee historical effective date；
- ETF stamp-duty exemption effective range。

不得使用“2026 当前费用”无声明地回测整个 2012~2026 历史。

---

# 4. Southbound Broker Commission — CARRY-FORWARD F2

用户明确给出的：

```text
ETF commission = 0.00005
```

目前主要作为境内 ETF 券商佣金基线。

`03110.HK` 的港股通实际券商佣金是否也是：

```text
0.00005
```

当前 packet 没有证明。

因此 Gate 3 / Method Research 可以使用：

```text
placeholder / current scenario
```

但必须标记：

```text
SOUTHBOUND_BROKER_COMMISSION
= UNKNOWN_PENDING_BROKER_FEE_AUDIT
```

不得在 Gate 4 / Gate 6 把 0.00005 当成已验证的港股通真实佣金。

---

# 5. Actual Holdings Observation — PASS

当前实现：

```text
actual position qty
× latest mark price
÷ portfolio value
```

形成 observation 中的：

```text
current weights
```

而不是：

```text
last target weights
```

这是正确的。

测试：

```text
test_observation_uses_actual_holdings_not_target
```

覆盖：

```text
target B ≈ 50%
B buy-disabled
actual B = 0
next obs B weight = 0
```

Reviewer 批准。

---

# 6. Cash 作为隐含残差 — ACCEPTED FOR V1

当前 observation 仍保持：

```text
104 dimensions
```

没有增加显式 broker cash feature。

现金可以由：

$$
w_{cash}^{broker}
=
1-\sum_iw_i^{actual}
$$

隐含得到。

V1 可以接受，不要求修改 Action/Observation contract。

但必须满足：

$$
Cash_t \ge 0
$$

并且：

$$
\sum_iw_i^{actual}\le1+\epsilon
$$

这将在 Gate 3 Preflight 中强制验证。

---

# 7. End-to-End Transition — PASS

新测试已经覆盖：

```text
action
→ target
→ buy-disabled
→ lot rounding
→ fill
→ transaction cost
→ accounting
→ actual holdings
```

并验证：

```text
rejected trade has no fee
cost only on filled quantity
lot size is respected
V = cash + Σ market value
```

Reviewer 批准。

---

# 8. Overnight Timing — PASS

新增测试证明：

```text
Day t close
→ old position survives overnight
→ Day t+1 open PnL occurs
→ then rebalance
```

这是进入 RL 前非常关键的 timing invariant。

Reviewer 批准。

---

# 9. Execution Friction Convention — PASS

冻结：

```text
Fill.price = reference execution price
```

而：

```text
spread
slippage
impact
```

全部通过：

```text
CostBreakdown
```

显式扣除。

这是当前最适合研究阶段的设计，因为便于：

- attribution；
- 1x/2x/3x stress；
- no-double-count testing。

Reviewer 批准。

---

# 10. Cost Currency Convention — PASS

冻结：

```text
CostBreakdown fields = Base Currency
```

对于 Southbound：

```text
local HKD cost
→ fx_to_base
→ CNY CostBreakdown
```

方向正确。

后续不要出现：

```text
some CostBreakdown fields in HKD
some in CNY
```

---

# 11. EnvironmentMode — PASS

当前：

```text
METHOD_RESEARCH
INSTRUMENT_BACKTEST
PAPER
LIVE
```

划分是必要的。

Reviewer 批准。

---

## 11.1 Gate 3 推荐模式

Gate 3 的第一个 TD3/SAC/PPO Sanity Run 建议统一：

```text
EnvironmentMode = METHOD_RESEARCH
```

目的：

> 先验证算法能否正确学习 weight allocation semantics。

不要在第一次 RL sanity 中混入：

```text
historical PremiumGuard approximation
QMT broker execution
Southbound broker unknowns
```

这些属于后续层。

---

# 12. PremiumGuard — PASS

当前：

```text
METHOD_RESEARCH / INSTRUMENT_BACKTEST:
realtime PremiumGuard disabled
```

```text
PAPER / LIVE:
IOPV missing/stale → fail closed
```

逻辑成立。

但必须在所有 experiment manifest 中记录：

```text
environment_mode
premium_guard_mode
```

避免未来看到 US_BROAD 的回测结果时无法判断是否使用了 PremiumGuard。

---

# 13. Observation Warm-Up — PASS

当前：

```text
min_history = 252
```

且：

```text
find first all-finite observation
```

比：

```text
NaN → 0
```

安全得多。

Reviewer 批准。

---

# 14. IMPORTANT：生产 Environment 禁止“缺锚点就补 0”

报告提到：

```text
缩略测试宇宙缺 GOLD/CN_DURATION anchor 时
使用有限占位 0
```

这只能存在于：

```text
unit-test fixture
synthetic reduced-universe test
```

正式 11-Core Environment 中：

```text
missing required anchor feature
```

必须：

```text
RAISE / INVALID DATA
```

不得补 0。

Gate 3 Preflight 必须验证实际 11-Core observation 没有这种 fallback。

---

# 15. C3 Adjustment PIT — SUBSTANTIALLY PASS

真实 QMT corporate-action event：

```text
510300: 8/8
512890: 1/1
511260: 4/4
515070: 1/1
```

共：

```text
14/14
```

已经能够用：

```text
raw close + event table
```

恢复合理 total-return movement。

这证明算法方向正确。

---

# 16. C3 Remaining Requirement

当前验证仍然主要是：

```text
QMT raw/events
vs
QMT front
```

即同一数据体系内验证。

因此：

```text
C3 = PARTIALLY_RESOLVED
```

保持正确。

---

## 16.1 Gate 3 Preflight 需要进一步报告

当前 tolerance：

```text
|TR - front| < 1%
```

太宽。

Gate 3 必须输出：

```text
max_abs_return_diff
median_abs_return_diff
event-by-event diff
```

不要只给：

```text
14/14 < 1%
```

建议正常接受目标：

```text
max_abs_return_diff <= 0.0001
```

即 1bp。

如果高于 1bp：

```text
STOP AND EXPLAIN
```

除非能明确证明来自：

- price rounding；
- official distribution rounding；
- provider adjustment convention。

---

# 17. Gate 3 PRE-FLIGHT P1 — CASH SOLVENCY

这是 Gate 3 训练前新增的最重要测试。

Action softmax：

$$
\sum_iw_i^{target}=1
$$

同时存在：

```text
commission
spread
slippage
lot rounding
```

所以 OrderGenerator 必须保证：

$$
Cash_{after}\ge0
$$

并保留执行现金缓冲。

---

## 17.1 Required tests

必须新增：

```text
test_no_negative_cash_after_max_investment
test_rebalance_sells_before_buys
test_buy_sizing_reserves_transaction_cost
```

至少测试：

### Case A

```text
1,000,000 cash
target = 100% one ETF
nonzero fees
```

结果：

```text
cash >= 0
no leverage
```

### Case B

```text
currently 100% A
target 100% B
```

必须：

```text
sell A
→ receive cash
→ buy B
```

不能因为先买 B 而产生：

```text
negative cash
or unnecessary rejection
```

### Case C

actual holdings：

$$
\sum_iw_i^{actual}\le1+\epsilon
$$

---

# 18. Broker Cash Buffer

EXECUTION_SPEC 原始设计中：

```text
broker_cash_buffer_pct = 0.01
```

Gate 3 Preflight 必须确认 Environment 是否真正使用该概念。

允许两种实现：

## A

```text
investable_value = portfolio_value × (1 - cash_buffer)
```

## B

使用 cost-aware sizing 动态保留足够现金。

无论采用哪种：

> 不允许 long-only/no-leverage environment 出现负现金。

如果修改既有 1% buffer：

```text
RFC required
```

---

# 19. Gate 3 PRE-FLIGHT P2 — CNY BASE-CURRENCY RETURN

Gate 3 会开始接入真实 11-Core 数据。

其中：

```text
03110.HK
```

以：

```text
HKD
```

报价。

因此对中国投资者：

$$
R_{portfolio,CNY}
\ne
R_{3110,HKD}
$$

必须包含 FX。

---

## 19.1 Gate 3 Requirement

对于：

```text
HK_DIVIDEND
```

研究序列必须明确是：

```text
CNY total-return series
```

例如：

$$
V^{CNY}_t
=
P^{HKD}_t
\times
FX_{HKD/CNY,t}
$$

然后计算：

$$
R_t^{CNY}
=
\frac{V_t^{CNY}}{V_{t-1}^{CNY}}-1
$$

---

## 19.2 允许的替代

如果 Gate 3 为简化而使用：

```text
境内 CNY-listed HK dividend ETF
```

作为 research instrument，

也可以。

但 Run Manifest 必须明确：

```text
HK_DIVIDEND research instrument
```

不能默默换标的。

---

# 20. Gate 3 PRE-FLIGHT P3 — MULTI-MARKET DECISION TIMESTAMP

A股收盘：

```text
15:00 CST
```

HKEX 正常交易日收盘晚于 A 股。

如果 Gate 3 使用：

```text
03110.HK day-t close
```

作为 feature，

那么策略的 canonical decision timestamp 必须定义在：

```text
所有当日输入市场数据已经 available 之后
```

例如：

```text
post-HK-close EOD decision
```

然后：

```text
next-session execution
```

这样不会出现：

```text
使用16:00港股数据
却假设15:00已经做出动作
```

的隐藏 look-ahead。

---

# 21. Gate 3 PRE-FLIGHT P4 — RESEARCH INSTRUMENT MAPPING

Gate 3 每个 run manifest 必须打印：

| Asset Slot | Research Instrument / Series | Currency | Source | Start |
|---|---|---|---|---|
| CN_LARGE | ... | CNY | QMT | ... |
| CN_SMALL | ... | CNY | QMT | ... |
| CN_DIVIDEND | ... | CNY | QMT | ... |
| CHINEXT | ... | CNY | QMT | ... |
| STAR | ... | CNY | QMT | ... |
| HK_TECH | ... | CNY | QMT | ... |
| HK_DIVIDEND | ... | CNY-normalized | Sina/QMT-alternative | ... |
| US_BROAD | ... | CNY | QMT | ... |
| GOLD | ... | CNY | QMT | ... |
| CN_DURATION | ... | CNY | QMT | ... |
| CASH_LIKE | ... | CNY | QMT | ... |

如果某 Slot 缺失：

```text
DO NOT DROP IT SILENTLY
```

必须：

```text
STOP
```

或走批准的 Instrument mapping。

ActionDim 必须保持：

```text
11
```

---

# 22. Gate 3 PRE-FLIGHT P5 — ACTUAL 11-CORE OBSERVATION

在训练前用真实数据生成至少：

```text
100 consecutive observations
```

必须验证：

```text
shape = (104,)
all finite
no fallback anchor zeros
no slot silently missing
actual weights valid
```

并输出：

```text
min
max
mean
std
```

检查是否有明显 scale pathology。

---

# 23. Fee Scenario Manifest

Gate 3 不是正式 performance test。

所以允许使用：

```text
CURRENT_FEE_SCENARIO_2026
```

但 run manifest 必须写：

```yaml
fee_scenario:
  name: CURRENT_FEE_SCENARIO_2026
  point_in_time_historical: false
  mainland_broker_commission: 0.00005
  mainland_exchange_fee_inclusion: unknown
  southbound_broker_commission: placeholder_or_unknown
```

这样未来不会把 Gate 3 结果误认为严格现实历史成本结果。

---

# 24. Gate 3 RL Sanity Scope

完成全部 Preflight 后，允许：

```text
one fold
one seed
PPO
SAC
TD3
Equal Weight baseline
```

算法必须：

```text
same data
same environment
same action transform
same reward
same cost scenario
same seed where meaningful
```

目标仅是：

> RL pipeline correctness and policy behavior sanity。

---

# 25. Gate 3 禁止

```text
NO Optuna
NO 10/20 seed study
NO model winner conclusion
NO performance publication
NO Theme Sleeve
NO dynamic InstrumentSelector ranking
NO QMT live orders
NO broker paper orders
```

---

# 26. Gate 3 必须报告的 Policy Sanity Metrics

不仅要看 return。

每个 TD3/SAC/PPO 都必须报告：

```text
training reward curve
NaN / inf count
action mean
action std
asset weight mean
asset weight max
weight concentration
HHI
daily turnover
fraction of steps with >50% single asset
cash residual
number of rejected trades
cost / gross pnl
```

检查 policy 是否：

```text
collapse to one asset
always equal-weight
always cash-like
hyper-turnover
NaN/unstable
```

---

# 27. Equal-Weight Baseline

Gate 3 必须使用：

```text
same Environment transition
same cost accounting
same next-open execution
same lot rounding
same tradability
```

而不是单独用另一个简单 vectorized return formula。

否则无法作为 Environment sanity baseline。

---

# 28. Carry-Forward Register

## C1 — 03110 same-day reversal

```text
status: OPEN
deadline: before Gate 6
```

不影响 Daily Gate 3。

---

## C2 — Proxy PIT audit

如果 Gate 3：

```text
actual ETF only
```

则 C2 可继续开放。

如果 Gate 3 使用任何 proxy：

```text
C2 must close before training
```

---

## C3 — Adjustment PIT

```text
status: PARTIALLY_RESOLVED
```

Gate 3 Preflight 完成：

```text
actual real-data loader integration
+
event diff report
```

后可关闭或继续标注 minor provider risk。

---

## F1 — Historical Fee Rules

```text
status: OPEN
deadline: before Gate 4
```

---

## F2 — Southbound Broker Commission

```text
status: OPEN
deadline: before Gate 4 realistic cost comparison / before Gate 6 execution
```

---

# 29. Gate 3 Review Packet

完成后生成：

```text
docs/review_packets/GATE_3_RL_SANITY.md
```

必须包含：

## 1. Gate 3 Preflight

### P1 Cash solvency
### P2 CNY base-currency return
### P3 Multi-market timestamp
### P4 Slot→Research Series mapping
### P5 100 real observations finite check
### C3 corporate-action exact diff

---

## 2. Data interval

```text
start
end
number of days
warmup
```

---

## 3. Environment mode

```text
METHOD_RESEARCH
```

或其他已解释模式。

---

## 4. Algorithm config

```text
TD3
SAC
PPO
```

exact config。

---

## 5. Training result

只做 sanity。

---

## 6. Weight/action diagnostics

---

## 7. Turnover / Cost

---

## 8. Equal Weight comparison

仅用于 sanity，不做 winner 结论。

---

## 9. Save / Load

必须证明：

```text
same observation
→ loaded model produces same deterministic action
```

在算法允许 deterministic inference 的语义下。

---

## 10. Exact pytest output

---

## 11. Warnings / anomalies

---

## 12. Carry-forward status

---

## 13. Git commit

---

# 30. Gate 3 STOP Condition

完成 Gate 3 后：

```text
STOP-GATE REACHED
```

必须交回 Reviewer。

在 Gate 3 批准之前：

```text
DO NOT START WALK-FORWARD
DO NOT START MULTI-SEED
DO NOT START HYPERPARAMETER SEARCH
```

---

# 31. Reviewer Final Assessment of Gate 2

Gate 2 当前已经具备了让 RL 开始“试运行”的基本资格。

尤其关键的是，以下容易制造假 Alpha 的问题已经被提前处理：

- same-close future fill；
- target weight masquerading as actual holding；
- rejected trade fee；
- lot rounding；
- transaction friction double counting；
- overnight PnL disappearance；
- stale/missing IOPV live buying；
- ETF distribution / share-conversion fake jumps；
- HK cost currency ambiguity。

这已经明显优于许多论文级 DRL trading environment。

下一阶段最大的风险已经从：

> “环境会计是否错”

转移为：

> “真实 11-Core 数据进入环境后，时间、币种、现金和 feature scaling 是否仍保持这些不变量”。

因此正式批准进入 Gate 3，但要求先通过 Preflight。

---

# 32. Reviewer Approval Record

```yaml
gate: 2
decision: APPROVED_WITH_GATE3_PREFLIGHT_CONDITIONS
date: 2026-08-08

gate3:
  authorized: true
  training_authorized_after_preflight: true

resolved:
  southbound_etf_stamp_duty_bug: true
  afrc_levy: true
  actual_holdings_state: true
  end_to_end_transition: true
  overnight_timing: true
  friction_double_count: true
  cost_currency_contract: true
  environment_modes: true
  warmup_finite: true

gate3_preflight:
  cash_solvency: required
  sell_before_buy: required
  fee_aware_buy_sizing: required
  hkd_to_cny_research_return: required
  multi_market_decision_timestamp: required
  slot_series_manifest: required
  real_104d_obs_validation: required
  corporate_action_diff_precision: required

carry_forward:
  C1_03110_same_day_rule: before_gate6
  C2_proxy_PIT: before_proxy_use
  C3_adjustment_independent_validation: real_data_gate3_or_later
  F1_historical_fee_rules: before_gate4
  F2_southbound_broker_commission: before_gate4_or_gate6

permissions:
  enter_gate3_preflight: true
  train_td3_sac_ppo_after_preflight: true
  optuna: false
  multiseed: false
  walk_forward: false
  theme_sleeve: false
  qmt_live_orders: false
```

---

# 33. Agent Next Instruction

```text
1. Mark Gate 2 APPROVED.
2. Update CODEX_AGENT_STATUS.md.
3. Enter Gate 3.
4. Run Gate 3 Preflight P1-P5 before any model fit.
5. If any Preflight fails: STOP, do not train.
6. If all Preflight passes:
      run one-fold / one-seed TD3/SAC/PPO + Equal Weight sanity.
7. Generate GATE_3_RL_SANITY.md.
8. STOP.
9. Return packet to Reviewer / ChatGPT.
```

---

## END OF REVIEWER RESPONSE
