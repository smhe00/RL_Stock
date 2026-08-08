# GATE 2 Reviewer Response
## FinRL-X 中国 ETF 项目 — Environment & Accounting 审核意见

**Reviewed artifact:** `GATE_2_ENVIRONMENT.md`  
**Review date:** 2026-08-08  
**Decision:** `REVISIONS_REQUIRED_BEFORE_GATE_3`  
**Gate 2 implementation quality:** `SUBSTANTIALLY_CORRECT`  
**Gate 3 authorization:** `NOT YET AUTHORIZED`

---

# 1. Reviewer Decision

Gate 2 的主体工程方向是正确的，已经完成了本阶段最关键的基础设施：

- canonical `TargetAssetWeights` contract；
- 11 维固定 Action Space；
- 104 维 observation 初版；
- Portfolio Accounting；
- MockBroker；
- CostModel skeleton；
- Tradability；
- PremiumGuard fail-closed；
- FX skeleton；
- t → t+1 execution timing；
- no-lookahead feature test；
- adjustment / distribution PIT test；
- 29 个 pytest 测试；
- synthetic 3-step environment smoke trajectory。

这些内容说明项目已经从“架构设计”进入了真正可验证的交易环境工程阶段。fileciteturn26file0

但当前仍有 **3 个 Gate-3 blocker**，其中一个是确定的交易规则错误，另外两个涉及 RL Environment transition 的金融语义。

因此当前状态：

```text
GATE_2_STATUS = REVISIONS_REQUIRED_BEFORE_GATE_3
```

Agent 必须生成：

```text
docs/review_packets/GATE_2_CORRECTIONS.md
```

完成本文件要求后再回传 Reviewer。

在此之前：

```text
DO NOT START TD3/SAC/PPO RL SANITY
```

---

# 2. BLOCKER-1：Southbound ETF 印花税实现错误

Gate 2 示例当前对 03110.HK 计算：

```text
tax (印花税 0.1%) = 300 HKD
```

这是错误的。

上交所当前官方“港股通交易税费”页面明确写明：

> 港股通 ETF 的交易暂不征收印花税。

因此对于：

```text
03110.HK
```

应：

```text
stamp_duty = 0
```

而不是：

```text
stamp_duty = 0.001 × notional
```

---

# 3. Southbound CostModel 还漏了 AFRC Levy

当前 Gate 2 示例包含：

```text
HKEX trading fee = 0.00565%
SFC trading levy = 0.0027%
```

但漏掉：

```text
AFRC transaction levy = 0.00015%
```

当前官方港股通税费为：

```text
Trading Fee            0.00565%
SFC Trading Levy       0.00270%
AFRC Transaction Levy  0.00015%
Stamp Duty             0 for Stock Connect ETF
```

投资者赔偿征费 / 特别征费目前暂不征收。

---

# 4. 03110 Cost Example 应修正

沿用 Gate 2 自己的示例假设：

```text
notional = 300,000 HKD
broker commission = 15 HKD
spread = 30 HKD
slippage = 60 HKD
share settlement fee = 6 HKD   # 暂沿用当前 skeleton assumption
```

则：

```text
HKEX trading fee:
300,000 × 0.00565% = 16.95

SFC levy:
300,000 × 0.0027% = 8.10

AFRC levy:
300,000 × 0.00015% = 0.45

Stamp duty:
0

Settlement:
6.00

Broker commission:
15.00

Spread:
30.00

Slippage:
60.00
```

在上述 skeleton assumptions 下：

```text
total = 136.50 HKD
```

而不是当前模型中包含 300 HKD 印花税的结果。

### 注意

`share settlement fee = 0.002%, min 2 / max 100 HKD`

仍应在 Gate 6 用**当时最新中国结算规则**再次冻结。

Gate 2 现在需要做的是：

```text
stamp_duty_for_southbound_etf = 0
AFRC levy = included
```

---

# 5. 必须增加 Fee Source Metadata

交易费用不能只写数字。

建议：

```python
@dataclass(frozen=True)
class FeeRule:
    name: str
    rate: float | None
    minimum: float | None
    maximum: float | None
    currency: str
    effective_from: date
    effective_to: date | None
    source: str
    applies_to: tuple[str, ...]
```

至少要求：

```text
Mainland ETF
Southbound ETF
```

的费率配置带：

```text
effective_date
source
```

避免以后费率变化后历史回测被当前规则污染。

---

# 6. Mainland ETF Exchange Fee：当前不是 Gate 2 blocker，但必须避免双算

Gate 2 当前：

```text
exchange_fee = 0.0 (待核实)
```

上交所当前基金竞价交易经手费标准为：

```text
ETF / LOF / closed-end fund:
0.004% both sides
```

货币 ETF / 债券 ETF 暂免。

但这里必须注意：

> 交易所经手费是“会员等交上交所”的费用。

用户实际给定的：

```text
broker ETF commission = 0.00005
```

是否已经包含交易所经手费，取决于券商实际收费口径。

因此 **绝对不能简单再加 0.004%**，否则可能 double count。

Gate 2 Correction 只需要加入：

```yaml
broker_commission:
  rate: 0.00005
  includes_exchange_handling_fee: UNKNOWN_PENDING_BROKER_FEE_AUDIT
```

正式 Gate 4 performance backtest 前必须冻结。

---

# 7. BLOCKER-2：Environment 必须证明使用“实际持仓权重”，不是 target weights

Observation 当前定义：

```text
8 × 11 features
+ 当前权重 11
+ global 5
```

但 Gate Packet 没有证明：

```text
current weights
```

究竟来自：

```text
TargetAssetWeights
```

还是：

```text
actual post-fill portfolio holdings
```

这对 RL 非常关键。

---

# 8. 正确状态必须是 Actual Portfolio State

RL 应观察：

$$
s_t=
[X_t,w_t^{actual},cash_t]
$$

而不是：

$$
[X_t,w_t^{target}]
$$

因为以下情况都会产生：

$$
w^{actual}\ne w^{target}
$$

- lot-size rounding；
- buy-disabled；
- sell-only；
- premium block；
- insufficient cash；
- min-order threshold；
- partial fill；
- market closed；
- failed order。

如果 Observation 仍把 target 当 current position：

> Agent 会以为自己持有了实际上没有成交的资产。

这会造成严重的 POMDP / accounting inconsistency。

---

# 9. Required Test：Target ≠ Actual

必须增加一个明确测试：

```text
test_observation_uses_actual_holdings_not_target
```

建议场景：

```text
Portfolio = 1,000,000

Target:
  Asset A = 50%
  Asset B = 50%

Asset B:
  BUY_DISABLED

Result:
  A actually purchased
  B remains 0

Next observation:
  weight_A = actual market value / NAV
  weight_B = 0
  cash = residual actual cash
```

必须断言：

```text
obs_current_weight_B != target_weight_B
obs_current_weight_B == actual_weight_B
```

---

# 10. BLOCKER-3：需要 Environment End-to-End Transition Test

Gate 2 当前大部分测试是：

```text
Accounting
Cost
Tradability
Premium
OrderGenerator
Feature
```

各模块独立测试。

这是好的，但还不够。

在进入 RL 前必须验证整条 transition：

```text
raw action
  ↓
softmax
  ↓
TargetAssetWeights
  ↓
Instrument selection
  ↓
Tradability / Premium
  ↓
OrderGenerator
  ↓
lot rounding
  ↓
MockBroker fill/reject
  ↓
Cost
  ↓
PortfolioAccounting
  ↓
actual weights
  ↓
reward
  ↓
next observation
```

---

# 11. Required End-to-End Test

新增：

```text
test_environment_end_to_end_transition
```

必须至少包含：

```text
3 assets
1 buy disabled
1 lot-size rounded
1 normal fill
nonzero transaction cost
```

检查：

## 11.1 Accounting

$$
V_{t+1}
=
Cash_{t+1}
+
\sum Position_{i,t+1}Price_{i,t+1}
$$

## 11.2 Weight

$$
w^{obs}_{i,t+1}
=
\frac{MV_{i,t+1}}{V_{t+1}}
$$

## 11.3 Cost

```text
cost only applied on executed quantity
```

未成交订单不得产生费用。

## 11.4 Tradability

buy-disabled asset position 不增加。

## 11.5 Lot size

执行数量必须是 lot multiple。

---

# 12. 必须冻结 Spread / Slippage 的记账语义

当前 hand example：

```text
fill @ 10.00
spread = cash cost
slippage = cash cost
```

这是可以接受的一种建模方法。

另一种方法是：

```text
reference price = 10.00
effective fill = 10.003
```

但**两种只能选一种**。

否则未来很容易出现：

```text
fill price 已经加 slippage
+
CostBreakdown 又扣 slippage
```

导致 double count。

---

# 13. Gate 2 必须记录统一约定

推荐 V1：

```text
Fill.price = reference execution price
spread/slippage/impact = explicit CostBreakdown cash costs
```

或者：

```text
Fill.price = effective execution price
CostBreakdown spread/slippage/impact = 0
```

二选一。

Reviewer 更推荐第一种，因为便于：

- decomposition；
- stress test；
- attribution。

但必须写入：

```text
docs/DECISIONS.md
```

并增加：

```text
test_no_double_count_execution_friction
```

---

# 14. Reward Period 需要再加一个明确测试

当前：

```text
Day t close
→ action
→ Day t+1 open fill
→ Day t+1 close mark
```

方向正确。

但必须确认已有持仓在：

```text
t close → t+1 open
```

这段 overnight gap 中仍由**旧组合**承担收益/亏损。

不能让新 action 在 t close 就“穿越生效”。

---

# 15. Required Overnight Test

增加：

```text
test_old_positions_hold_through_overnight_gap_before_rebalance
```

例：

```text
Day t close:
  hold A = 100 shares
  A close = 10

Day t+1 open:
  A open = 9

RL target:
  sell A at t+1 open
```

Portfolio 必须先承受：

```text
100 × (9 - 10) = -100
```

overnight PnL，

然后才在 9 元执行卖出。

禁止出现：

```text
t close target=0
→ overnight loss 消失
```

---

# 16. Cost Currency Contract 当前存在潜在歧义

`Fill` 描述为：

```text
cost(base)
```

但 Southbound 示例中的所有费用单位实际是：

```text
HKD
```

因此 contract 必须明确：

### Option A — 推荐

```python
CostBreakdown:
    local_currency: str
    local_total: float
    base_currency: str
    fx_rate: float
    base_total: float
```

### Option B

规定：

```text
CostBreakdown 全部字段永远是 Base Currency
```

那么 SouthboundCostModel 必须在计算时完成 FX 转换。

当前不能一边：

```text
schema says base
```

一边：

```text
example uses HKD
```

---

# 17. 这项可以作为 Carry-Forward，但 contract 现在就要冻结

Gate 2 主 Environment 当前只跑 CNY instrument，因此：

```text
multi-currency integration
```

不阻止 Gate 3 Core RL sanity。

但是：

> `CostBreakdown currency semantics`

必须现在写清楚。

否则以后 FX accounting 会出现隐性单位错误。

---

# 18. PremiumGuard 与历史研究模式存在一个必须提前定义的问题

当前 Live 语义：

```text
IOPV missing/stale
→ buy blocked
```

这是正确的。

但 513500 的：

```text
historical realtime IOPV
```

不可得。

如果把 Live PremiumGuard 原封不动用于历史 RL：

```text
US_BROAD
```

将可能永久：

```text
BUY_DISABLED
```

这会让 11 维 Core Action Space 中一个槽位失效。

---

# 19. 必须定义 Environment Mode

在 Gate 3 前冻结：

```text
METHOD_RESEARCH
INSTRUMENT_BACKTEST
PAPER
LIVE
```

至少 4 种 mode。

## 19.1 METHOD_RESEARCH

目标：

> 比较 TD3/SAC/PPO 的资产配置能力。

允许：

```text
Asset Slot return series
no historical realtime PremiumGuard
```

结果不得宣称完全可执行。

---

## 19.2 INSTRUMENT_BACKTEST

使用实际 ETF 历史。

对于 513500：

```text
historical IOPV unavailable
```

必须明确：

```text
PremiumGuard not faithfully reconstructable
```

可运行：

```text
NO_PREMIUM_GUARD scenario
```

或经 Reviewer 批准的 conservative approximation。

报告必须标记 limitation。

---

## 19.3 PAPER / LIVE

必须：

```text
realtime market price
+
realtime IOPV
+
fail-closed PremiumGuard
```

---

# 20. 这项在 Gate 3 前必须完成

否则我们无法解释：

> Gate 3 的 513500 到底为什么能买 / 不能买。

新增：

```text
EnvironmentMode
```

并写入 Run Manifest。

---

# 21. Observation Warm-Up 需要明确

当前 feature 包含：

```text
drawdown_250
cn_large_vol_percentile_252
```

因此 Environment 不能从第一天直接产生有效 104 维 observation。

Gate 3 前必须定义：

```text
minimum_history
```

建议：

```text
>= 252 valid observations
```

并且测试：

```text
all observation values finite
```

禁止：

```text
NaN → silently fill 0
```

除非该填充行为有明确经济含义。

---

# 22. Required Warm-Up Test

增加：

```text
test_observation_requires_full_lookback
test_observation_is_finite_after_warmup
```

---

# 23. Adjustment PIT：方向正确，但 Carry-Forward C3 不能完全关闭

本次实现：

```text
total_return_with_events
```

并测试：

- cash dividend；
- split；
- share conversion；
- bond distribution。

这很好。

但是当前 Environment：

```text
尚未接真实 Data Loader
```

所以只能证明：

> adjustment algorithm 可以 PIT 工作。

还不能证明：

> QMT/实际数据源上的每只 ETF corporate-action event 能正确驱动 total-return series。

因此：

```text
C3 = PARTIALLY RESOLVED
```

而不是完全 Closed。

---

# 24. C3 的正式关闭条件

在 Gate 3 前完成：

```text
real data integration
```

并抽查至少：

```text
510300
512890
511260
515070
```

真实 event date。

证明：

```text
raw price
+
event table
→ total return
```

与独立数据源结果一致。

---

# 25. Proxy Carry-Forward C2 仍然存在

Gate 2 没有使用未验证 proxy，正确。

因此 C2 不阻止当前 correction。

但：

```text
Gate 3 RL Sanity
```

如果使用 proxy：

必须先完成：

```text
launch date / backfill audit
```

如果 Gate 3 只用 actual ETF history：

C2 可以继续延期到 Gate 4 Method Research。

Agent 必须在 Gate 3 Packet 明确说明到底用了哪种数据。

---

# 26. 03110 Carry-Forward C1 保持

当前：

```text
same_day_reversal = UNKNOWN_PENDING_RULE_VERIFICATION
```

正确。

Gate 2/3 研究使用 Daily t→t+1，不需要 T+0，因此不阻塞。

Gate 6 前必须关闭。

---

# 27. 11 Core 与 HK_DIVIDEND 的研究数据来源必须在 Gate 3 前明确

Gate 1 已经发现：

```text
QMT 03110.HK market data = unavailable
```

因此 Gate 3 的真实 11-Core 训练如果包含：

```text
HK_DIVIDEND
```

必须明确使用：

```text
Sina 03110 historical research data
```

或者：

```text
approved domestic proxy instrument
```

不能在代码中默默：

```text
drop HK_DIVIDEND
```

同时仍声称：

```text
ActionDim = 11
```

---

# 28. Gate 3 前 Instrument Mapping 必须打印

要求每个 run manifest 输出：

| Asset Slot | Research Instrument / Series |
|---|---|
| CN_LARGE | ... |
| CN_SMALL | ... |
| ... | ... |
| HK_DIVIDEND | ... |
| US_BROAD | ... |

这样 Reviewer 可以确认每个 action dimension 对应的真实资产序列。

---

# 29. 关于 29 个 Tests 的评价

根据 Gate Packet，现有测试覆盖面是好的。fileciteturn26file0

尤其值得保留：

```text
accounting identity
oversell guard
premium fail-closed
no-lookahead feature perturbation
next-open execution
adjustment events
```

但进入 RL 前还缺 5 个关键 integration tests：

```text
test_environment_end_to_end_transition
test_observation_uses_actual_holdings_not_target
test_old_positions_hold_through_overnight_gap_before_rebalance
test_no_double_count_execution_friction
test_observation_is_finite_after_warmup
```

---

# 30. Gate 2 Required Corrections Checklist

Agent 必须逐项完成：

## Cost

- [ ] Southbound ETF stamp duty 改为 0。
- [ ] 加 AFRC levy 0.00015%。
- [ ] 增加 Southbound ETF fee unit test。
- [ ] 增加 fee source / effective-date metadata。
- [ ] Mainland `0.004% handling fee` 不直接加入 retail cost，先标记 broker commission inclusion 未知，避免 double count。

## Environment transition

- [ ] Observation current weights 明确来自 actual positions。
- [ ] 增加 blocked-trade actual-weight test。
- [ ] 增加 end-to-end transition test。
- [ ] cost 只对 fill quantity 计费。
- [ ] rejected order 不计交易费用。

## Timing

- [ ] 增加 overnight old-position test。
- [ ] 保证 action 只在 t+1 execution point 生效。

## Execution friction

- [ ] 冻结 spread/slippage accounting convention。
- [ ] 增加 no-double-count test。

## Currency

- [ ] 冻结 CostBreakdown currency contract。

## Premium

- [ ] 增加 EnvironmentMode。
- [ ] 区分 METHOD_RESEARCH / INSTRUMENT_BACKTEST / PAPER / LIVE。
- [ ] Gate 3 run manifest 明确 PremiumGuard behavior。

## Observation

- [ ] 明确 warm-up length。
- [ ] 104-d observation 必须全部 finite。

## Adjustment

- [ ] C3 状态改为 PARTIALLY_RESOLVED，直到真实数据验证。
- [ ] Gate 3 前若使用实际 ETF 数据，至少验证 4 个真实 corporate-action event。

---

# 31. Gate 2 Correction Packet

Agent 生成：

```text
docs/review_packets/GATE_2_CORRECTIONS.md
```

必须包含：

```markdown
# GATE 2 Corrections

## 1. Southbound ETF fee correction
## 2. Fee source / effective-date configuration
## 3. Actual-vs-target weight semantics
## 4. End-to-end environment transition test
## 5. Overnight holding timing test
## 6. Spread/slippage accounting convention
## 7. Cost currency convention
## 8. Environment modes
## 9. Observation warm-up / finite tests
## 10. Adjustment PIT carry-forward
## 11. Exact pytest output
## 12. Files changed
## 13. Git commit
```

---

# 32. Gate 3 Authorization Criteria

Gate 3 只有在以下条件完成后才授权：

```text
Southbound ETF stamp duty bug fixed
AFRC levy added
actual holdings used in state
environment E2E test passes
overnight timing test passes
execution friction double-count impossible
cost currency semantics frozen
research/live premium modes separated
observation finite after warmup
```

然后：

```text
GATE_2 = APPROVED
GATE_3 = AUTHORIZED
```

---

# 33. Gate 3 未来允许的范围

Gate 2 correction 批准以后，Gate 3 只能：

```text
one fold
one seed
PPO
SAC
TD3
Equal Weight baseline
```

目标仍然只是：

> **RL Sanity**

不允许：

```text
Optuna
10~20 seeds
正式性能结论
Theme Sleeve
Live QMT
```

---

# 34. Reviewer 对当前 Environment 的总体评价

当前设计里最正确的几项是：

1. **固定 11 维 action space**；
2. **Asset Slot 与 ETF Instrument 解耦**；
3. **t close → t+1 execution**；
4. **Portfolio Accounting 独立模块**；
5. **PremiumGuard fail-closed**；
6. **raw execution price 与 total-return research series 分离**；
7. **事件驱动的 adjustment 方向**。

这些都应该保持不变。

当前问题主要不是架构方向，而是：

> 环境还需要最后一轮“跨模块一致性”验证，才能安全地让 TD3/SAC/PPO 开始学习。

---

# 35. External Rule Verification Used by Reviewer

本次 Reviewer 额外核对了 2026-08 当前官方交易规则。

## Southbound ETF

上海证券交易所当前港股通税费说明：

```text
Trading Fee: 0.00565%
SFC Trading Levy: 0.0027%
AFRC Transaction Levy: 0.00015%
Stock Connect ETF Stamp Duty: temporarily exempt
```

因此 Gate 2 当前对 03110 征收 0.1% 印花税属于确定错误。

## Mainland ETF

上交所当前收费表显示：

```text
ETF auction handling fee = 0.004% both sides
Money-market ETF / Bond ETF = temporarily exempt
```

但该经手费属于会员等向交易所支付的费用。

用户券商实际的：

```text
ETF commission = 0.00005
```

是否已经包含该费用必须按券商实际账单确认，不能自动叠加。

---

# 36. Reviewer Approval Record

```yaml
gate: 2
decision: REVISIONS_REQUIRED_BEFORE_GATE_3
date: 2026-08-08

implementation:
  architecture_direction: approved
  accounting_core: provisionally_approved
  timing_core: provisionally_approved
  rl_ready: false

blockers:
  - southbound_etf_stamp_duty_bug
  - actual_holdings_state_not_proven
  - end_to_end_environment_transition_not_proven

carry_forward:
  C1:
    topic: 03110_same_day_rule
    deadline: before_gate6
  C2:
    topic: proxy_point_in_time_audit
    deadline: before_use_in_strict_oos
  C3:
    topic: real_data_adjustment_pit_validation
    status: partially_resolved
    deadline: before_real_data_rl

permissions:
  patch_gate2: true
  add_tests: true
  refine_cost_contract: true
  enter_gate3: false
  train_rl: false
  live_qmt_orders: false

required_next_packet:
  GATE_2_CORRECTIONS.md
```

---

# 37. Agent Next Instruction

```text
1. Do NOT start Gate 3.
2. Patch Gate 2 according to this review.
3. Fix Southbound ETF fee model first.
4. Add environment integration tests.
5. Freeze actual-position observation semantics.
6. Freeze execution-friction and cost-currency conventions.
7. Define EnvironmentMode.
8. Add warm-up/finite observation tests.
9. Generate GATE_2_CORRECTIONS.md.
10. Commit.
11. STOP.
12. Return packet to Reviewer / ChatGPT.
```

---

## END OF REVIEWER RESPONSE
