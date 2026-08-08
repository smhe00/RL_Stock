# GATE 0 Reviewer Response
## FinRL-X 中国 ETF 项目 — Upstream Architecture Audit 审核意见

**Review status:** `APPROVED_WITH_REQUIRED_CORRECTIONS`  
**Reviewed artifact:** `GATE_0_UPSTREAM_AUDIT.md`  
**Audit target:** `AI4Finance-Foundation/FinRL-Trading`  
**Audited master commit:** `e65d6f0483ead7d2ef4a5fc940cdf960392a25c1`  
**Review date:** 2026-08-08

---

# 1. Reviewer Decision

Gate 0 的总体方向正确，已经完成本阶段最重要的工作：

- 找到了 FinRL-X 当前 master 的实际代码结构；
- 正确认识到中国 ETF 项目不能直接照搬上游的美国市场 Backtest / Alpaca Execution；
- 正确认识到 Mainland / Southbound CostModel、RiskOverlay、Tradability、Premium、FX、QMT Broker Adapter 必须自行实现；
- 没有越权开始中国 ETF Environment、QMT 或正式训练；
- 上游 commit 已固定，符合 reproducibility 要求。

因此：

> **Gate 0 可以通过，但必须先修正本回复列出的 4 个关键事实/架构表述。**

完成这些修正后，Agent **允许进入 Gate 1 — Data & Universe Audit**。

但仍然禁止：

- 编写正式 `ChinaETFPortfolioEnv`；
- 正式训练 TD3/SAC/PPO；
- 接真实 QMT 下单；
- 改变 Frozen ETF Universe；
- 改变 Reward / Action Space / Risk Limits；
- 大规模重构 FinRL-X。

---

# 2. 必须修正：TD3 并非“在 FinRL-X 中不存在”

原 Gate 0 文档写：

> “TD3 是否已在 FinRL-X 中存在？否。”

这个结论过强，需要修改。

当前 audited master：

```text
src/strategies/rl_model.py
```

明确存在：

```python
def train_td3(agent):
    TD3_PARAMS = {
        "batch_size": 100,
        "buffer_size": 1000000,
        "learning_rate": 0.001,
    }

    model_td3 = agent.get_model("td3", model_kwargs=TD3_PARAMS)

    trained_td3 = agent.train_model(
        model=model_td3,
        tb_log_name="td3",
        total_timesteps=30000,
    )
    return trained_td3
```

但是在当前：

```python
run_models(...)
```

中：

```python
#td3_model = train_td3(agent)
#sac_model = train_sac(agent)
```

被注释掉。

当前实际启用的是：

```text
A2C
PPO
DDPG
```

并且后续 TD3 / SAC evaluation path 同样被注释。

因此正确结论应改为：

> **FinRL-X master 中存在 TD3 的 legacy/helper training entry point，并通过经典 FinRL `DRLAgent.get_model("td3")` 调用 TD3；但 TD3 当前没有形成启用状态的、符合 FinRL-X `BaseStrategy.generate_weights()` contract 的正式 Portfolio Allocator。**

这是非常重要的区别。

## 2.1 后续工程决策不变

仍然建议：

```text
src/china_etf/allocators/
    ppo_allocator.py
    sac_allocator.py
    td3_allocator.py
```

三个 allocator 使用同一个基类/接口。

但是不要写成：

> “因为 upstream 完全没有 TD3，所以我们新增 TD3。”

应该写成：

> “upstream 有 TD3 legacy training helper，但当前不是 production-ready / contract-compliant allocator；本项目建立统一 TD3/SAC/PPO allocator layer。”

---

# 3. 必须修正：上游并不存在一个真正统一的 concrete weight schema

原 Gate 0 报告中最需要纠正的架构判断是：

> “上游已以 `StrategyResult.weights` 为统一接口（TradeExecutor 与 BacktestEngine 都消费 weights）。”

这个表述从**架构理念**上接近 README，但从**当前代码事实**上不准确。

---

## 3.1 StrategyResult 只规定类型为 DataFrame

当前：

```python
@dataclass
class StrategyResult:
    strategy_name: str
    weights: pd.DataFrame
    metadata: Optional[Dict[str, Any]] = None
```

以及：

```python
generate_weights(
    self,
    data: Dict[str, pd.DataFrame],
    target_date: Optional[str] = None
) -> StrategyResult
```

这里只规定：

```text
weights = pd.DataFrame
```

并没有冻结 DataFrame schema。

---

## 3.2 TradeExecutor 期待的是 long-form schema

当前：

```text
src/trading/trade_executor.py
```

的 `_weights_to_orders()` 实际直接读取：

```python
gvkey = row["gvkey"]
weight = row["weight"]
```

因此 Live Execution path 隐含要求：

```text
gvkey | weight
------+-------
xxx   | 0.20
yyy   | 0.30
...
```

---

## 3.3 BacktestEngine 期待的是 wide-form schema

当前：

```python
BacktestEngine.run_backtest(
    strategy_name,
    price_data,
    weight_signals,
)
```

其中 `weight_signals` 文档与实现要求：

```text
index   = dates
columns = tickers
values  = target weights
```

即：

```text
date        AAPL   MSFT   ...
2026-01-01  0.30   0.25
...
```

BacktestEngine 并不直接接受：

```text
StrategyResult
```

更没有直接接受：

```text
gvkey/weight long table
```

---

# 4. Reviewer 架构要求：定义我们自己的 canonical weight contract

这个问题不能留到后面临时解决。

中国 ETF 项目必须建立一个唯一 Source of Truth：

```python
@dataclass(frozen=True)
class TargetAssetWeights:
    decision_time: pd.Timestamp
    weights: pd.Series
    metadata: Mapping[str, Any]
```

其中必须满足：

```text
weights.index = AssetSlot ID
weights.value = float target weight
```

例如：

```text
CN_LARGE       0.15
CN_SMALL       0.08
CN_DIVIDEND    0.10
CHINEXT        0.08
STAR           0.08
HK_TECH        0.08
HK_DIVIDEND    0.08
US_BROAD       0.10
GOLD           0.10
CN_DURATION    0.08
CASH_LIKE      0.07
```

且：

$$
w_i \ge 0
$$

$$
\sum_i w_i = 1
$$

---

## 4.1 必须显式建立 Adapter

推荐：

```text
TargetAssetWeights
        │
        ├── to_backtest_frame()
        │        ↓
        │   date × asset/instrument wide frame
        │
        ├── InstrumentSelector
        │        ↓
        │   TargetInstrumentWeights
        │
        └── FinRLXStrategyAdapter
                 ↓
             StrategyResult
```

后续：

```text
Backtest
Paper
Live
```

都只能从同一个：

```text
TargetAssetWeights
```

向下转换。

不要让：

```text
Backtest DataFrame schema
```

和：

```text
Live DataFrame schema
```

各自成为 Source of Truth。

---

# 5. 必须修正：FinRL-X “版本”存在三个不同口径

Gate 0 报告写：

> 当前正式版本与 commit：master HEAD e65d6f...；remote tag v1.0.0 = 0b5b423...

需要补充一个重要事实：

当前 audited master 的：

```text
setup.py
```

写的是：

```python
version="2.0.2"
```

与此同时：

GitHub latest release 是：

```text
v1.0.0 — FinRL-X: Initial Public Release
```

发布时间：

```text
2026-03-25
```

tag commit：

```text
0b5b4235640e74cd6e59f374bb13b3779e898e57
```

而当前 master HEAD：

```text
e65d6f0483ead7d2ef4a5fc940cdf960392a25c1
```

时间：

```text
2026-05-02
```

因此不要简单写：

```text
FinRL-X current version = v1.0.0
```

或：

```text
current version = 2.0.2
```

正确记录方式：

```yaml
upstream:
  github_latest_release: v1.0.0
  github_release_commit: 0b5b4235640e74cd6e59f374bb13b3779e898e57
  audited_branch: master
  audited_commit: e65d6f0483ead7d2ef4a5fc940cdf960392a25c1
  package_metadata_version: 2.0.2
```

项目 reproducibility 以：

```text
audited_commit
```

为准，而不是版本字符串。

---

# 6. 必须补充：Dependency Audit 比报告写的更严重

Gate 0 已经正确指出：

> `requirements.txt` 未声明 DRL dependencies。

Reviewer 进一步核验后确认：

当前 `requirements.txt` 不包含至少：

```text
finrl
stable-baselines3
gymnasium
PyPortfolioOpt / pypfopt
```

而代码：

```text
rl_model.py
fundamental_portfolio_drl.py
```

实际 import：

```python
from finrl.agents.stablebaselines3.models import DRLAgent
from finrl.meta.env_portfolio_allocation.env_portfolio import StockPortfolioEnv
```

以及：

```python
from pypfopt ...
```

`setup.py` 的 optional `ml` extras 虽然包含：

```text
gymnasium
stable-baselines3
```

但仍然没有声明：

```text
finrl
pypfopt
```

因此 Gate 0 的判断：

> “clean install 不可复现当前 DRL path”

是成立的。

但请把证据补充完整，不要只写：

```text
requirements.txt 缺 DRL dependency
```

应明确：

> “requirements 与 setup extras 均不足以完整复现现有 fundamental_portfolio_drl / rl_model path。”

---

# 7. 一个额外的 upstream 风险：DRL path 并未真正接入 BaseStrategy contract

当前 repository 搜索 `generate_weights()`，主要正式 contract 位于：

```text
base_strategy.py
ml_strategy.py
trade_executor.py
```

而：

```text
fundamental_portfolio_drl.py
rl_model.py
```

属于较老/独立的 DRL workflow。

因此不能假设：

```text
README 写 DRL Allocator
=
当前所有 DRL code 已经实现 BaseStrategy contract
```

这正是中国 ETF 项目需要建立统一 allocator layer 的原因。

推荐：

```python
class BaseRLAllocator(Protocol):
    def fit(...): ...
    def generate_weights(...) -> TargetAssetWeights: ...
    def save(...): ...
    def load(...): ...
```

然后：

```text
TD3Allocator
SACAllocator
PPOAllocator
```

完全使用同一个 contract。

---

# 8. BacktestEngine 结论：报告基本正确，但必须降级为 reference implementation

Gate 0 对 BacktestEngine 的判断基本正确：

- `bt` library；
- 默认 `transaction_cost=0.001`；
- optional cost model；
- 默认美国 benchmark；
- 无中国市场交易制度；
- 无我们要求的 T/T+1 signal/execution semantics。

Reviewer 建议进一步锁死：

> **上游 BacktestEngine 不作为中国 ETF 最终回测 Source of Truth。**

原因不仅是成本。

当前 engine 会：

```python
price_data = price_data.ffill()
```

以及：

```python
weight_signals
    .reindex(price_data_clean.index)
    .ffill()
```

这种做法用于美国普通资产的 generic backtest 可以接受，但不能表达：

- ETF 尚未上市；
- 港股休市而 A 股开市；
- 港股通 sell-only；
- 停牌；
- QDII premium buy block；
- T+0 / T+1；
- lot size；
- next-open execution；
- 实际 cash availability。

因此：

```text
FinRL-X BacktestEngine
```

可以：

- 参考；
- smoke comparison；
- compatibility adapter；

但 Gate 2 之后正式中国 ETF OOS 结果，应以项目自己的：

```text
PortfolioAccounting
ExecutionSimulator / MockBroker
CostModel
TradabilityMask
```

为准。

---

# 9. Transaction Cost 审计：通过

Gate 0 对上游 transaction cost path 的判断可以批准。

当前：

```text
BacktestConfig.transaction_cost = 0.001
```

默认走：

```python
commissions=lambda q, p:
    abs(q) * p * transaction_cost
```

也支持：

```text
bt CostModel
```

以及 volume / volatility input。

结论正确：

> 中国 ETF 的 Mainland / Southbound CostModel 必须独立自建。

Gate 1/2 不要删除 upstream nonlinear-cost capability 的参考价值，但不要直接认为它满足中国 ETF 实盘要求。

---

# 10. Risk Overlay 审计：通过

Gate 0 判断正确：

当前上游没有满足本项目要求的 Portfolio-level Risk Overlay。

`TradeExecutor` 当前主要检查：

- max order value；
- max portfolio turnover；
- min order size。

这不是我们需要的：

```text
HardTech Exposure
China Growth Exposure
Theme Sleeve
Single Theme
Long-only
Cash Buffer
Premium
Tradability
Liquidity
```

因此：

```text
src/china_etf/risk/risk_overlay.py
```

自建是正确方向。

---

# 11. Alpaca Coupling 审计：通过，但发现一个必须禁止复制的危险行为

Gate 0 正确判断：

```text
TradeExecutor
```

对：

```text
AlpacaManager
```

高度耦合。

Reviewer 额外发现当前 upstream：

```python
_get_current_price(...)
```

在 quote 失败时：

```python
return 100.0
```

这种 fallback 在真实交易系统中不可接受。

中国 ETF Execution Layer 必须：

```text
FAIL CLOSED
```

即：

```text
quote missing / stale
    ↓
NO ORDER
    ↓
reason = QUOTE_UNAVAILABLE
```

绝对禁止：

```text
missing quote → invented default price
```

请把这条加入：

```text
docs/DECISIONS.md
```

作为硬性安全规则。

---

# 12. Broker Abstraction 审计：通过

Gate 0 判断：

> 上游没有真正通用 Broker abstraction。

批准。

我们继续采用：

```text
BrokerAdapter
├── MockBrokerAdapter
└── QMTBrokerAdapter
```

注意：

`rebalance()` 不应成为唯一 Broker primitive。

Broker 基础 primitive 保持：

```text
get_account
get_positions
get_cash
get_quote
get_instrument
place_order
cancel_order
get_order
get_fills
```

Portfolio rebalance 保持在：

```text
ExecutionPlanner / OrderGenerator
```

上层。

---

# 13. Upstream Tests 审计：接受

Gate 0 没有发现正式 `tests/` suite。

本项目必须自建：

```text
weight invariants
no-lookahead
cost
accounting
tradability
action dimension
persistence
seed
```

本 Gate 是 read-only architecture audit，因此：

> “没有执行 upstream tests”

不构成 Gate 0 失败。

---

# 14. 关于 `src/china_etf/`：批准，但增加边界条件

Gate 0 推荐：

```text
src/china_etf/
```

自建中国 ETF 核心。

Reviewer **批准**。

但必须避免另一个极端：

> 最终做成一个与 FinRL-X 完全无关的新框架，只是目录旁边放着 FinRL-X。

因此必须保留：

```text
FinRL-X weight-centric architecture
```

的核心思想与 boundary compatibility。

项目内部可以有更严格的 contract：

```text
TargetAssetWeights
TargetInstrumentWeights
RiskDecision
OrderPlan
```

然后在必要的上游边界：

```text
FinRLXStrategyAdapter
FinRLXBacktestAdapter
```

进行转换。

---

# 15. Reviewer 对 Gate 0 的逐项裁决

| Gate 0 项目 | 结论 |
|---|---|
| audited master commit | PASS |
| GitHub release识别 | PASS，但补 package version discrepancy |
| PPO/SAC位置识别 | PASS |
| TD3状态判断 | **REVISE** |
| `generate_weights()` signature | PASS |
| concrete weights schema | **REVISE / CRITICAL** |
| BacktestEngine识别 | PASS |
| transaction-cost path | PASS |
| Risk Overlay判断 | PASS |
| Alpaca coupling | PASS |
| Broker abstraction | PASS |
| Gym/StockPortfolioEnv判断 | PASS |
| Backtest-Live weight contract | **REVISE / CRITICAL** |
| upstream tests | PASS |
| 中国ETF不兼容项 | PASS |
| no unauthorized implementation | PASS |

---

# 16. Gate 0 最终状态

正式状态：

```text
GATE_0_STATUS = APPROVED_WITH_REQUIRED_CORRECTIONS
```

Agent 必须在进入 Gate 1 前先完成一个很小的文档修订 commit。

必须修改：

```text
docs/review_packets/GATE_0_UPSTREAM_AUDIT.md
docs/upstream/FINRL_X_UPSTREAM_SNAPSHOT.md
docs/DECISIONS.md
docs/CODEX_AGENT_STATUS.md
```

---

# 17. Required Corrections Checklist

Agent 必须逐项勾选：

- [ ] 将“TD3 不存在”改为“TD3 legacy helper 存在，但当前未启用为正式 FinRL-X allocator”。
- [ ] 增加 `train_td3()` / commented `run_models()` 状态说明。
- [ ] 将“Backtest 与 Live 共享同一 concrete `StrategyResult.weights` schema”删除。
- [ ] 明确 TradeExecutor long-form `gvkey/weight` 与 BacktestEngine wide-form date×ticker 的 schema mismatch。
- [ ] 增加本项目 `TargetAssetWeights` canonical contract 决策。
- [ ] 增加 Backtest / Execution Adapter 决策。
- [ ] 记录 GitHub release `v1.0.0`、master SHA 和 `setup.py version=2.0.2` 三个版本口径。
- [ ] 补充 dependency gap：`finrl` / `stable-baselines3` / `gymnasium` / `pypfopt` 的声明情况。
- [ ] 增加“upstream DRL path 不是正式 BaseStrategy allocator”的说明。
- [ ] 增加 `quote failure → FAIL CLOSED`，禁止 default price。
- [ ] 明确 upstream BacktestEngine 仅作为 reference/compatibility，不作为中国 ETF 正式 OOS Source of Truth。
- [ ] 更新 `CODEX_AGENT_STATUS.md` 为 Gate 0 approved-with-corrections。

完成后不需要再次提交一个完整 Gate 0 Review Packet。

只需保存：

```text
docs/review_packets/GATE_0_CORRECTIONS.md
```

内容包括：

```text
changed files
exact corrections
commit SHA
```

然后可直接进入 Gate 1。

---

# 18. Gate 1 — Reviewer 授权范围

完成上述 corrections 后：

```text
GATE 1 AUTHORIZED
```

Gate 1 **只允许做 Data & Universe Audit**。

允许：

- ETF 元数据调查；
- 交易规则调查；
- 数据源调查；
- QMT read-only data capability 调查；
- 历史数据覆盖；
- ETF / index proxy 设计；
- AUM / liquidity；
- premium / IOPV availability；
- Stock Connect eligibility timeline；
- correlation analysis；
- alternative instrument screening。

禁止：

- 写正式 PortfolioEnv；
- 写完整 CostModel；
- 写正式 RiskOverlay；
- 训练 RL；
- 调超参数；
- QMT 下单；
- 改 Frozen Asset Slots。

---

# 19. Gate 1 必须额外回答的问题

除原 EXECUTION_SPEC §66 外，Reviewer 要求 Gate 1 补充：

## 19.1 每个 Asset Slot 至少调查 alternative instrument

不要只列 preferred ETF。

格式：

| Slot | Preferred | Alternative 1 | Alternative 2 | Selection reason |
|---|---|---|---|---|

目的是验证：

```text
Asset Slot != ETF Code
```

架构是否真的可实现。

---

## 19.2 明确 ETF history 与 proxy history

每个 slot：

```text
ETF_REAL_HISTORY_START
PROXY_HISTORY_START
```

必须分开。

---

## 19.3 明确所有价格字段语义

至少区分：

```text
raw close
adjusted close
NAV
IOPV
premium/discount
```

不能把 ETF 收盘价和 NAV 混在一起。

---

## 19.4 相关性结果必须报告 overlap length

任何：

$$
\rho
$$

都必须同时报告：

```text
start
end
N observations
```

否则短历史 ETF 的 correlation 没有比较意义。

---

## 19.5 Downside / Tail Correlation 先定义再计算

Gate 1 报告中必须写清楚：

```text
Downside Correlation definition
Tail Correlation definition
```

Reviewer 批准定义后，才允许这些指标参与资产删选。

不要自行用不透明第三方函数得到一个数字。

---

## 19.6 03110.HK

必须分别回答：

```text
official southbound eligibility
historical eligibility start
current eligibility
market data availability
QMT quote capability
QMT order capability
currency
lot size
fee availability
```

如果券商/QMT capability 无法在 Gate 1 读模式确认：

```text
UNKNOWN_PENDING_BROKER_TEST
```

不要猜。

---

## 19.7 513500

必须回答：

```text
historical NAV availability
historical premium availability
IOPV availability
premium distribution availability
alternative S&P500 instruments
```

Gate 1 不确定 PremiumGuard threshold。

只调查数据是否足够。

---

# 20. Reviewer 对 Gate 1 的一个额外原则

Gate 1 目的不是找：

> “过去收益最高的 ETF”。

目的是找：

> “最能可靠代表 Asset Slot、历史足够长、流动性好、成本低、实盘可执行、且数据可审计的 Instrument”。

禁止按：

```text
past CAGR
```

作为 preferred ETF 的主要筛选标准。

---

# 21. Agent 下一条执行指令

Agent 收到本回复后按以下顺序执行：

```text
Step 1
Patch Gate 0 documents using Required Corrections Checklist

Step 2
Write GATE_0_CORRECTIONS.md

Step 3
Commit corrections

Step 4
Update CODEX_AGENT_STATUS.md:
GATE 0 = APPROVED_WITH_REQUIRED_CORRECTIONS → CORRECTIONS_COMPLETE

Step 5
Enter Gate 1 Data & Universe Audit

Step 6
STOP at GATE_1_DATA_UNIVERSE.md

Step 7
Return Gate 1 packet to Reviewer / ChatGPT
```

不要执行 Gate 2。

---

# 22. Reviewer Approval Record

```yaml
gate: 0
decision: APPROVED_WITH_REQUIRED_CORRECTIONS
date: 2026-08-08

permission_after_corrections:
  enter_gate_1: true
  implement_portfolio_env: false
  train_rl: false
  connect_qmt_orders: false
  change_frozen_universe: false

required_next_review:
  packet: GATE_1_DATA_UNIVERSE.md
```

---

# 23. Reviewer Summary

Gate 0 的核心审计质量是合格的。

最主要的问题不是方向错误，而是两个地方把 FinRL-X 当前代码的成熟程度描述得过高：

1. **TD3 不是完全不存在，而是存在 legacy training helper、当前未接成正式 allocator。**
2. **weight-centric 是正确的架构理念，但当前 Backtest 与 Live 的 concrete weight DataFrame schema 并未真正统一。**

这两个问题修正后，项目方向与 EXECUTION_SPEC 一致，可以安全进入 Gate 1。

---

## END OF REVIEWER RESPONSE
