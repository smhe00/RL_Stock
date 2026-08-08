# GATE 1 Corrections — Reviewer Final Response
## FinRL-X 中国 ETF 项目 — Data & Universe Audit 最终验收

**Reviewed artifact:** `GATE_1_CORRECTIONS.md`  
**Review decision:** `APPROVED_WITH_CARRY_FORWARD_CONDITIONS`  
**Gate 1 status:** `APPROVED`  
**Gate 2 authorization:** `AUTHORIZED`  
**Review date:** 2026-08-08

---

# 1. Final Decision

本次 `GATE_1_CORRECTIONS.md` 已经实质完成上一轮 Reviewer 要求的关键修正。

主要阻塞项已经闭环：

- 513500 的 `close/NAV` 已从“实时可交易溢价”降级为异步 `close_to_official_nav_gap`；
- 历史 IOPV 正确标记为不可得；
- 03110.HK Board Lot 已修正为 50，并区分官方规则与 Broker/QMT 支持；
- 单日成交额已与 ADV20 / ADV60 分离；
- 511260 / 511360 的流动性与 AUM 已补齐；
- AUM 与二级市场 Market Cap 已分离；
- 相关性 120D / 250D 已独立复算；
- 原 union-tail Pearson 已撤销；
- 新增 stress correlation 与 lower-tail co-exceedance；
- Index Base Date 与 Launch Date 已开始分离；
- ETF raw / adjusted / NAV 已明确不同语义；
- `CASH_LIKE=511360` 已明确为 `SHORT_CREDIT`，不再等价于 Broker Cash。

因此：

```text
GATE_1 = APPROVED
GATE_2 = AUTHORIZED
```

Agent 可以开始：

> **Gate 2 — Environment & Accounting**

无需再次停留在 Gate 1。

---

# 2. 513500 Premium Correction — PASS

Reviewer 批准本次修正。

正确语义已经变为：

```text
close_to_official_nav_gap
```

而不是：

```text
realtime executable premium
```

并明确：

```text
HISTORICAL_REALTIME_PREMIUM = NOT_AVAILABLE
```

这是正确处理。

以下数据可以继续保留用于研究诊断：

```text
mean
P90
P95
P99
min
max
latest close_to_official_nav_gap
```

但 Gate 2 / Gate 6 都不得把这些 percentile 直接用于 Live `PremiumGuard`。

---

## 2.1 Gate 2 PremiumGuard 规则

Gate 2 只实现接口与 Fail-Closed 行为。

推荐：

```python
class PremiumGuard:
    def evaluate(
        self,
        instrument,
        timestamp,
        market_price,
        iopv=None,
    ) -> PremiumDecision:
        ...
```

如果：

```text
instrument requires premium protection
AND realtime IOPV unavailable/stale
```

则默认：

```text
BUY_ALLOWED = False
HOLD_ALLOWED = True
SELL_ALLOWED = True
```

除非后续 Reviewer 批准其他 fallback。

---

# 3. 03110.HK Metadata — PASS WITH ONE CARRY-FORWARD

以下修正批准：

```text
board_lot_size = 50
effective_date = 2026-07-24
southbound_eligible_from = 2024-05-06
currency = HKD
QMT market data = unavailable
QMT order capability = unknown pending Gate 6
```

正确区分了：

```text
official board lot
```

与：

```text
broker metadata / execution support
```

---

## 3.1 Carry-Forward C1：03110 “T+0” 不得在 Gate 2 直接硬编码为 True

本次 correction 已正确指出：

```text
03110 是 HKEX-listed + Southbound eligible
```

而不是 SSE cross-border ETF。

但 `same-day trading / turnaround` 的正式规则仍没有在 correction packet 中给出完成验证的 exact rule。

因此进入 Gate 2 时：

```yaml
03110:
  same_day_reversal:
    status: UNKNOWN_PENDING_RULE_VERIFICATION
```

而不是：

```yaml
same_day_reversal: true
```

Gate 2 的 Daily `t close → t+1 execution` 研究本身不会因此阻塞。

但在 Instrument Master 中必须保留 unknown 状态。

在 Gate 6 前必须完成：

```text
HKEX / Southbound official rule verification
+
broker capability verification
```

---

# 4. Liquidity / ADV — PASS

Reviewer 批准：

```text
turnover_value_1d
ADV20
ADV60
median60
```

的字段拆分。

尤其：

```text
511260
511360
```

已经通过 QMT amount 补齐，不再因为 AkShare spot 缺失而标记 NA。

这些数据足以支持 Gate 2 的：

```text
LiquidityGuard skeleton
```

---

# 5. AUM vs Market Cap — PASS

Reviewer 批准以下分离：

```text
shares_outstanding
NAV
aum_nav_based
market_cap
```

513500 的例子很好地说明了为什么两者不能混用：

```text
NAV-based AUM ≈ 250.31亿
secondary-market market cap ≈ 272.70亿
```

后续 InstrumentSelector 不得把：

```text
market_cap
```

当作：

```text
fund AUM
```

---

## 5.1 AUM 数据用途限制

Gate 2 中：

```text
AUM
ADV
```

只能用于：

- liquidity / instrument quality metadata；
- InstrumentSelector constraints；
- audit / reporting。

V1 不允许直接作为 RL observation。

避免无必要增加 slow-moving feature。

---

# 6. Correlation Verification — PASS

三组独立复算结果已经满足 Reviewer 上一轮要求：

```text
AI|STAR
CHINEXT|CN_LARGE
SEMICONDUCTOR|STAR
```

并确认：

```text
rho120 != rho250
```

此前部分 3 位小数相等主要来自舍入。

特别重要的核心结论：

$$
\rho_{250}(STAR,SEMICONDUCTOR)\approx0.9715
$$

继续成立。

因此：

```yaml
risk:
  hardtech_max: 0.30
```

保持为 Mandatory Constraint。

---

# 7. Tail / Stress Metric — PASS

原来的：

```text
union-tail Pearson
```

已经正确删除。

批准 V1 stress metric：

## 7.1 China downside conditioned correlation

$$
CN\_LARGE\_DOWNSIDE\_CORR
=
Corr(r_i,r_j\mid r_{CN\_LARGE}<0)
$$

## 7.2 China stress correlation

$$
CN\_LARGE\_STRESS\_CORR
=
Corr(r_i,r_j\mid
r_{CN\_LARGE}\le q_{10\%})
$$

## 7.3 Lower-tail co-exceedance

$$
P(I_i=1\mid I_j=1)
$$

## 7.4 TailDependenceScore

$$
TDS=
\frac{P(I_i=1,I_j=1)}{0.1^2}
$$

其中：

$$
I_i=1(r_i\le q_i(0.1))
$$

---

# 8. 修正后的风险结论 — PASS

Reviewer 同意以下更保守的结论：

### HardTech

```text
STAR + SEMICONDUCTOR
```

高度重叠。

### AI

与：

```text
STAR
CHINEXT
SEMICONDUCTOR
```

存在显著成长/科技 Beta 重叠。

### CN_DURATION

可以称：

```text
meaningful / mild defensive diversifier
```

但当前数据不足以称：

```text
extreme crash hedge
```

### GOLD

保留：

```text
non-equity / diversifying risk source
```

但不再使用旧 union-tail 负相关数字做强结论。

这符合项目对统计证据的要求。

---

# 9. Proxy Metadata — PASS FOR GATE 1, WITH CARRY-FORWARD

本次已经正确加入：

```text
base_date
launch_date
is_backfilled_before_launch
```

并明确：

$$
BaseDate\ne PointInTimeAvailableDate
$$

这是 Gate 1 最重要的数据纪律之一。

---

## 9.1 Carry-Forward C2：未验证 Proxy 禁止进入 Gate 2 正式 Feature Pipeline

当前仍存在：

```text
HSHYLDI launch date 待验证
中债国债总财富 launch date 待验证
H30184 待验证
930713 待验证
H30590 待验证
931152 待验证
399967 部分元数据待验证
```

这不再阻塞 Gate 2。

原因：

> Gate 2 可以先使用真实 ETF 历史构建 Environment / Accounting。

但必须执行以下规则：

```text
PROXY_STATUS != VERIFIED
    ↓
STRICT_PIT_PIPELINE = FORBIDDEN
```

换言之：

### Gate 2 可以

```text
Core real ETF data
```

### Gate 2 不可以

```text
把未完成 launch/backfill audit 的 proxy
作为严格 PIT 训练数据
```

Proxy Audit 必须在 Gate 3 RL Sanity 前完成。

---

# 10. Price Semantics / Adjustment — PASS WITH CRITICAL CARRY-FORWARD

本次冻结：

```text
execution_price_series = raw tradable market price
research_total_return_series = adjusted / total-return-consistent series
```

方向正确。

并且已经发现：

```text
QMT front
```

并非所有 ETF 都可以简单解释为同一种经济语义。

这是非常有价值的发现。

---

# 11. Carry-Forward C3：Gate 2 不得直接把 QMT `front` 当作 Point-in-Time Truth

这是本次批准 Gate 2 时最重要的继续约束。

`front/qfq` 是为了构造连续价格历史而生成的调整序列。

在强化学习项目中必须避免：

```text
today下载的全历史 qfq
→ 直接当成历史时点 t 当时真实可见的 price level
```

尤其对于：

- 分红；
- 拆分；
- 基金份额折算；
- 后续 corporate action；

必须确认 adjustment factor 的时间语义。

---

## 11.1 Gate 2 推荐实现

内部数据层保留：

```text
raw_market_price
distribution_cash
split_factor
conversion_factor
```

研究收益优先计算：

$$
TR_t=
\frac{
P_t \times Adjustment_t + CashDistribution_t
}{
P_{t-1}\times Adjustment_{t-1}
}-1
$$

或者使用已验证不会对本项目 return features 引入未来信息的 provider total-return series。

---

## 11.2 Gate 2 Feature V1

当前冻结的 Feature：

```text
returns
volatility
drawdown
```

主要是比例/收益特征。

这降低了 qfq scale-level leakage 风险。

但是 Gate 2 必须写：

```text
test_adjustment_point_in_time_semantics
```

至少覆盖：

- 510300 dividend；
- 512890 share conversion；
- 511260 distribution；
- 515070 adjustment event。

---

# 12. CASH_LIKE — PASS

正确修正：

```text
511360:
  risk_class = SHORT_CREDIT
  cash_equivalent = false
```

同时：

```text
BROKER_CASH
```

继续独立。

因此 Gate 2 Portfolio Accounting 必须同时有：

```text
position: CASH_LIKE ETF
```

和：

```text
cash balance: actual broker cash
```

不得合并。

---

# 13. Alternative Instrument Audit — ACCEPTED FOR GATE 1

Gate 1 已经证明：

```text
Asset Slot != ETF Code
```

这一设计可以真正落地。

当前不要求再次筛选 preferred instrument。

---

## 13.1 Gate 2 暂不启用自动替换

虽然 alternatives 已经存在，但 Gate 2 的：

```text
InstrumentSelector
```

先做确定性：

```text
preferred if tradable
else FAIL / fallback under explicit rule
```

不要立即实现：

```text
动态评分切换ETF
```

否则会同时引入：

- premium；
- spread；
- tracking error；
- liquidity；
- rebalance；

多个变量，难以验证 Environment。

自动 Instrument Ranking 留到 Gate 5/6 或独立 RFC。

---

# 14. One Remaining Reporting Defect — NON-BLOCKING

上一轮 Reviewer 要求关键相关性 pair 在 Gate Packet 中直接显示 overlap：

```text
start
end
N
```

本次 correction 对 3 对资产给出了 exact window / N，但其他关键 pair 仍主要引用：

```text
tail_metrics_correction.csv
```

这不是 Gate 2 blocker。

但要求：

> Gate 2 Review Packet 中引用任何 correlation / stress 数字时，必须直接附该 metric 的 overlap N 和 date range。

不要让 Reviewer 依赖本地 CSV 才能解释数字。

---

# 15. Gate 1 最终逐项裁决

| Item | Final Decision |
|---|---|
| 513500 asynchronous NAV-gap semantics | PASS |
| historical realtime premium claim removed | PASS |
| 03110 board lot | PASS |
| 03110 Southbound eligibility | PASS |
| 03110 QMT capability separation | PASS |
| 03110 same-day trading rule | CARRY-FORWARD C1 |
| ADV20 / ADV60 | PASS |
| 511260 / 511360 liquidity | PASS |
| AUM vs Market Cap | PASS |
| 511260 / 511360 AUM | PASS |
| correlation recalculation | PASS |
| rho120/rho250 verification | PASS |
| downside naming | PASS |
| union-tail metric removed | PASS |
| new tail/stress metrics | PASS |
| proxy base vs launch date | PASS |
| incomplete proxy verification | CARRY-FORWARD C2 |
| raw vs adjusted price semantics | PASS |
| ETF dividend / adjustment spot checks | PASS |
| QMT qfq/front PIT semantics | CARRY-FORWARD C3 |
| CASH_LIKE short-credit semantics | PASS |
| frozen 11+5 universe | PASS |

---

# 16. Gate 2 Authorized Scope

Agent 现在可以开始：

## 16.1 Canonical Contracts

实现：

```text
TargetAssetWeights
TargetInstrumentWeights
TradabilityDecision
PremiumDecision
CostBreakdown
OrderPlan
```

---

## 16.2 Portfolio Accounting

实现：

```text
cash
positions
market value
realized pnl
unrealized pnl
fees
FX pnl
portfolio value
```

以及 accounting identity tests。

---

## 16.3 MockBroker

实现：

```text
quote
position
cash
order
fill
reject
```

不允许真实 QMT order。

---

## 16.4 Cost Model

实现：

```text
CostModel Protocol
MainlandETFCostModel skeleton
SouthboundETFCostModel skeleton
```

Gate 2 可以先使用配置化费率和简单 spread/slippage。

不要尝试一开始实现复杂 market impact calibration。

---

## 16.5 Tradability

实现：

```text
buy_allowed
sell_allowed
reason_codes
```

---

## 16.6 PremiumGuard

只实现：

```text
interface
data freshness
fail-closed behavior
```

不要使用当前 `close_to_official_nav_gap P95` 作为 Live threshold。

---

## 16.7 FX Skeleton

Base Currency：

```text
CNY
```

实现 HKD mark-to-market 结构。

不要求 Gate 2 完成真实港股结算汇率模型。

---

## 16.8 ChinaETFPortfolioEnv

仅：

```text
11 Core
fixed action dimension = 11
long only
no leverage
```

禁止 Theme Sleeve。

---

# 17. Gate 2 明确禁止

```text
NO TD3 performance comparison
NO SAC performance comparison
NO PPO performance comparison
NO Optuna
NO multi-seed performance study
NO Theme Sleeve
NO live QMT order
NO changing frozen universe
NO dynamic Instrument ranking
NO using unverified proxy in strict PIT pipeline
```

Gate 2 的目标是：

> **证明 Environment 的金融会计与时间语义正确。**

不是产生收益。

---

# 18. Gate 2 必须完成的测试

## 18.1 Weight invariants

$$
w_i\ge0
$$

$$
\sum_iw_i=1
$$

---

## 18.2 Accounting identity

无外部现金流：

$$
V_{t+1}
=
V_t
+MarketPnL
+FXPnL
-Fees
$$

---

## 18.3 No-lookahead

修改：

```text
t+1 이후 data
```

不得改变：

```text
feature_t
action_t
```

---

## 18.4 Decision timing

必须证明：

```text
Day t close
→ feature/signal
→ Day t+1 execution
```

没有：

```text
same-close fill
```

---

## 18.5 Tradability

测试：

```text
NOT_LISTED
SUSPENDED
BUY_DISABLED
SELL_ONLY
MARKET_CLOSED
DATA_STALE
```

---

## 18.6 PremiumGuard

至少：

```text
IOPV missing → buy blocked
IOPV stale → buy blocked
hold/sell allowed
```

---

## 18.7 Lot size

A股：

```text
100-unit lot
```

03110 暂不进入 Gate 2 live execution，但 Instrument Master 保存：

```text
lot=50
```

---

## 18.8 Adjustment semantics

必须覆盖 Carry-Forward C3。

---

# 19. Gate 2 Review Packet

生成：

```text
docs/review_packets/GATE_2_ENVIRONMENT.md
```

必须包含：

## 1. Canonical object schemas

展示 exact fields。

## 2. State / action shape

Core-only：

$$
ActionDim=11
$$

## 3. Hand-calculated accounting example

至少 3~5 个交易日。

必须人工可复算。

## 4. Cost breakdown example

例如：

```text
commission
exchange fee
spread
slippage
total
```

## 5. Tradability example

至少：

```text
buy blocked / sell allowed
```

案例。

## 6. PremiumGuard fail-closed example

## 7. FX accounting example

可以使用 mock HKD instrument。

## 8. No-lookahead test

展示 exact test。

## 9. t→t+1 execution test

## 10. Adjustment PIT test

## 11. Pytest exact output

## 12. Known limitations

## 13. Carry-Forward C1/C2/C3 current status

## 14. Files changed

## 15. Git commit

---

# 20. Gate 2 Stop Condition

Agent 完成 Gate 2 后必须：

```text
STOP-GATE REACHED
```

并将：

```text
GATE_2_ENVIRONMENT.md
```

返回 Reviewer。

在 Reviewer 批准 Gate 2 前：

```text
DO NOT START RL TRAINING
```

---

# 21. Reviewer Approval Record

```yaml
gate: 1
decision: APPROVED_WITH_CARRY_FORWARD_CONDITIONS
date: 2026-08-08

universe:
  core_slots: 11
  theme_candidates: 5
  changed: false

gate2:
  authorized: true

carry_forward:
  C1:
    topic: 03110_same_day_trading_rule
    deadline: before_gate6
  C2:
    topic: proxy_launch_backfill_verification
    deadline: before_gate3
  C3:
    topic: adjusted_price_point_in_time_semantics
    deadline: gate2

permissions:
  implement_environment: true
  implement_accounting: true
  implement_mock_broker: true
  implement_cost_skeleton: true
  implement_qmt_live_orders: false
  train_rl_for_performance: false
  implement_theme_sleeve: false
```

---

# 22. Agent Next Instruction

```text
1. Mark Gate 1 APPROVED.
2. Update CODEX_AGENT_STATUS.md.
3. Preserve Carry-Forward C1/C2/C3.
4. Enter Gate 2.
5. Implement only Environment & Accounting scope.
6. Generate GATE_2_ENVIRONMENT.md.
7. STOP.
8. Return packet to Reviewer / ChatGPT.
```

---

# 23. Final Reviewer Summary

Gate 1 已经完成其核心使命：

> **证明资产池的数据可获得、Instrument 可映射、关键元数据可审计，并把容易产生假 Alpha 的数据语义问题提前暴露出来。**

本次 corrections 的质量足以解除 Gate 1 阻塞。

当前最重要的下一步不再是继续优化 Universe，而是验证：

$$
\boxed{
Data
\rightarrow
Feature
\rightarrow
TargetWeight
\rightarrow
Trade
\rightarrow
Accounting
}
$$

这一条金融会计链条是否完全正确。

因此正式批准进入：

> **GATE 2 — Environment & Accounting**

---

## END OF REVIEWER RESPONSE
