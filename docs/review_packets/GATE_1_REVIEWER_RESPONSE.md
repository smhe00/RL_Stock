# GATE 1 Reviewer Response
## FinRL-X 中国 ETF 项目 — Data & Universe Audit 审核意见

**Review status:** `REVISIONS_REQUIRED_BEFORE_GATE_2`  
**Reviewed artifact:** `GATE_1_DATA_UNIVERSE.md`  
**Review date:** 2026-08-08  
**Next gate:** Gate 2 — Environment & Accounting  
**Gate 2 authorization:** **NOT YET AUTHORIZED**

---

# 1. Reviewer Decision

Gate 1 的总体质量较高，尤其以下部分值得保留：

- QMT 作为境内 ETF 日线主数据源；
- AkShare / Sina 仅作为交叉验证与补缺；
- 16/16 标的历史覆盖已建立；
- 03110.HK 港股通资格起始日已追溯；
- 513500 已意识到需要 PremiumGuard；
- 已建立 Preferred / Alternative Instrument 思路；
- 已显式区分 REAL ETF 与 PROXY；
- 已开始计算 120D / 250D / stress correlation；
- 未越权编写 PortfolioEnv、训练 RL 或真实下单。

但本 Gate 中仍存在若干**会直接传播到 Gate 2 环境与后续 OOS 结论的基础数据定义问题**。

因此当前状态为：

```text
GATE_1_STATUS = REVISIONS_REQUIRED_BEFORE_GATE_2
```

Agent 必须完成本文件中的 Required Corrections，并生成：

```text
docs/review_packets/GATE_1_CORRECTIONS.md
```

经 Reviewer 确认后，才允许进入 Gate 2。

---

# 2. CRITICAL-1：513500 的 `close / NAV - 1` 不能直接定义为“历史可交易溢价”

原 Gate 1 写：

```text
历史溢价序列可构造：
price（QMT raw） vs NAV（sina）
```

并进一步报告：

```text
mean +1.34%
P90 +5.18%
P95 +7.28%
P99 +13.98%
当前 +8.74%
```

这个结论目前**不能作为 PremiumGuard 的正式历史输入**。

## 2.1 原因：跨市场时间不同步

513500 是中国交易时段交易的 S&P500 QDII ETF。

A股 ETF 二级市场收盘：

```text
China ~15:00 CST
```

而美国股票现货市场的收盘发生在之后。

基金官方 NAV 的估值时点与上海二级市场 15:00 的价格不是天然同步。

因此：

$$
Gap_t=\frac{Close^{ETF}_t}{NAV_t}-1
$$

可能同时包含：

- 真正供求溢价；
- 美股现货市场时差；
- USD/CNY / CNH 变动；
- 美国股指期货在中国交易时段的变化；
- NAV 发布时滞；
- 不同数据源 date label 语义。

所以：

```text
close/NAV gap
```

不等价于：

```text
contemporaneous executable premium
```

---

# 3. 513500 正确的数据分层

Gate 1 必须把 513500 的指标拆成：

## 3.1 `close_to_official_nav_gap`

可保留：

$$
G_t=\frac{P_t^{close}}{NAV_t}-1
$$

但名称必须明确：

```text
close_to_official_nav_gap
```

不得简称：

```text
premium
```

除非完成估值时点对齐验证。

---

## 3.2 `realtime_iopv_premium`

Live / Paper Trading 的 PremiumGuard 应优先使用：

$$
Premium_t=
\frac{P_t^{market}}{IOPV_t}-1
$$

其中：

- ETF market price；
- IOPV / indicative NAV；
- 时间戳必须足够接近。

---

## 3.3 如果历史 IOPV 不可得

Gate 1 应记录：

```text
HISTORICAL_REALTIME_PREMIUM = NOT_AVAILABLE
```

而不是：

```text
historical premium available
```

可以保留 `close_to_official_nav_gap` 用于：

- 风险研究；
- proxy；
- event study；

但不能直接用 P90/P95 做 Live PremiumGuard threshold。

---

## 3.4 Gate 2 / Later 的候选历史 fair-value 方案

后续如确有需要，可研究：

$$
FairNAV_{CN,t}
=
NAV_{t-1}
\times
(1+SP500/FuturesMove_t)
\times
FXMove_t
$$

但这需要单独 RFC / Validation。

本 Gate 不要求实现。

---

# 4. 513500 当前结论允许保留到什么程度

官方基金公告已经明确多次提示 513500 存在较大二级市场溢价风险。

因此可以保留：

> `513500 requires PremiumGuard`

但不能保留未经同步验证的：

> “当前真实溢价 = 8.74%，超过历史 P95 7.28%”

作为正式事实。

应改成：

```text
close_to_official_nav_gap = 8.74% (dataset-derived, asynchronous)
official premium-risk warning = confirmed
realtime executable premium = requires IOPV-aligned validation
```

---

# 5. CRITICAL-2：03110.HK Board Lot 已经可以确认，不应继续标记 UNKNOWN

Gate 1 写：

```text
Lot size = UNKNOWN_PENDING_BROKER_TEST
```

这不准确。

Global X 官方产品页当前明确：

```text
Stock Code: 3110
Board Lot Size: 50 Units
Trading Currency: HKD
```

HKEX 2026-07-21 的 Trading Arrangement Notice 也明确：

```text
with effect from 24/07/2026
3110 / 83110 board lot:
100 → 50
```

因此 Gate 1 应冻结：

```yaml
03110.HK:
  board_lot_size: 50
  effective_date: 2026-07-24
  source: HKEX / Global X
```

### 注意

Broker 是否能正确识别 50 份一手仍需 Gate 6 验证。

所以应区分：

```text
OFFICIAL_BOARD_LOT = 50
BROKER_METADATA_SUPPORT = UNKNOWN_PENDING_BROKER_TEST
```

不能把两个问题混在一起。

---

# 6. CRITICAL-3：03110 的“T+0”依据需要改写

原报告将：

```text
03110.HK = T+0
```

部分依据写成：

> “港股通 ETF 参照跨境 ETF T+0”。

这在概念上混淆了两个市场。

03110.HK 是：

```text
HKEX-listed ETF
+
Southbound Stock Connect eligible
```

不是：

```text
SSE-listed cross-border ETF
```

所以不能直接拿上交所“跨境 ETF 当日回转”规则作为 03110 的法律/交易依据。

Gate 1 必须拆分：

```text
listing_market = HKEX
trading_market_rule = HKEX
stock_connect_eligibility = Southbound
settlement / account availability = Stock Connect + broker
```

对于 03110：

```text
same-day trading capability:
  verify under HKEX / Southbound trading rules

settlement:
  separate field

broker execution support:
  Gate 6
```

---

# 7. 03110 港股通资格：Gate 1 判断正确

以下可以批准：

```text
03110 listed: 2013-06-17
Southbound inclusion effective: 2024-05-06
Current Southbound eligible: YES
```

上交所 2024-04-26 通知明确：

```text
03110 GX HS HIGH DIV
调入
2024-05-06 生效
```

HKEX 2026 Southbound eligible ETF 材料仍列出 3110。

所以：

```text
pre-2024-05-06 Southbound instrument backtest = NOT LIVE-ELIGIBLE
```

这一判断正确。

---

# 8. CRITICAL-4：`ADV` 字段定义错误 / 不一致

Gate 1 多处将：

```text
2026-08-07 当日成交额
```

标记为：

```text
ADV
```

这是错误命名。

ADV 应为：

```text
Average Daily Value
```

例如：

$$
ADV20=\frac{1}{20}\sum_{k=1}^{20}Amount_{t-k}
$$

建议 Gate 1 统一计算：

```text
turnover_value_1d
ADV20
ADV60
median_turnover_60
```

优先用：

```text
QMT daily amount
```

计算，不依赖 AkShare spot。

---

# 9. 511260 / 511360 不应因 AkShare Spot 缺失而 ADV=NA

Gate 1 已有 QMT 日线数据。

因此即使：

```text
AkShare spot
```

没有债券 ETF，

仍可以从：

```text
QMT amount
```

直接计算：

```text
ADV20
ADV60
```

必须补齐。

同理：

03110 Sina 日线已经包含成交数据时，也应计算可比较的 HKD ADV20/60。

---

# 10. AUM 与 Market Cap 必须分开

Gate 1 表中使用：

```text
总市值
```

但 ETF 研究应明确区分：

```text
ETF market capitalization
fund net assets / AUM
shares outstanding
NAV
```

特别是 QDII ETF 存在二级市场溢价时：

$$
MarketCap
\ne
AUM
$$

因此 `InstrumentSelector` 不能把二级市场 Market Cap 当成 AUM 使用。

Gate 1 修订表建议：

| field | meaning |
|---|---|
| `aum_nav_based` | 基于基金净资产的规模 |
| `market_cap` | 二级市场价格 × 份额 |
| `shares_outstanding` | ETF 流通份额 |
| `adv20` | 20D 平均成交额 |

---

# 11. 511260 / 511360 的 AUM 需要补齐

Gate 1 当前：

```text
511260 AUM = NA
511360 AUM = NA
```

不够。

这两只又是：

```text
CN_DURATION
CASH_LIKE
```

两个关键防御槽位。

必须至少从：

1. 基金公司官方；
2. 交易所基金信息；
3. 可信基金数据源；

取得最新：

```text
AUM / fund NAV
```

并记录 source / date。

如果仍获取不到：

```text
AUM = UNKNOWN
```

但必须说明已尝试的官方来源，而不是因为 AkShare spot 不返回就停止。

---

# 12. CRITICAL-5：Correlation 表存在需要排查的异常模式

Gate 1 报告中多组：

```text
rho120
rho250
```

在三位小数下完全相同：

```text
AI|STAR           0.897 / 0.897
CHINEXT|CN_LARGE  0.886 / 0.886
AI|CHINEXT        0.885 / 0.885
CN_LARGE|CN_SMALL 0.805 / 0.805
CN_SMALL|ROBOTICS 0.800 / 0.800
```

这不是证明脚本有 bug，但模式足够异常，必须在进入 Gate 2 前确认。

Agent 必须：

1. 输出每一对的：
   - `n_120`
   - `start_120`
   - `end_120`
   - `rho_120`
   - `n_250`
   - `start_250`
   - `end_250`
   - `rho_250`
2. 随机抽 3 对人工用 pandas 独立重算；
3. 在 Gate correction 中粘贴 exact result。

---

# 13. Gate 1 报告没有真正满足“所有相关性报告 overlap”

报告正文说：

> overlap 已保存于 correlations.csv。

但 Reviewer 需要审核的 Gate Packet 本身应包含关键 overlap。

至少核心的 15~20 个 pair 需要在 packet 中直接展示：

```text
window
start
end
n_obs
```

不能要求 Reviewer 去依赖未上传的本地 CSV 才能判断。

---

# 14. CRITICAL-6：当前 Tail Correlation 定义存在选择偏差

Gate 1 定义：

> “两序列至少一个处于自身全期收益分位 ≤10% 的日子，在这些日子计算 Pearson correlation。”

形式：

$$
A=
\{r_i\le q_i(0.1)\}
\cup
\{r_j\le q_j(0.1)\}
$$

然后计算：

$$
Corr(r_i,r_j\mid A)
$$

这个定义会产生明显 selection bias。

例如：

- i 暴跌、j 正常；
- j 暴跌、i 正常；

都被选进样本。

这会机械性地制造低相关甚至负相关。

因此类似：

```text
CN_LARGE | CN_DURATION tail = -0.646
CN_LARGE | US_BROAD tail = -0.162
```

目前**不能直接解释成真正的 tail diversification**。

---

# 15. Tail Metric 修正方案

Gate 1 correction 至少实现以下一个简单、透明指标：

## 15.1 Lower-tail co-exceedance

定义：

$$
I_i=
1(r_i\le q_i(0.1))
$$

$$
I_j=
1(r_j\le q_j(0.1))
$$

报告：

$$
P(I_i=1\mid I_j=1)
$$

以及对称版本：

$$
P(I_j=1\mid I_i=1)
$$

可进一步标准化：

$$
TailDependenceScore=
\frac{P(I_i=1,I_j=1)}{0.1^2}
$$

---

## 15.2 Benchmark Stress Correlation

对于本项目也可保留：

$$
Corr(r_i,r_j\mid r_{CN\_LARGE}\le q_{CN\_LARGE}(0.1))
$$

但名称必须写：

```text
CN_LARGE_STRESS_CORR
```

不是泛称：

```text
tail correlation
```

---

# 16. Downside Correlation 也需要改名

Gate 1 定义：

```text
限定 CN_LARGE < 0 的日子
```

这本身可以作为一个有价值的指标。

但它测的是：

> A股大盘下跌时，不同资产如何共同变化。

所以应命名：

```text
CN_LARGE_DOWNSIDE_CORR
```

不要泛化叫：

```text
downside correlation
```

因为对：

```text
US_BROAD
HK_DIVIDEND
GOLD
CN_DURATION
```

这是 China-equity-conditioned stress metric，而不是 pairwise downside correlation。

---

# 17. Reviewer 对现有相关性结论的裁决

## 可以保留

```text
STAR / SEMICONDUCTOR highly redundant
AI strongly overlaps China growth
China equity cluster exists
CN_DURATION provides meaningful diversification
GOLD provides meaningful diversification
```

尤其：

```text
STAR|SEMICONDUCTOR rho250 ≈ 0.97
```

已经足够支持：

```text
HardTech combined cap is necessary
```

## 暂不允许保留强结论

以下要等 tail metric 修正：

```text
CN_DURATION tail = -0.646 therefore extreme-crash hedge
US_BROAD negative tail correlation
HK_DIVIDEND negative tail relationship
```

不能从当前 union-tail Pearson 直接推导。

---

# 18. CRITICAL-7：Proxy 的 `Base Date` 不等于 Point-in-Time 可用历史

附录 B 当前多处写：

```text
PROXY_HISTORY_START = 指数基日
```

这是很危险的。

指数通常有：

```text
base date
launch date
historical backfilled series
live calculated series
```

一个指数可以：

```text
base date = 2014
launch date = 2020
```

并在发布时回溯计算 2014~2020 的历史。

这段历史在 2015 年并不是投资者当时可获得的信息。

因此：

$$
IndexBaseDate
\ne
PointInTimeAvailableDate
$$

---

# 19. Proxy Metadata 必须扩展

每个 proxy 必须记录：

```text
index_base_date
index_launch_date
data_series_start
is_backfilled_before_launch
methodology_version
source
```

严格 Method OOS 中：

```text
pre-launch backfilled history
```

不能默认当成真正 Point-in-Time 指数历史。

允许用于：

```text
SCENARIO / METHOD PROXY
```

但必须标记。

这对以下尤其关键：

```text
HSTECH
STAR50
AI index
Robotics index
Innovation Drug index
other thematic indexes
```

---

# 20. CRITICAL-8：ETF adjusted price 必须明确用于什么

Gate 1 当前同时有：

```text
raw close
front/qfq adjusted close
NAV
```

Gate 2 前必须冻结不同价格字段的用途。

建议：

## Execution / Premium

使用：

```text
raw tradable market price
```

## Return / Correlation / Features

需要一个：

```text
total_return_consistent_series
```

不能默认所有数据源的 `qfq/front` 对 ETF 都有完全相同语义。

---

# 21. ETF 分红对研究结果的影响不可忽略

以下类型尤其需要检查：

```text
HK_DIVIDEND
CN_DIVIDEND
CASH_LIKE
CN_DURATION
部分 GOLD / cross-border products
```

如果直接用 raw close：

```text
distribution ex-date
```

会被错误当成价格下跌。

如果直接信任 provider qfq：

又需要确认：

- 分红调整是否完整；
- 基金拆分/折算是否完整；
- QMT 与 AkShare 的 adjustment factor 是否一致；
- adjustment 是否会影响 point-in-time feature semantics。

Gate 1 correction 至少抽查：

```text
3只高分红/债券ETF
+
1只普通股票ETF
```

在分红日前后：

```text
raw close
adjusted close
cash distribution
return
```

是否合理。

---

# 22. 建议冻结“双价格体系”

本项目后续使用：

```text
execution_price_series
```

与：

```text
research_total_return_series
```

两个明确概念。

不要让同一个：

```text
close
```

字段同时承担：

- 实盘成交；
- total-return feature；
- premium；
- PnL；

四种不同语义。

---

# 23. CASH_LIKE Slot 需要标记经济风险，不要求本 Gate 换标的

当前：

```text
CASH_LIKE preferred = 511360 短融ETF
```

它并不等于无风险现金。

它包含：

```text
short credit duration
credit spread
fund liquidity
```

Gate 1 alternative 中：

```text
511880 / 511990
```

更接近 money-market cash proxy。

本 Gate **不要求修改 Frozen Slot 或 preferred instrument**。

但必须在 `instrument_master` / universe audit 中将 511360 标记为：

```text
risk_class = SHORT_CREDIT
cash_equivalent = false
```

而 Broker Cash：

```text
risk_class = CASH
```

继续分开。

后续若要把 preferred 从 511360 改成 511880/511990：

```text
RFC required
```

---

# 24. Alternative Instrument 表需要升级

当前替代品筛选是良好开端，但不足以支持 InstrumentSelector。

每个 preferred / alternative 至少补：

```text
list_date
history_years
ADV20
ADV60
AUM
expense_ratio (if available)
benchmark
premium_data_available
QMT_market_data_available
```

对于 US_BROAD：

还必须增加：

```text
premium_risk_status
```

不能因为：

```text
513650 / 159655
```

是同一个指数，就认为它们天然解决 513500 premium 问题。

---

# 25. 当前 Universe 不要求修改

Reviewer 当前**不建议更换 11 Core + 5 Theme**。

保持：

```text
CORE = 11
THEME = 5
```

以下结论仍成立：

```text
STAR + SEMICONDUCTOR redundancy is high
AI overlaps growth
GOLD / CN_DURATION provide diversification
HK_DIVIDEND slot remains useful
US_BROAD slot remains useful
```

本次修订是：

> 修正数据定义和 Instrument evidence，

不是重新设计资产池。

---

# 26. Data Source 结论

Gate 1 推荐：

```text
QMT = primary mainland market data
```

Reviewer 同意。

但必须明确：

```text
QMT front-adjusted data
```

仍需 adjustment semantics audit。

03110：

```text
Sina historical = research fallback
official HKEX / fund manager = metadata source
QMT = currently unavailable
```

不能把 Sina 变成 Live source。

---

# 27. 03110 最新官方元数据应补入

Gate 1 correction 建议补：

```yaml
HK_DIVIDEND:
  code: "3110"
  exchange: HKEX
  currency: HKD
  listing_date: 2013-06-17
  southbound_eligible_from: 2024-05-06
  current_southbound_eligible: true
  board_lot_size: 50
  board_lot_effective_date: 2026-07-24
  management_fee: 0.0068
  qmt_market_data: false
  qmt_order_capability: unknown_pending_gate6
```

注意管理费是基金层持续费用，不是每笔交易费。

---

# 28. Required Corrections Checklist

Agent 必须逐项完成：

## 28.1 513500

- [ ] 将历史 `premium` 改名为 `close_to_official_nav_gap`。
- [ ] 删除“历史实时溢价已可得”的结论。
- [ ] 删除当前 `8.74% > P95` 作为实时 PremiumGuard 证据的表述。
- [ ] 保留“官方已提示显著二级市场溢价风险”。
- [ ] 记录历史 IOPV 为 `NOT_AVAILABLE`。
- [ ] 明确 Gate 2 不允许用 asynchronous NAV gap 直接调 PremiumGuard threshold。

## 28.2 03110.HK

- [ ] board lot 更新为 50。
- [ ] 记录 2026-07-24 生效。
- [ ] 区分 official lot 与 broker metadata support。
- [ ] T+0 / same-day trading 的 authority 改为 HKEX/Southbound，而不是 SSE cross-border ETF rule。
- [ ] 保留 2024-05-06 Southbound eligibility start。
- [ ] 计算 ADV20 / ADV60。

## 28.3 Liquidity

- [ ] 所有 “ADV=单日成交额” 字段改名。
- [ ] 对 16 preferred instruments 计算 ADV20 / ADV60。
- [ ] 511260 / 511360 使用 QMT amount 补齐。
- [ ] alternatives 至少计算 ADV20。

## 28.4 AUM

- [ ] Market Cap 与 AUM 分开。
- [ ] 补 511260 AUM。
- [ ] 补 511360 AUM。
- [ ] 03110 使用官方 NAV-based AUM。
- [ ] 513500 不得用二级 market cap 代替 fund AUM。

## 28.5 Correlation

- [ ] 核验 rho120/rho250 重复值是否正确。
- [ ] 至少 3 对独立 pandas 手算核验。
- [ ] Gate Packet 中直接展示 overlap start/end/N。
- [ ] `downside` 改名 `CN_LARGE_DOWNSIDE_CORR`。
- [ ] 删除当前 union-tail Pearson 作为正式 tail metric。
- [ ] 加 lower-tail co-exceedance 或 benchmark-stress tail metric。
- [ ] 不用当前 tail=-0.646 等数值做强风险结论。

## 28.6 Proxy

- [ ] 每个 proxy 补 `index_launch_date`。
- [ ] 区分 `base_date` 与 `launch_date`。
- [ ] 标记 `is_backfilled_before_launch`。
- [ ] pre-launch backfilled history 不进入严格 PIT OOS。

## 28.7 Price semantics

- [ ] 冻结 `execution_price_series`。
- [ ] 冻结 `research_total_return_series`。
- [ ] 抽查 ETF 分红/除息 adjustment。
- [ ] 记录 QMT front / AkShare qfq adjustment semantics。
- [ ] Gate 2 feature 不允许无定义地混用 raw/qfq/NAV。

## 28.8 CASH_LIKE

- [ ] 511360 标记为 `SHORT_CREDIT`。
- [ ] 不把 511360 等同 Broker Cash。
- [ ] 暂不改 preferred；如后续切换货币 ETF，走 RFC。

---

# 29. Correction Packet 要求

生成：

```text
docs/review_packets/GATE_1_CORRECTIONS.md
```

必须包含：

```markdown
# GATE 1 Corrections

## 1. 513500 timing / premium correction
## 2. 03110 official metadata correction
## 3. ADV20/ADV60 table
## 4. AUM vs market cap table
## 5. Correlation script verification
## 6. Revised stress/tail metric
## 7. Proxy base-date vs launch-date table
## 8. ETF adjustment / dividend spot checks
## 9. Updated universe table
## 10. Files changed
## 11. Commands
## 12. Exact outputs
## 13. Commit SHA
```

---

# 30. Gate 2 Authorization Criteria

只有以下条件都满足才允许 Gate 2：

```text
513500 historical premium semantics corrected
03110 lot corrected
ADV fields corrected
critical AUM data filled or justified
correlation calculation verified
tail metric corrected
proxy launch/backfill metadata added
price-series semantics frozen
```

然后：

```text
GATE_1 = APPROVED
GATE_2 = AUTHORIZED
```

---

# 31. Gate 2 预先提醒：不要过度实现

Gate 2 允许实现：

```text
TargetAssetWeights
PortfolioAccounting
MockBroker
Cost model skeleton
Tradability
PremiumGuard interface
FX skeleton
ChinaETFPortfolioEnv
no-lookahead tests
```

但 Gate 2 仍然：

```text
NO RL performance optimization
NO Optuna
NO live QMT orders
NO Theme Sleeve
```

---

# 32. Gate 1 当前逐项裁决

| 项目 | 结论 |
|---|---|
| 16/16 preferred instrument coverage | PASS |
| QMT mainland data availability | PASS |
| 03110 Southbound eligibility | PASS |
| 03110 board lot | **REVISE** |
| 03110 QMT quote limitation | PASS |
| 513500 official premium risk | PASS |
| 513500 historical executable premium | **REVISE / CRITICAL** |
| raw/NAV/IOPV field separation | PARTIAL |
| alternatives screening | PARTIAL |
| ADV liquidity metrics | **REVISE** |
| AUM completeness | PARTIAL |
| rho120/rho250 | **VERIFY** |
| downside definition | REVISE NAME |
| tail correlation definition | **REVISE / CRITICAL** |
| proxy plan | PARTIAL / add launch-date |
| Point-in-Time discipline | GOOD, incomplete proxy metadata |
| frozen universe unchanged | PASS |
| unauthorized implementation | PASS |

---

# 33. Reviewer Summary

Gate 1 已经证明：

> 这套 ETF Universe 可以获得足够的数据，并且核心资产结构具有研究价值。

最有价值的实证发现仍然成立：

1. `STAR` 与 `SEMICONDUCTOR` 高度重复；
2. `AI` 与中国成长核心资产高度重叠；
3. `CN_DURATION` 和 `GOLD` 为组合提供重要非权益风险源；
4. `HK_DIVIDEND` 是有价值的港股价值风格 Slot；
5. `US_BROAD` 必须保留，但具体 QDII Instrument 的折溢价执行问题必须单独处理。

但 Gate 1 当前把若干“可计算的数”过早解释成了“可交易事实”：

- `close/NAV gap` → 真 premium；
- 单日成交额 → ADV；
- index base date → PIT history；
- union-tail Pearson → crash diversification；
- broker metadata unknown → official lot unknown。

这些必须在进入 Environment 之前修正。

---

# 34. Reviewer Approval Record

```yaml
gate: 1
decision: REVISIONS_REQUIRED_BEFORE_GATE_2
date: 2026-08-08

universe:
  core_slots: unchanged
  theme_slots: unchanged

permission:
  patch_gate1_documents: true
  continue_data_audit: true
  enter_gate2: false
  implement_portfolio_env: false
  train_rl: false
  connect_qmt_orders: false

required_next_packet:
  GATE_1_CORRECTIONS.md
```

---

# 35. Agent 下一条指令

```text
1. 不进入 Gate 2。
2. 按 Required Corrections Checklist 修订 Gate 1。
3. 生成 GATE_1_CORRECTIONS.md。
4. 提交 correction commit。
5. STOP。
6. 将 GATE_1_CORRECTIONS.md 回传 Reviewer / ChatGPT。
```

---

## END OF REVIEWER RESPONSE
