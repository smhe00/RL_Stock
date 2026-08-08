# FinRL-X 中国 ETF 多资产强化学习配置与实盘系统
## Codex / Agent 工程执行规格 V1.0

> **文档用途**：本文件是后续 Codex / Coding Agent 的主执行规范（Execution Spec / Source of Truth）。  
> **目标读者**：可能使用较低推理预算、上下文有限的自动编码 Agent。  
> **核心原则**：Agent 不得凭经验改变关键架构；遇到不确定事项先取证、写 RFC、生成 Review Packet，然后停止在 Gate 等待人工/ChatGPT 复核。  
> **基线冻结日期**：2026-08-08。  
> **最终目标**：研究结果能够从严格 OOS 回测平滑迁移到 QMT / miniQMT Paper Trading 和小资金实盘，而不是只得到漂亮的历史曲线。

---

# 0. Agent 启动后必须先读本节

## 0.1 绝对禁止事项

Agent **不得**做以下事情，除非有明确的书面批准记录：

1. 不得把框架从 **FinRL-X / FinRL-Trading** 换回经典 FinRL 作为主框架。
2. 不得把 TD3 / SAC / PPO 改成其他算法并替代主实验。
3. 不得让 RL 直接输出具体 ETF 代码；RL 输出的是固定维度的 **Asset Slot / Sleeve Weight**。
4. 不得让主题资产数量改变 RL 网络的 action dimension。
5. 不得用当天收盘价生成信号后又假设按当天收盘价成交。
6. 不得随机打乱时间序列做 Train/Test Split。
7. 不得使用 Test/OOS 数据进行 Feature Scaling、Hyperparameter Selection、Universe Selection 或阈值调参。
8. 不得使用未来才上市的 ETF 历史“补齐”成真实 ETF 数据；若使用指数代理必须显式标记 `is_proxy=true`。
9. 不得把 2026 年已知政策赛道回测到过去后宣称是严格 OOS Alpha。
10. 不得把单边券商佣金 `0.00005` 当成总交易成本。
11. 不得忽略 ETF 折溢价、Bid-Ask Spread、Slippage、交易规则、停牌或港股通资格变化。
12. 不得在未完成 Paper Trading 验证前直接调用真实下单接口。
13. 不得让策略模块 import / 调用 QMT API；Broker 必须通过 Adapter 隔离。
14. 不得删除失败实验、异常结果或不利的随机种子。
15. 不得只报告“最佳一次训练结果”。
16. 不得因为某个模型历史收益高就提前进入下一阶段。
17. 不得未经批准自动扩大主题池、ETF 池或宏观特征集合。
18. 不得为了“让回测更好看”调整交易成本、成交价格模型或回测时间窗口。
19. 不得修改本文件的 Frozen Decisions；如确有必要，必须先走 RFC 流程。
20. 不得越过本文定义的 `STOP-GATE`。

---

# 1. 项目目标

建立一套基于 **FinRL-X** 的中国可交易 ETF 多资产动态配置系统。

主要比较三种强化学习算法：

- TD3
- SAC
- PPO

研究问题不是：

> “预测某只 ETF 明天上涨还是下跌”。

而是：

> 在给定市场状态、当前组合、交易成本和风险约束下，动态产生下一期目标资产配置权重。

形式化：

$$
s_t \rightarrow \pi_\theta(s_t) \rightarrow w_t^{raw}
$$

经过确定性工程模块：

$$
w_t^{raw}
\rightarrow
w_t^{risk}
\rightarrow
w_t^{tradable}
\rightarrow
w_t^{instrument}
\rightarrow
Orders_t
$$

最终形成：

```text
Market Data
    ↓
Point-in-Time Features
    ↓
TD3 / SAC / PPO
    ↓
Asset/Sleeve Weights
    ↓
Risk Overlay
    ↓
Tradability / Premium / Liquidity Controls
    ↓
Instrument Selector
    ↓
Order Generator
    ↓
BrokerAdapter
    ↓
QMT / miniQMT
    ↓
A股 ETF / 港股通 ETF
```

项目必须同时满足：

- 可复现研究；
- 无明显 Look-Ahead；
- Walk-forward OOS；
- 真实交易成本；
- 多随机种子；
- 可回测；
- 可 Paper Trading；
- 可小资金实盘；
- 研究与实盘使用同一权重语义。

---

# 2. 为什么使用 FinRL-X

主框架固定为：

**AI4Finance-Foundation / FinRL-Trading（FinRL-X）**

上游定位：

- weight-centric；
- 数据 / 策略 / 回测 / 执行模块化；
- Stock Selection；
- Portfolio Allocation；
- Timing；
- Risk Overlay；
- Alpaca paper/live execution；
- 目标权重作为策略与执行之间的统一接口。

FinRL-X v1.0.0 于 2026 年 3 月首次公开发布，论文为：

`FinRL-X: An AI-Native Modular Infrastructure for Quantitative Trading`
`arXiv:2603.21330`

上游官方 Portfolio Allocation 示例当前明确展示 PPO / SAC。经典 FinRL 2026 版本明确支持 A2C / DDPG / PPO / TD3 / SAC。

**因此工程决策为：**

- FinRL-X = 主架构；
- Stable-Baselines3 = DRL 算法实现；
- TD3 必须按 FinRL-X 的 `generate_weights()` / weight-centric contract 接入；
- 不需要自己重写 TD3 数学算法；
- 如果当前 FinRL-X branch 已经包含 TD3 allocator，则复用；
- 如果没有，则实现一个最小、隔离、可测试的 TD3 allocator adapter；
- 不得为了 TD3 回退到经典 FinRL 作为整个系统框架。

---

# 3. 上游版本管理

Agent 第一次执行必须：

1. 检查当前 FinRL-X 最新代码；
2. 记录：
   - repository；
   - branch；
   - commit SHA；
   - release/tag；
   - Python version；
   - Stable-Baselines3 version；
   - Gym/Gymnasium version；
   - PyTorch version；
3. 生成：

```text
docs/upstream/FINRL_X_UPSTREAM_SNAPSHOT.md
```

4. 在项目配置中保存：

```yaml
finrl_x:
  repository: AI4Finance-Foundation/FinRL-Trading
  commit: <exact_sha>
  observed_date: 2026-08-08_or_actual_date
```

### 规则

- 开发过程中不得无声升级 FinRL-X。
- 若升级 upstream，必须重新跑 regression tests。
- Upstream change 需要 RFC。
- 不要大规模 fork-and-rewrite upstream。
- 优先用扩展模块 / Adapter / Subclass / Composition。

---

# 4. 冻结的投资范围

投资标的限定为中国投资者可通过境内证券账户实际交易的 ETF，包括：

1. 上交所 ETF；
2. 深交所 ETF；
3. 港股通合资格 ETF。

暂不纳入：

- A/H 个股；
- 海外券商直接交易的美股 ETF；
- 期货；
- 期权；
- 杠杆 ETF；
- 反向 ETF；
- 融资融券；
- 做空；
- 加杠杆。

组合基础货币：

$$
BaseCurrency = CNY
$$

香港资产必须有独立 Currency / FX 处理。

---

# 5. 资产设计原则：Asset Slot 与 ETF Instrument 解耦

**RL 不学习 ETF 代码。**

RL 只学习经济风险槽位：

```text
Asset Slot
```

具体 ETF 代码由：

```text
InstrumentSelector
```

决定。

例如：

```text
US_BROAD
    ↓
InstrumentSelector
    ↓
513500 或同类更优替代ETF
```

目的：

- 允许 ETF 替代；
- 允许因溢价暂时禁止买入；
- 允许某 ETF 流动性恶化；
- 允许港股通资格变化；
- 不因交易工具改变而重训 RL；
- 研究对象保持为“资产配置”，不是 ETF 代码记忆。

---

# 6. Core Asset Slot V1.0

当前冻结的核心风险槽位：

| Slot | Preferred Instrument | 角色 |
|---|---:|---|
| `CN_LARGE` | 510300 | 沪深300 / 中国大盘 |
| `CN_SMALL` | 512100 | 中证1000 / Size |
| `CN_DIVIDEND` | 512890 | 红利低波 / Value / LowVol |
| `CHINEXT` | 159915 | 创业板 / 成长制造 |
| `STAR` | 588000 | 科创50 / Hard Tech |
| `HK_TECH` | 513180 | 港股科技成长 |
| `HK_DIVIDEND` | 03110.HK | 港股高息价值 |
| `US_BROAD` | 513500 | 美国大盘权益 |
| `GOLD` | 518880 | 黄金 |
| `CN_DURATION` | 511260 | 10Y 国债 / Duration |
| `CASH_LIKE` | 511360 | 短融 / Cash-like |

数量：

$$
N_{core}=11
$$

### 注意

`CASH_LIKE` 不是券商真实现金。

执行层还必须维护：

```text
BROKER_CASH_BUFFER
```

用于：

- 佣金；
- 交易费用；
- 价格波动；
- 最小交易单位误差；
- 港股费用；
- 未成交订单；
- 汇率误差。

V1 默认：

```yaml
execution:
  broker_cash_buffer_pct: 0.01
```

即 1%。

该值可以后续验证后修改，但属于 Execution 参数，不能由 RL 直接支配。

---

# 7. Policy Theme Candidate Pool V1.0

冻结日期：2026-08-08。

候选主题：

| Theme | Preferred ETF | 政策映射 |
|---|---:|---|
| `SEMICONDUCTOR` | 512480 | 集成电路 |
| `AI` | 515070 | 人工智能+ / 算力 / AI应用 |
| `ROBOTICS` | 159770 | 机器人 / 具身智能 |
| `BIOTECH` | 159992 | 创新药 / 生物医药 |
| `AEROSPACE` | 512660 | 航空航天 / 卫星 / 军工电子代理 |

2026 年政策关注的其他方向，例如：

- 低空经济；
- 商业航天；
- 6G；
- 量子科技；
- 生物制造；
- 脑机接口；
- 未来能源；

进入 `WATCHLIST`，不因为政策重要就自动加入 RL 训练。

---

# 8. 关键修正：RL Action Dimension 必须固定

**禁止**：

```text
今天11维
明天12维
后天13维
```

Stable-Baselines3 的 TD3 / SAC / PPO policy 需要固定 observation/action space。

因此正式结构改为：

## Phase 1 — Core-only

固定：

$$
ActionDim=11
$$

## Phase 2 — Hierarchical Theme Sleeve

顶层固定：

```text
11 Core Slots + THEME_SLEEVE
```

即：

$$
ActionDim=12
$$

RL 只决定：

$$
w_{THEME\_SLEEVE}
$$

具体主题由 ThemeSelector / ThemeAllocator 决定。

结构：

```text
TD3 / SAC / PPO
      ↓
12-d Fixed Top-Level Weights
      ↓
THEME_SLEEVE total weight
      ↓
ThemeSelector
      ↓
0~2 active themes
      ↓
ThemeAllocator
      ↓
Concrete theme weights
```

若没有任何主题满足条件：

$$
K=0
$$

则：

```text
THEME_SLEEVE weight
    → CASH_LIKE
```

而不是改变 action dimension。

---

# 9. ThemeSelector V1

Phase 2 的第一版 ThemeSelector 必须是简单、确定、可审计的规则，不要一开始再引入第二套 RL。

建议 V1：

对每个 Theme：

$$
Score_i=
\frac{R_{60,i}}
{\sigma_{60,i}+\epsilon}
$$

并加入趋势过滤：

$$
Price_i > MA_{120,i}
$$

有效候选要求：

$$
Score_i>0
$$

然后：

```text
Select top 0~2
```

如果 0 个满足，则 `K=0`。

如果 1 个满足，则 `K=1`。

如果 >=2 个满足，则选择 Top-2。

Theme sleeve 内 V1 可使用：

```text
Equal Weight among active themes
```

或者经审批后使用 Score-proportional。

**不要同时修改 Selector 和 Top-level RL，否则难以判断收益来自哪里。**

---

# 10. Theme 与 Core 的重复暴露

## 10.1 STAR 与 Semiconductor

科创50当前存在较高半导体暴露。

因此：

```text
588000 = Hard-Tech Base
512480 = Semiconductor Tilt
```

不得认为完全独立。

硬约束：

$$
w_{STAR}+w_{SEMICONDUCTOR}
\le
W_{HardTech,max}
$$

V1：

```yaml
risk:
  hardtech_max: 0.30
```

---

## 10.2 China Growth 总暴露

定义：

$$
W_{GrowthCN}=
w_{CHINEXT}
+w_{STAR}
+w_{SEMICONDUCTOR}
+w_{AI}
+w_{ROBOTICS}
$$

V1：

```yaml
risk:
  china_growth_max: 0.50
```

---

## 10.3 Policy Theme 限额

```yaml
risk:
  single_theme_max: 0.12
  theme_sleeve_max: 0.25
```

即：

$$
w_i^{theme}\le12\%
$$

$$
\sum w_{theme}\le25\%
$$

这些是安全上限，不是目标权重。

---

# 11. Core 资产风险解释

Core 不是 11 个完全独立的资产。

分层理解：

## Level A — 大类独立性

```text
GOLD
CN_DURATION
CASH_LIKE
US_BROAD
```

## Level B — 地区/风格

```text
CN_LARGE
CN_SMALL
CN_DIVIDEND
HK_TECH
HK_DIVIDEND
```

## Level C — 中国成长

```text
CHINEXT
STAR
```

## Level D — Policy Alpha Sleeve

```text
SEMICONDUCTOR
AI
ROBOTICS
BIOTECH
AEROSPACE
```

**Theme 的主要目标是 Alpha / Tactical Exposure，不是 Diversification。**

---

# 12. 数据架构：Point-in-Time 是硬要求

所有数据必须带有时间语义。

建议最少字段：

```text
event_time
available_time
source
instrument
field
value
quality_flag
```

其中：

- `event_time`：市场数据对应时点；
- `available_time`：策略实际可使用该信息的最早时点。

策略在决策时间 $t$ 只能使用：

$$
available\_time \le t
$$

---

# 13. 必须维护的数据表/数据集

建议逻辑表：

```text
instrument_master
daily_bars
nav_or_iopv
premium_discount
trading_calendar
tradability
stock_connect_eligibility
fx_rates
corporate_or_fund_events
features
universe_snapshots
backtest_runs
orders
fills
positions
```

### `instrument_master` 至少包含

```text
asset_slot
instrument_code
exchange
currency
asset_class
etf_type
list_date
delist_date
lot_size
tick_size
turnaround_rule
preferred
is_qdii
is_stock_connect
benchmark_name
source
```

---

# 14. 数据源优先级

Agent 不得只因调用方便就使用低质量网站数据。

优先级：

1. 券商 / QMT 可验证真实行情与交易元数据；
2. 上交所 / 深交所 / 港交所 / 港股通官方规则；
3. 基金公司官方 NAV / 产品信息；
4. 权威数据供应商；
5. AkShare / Tushare 等 API 作为数据获取工具；
6. 第三方网页只允许用于交叉验证，不作为唯一 Source of Truth。

每个数据源必须写入：

```text
docs/data/DATA_SOURCE_MANIFEST.md
```

---

# 15. 数据代理与 ETF 上市前历史

严禁：

```text
ETF 2020年上市
→ 人工把2010~2019复制成“ETF价格”
```

允许：

```text
underlying index / asset proxy
```

但必须显式标记：

```text
is_proxy = true
proxy_for = <asset_slot>
```

必须区分两个回测层次：

## A. Method Research

目标：

> 判断 TD3 / SAC / PPO 作为资产配置算法是否有增益。

允许使用合规的 Asset-Class / Index Proxy 扩展历史，但必须 point-in-time，且不能伪装为 ETF 实盘价格。

## B. Instrument Backtest

目标：

> 判断具体 ETF + 成本 + 规则是否可执行。

只能在该 ETF 实际上市/可交易之后使用。

---

# 16. Universe Look-Ahead Bias

## 16.1 Core Universe

即使当前 Core 看起来“长期稳定”，仍然是 2026 年视角选择出的工具。

因此历史结果需要标记：

```text
METHOD_OOS
INSTRUMENT_SCENARIO
LIVE_FORWARD
```

不要把所有回测统一称为“严格 OOS”。

## 16.2 Policy Theme

2026 年政策主题尤其存在明显 hindsight。

因此：

```text
2026 Policy Theme Pool
```

只能用于：

- Scenario Backtest；
- 2026-08-08 之后 Forward Test；
- Paper；
- Live。

不得用其过去十年回测结果证明“模型过去就知道政策主题”。

---

# 17. ETF 交易规则必须数据化

上交所当前公开规则说明：

- 股票 ETF 通常 T+1；
- 债券 ETF、黄金 ETF、跨境 ETF、货币 ETF 可支持日内回转 T+0；
- ETF 最小买卖单位通常 1 手 = 100 份。

但工程实现**不得只按 Asset Class 硬编码**。

必须在 `instrument_master` 中逐 instrument 验证：

```text
turnaround_rule
lot_size
tick_size
```

原因：

- 市场规则可能变化；
- 港股通规则不同；
- 券商 API 实际权限可能不同。

---

# 18. 港股通 Capability Audit

`HK_DIVIDEND = 03110.HK` 进入 Live 前必须执行：

```text
BrokerCapabilityAudit
```

确认：

1. 当前仍属于合资格港股通 ETF；
2. 用户账户具备相应权限；
3. QMT / miniQMT 的该券商接口能否：
   - 订阅行情；
   - 查询证券元数据；
   - 查询港股通持仓；
   - 下单；
   - 撤单；
   - 获取成交；
4. 证券代码格式；
5. 交易货币 / 结算；
6. 交易费用；
7. Lot size；
8. 交易时间；
9. Sell-only /资格变化行为。

如果 QMT 不支持港股通 ETF：

```text
HK_DIVIDEND
```

Asset Slot 不删除。

改由 InstrumentSelector 寻找境内可交易的港股高股息替代 ETF。

**这就是 Asset Slot / Instrument 解耦的原因。**

---

# 19. Currency / FX Model

Portfolio base currency：

$$
CNY
$$

所有 instrument 必须有：

```text
currency
```

对于 HKD 资产：

$$
V_{CNY}
=
V_{HKD}\times FX_{HKD/CNY}
$$

需要：

```text
FXModel
```

不得忽略：

- Mark-to-market FX；
- 港股通结算汇率；
- FX 相关费用/价差（若有）；
- 汇率数据时间。

Backtest 与 Live 的 FX 语义必须一致或清晰记录差异。

---

# 20. 交易佣金与成本模型

用户给定 ETF 券商佣金：

$$
c_{commission}=0.00005
$$

单边，即万分之 0.5。

配置：

```yaml
cost:
  broker_commission_rate: 0.00005
  broker_min_commission_cash: null
```

### 重要

`broker_min_commission_cash` 未确认前不得假设为 0。

Agent 必须在 Live 前向券商/账户规则核实：

> ETF 每笔交易是否存在最低佣金。

---

# 21. 总交易成本

禁止：

$$
Cost=0.00005\times Turnover
$$

完整成本：

$$
C_t=
Commission_t
+ExchangeFee_t
+Tax_t
+Spread_t
+Slippage_t
+Impact_t
+FXCost_t
$$

分别实现。

---

# 22. CostModel 接口

```python
class CostModel(Protocol):
    def estimate(
        self,
        instrument,
        side,
        quantity,
        reference_price,
        market_state,
    ) -> CostBreakdown:
        ...
```

`CostBreakdown`：

```text
commission
exchange_fee
tax
spread
slippage
impact
fx_cost
total
```

---

# 23. MainlandETFCostModel

至少包含：

```text
broker commission
exchange fee
spread
slippage
market impact
```

费用规则配置化。

严禁把交易所费率散落在代码中。

配置建议：

```text
config/fees/mainland_etf.yaml
```

---

# 24. SouthboundETFCostModel

至少包含：

```text
broker commission
HKEX fee
regulatory levy
settlement related fee
spread
slippage
market impact
FX / settlement effect
```

配置：

```text
config/fees/southbound_etf.yaml
```

必须保存：

```text
effective_date
source
```

费用调整时可以 point-in-time 回放。

---

# 25. PremiumGuard

针对 QDII / 跨境 ETF，例如 `US_BROAD`：

RL 输出：

```text
US_BROAD weight
```

执行层选择 instrument。

`PremiumGuard`：

```python
class PremiumGuard:
    def status(self, instrument, asof) -> PremiumStatus:
        ...
```

至少返回：

```text
premium_pct
data_age
buy_allowed
warning_level
```

如果：

$$
Premium_t > Threshold_t
$$

则：

```text
BUY_DISABLED
HOLD_ALLOWED
SELL_ALLOWED
```

不要简单删除资产。

Threshold 初期不要拍脑袋写 1%。

应由历史分布计算：

$$
P_{90},P_{95},P_{99}
$$

并在 Validation 期选择，不得使用 Test 调参。

---

# 26. TradabilityMask

接口：

```python
class TradabilityMask:
    def get(self, instrument, timestamp) -> TradabilityState:
        ...
```

返回：

```text
buy_allowed
sell_allowed
reason_codes
```

Reason code 示例：

```text
NOT_LISTED
DELISTED
SUSPENDED
STOCK_CONNECT_NOT_ELIGIBLE
STOCK_CONNECT_SELL_ONLY
PREMIUM_TOO_HIGH
LIQUIDITY_TOO_LOW
MARKET_CLOSED
BROKER_UNSUPPORTED
DATA_STALE
```

必须允许：

```text
sell_allowed=True
buy_allowed=False
```

---

# 27. Liquidity Guard

不得使用未来成交量。

以 $t$ 时点可见数据计算：

```text
ADV20
median_spread
```

执行限制：

$$
OrderNotional_i
\le
p_{ADV}\times ADV20_i
$$

V1 可先配置保守值：

```yaml
execution:
  max_order_adv_fraction: 0.01
```

即不超过近期日均成交额 1%。

这不是最终参数，需根据实际资金规模验证。

---

# 28. Portfolio Accounting

每个 step 必须满足会计恒等式。

至少记录：

```text
cash
positions
market_value
fees
realized_pnl
unrealized_pnl
fx_pnl
portfolio_value
```

需要单元测试验证：

$$
V_{t+1}
=
V_t
+MarketPnL
+FXPnL
-Fees
+ExternalCashFlow
$$

无外部资金流时：

$$
ExternalCashFlow=0
$$

若不平衡超过 tolerance，测试失败。

---

# 29. RL Action Space

Phase 1：

$$
a_t\in R^{11}
$$

Phase 2：

$$
a_t\in R^{12}
$$

raw action 经过 simplex mapping。

推荐：

$$
w_i=
\frac{\exp(z_i)}
{\sum_j\exp(z_j)}
$$

或等价稳定实现。

映射必须单独测试：

- no NaN；
- no inf；
- $w_i\ge0$；
- $\sum w_i=1$。

之后 Risk Overlay / Cash Buffer 再调整可投资权重。

---

# 30. Observation Space V1：保持克制

不要一开始塞 100 个技术指标。

每个 Asset Slot V1 特征：

```text
log_return_5
log_return_20
log_return_60
log_return_120
realized_vol_20
realized_vol_60
drawdown_60
drawdown_250
```

即每资产 8 个。

Core-only：

$$
8\times11=88
$$

加：

```text
current target/actual weights
```

约 11 个。

再加入少量 Global Features：

```text
cross_sectional_return_dispersion_20
equity_average_corr_60
cn_large_vol_percentile_252
gold_equity_corr_60
bond_equity_corr_60
```

V1 不强制宏观数据。

宏观因子留作后续 Ablation：

- 利率；
- 汇率；
- PMI；
- 信用利差；
- VIX 等。

原因：

> 先证明基础环境与 RL pipeline 正确，再增加 Feature Complexity。

---

# 31. Feature Engineering 无泄漏规则

所有 rolling feature：

$$
Feature_t=f(Data_{\le t})
$$

Scaling：

- scaler 只在 Train Fit；
- Validation/Test 只 Transform；
- 每个 Walk-forward fold 独立 Fit。

禁止：

```text
全样本标准化
→ 再切Train/Test
```

---

# 32. Decision / Execution Timing

V1 研究主频率：

```text
Daily EOD decision
```

但严格使用：

```text
Day t close data
→ after-close feature
→ target weights
→ Day t+1 execution
```

禁止：

```text
Day t close features
→ Day t close fill
```

V1 backtest 成交参考：

```text
next trading session open
+ spread
+ slippage
+ fees
```

后续可用更细粒度行情升级，但必须作为单独实验。

---

# 33. 多市场 Calendar

A股与港股可能存在不同休市日。

统一策略时钟可使用：

```text
Mainland portfolio decision calendar
```

但每个 instrument 独立：

```text
market_open
buy_allowed
sell_allowed
last_valid_price
```

如果香港市场闭市：

- 不允许港股 instrument 买卖；
- 使用最后可用价格进行 mark；
- FX 仍按可获得的 point-in-time 数据处理；
- 不得 forward-fill 成“当天成交价”。

---

# 34. Reward V1

首版：

$$
r_t=
\log
\frac{V_{t+1}^{net}}
{V_t^{net}}
$$

其中已经扣除：

- commission；
- exchange fee；
- spread；
- slippage；
- impact；
- FX cost。

不额外先加 TurnoverPenalty。

原因：

> 让真实成本自己惩罚无意义的调仓。

---

# 35. Reward Ablation

后续固定四组：

### R0

$$
Reward=NetReturn
$$

### R1

$$
Reward=NetReturn-\lambda_\sigma Risk
$$

### R2

$$
Reward=NetReturn-\lambda_{DD}DrawdownPenalty
$$

### R3

$$
Reward=NetReturn-\lambda_{TO}Turnover
$$

先做 R0。

只有 R0 pipeline 正确后再做 R1/R2/R3。

---

# 36. Risk Overlay 分层

## RiskOverlayV0 — Mandatory Hard Constraints

用于算法公平比较：

- Long only；
- No leverage；
- single position max；
- theme sleeve max；
- hard-tech max；
- China growth max；
- cash buffer；
- tradability；
- premium；
- liquidity；
- lot size。

## RiskOverlayV1 — Optional Dynamic Risk

后续可增加：

- volatility targeting；
- drawdown brake；
- regime risk-off；
- trailing stop。

**必须单独 Ablation。**

不要把动态风控的收益误算成 TD3/SAC/PPO 的收益。

报告必须同时给：

```text
RAW POLICY
POLICY + V0
POLICY + V1
```

---

# 37. Baseline Strategies

至少：

1. Equal Weight；
2. Risk Parity；
3. Minimum Variance；
4. Mean-Variance；
5. Momentum；
6. Trend + Risk Parity。

所有 baseline 尽量使用与 RL 相同：

- universe；
- cost；
- execution timing；
- tradability；
- risk overlay。

否则比较无意义。

---

# 38. TD3 / SAC / PPO 公平比较

固定：

```text
same data
same folds
same features
same reward
same costs
same execution model
same risk overlay
same initial capital
same asset universe
```

算法不同。

---

# 39. Algorithm Smoke Test

第一轮只要求：

- 能训练；
- reward 非 NaN；
- weight 合法；
- policy 能产生不同状态下的不同权重；
- Backtest accounting 正确；
- 保存/加载模型后结果一致；
- seed 固定时可复现。

Smoke Test 不做性能结论。

---

# 40. Hyperparameter 原则

在首次 pipeline review 前：

**禁止大规模 Optuna。**

Smoke Test 可以：

- Stable-Baselines3 默认参数；
- 小幅必要适配；
- seed=42。

Gate 通过后才允许调参。

Hyperparameter 只能依据：

```text
Train + Validation
```

不得依据 Test。

三算法计算预算要尽量可比。

建议初版最大：

```text
<= 20~30 trials / algorithm / fold-family
```

如需扩大，写 RFC。

---

# 41. Random Seeds

最低：

$$
N_{seed}=10
$$

正式结论推荐：

$$
N_{seed}=20
$$

报告：

```text
median
mean
std
IQR
best
worst
```

主结论看：

$$
Median
$$

而不是 Best Seed。

---

# 42. Walk-Forward

禁止随机切分。

结构示例：

```text
Train
→ Validation
→ Test
→ Roll Forward
```

具体年份由 `Data Availability Audit` 后确定。

每 fold：

1. Train；
2. Validation 选超参数；
3. Freeze；
4. Test；
5. 保存 immutable Test result；
6. 不得因 Test 不满意回头改参数；
7. 下一 fold。

最终拼接：

```text
OOS Equity Curve
```

---

# 43. OOS Data Contamination 防护

每个 fold 生成：

```text
FoldManifest
```

包含：

```text
train_start
train_end
validation_start
validation_end
test_start
test_end
scaler_fit_range
universe_snapshot
feature_version
cost_model_version
code_commit
random_seed
```

运行结果 hash 后保存。

---

# 44. 指标

至少：

```text
CAGR
Annualized Return
Annualized Volatility
Sharpe
Sortino
Maximum Drawdown
Calmar
Turnover
Total Transaction Cost
Cost / Gross Profit
Win Rate
CVaR
Worst 1D
Worst 5D
Recovery Time
Average Number of Active Assets
Average Cash-like Weight
```

RL 额外：

```text
seed dispersion
training stability
action concentration
weight turnover
policy entropy / action dispersion where applicable
```

---

# 45. Cost Stress Test

固定：

```text
1x
2x
3x
```

交易成本压力。

不能仅增加 commission。

Spread / Slippage / Impact 也应按规则成比例或按场景增加。

候选策略如果在 2x cost 下完全崩溃，不进入 Paper。

---

# 46. Execution Friction Stress

额外测试：

```text
next_open execution
next_open + 5bp
next_open + 10bp
1-day signal delay
missed_trade probability
```

目的是判断策略是否依赖理想成交。

---

# 47. Theme 历史测试标记

任何包含 2026 Policy Theme Pool 的历史结果必须在报告标题中包含：

```text
SCENARIO / HINDSIGHT-DEFINED THEME UNIVERSE
```

不得标记为：

```text
STRICT METHOD OOS
```

---

# 48. 推荐代码边界

尽量贴合 FinRL-X 当前目录，不要求机械照搬。

新增模块建议：

```text
src/
├── china_etf/
│   ├── universe/
│   │   ├── asset_slots.py
│   │   ├── instrument_registry.py
│   │   └── theme_selector.py
│   ├── data/
│   │   ├── provider.py
│   │   ├── point_in_time.py
│   │   ├── tradability.py
│   │   ├── premium.py
│   │   └── fx.py
│   ├── features/
│   │   └── etf_features.py
│   ├── environment/
│   │   └── portfolio_env.py
│   ├── allocators/
│   │   ├── ppo_allocator.py
│   │   ├── sac_allocator.py
│   │   └── td3_allocator.py
│   ├── risk/
│   │   └── risk_overlay.py
│   ├── cost/
│   │   ├── base.py
│   │   ├── mainland.py
│   │   └── southbound.py
│   ├── execution/
│   │   ├── instrument_selector.py
│   │   ├── order_generator.py
│   │   └── broker/
│   │       ├── base.py
│   │       ├── mock.py
│   │       └── qmt.py
│   └── validation/
│       ├── walk_forward.py
│       ├── metrics.py
│       ├── baselines.py
│       └── stress.py
```

如果 upstream 已有相同功能，优先复用。

---

# 49. 核心接口

## AssetSlot

```python
@dataclass(frozen=True)
class AssetSlot:
    name: str
    asset_class: str
    region: str
    style: str | None
    theme: str | None
    currency: str
```

## InstrumentDefinition

```python
@dataclass(frozen=True)
class InstrumentDefinition:
    code: str
    asset_slot: str
    exchange: str
    currency: str
    list_date: date
    lot_size: int
    tick_size: float
    turnaround_rule: str
    is_qdii: bool
    is_stock_connect: bool
    preferred: bool
```

## InstrumentSelector

```python
class InstrumentSelector:
    def select(
        self,
        asset_slot: str,
        asof: datetime,
        state: "MarketState",
    ) -> "InstrumentSelection":
        ...
```

## BrokerAdapter

```python
class BrokerAdapter(Protocol):
    def get_account(self): ...
    def get_positions(self): ...
    def get_cash(self): ...
    def get_quote(self, symbol): ...
    def get_instrument(self, symbol): ...
    def place_order(self, order): ...
    def cancel_order(self, order_id): ...
    def get_order(self, order_id): ...
    def get_fills(self, order_id): ...
```

不要把 `rebalance()` 作为唯一 Broker 原语。

`rebalance` 应主要在上层 `OrderGenerator / ExecutionPlanner` 中完成，以便：

- Backtest；
- Mock；
- QMT；

共享相同逻辑。

---

# 50. QMT Adapter 隔离

QMT / miniQMT 可能有：

- Windows 限制；
- 特定 Python 版本；
- xtquant dependency；
- 券商差异。

因此：

```text
Research Core
```

不得 import `xtquant`。

仅：

```text
src/china_etf/execution/broker/qmt.py
```

或独立 package 使用。

CI 中使用：

```text
MockBrokerAdapter
```

QMT 环境只跑 integration tests。

---

# 51. OrderGenerator

输入：

```text
current positions
target instrument weights
portfolio value
cash
quotes
lot sizes
fees
tradability
```

输出：

```text
ordered sells
ordered buys
```

要求：

1. 先计算理论 target shares；
2. 按 lot size 取整；
3. 保留 cash buffer；
4. 小额偏差可不交易；
5. 优先卖出再买入；
6. 使用 broker-reported available cash；
7. 不允许超卖；
8. 不允许交易 buy-disabled instrument。

配置：

```yaml
execution:
  weight_tolerance_bps: 20
  min_order_notional_cny: 1000
```

以上是初始值，后续可验证修改。

---

# 52. Backtest 与 Live 共享同一 Target Weight Contract

以下对象必须一致：

```text
TargetAssetWeights
TargetInstrumentWeights
RiskDecision
TradabilityDecision
OrderPlan
```

不要维护两套策略逻辑：

```text
research_strategy.py
live_strategy_rewritten.py
```

Live 不得重新解释 RL 输出。

---

# 53. Phase 规划

---

## Phase 0 — Upstream & Feasibility Audit

### 目标

确认 FinRL-X、数据、QMT 和 ETF universe 的真实能力边界。

### 必须输出

```text
docs/upstream/FINRL_X_UPSTREAM_SNAPSHOT.md
docs/data/DATA_SOURCE_MANIFEST.md
docs/universe/ETF_UNIVERSE_AUDIT.md
docs/execution/QMT_CAPABILITY_AUDIT.md
```

### 禁止

- 不训练正式模型；
- 不写真实下单；
- 不进行大规模重构。

---

## Phase 1 — Core Data + Environment

只使用 11 Core。

实现：

- Instrument Registry；
- Data Provider；
- Point-in-Time Features；
- Tradability；
- Cost Model；
- Portfolio Accounting；
- Environment；
- Mock Broker；
- basic baselines。

### Exit Criteria

所有 invariant tests 通过。

---

## Phase 2 — TD3 / SAC / PPO Core Research

实现统一 allocator。

完成：

- smoke train；
- single fold；
- multi-seed；
- walk-forward；
- baseline comparison；
- cost stress；
- execution stress。

---

## Phase 3 — Hierarchical Policy Theme Sleeve

加入：

```text
THEME_SLEEVE
```

固定 action dim 12。

实现 ThemeSelector。

只能做：

- Scenario Backtest；
- Forward Test。

不得污染 Core Method OOS 结论。

---

## Phase 4 — QMT Paper Trading

连接：

```text
QMTBrokerAdapter
```

先：

```text
dry-run
shadow portfolio
paper
```

验证真实数据延迟、订单、成交、费用、组合漂移。

---

## Phase 5 — Small-Capital Live

只有最终 Review Gate 批准后允许。

必须有：

- manual kill switch；
- position limit；
- daily reconciliation；
- alert；
- audit log；
- fallback safe portfolio。

---

# 54. 测试规范

必须使用 pytest 或项目既有测试框架。

## 54.1 Weight Invariants

```text
finite
non-negative
sum to expected total
masked asset cannot increase
cash buffer respected
```

## 54.2 No-Lookahead Tests

构造未来数据发生极端变化：

> 修改 $t+1$ 之后数据不能改变 $t$ 的 feature / action。

## 54.3 Cost Tests

- cost >= 0；
- qty 越大成本不能无故下降；
- buy/sell 费用按配置；
- min commission（若启用）正确；
- 2x stress 可预测。

## 54.4 Accounting Tests

Portfolio identity。

## 54.5 Tradability Tests

- pre-listing 禁买；
- sell-only 禁增仓；
- suspended 不成交；
- premium guard 禁买允许卖。

## 54.6 Action Dimension Tests

Phase 1 永远 11。

Phase 3 永远 12。

Theme K 变化不得改变 policy shape。

## 54.7 Persistence Tests

模型保存/加载结果一致。

## 54.8 Seed Tests

固定 seed 在同环境近似可复现。

---

# 55. 日志与可追溯性

每次实验必须有：

```text
run_id
git_commit
upstream_commit
config_hash
data_snapshot_id
feature_version
universe_version
cost_version
algorithm
seed
fold
start_time
end_time
```

输出目录：

```text
runs/<run_id>/
```

至少：

```text
config.yaml
manifest.json
metrics.json
weights.parquet
trades.parquet
equity_curve.parquet
training_log.*
```

---

# 56. 实验命名规范

示例：

```text
CORE_TD3_R0_DAILY_FOLD03_SEED07
CORE_SAC_R0_DAILY_FOLD03_SEED07
CORE_PPO_R0_DAILY_FOLD03_SEED07
```

Theme：

```text
SCENARIO_THEME_TD3_R0_...
FORWARD_THEME_SAC_...
```

名称中必须体现是否：

```text
STRICT_OOS
SCENARIO
FORWARD
PAPER
LIVE
```

---

# 57. 统计报告原则

禁止只写：

```text
TD3 Sharpe = 1.52
```

必须写：

```text
TD3 median Sharpe
IQR
seed distribution
fold distribution
transaction cost
MDD
turnover
```

同时给 Baseline。

主判断至少：

$$
P(Sharpe_{RL}>Sharpe_{Baseline})
$$

可通过 seeds / folds 的 paired comparison 估计。

高级统计（PSR/DSR/Bootstrap CI）可在基础流程稳定后加入。

---

# 58. Model Selection

最终候选不是“最高 CAGR”。

推荐评分考虑：

```text
OOS Sharpe
MDD
Calmar
2x Cost Survival
Seed Stability
Fold Stability
Turnover
Execution Robustness
```

如果：

- TD3 CAGR最高；
- 但 seeds 极不稳定；
- 或 2x cost 失效；

不得判定 TD3 胜出。

---

# 59. 初始风险限制

配置化：

```yaml
risk:
  long_only: true
  leverage_max: 1.0
  single_core_max: 0.25
  single_theme_max: 0.12
  theme_sleeve_max: 0.25
  hardtech_max: 0.30
  china_growth_max: 0.50
```

Cash Buffer：

```yaml
execution:
  broker_cash_buffer_pct: 0.01
```

所有超限处理必须记录：

```text
pre_overlay_weights
post_overlay_weights
constraint_reason
```

---

# 60. 不能过早优化的内容

以下内容在 Core Pipeline 验收前禁止投入大量工程：

- Transformer；
- LSTM；
- Attention；
- LLM sentiment；
- 另类数据；
- 高频数据；
- 自动宏观新闻；
- Multi-Agent；
- 自适应 reward；
- Meta-RL；
- Offline RL；
- Bayesian optimization 大规模调参；
- 强化学习 ThemeSelector；
- Intraday execution RL。

先证明最小系统。

---

# 61. Source of Truth 文档

建议 repository 内持续维护：

```text
docs/
├── EXECUTION_SPEC.md
├── DECISIONS.md
├── CODEX_AGENT_STATUS.md
├── upstream/
├── data/
├── universe/
├── review_packets/
└── rfc/
```

本文件应复制为：

```text
docs/EXECUTION_SPEC.md
```

---

# 62. Change Control / RFC

任何以下改动必须写：

```text
docs/rfc/RFC-XXXX-<topic>.md
```

包括：

- 换 ETF；
- 加/删 Asset Slot；
- 改主题池；
- 改 action dimension；
- 改 reward；
- 改主要 feature；
- 改交易频率；
- 改成交价模型；
- 改 risk limit；
- 改 cost assumption；
- 换 RL 库；
- 改 FinRL-X upstream；
- 进入真实下单。

RFC 格式：

```markdown
# RFC

## Proposed change
## Why
## Evidence
## Expected benefit
## Risks
## Backward compatibility
## Tests
## Impact on historical comparability
## Recommendation
```

写完后：

**STOP。**

等待 Reviewer 批准。

---

# 63. Reviewer / ChatGPT 回报机制

用户要求关键结果回报 ChatGPT 复核。

因此 Agent 在每个 Gate 必须：

1. 生成 Review Packet；
2. 更新 `docs/CODEX_AGENT_STATUS.md`；
3. 明确打印：

```text
STOP-GATE REACHED.
Please provide the generated review packet to the reviewer/ChatGPT
before continuing.
```

4. **不得自行继续下一个 Gate**。

除非 repository 中已有明确记录：

```text
APPROVED_BY_REVIEWER
```

和日期。

---

# 64. Review Packet 统一格式

每个 Gate 文件：

```text
docs/review_packets/GATE_<N>_<NAME>.md
```

必须包含：

```markdown
# Gate Review Packet

## 1. Goal
## 2. What was implemented
## 3. Files changed
## 4. Architecture decisions
## 5. Data sources
## 6. Commands executed
## 7. Tests and exact results
## 8. Metrics / tables
## 9. Known limitations
## 10. Deviations from EXECUTION_SPEC
## 11. Open risks
## 12. Recommended next action
## 13. Git commit / branch
```

不得只回复：

> “完成了，测试通过。”

---

# 65. STOP-GATE 0 — Upstream Audit

Agent 完成：

- FinRL-X snapshot；
- Portfolio Allocation path；
- PPO/SAC actual implementation；
- TD3 support audit；
- `generate_weights()` contract；
- Backtest engine；
- Risk overlay；
- Alpaca coupling；
- dependency graph。

必须回报：

```text
GATE_0_UPSTREAM_AUDIT.md
```

### Reviewer 重点检查

- 是否理解 FinRL-X 真实代码，而不是凭 README 猜；
- TD3 是已有还是需 adapter；
- 是否避免重写 upstream；
- 哪些模块可以直接复用。

**Gate 0 未批准不得正式写 China ETF Environment。**

---

# 66. STOP-GATE 1 — Data & Universe Audit

必须回报：

```text
GATE_1_DATA_UNIVERSE.md
```

包含 11 Core + 5 Theme：

- 上市日期；
- 当前代码；
- 交易所；
- 币种；
- ETF 类型；
- 成交额；
- AUM（若可得）；
- Benchmark；
- 历史覆盖；
- QMT 数据可得性；
- Premium 数据可得性；
- T+0/T+1；
- Lot size；
- 港股通资格；
- 代理数据方案。

必须生成相关性初筛：

$$
\rho_{120}
$$

$$
\rho_{250}
$$

以及：

- Downside correlation；
- Tail correlation；
- Rolling beta。

如果数据不足必须写：

```text
NOT AVAILABLE
```

不得编造。

### Reviewer 重点检查

- ETF Universe 是否需要替换；
- 588000 / 512480 重复暴露；
- 513500 premium；
- 03110/QMT feasibility；
- 历史长度是否足够。

**Gate 1 未批准不得冻结正式训练数据集。**

---

# 67. STOP-GATE 2 — Environment & Accounting

回报：

```text
GATE_2_ENVIRONMENT.md
```

必须展示：

- state shape；
- action shape；
- sample action → weights；
- one-step accounting；
- cost breakdown；
- tradability example；
- premium guard example；
- unit tests；
- no-lookahead test。

必须人工可读地给一个小型 3~5 天 hand-calculated example。

### Reviewer 重点检查

- 会计是否正确；
- Reward 是否正确；
- t / t+1 是否错位；
- 是否隐含未来数据；
- Cost 是否现实；
- Action 是否 fixed dimension。

**Gate 2 未批准不得开始正式 RL 比较。**

---

# 68. STOP-GATE 3 — First RL Sanity

使用：

```text
one fold
one seed
TD3
SAC
PPO
```

只做 sanity。

回报：

```text
GATE_3_RL_SANITY.md
```

必须包含：

- training curves；
- action distribution；
- weight concentration；
- turnover；
- reward stability；
- save/load；
- equal-weight baseline；
- runtime；
- errors/warnings。

### Reviewer 重点检查

- 是否出现 trivial policy；
- 是否全部现金；
- 是否极端单资产；
- 是否 weight collapse；
- TD3/SAC/PPO contract 是否真的一致；
- 是否需要修环境而不是调参数。

**Gate 3 未批准禁止 Optuna / 大规模 seeds。**

---

# 69. STOP-GATE 4 — Core Walk-Forward

正式：

```text
Core-only
TD3/SAC/PPO
>=10 seeds
baselines
walk-forward
1x/2x/3x costs
```

回报：

```text
GATE_4_CORE_WALKFORWARD.md
```

必须包含完整表：

| Model | Median CAGR | Median Sharpe | MDD | Calmar | Turnover | 2x Cost | Seed IQR |
|---|---:|---:|---:|---:|---:|---:|---:|

以及每 fold。

不得仅给总 Equity Curve。

### Reviewer 重点检查

- 是否真正 OOS；
- 是否 RL 真优于简单 baseline；
- 是否一个 fold 驱动全部收益；
- seeds 是否稳定；
- cost sensitivity；
- China growth concentration。

**Gate 4 是核心研究结论 Gate。**

---

# 70. STOP-GATE 5 — Theme Sleeve

仅在 Gate 4 完成后。

回报：

```text
GATE_5_THEME_SLEEVE.md
```

必须明确分：

```text
SCENARIO
FORWARD
```

并给：

- ThemeSelector active history；
- K=0/1/2 比例；
- Theme contribution；
- Theme sleeve turnover；
- Theme vs Core overlap；
- HardTech / ChinaGrowth constraint activity；
- 主题加入前后风险收益变化。

### Reviewer 重点检查

- 是否只是科技 Beta；
- 是否存在 hindsight；
- 是否主题逻辑复杂度值得；
- Theme 是否应继续进入 Paper。

---

# 71. STOP-GATE 6 — QMT Dry-Run / Paper

回报：

```text
GATE_6_QMT_PAPER.md
```

必须包含：

- Broker capability；
- code format；
- quote delay；
- target vs actual position；
- order rejects；
- partial fills；
- fees；
- slippage；
- daily reconciliation；
- 513500 premium events；
- HK instrument behavior；
- fallback behavior。

### Reviewer 重点检查

- Research→Live semantic drift；
- QMT限制；
- 港股通可执行性；
- cash buffer；
- order sequencing；
- 实际成本与 backtest 差异。

---

# 72. STOP-GATE 7 — Live Readiness

回报：

```text
GATE_7_LIVE_READINESS.md
```

必须提供：

```text
capital limit
max loss / kill switch
max single position
max daily turnover
failure modes
broker disconnect behavior
data stale behavior
model missing behavior
order rejection behavior
manual override
reconciliation
rollback
```

在 Reviewer 明确批准前：

```text
REAL ORDER = DISABLED
```

---

# 73. CODEX_AGENT_STATUS.md 格式

持续更新：

```markdown
# Current Phase

## Last completed task

## Current branch / commit

## Tests

## Current Gate

## Blockers

## Deviations

## Next intended step

## Reviewer approval
PENDING / APPROVED
```

Agent 每次恢复工作先读：

1. `EXECUTION_SPEC.md`
2. `DECISIONS.md`
3. `CODEX_AGENT_STATUS.md`
4. 最近 Review Packet。

---

# 74. P0 任务清单

## P0.1 Upstream inspection

完成 Gate 0。

## P0.2 AssetSlot Registry

创建 Core + Theme 定义。

## P0.3 Instrument Registry

不要把 ETF code 写进模型类。

## P0.4 Data Source Audit

确认历史数据与 point-in-time 可用性。

## P0.5 QMT Capability Audit

只读，不下单。

---

# 75. P1 任务清单

## P1.1 CostModel

Mainland / Southbound。

## P1.2 Tradability

实现状态机。

## P1.3 PremiumGuard

先接口 + 数据审计。

## P1.4 FXModel

港股资产。

## P1.5 Portfolio Accounting

必须先于 RL。

## P1.6 Environment

Core-only fixed 11。

完成 Gate 2。

---

# 76. P2 任务清单

## P2.1 Equal Weight

先跑通。

## P2.2 Traditional Baselines

Risk parity / min var / MVO / momentum。

## P2.3 PPO Adapter

## P2.4 SAC Adapter

## P2.5 TD3 Adapter

所有：

```python
generate_weights(...)
```

输出统一格式。

## P2.6 RL Sanity

完成 Gate 3。

---

# 77. P3 任务清单

## P3.1 WalkForwardRunner

## P3.2 MultiSeedRunner

## P3.3 StressRunner

## P3.4 Results Aggregator

## P3.5 Core Research

完成 Gate 4。

---

# 78. P4 任务清单

## P4.1 Theme Sleeve

固定 top-level dim = 12。

## P4.2 ThemeSelector

K=0~2。

## P4.3 Theme Exposure Constraints

## P4.4 Scenario / Forward reports

完成 Gate 5。

---

# 79. P5 任务清单

## P5.1 BrokerAdapter

## P5.2 MockBroker

## P5.3 QMTBrokerAdapter

## P5.4 ExecutionPlanner

## P5.5 Reconciliation

## P5.6 Dry-run / Paper

完成 Gate 6。

---

# 80. P6 — Live Safety

只有批准后。

至少：

```text
kill switch
max capital
max position
max turnover
stale-data block
model-error fallback
broker-disconnect block
daily reconciliation
audit logs
```

---

# 81. Fail-Safe Portfolio

Live 系统必须定义模型失效时行为。

V1 建议：

```text
NO NEW RISK
```

即：

- 停止增加风险资产；
- 不自动清仓；
- 保留已有持仓；
- 允许按明确 hard-risk rule 降风险；
- 新资金保留 `CASH_LIKE / broker cash`；
- 发出告警。

不要因为模型文件缺失就自动 100% 买入任何 ETF。

---

# 82. Data Staleness

每个数据源设置：

```text
max_age
```

若关键数据 stale：

```text
SIGNAL_INVALID
NO_REBALANCE
```

对于 Premium 数据缺失：

- QDII ETF 允许 Hold / Sell；
- 默认禁止新增买入，除非有批准的 fallback rule。

---

# 83. Live Model Registry

模型必须：

```text
model_id
algorithm
train_range
validation_range
code_commit
data_snapshot
feature_version
cost_version
risk_version
approval_status
```

只有：

```text
approval_status=LIVE_APPROVED
```

才能被 Execution service 加载。

---

# 84. Paper 与 Live 的差异必须记录

例如：

```text
Paper:
  mock fee
  delayed quote
  simulated fill

Live:
  actual broker fee
  actual fill
```

所有差异写：

```text
docs/execution/PAPER_LIVE_DIFF.md
```

---

# 85. Reconciliation

每天至少：

```text
broker positions
internal positions
cash
pending orders
fills
portfolio value
```

做 reconciliation。

差异超过 tolerance：

```text
TRADING_HALTED
```

直到人工处理。

---

# 86. 研究结论的最低标准

不能因为：

$$
Sharpe_{TD3}>Sharpe_{PPO}
$$

就宣布 TD3 最好。

最终需要回答：

## Q1

RL 是否整体优于传统资产配置？

## Q2

TD3/SAC/PPO 中谁在 OOS + 多 seeds 下更稳定？

## Q3

优势在真实成本、延迟和执行摩擦下是否存在？

## Q4

Theme Sleeve 是否增加真正的风险调整收益，还是仅增加科技 Beta？

## Q5

Paper Trading 与 Backtest 差异是否足够小？

## Q6

Live Execution 是否能安全复现 Target Weight？

---

# 87. 当前 Frozen Decisions

```yaml
framework: FinRL-X

algorithms:
  - TD3
  - SAC
  - PPO

base_currency: CNY

core_slots: 11

theme_candidates: 5

phase1_action_dim: 11

phase2_action_dim: 12

theme_active_count:
  min: 0
  max: 2

broker_commission_rate: 0.00005

positioning:
  long_only: true
  leverage: false

execution_semantics:
  decision: daily_after_close
  execution: next_trading_session
  same_close_fill: forbidden

validation:
  random_split: forbidden
  walk_forward: required
  min_seeds: 10
  preferred_seeds: 20

live_broker:
  target: QMT_or_miniQMT
  direct_strategy_broker_dependency: forbidden
```

---

# 88. 初始 ETF Universe 配置草案

```yaml
core:
  CN_LARGE:
    preferred: ["510300"]
  CN_SMALL:
    preferred: ["512100"]
  CN_DIVIDEND:
    preferred: ["512890"]
  CHINEXT:
    preferred: ["159915"]
  STAR:
    preferred: ["588000"]
  HK_TECH:
    preferred: ["513180"]
  HK_DIVIDEND:
    preferred: ["03110.HK"]
  US_BROAD:
    preferred: ["513500"]
  GOLD:
    preferred: ["518880"]
  CN_DURATION:
    preferred: ["511260"]
  CASH_LIKE:
    preferred: ["511360"]

themes:
  SEMICONDUCTOR:
    preferred: ["512480"]
  AI:
    preferred: ["515070"]
  ROBOTICS:
    preferred: ["159770"]
  BIOTECH:
    preferred: ["159992"]
  AEROSPACE:
    preferred: ["512660"]
```

注意：

> `preferred` 不是硬编码唯一 ETF。  
> Gate 1 必须筛选同类 alternative instruments。

---

# 89. 建议配置文件

```text
config/
├── universe.yaml
├── risk.yaml
├── execution.yaml
├── features.yaml
├── algorithms/
│   ├── td3.yaml
│   ├── sac.yaml
│   └── ppo.yaml
└── fees/
    ├── mainland_etf.yaml
    └── southbound_etf.yaml
```

实验结果必须保存配置快照。

---

# 90. Agent 输出质量要求

每项工作完成后必须回答：

1. 做了什么；
2. 为什么；
3. 改了哪些文件；
4. 测试了什么；
5. exact test output；
6. 有什么已知风险；
7. 是否偏离本规格；
8. 下一步是什么；
9. 是否触发 STOP-GATE。

不得只写：

```text
Done.
```

---

# 91. Agent 遇到歧义时的决策顺序

优先级：

1. 本 `EXECUTION_SPEC.md`；
2. `DECISIONS.md`；
3. Reviewer 已批准的 RFC；
4. FinRL-X upstream contract；
5. 官方交易所/券商规则；
6. 最小改动原则。

如果仍冲突：

```text
WRITE RFC
STOP
```

不要自行“合理猜测”。

---

# 92. 关键工程哲学

## 92.1 不追求模型复杂度

更复杂不代表更赚钱。

## 92.2 先保证环境正确

错误的 Environment 可以制造假的 Alpha。

## 92.3 真实成本比漂亮 Reward 更重要

## 92.4 风险约束必须可解释

## 92.5 Research 与 Execution 解耦

## 92.6 ETF 是 Instrument，Asset Slot 才是策略对象

## 92.7 Policy Theme 是 Alpha Sleeve，不是伪分散

## 92.8 OOS 结论优先于 In-Sample 曲线

## 92.9 Median Seed 优先于 Best Seed

## 92.10 Paper Trading 是必须阶段，不是形式流程

---

# 93. 第一条 Agent 实际指令

收到本文后，Agent **不要立即开始编码完整系统**。

第一步只做：

> **Phase 0 / Gate 0：FinRL-X upstream architecture audit。**

任务：

1. 获取/检查 FinRL-X 当前代码；
2. 确认 exact commit；
3. 找出：
   - `BaseStrategy`
   - `generate_weights()`
   - Portfolio Allocation 实现
   - PPO
   - SAC
   - 是否已有 TD3
   - BacktestEngine
   - transaction cost path
   - Risk Overlay
   - TradeExecutor
   - AlpacaManager
4. 画出当前 upstream 调用链；
5. 明确哪些代码可以原样复用；
6. 明确最小扩展点；
7. 不写 ChinaETFPortfolioEnv；
8. 不接 QMT；
9. 不训练；
10. 生成：

```text
docs/review_packets/GATE_0_UPSTREAM_AUDIT.md
```

然后：

```text
STOP-GATE REACHED.
```

由用户把 Review Packet 交给 ChatGPT 验证。

---

# 94. Reviewer 希望 Gate 0 回答的具体问题

Agent 必须逐条回答：

1. FinRL-X 当前正式版本与 commit 是什么？
2. README 所说的 PPO/SAC DRL allocator 实际代码在哪？
3. TD3 是否已经在 FinRL-X 中存在？
4. 如果不存在，最小接入点是什么？
5. `generate_weights()` 输入/输出 exact schema 是什么？
6. 当前 BacktestEngine 如何接受 weights？
7. transaction costs 当前在哪处理？
8. 当前 Risk Overlay 是否可复用？
9. TradeExecutor 对 Alpaca 耦合程度如何？
10. Broker abstraction 是否已存在？
11. 如果新增 QMT，最小改动文件有哪些？
12. 是否存在 Gym environment，还是策略直接生成 weights？
13. TD3/SAC/PPO 若需要 Gym 环境，最合适放在哪里？
14. 如何保证 Backtest 和 Live 使用同一个 weight contract？
15. 当前 upstream tests 覆盖哪些部分？
16. 哪些 upstream assumptions 明显不适合中国 ETF？

如果上述问题没有回答完整：

> Gate 0 不通过。

---

# 95. 最终成功定义

项目最终成功不是：

```text
“某次 TD3 回测收益 80%”
```

而是满足：

1. 无明显数据泄漏；
2. OOS 多 folds；
3. 多随机种子；
4. RL 对传统 baseline 有稳定增益或明确知道没有增益；
5. 交易成本后仍成立；
6. 2x cost / execution stress 后不过度崩溃；
7. Theme 不只是增加科技 Beta；
8. Paper 与 Backtest 行为一致；
9. QMT 能准确执行 Target Weight；
10. 有完整风险控制；
11. 有 kill switch；
12. 有可审计日志；
13. 用户能理解为什么系统持有什么资产；
14. 小资金 Live 表现与 Paper 差异处于可解释范围。

如果最终研究证明：

> Risk Parity / Momentum 等简单模型明显优于 TD3/SAC/PPO，

这仍然是**成功的研究结论**。

Agent 不得为了“必须用 RL”而扭曲实验。

---

# 96. 上游/规则参考 Source-of-Truth

Agent 执行时应重新核实最新版本，不能只依赖本文件日期。

主要参考对象：

- AI4Finance-Foundation / FinRL-Trading（FinRL-X）
- FinRL-X paper: arXiv:2603.21330
- AI4Finance-Foundation / FinRL（经典算法参考）
- Stable-Baselines3 官方文档
- 上海证券交易所 ETF 官方规则
- 深圳证券交易所 ETF 官方规则
- 沪港通 / 深港通官方标的与规则公告
- 香港交易所 ETF / Stock Connect 官方资料
- 用户券商 QMT / miniQMT / xtquant 官方接口与账户真实费率

### 原则

> **代码事实以当前 repository 为准；交易规则以当前交易所与券商实际规则为准；本文件只定义架构与验证原则。**

---

# 97. 文档状态

```text
Spec Version: 1.0
Status: FROZEN FOR PHASE 0
Date: 2026-08-08
Primary Framework: FinRL-X
Next Required Action: GATE 0 UPSTREAM AUDIT
Reviewer Gate Required: YES
```

---

## END OF EXECUTION SPEC
