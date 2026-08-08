# Gate Review Packet

## GATE_0_UPSTREAM_AUDIT

## 1. Goal

按 EXECUTION_SPEC §93/§94 审计 FinRL-X（AI4Finance-Foundation/FinRL-Trading）上游：
确认版本、`generate_weights()` contract、PPO/SAC/TD3 现状、BacktestEngine、成本路径、Risk Overlay、
TradeExecutor/Alpaca 耦合度，并给出最小扩展点。**本 Gate 不写 ChinaETF 环境、不接 QMT、不训练。**

## 2. What was implemented

只读审计（shallow clone 到 `tmp/finrlx-upstream`，不入库），未修改 upstream。
产出本文件 + `docs/upstream/FINRL_X_UPSTREAM_SNAPSHOT.md`。

## 3. Files changed

- 新增 `docs/upstream/FINRL_X_UPSTREAM_SNAPSHOT.md`
- 新增 `docs/review_packets/GATE_0_UPSTREAM_AUDIT.md`
- 更新 `docs/CODEX_AGENT_STATUS.md`、`docs/DECISIONS.md`

## 4. Architecture decisions

- 复用上游 **weight contract**（`StrategyResult.weights`）与 S/A/T/R 概念分层。
- **不深度依赖 upstream 运行时**：其 requirements.txt 未声明 DRL 依赖，干净安装不可复现 DRL 路径。
- 中国 ETF 核心（环境/成本/风控/选择器/订单/回测/执行）在 `src/china_etf/` 自建。

## 5. Data sources

- 上游代码：`https://github.com/AI4Finance-Foundation/FinRL-Trading`（commit `e65d6f0`，2026-05-02）。
- 经典 FinRL 算法支持：FinRL / FinRL-Meta 文档与源码（DRLAgent 支持 a2c/ddpg/ppo/sac/td3）。

## 6. Commands executed

```text
git clone --depth 1 https://github.com/AI4Finance-Foundation/FinRL-Trading.git tmp/finrlx-upstream
git -C tmp/finrlx-upstream log -1 --format='%H %ci %s'
git ls-remote --tags origin            # 发现 refs/tags/v1.0.0
（以下为只读代码阅读：base_strategy / trade_executor / backtest_engine /
  fundamental_portfolio_drl / rl_model / alpaca_manager / risk_manager /
  walk_forward / execution_engine / README / requirements.txt 等）
```

## 7. Tests and exact results

无代码改动，无测试执行。上游仓库本身无 `tests/` 目录。

## 8. Metrics / tables

见下方 §94 逐条回答（含证据行号）。

## 9. Known limitations

- shallow clone 未见 tag 对象：`v1.0.0`（remote `0b5b4235`）的发布日期与内容未核实，需完整 fetch。
- README 声明的 "PPO/SAC DRL allocator" 依赖经典 `finrl` 包，未在 requirements.txt 声明，未实测可运行。
- 未安装/运行 upstream（本 Gate 范围仅代码审计）。

## 10. Deviations from EXECUTION_SPEC

无。未做任何 Frozen Decisions 修改。

## 11. Open risks

- upstream 演进（master 活跃）可能改变 contract；已固定 snapshot 记录。
- 经典 `finrl` 对 torch/gym 版本敏感，Phase 2 环境搭建时需锁版本。

## 12. Recommended next action

Reviewer 批准本 Gate 后进入 **Gate 1 — Data & Universe Audit**（EXECUTION_SPEC §66）：
11 Core + 5 Theme 的上市日期/代码/币种/成交额/历史覆盖/QMT 与 Premium 数据可得性/相关性初筛。

## 13. Git commit / branch

`RL_Stock` 独立仓 main 分支（本 Gate 提交待做，见 commit log）。

---

# 附录 A：EXECUTION_SPEC §94 逐条回答

### 1. FinRL-X 当前正式版本与 commit？

仓库 `AI4Finance-Foundation/FinRL-Trading`（README 标题 FinRL-X）。论文：`arXiv:2603.21330`。

存在 **三个不同版本口径**，不得混用：

```yaml
upstream:
  github_latest_release: v1.0.0          # "FinRL-X: Initial Public Release" (2026-03-25)
  github_release_commit: 0b5b4235640e74cd6e59f374bb13b3779e898e57
  audited_branch: master
  audited_commit: e65d6f0483ead7d2ef4a5fc940cdf960392a25c1   # 2026-05-02
  package_metadata_version: 2.0.2        # setup.py:27
```

项目 reproducibility 以 **audited_commit** 为准，而非版本字符串。

### 2. README 所说 PPO/SAC DRL allocator 实际代码在哪？

README Use Case 1 表（"DRL Allocator | Learning | PPO/SAC continuous weight generation"）。
实际代码不在独立 allocator 模块：`src/strategies/fundamental_portfolio_drl.py` 与
`src/strategies/rl_model.py` 封装经典 `finrl` 的 `DRLAgent` + `StockPortfolioEnv`（`rl_model.py:20-21`），
`fundamental_portfolio_drl.py:20-24` 相同 import，训练入口 `run_models`（`rl_model.py`）。

### 3. TD3 是否已在 FinRL-X 中存在？

**并非完全不存在，而是存在 legacy training helper、当前未启用为正式 allocator。**

- `src/strategies/rl_model.py:175` 存在 `train_td3(agent)`：`agent.get_model("td3", model_kwargs=TD3_PARAMS)`，
  经经典 FinRL `DRLAgent` 调用 SB3 TD3（TD3_PARAMS: batch_size=100 / buffer_size=1e6 / learning_rate=0.001）。
- 但 `run_models()` 中 `#td3_model = train_td3(agent)` 与 `#sac_model = train_sac(agent)` 被注释
  （`rl_model.py:265-266`）；当前实际启用 A2C / PPO / DDPG（`:131/:154/:167`）。
- 结论：**FinRL-X master 存在 TD3 legacy/helper training entry point，但没有启用状态的、
  符合 `BaseStrategy.generate_weights()` contract 的正式 Portfolio Allocator。**
- 经典 FinRL/FinRL-Meta DRLAgent 支持 `a2c/ddpg/ppo/sac/td3` 已另行核实
  （文档与 `OFF_POLICY_MODELS = ["ddpg","td3","sac"]`）。

### 4. 若不存在，最小接入点是什么？

新增 `src/china_etf/allocators/td3_allocator.py`：用 Stable-Baselines3 `TD3` 训练，
实现与 PPO/SAC 相同的 `generate_weights(data, target_date) -> StrategyResult` contract。
不修改 upstream，不动 SB3 算法本身。

### 5. `generate_weights()` 输入/输出 exact schema？

`src/strategies/base_strategy.py:26`：
`generate_weights(self, data: Dict[str, pd.DataFrame], target_date: Optional[str] = None) -> StrategyResult`。
输出 `StrategyResult{strategy_name: str, weights: pd.DataFrame, metadata: Dict}`（`:8-15`）。

**上游并未冻结 concrete weight schema**（详见 Q14）：TradeExecutor 隐含 long-form
（`gvkey | weight`），BacktestEngine 隐含 wide-form（`index=dates, columns=tickers`），二者不一致。
本项目必须冻结自己的 canonical contract（决策 D-005）：

```python
@dataclass(frozen=True)
class TargetAssetWeights:
    decision_time: pd.Timestamp
    weights: pd.Series          # index=AssetSlot ID, value=target weight
    metadata: Mapping[str, Any]
```

约束：`w_i >= 0`，`sum(w) = 1`。所有下游（Backtest / Paper / Live）只从该对象向下转换。

### 6. 当前 BacktestEngine 如何接受 weights？

`src/backtest/backtest_engine.py` 用 `bt` 库，`BacktestConfig` 默认
`rebalance_freq='Q'`、`transaction_cost=0.001`、`benchmark=['SPY','QQQ']`（`:33-53`），
`bt.Backtest(... commissions=...)` 传入成本（`:317`）。无 A股日历、无 next-open 成交语义。

接收格式为 **wide-form**：`weight_signals` 要求 `index=dates, columns=tickers`（`:132`），
且内部执行 `weight_signals.reindex(...).ffill()`（`:145-153`）与 `price_data.ffill()`（`:241`）。
该 ffill 语义无法表达：ETF 未上市、港股休市、港股通 sell-only、停牌、QDII 溢价禁买、
T+0/T+1、lot size、next-open 成交、实际 cash availability。

> **Reviewer 裁决（D-008）**：上游 BacktestEngine 仅作为 reference / smoke comparison /
> compatibility adapter，不作为中国 ETF 正式 OOS 回测的 Source of Truth。
> Gate 2 之后正式结果以本项目 `PortfolioAccounting + ExecutionSimulator/MockBroker +
> CostModel + TradabilityMask` 为准。

### 7. transaction costs 当前在哪处理？

仅回测侧：`BacktestEngine` 的 flat rate 或可选 `bt.AlmgrenChrissCostModel`（`:46-52`）。
执行侧（TradeExecutor/AlpacaManager）无成本计算。→ 中国 ETF 的 Mainland/Southbound CostModel 必须自建。

### 8. 当前 Risk Overlay 是否可复用？

**不可直接复用**。上游无组合级 Risk Overlay：`adaptive_rotation/risk_manager.py` 是个股止损
（absolute/trailing stop），`TradeExecutor._apply_risk_checks` 是最大单笔/最大换手/最小单
（`trade_executor.py` ExecutionConfig）。→ 组合级硬约束（long-only、HardTech、ChinaGrowth、theme sleeve）
需自建 `RiskOverlay`；上游 checks 可作为参考。

### 9. TradeExecutor 对 Alpaca 耦合程度如何？

**高**。`TradeExecutor` 直接持有 `AlpacaManager`（`trade_executor.py:73`），
`AlpacaManager` 是 alpaca-py 封装（多账户、positions、orders、rebalance）。
`execute_portfolio_rebalance(target_weights)` 也直接走 Alpaca。

### 10. Broker abstraction 是否已存在？

**否**。只有具体实现 `AlpacaManager`，无通用 Broker 协议。其方法形态
（get_positions / get_portfolio_value / place_order / cancel_order / get_order_status / wait_for_order_fill）
可作我们 `BrokerAdapter` Protocol 的参考蓝本。

### 11. 如果新增 QMT，最小改动文件有哪些？

不动 upstream：在 `src/china_etf/execution/broker/qmt.py` 实现 `BrokerAdapter`
（get_account/get_positions/get_cash/get_quote/place_order/cancel_order/get_order/get_fills），
`OrderGenerator` 在上层 `src/china_etf/execution/order_generator.py`。
参考 `docs/references/miniqmt/`（reverse_repo 的 XtQuantTrader 惰性 import、账户绑定、preflight 模式）。

### 12. 是否存在 Gym environment，还是策略直接生成 weights？

upstream 策略层**直接生成 weights**（`BaseStrategy.generate_weights`）；DRL 训练发生在经典
`StockPortfolioEnv`（gym），预测时 `DRLAgent.DRL_prediction` 输出 action 序列（`rl_model.py`
`_safe_DRL_prediction` 取 account/action memory）。→ 我们的方案保持 weight-centric：
训练用自建 `ChinaETF PortfolioEnv`（gymnasium），预测统一走 allocator → weights。

### 13. TD3/SAC/PPO 若需要 Gym 环境，最合适放在哪里？

`src/china_etf/environment/portfolio_env.py`（gymnasium.Env），SB3 直接训练；
allocators 包装为 weights contract。三层：Env（训练）→ SB3 model → allocator（weights）。

### 14. 如何保证 Backtest 和 Live 使用同一个 weight contract？

**上游并不存在真正统一的 concrete weight schema**（Reviewer 修正项）：

- `TradeExecutor._weights_to_orders()` 直接读 long-form：`row['gvkey']` / `row['weight']`
  （`trade_executor.py:237-249`）；
- `BacktestEngine.run_backtest()` 要求 wide-form：`index=dates, columns=tickers`（`backtest_engine.py:125-153`）。

二者互不直接兼容，且 BacktestEngine 不直接消费 `StrategyResult`。因此：

```text
TargetAssetWeights（唯一 Source of Truth，D-005）
        │
        ├── to_backtest_frame()        → date × asset/instrument wide frame
        ├── InstrumentSelector         → TargetInstrumentWeights
        └── FinRLXStrategyAdapter      → StrategyResult（上游边界兼容）
```

按 EXECUTION_SPEC §52 冻结 `TargetAssetWeights / TargetInstrumentWeights / RiskDecision /
TradabilityDecision / OrderPlan`；Backtest（MockBroker）与 Live（QMTBrokerAdapter）共享同一
OrderGenerator。禁止 Backtest schema 与 Live schema 各自成为 Source of Truth，禁止维护两套策略逻辑。

### 15. 当前 upstream tests 覆盖哪些部分？

仓库根**无 `tests/` 目录**，无可见测试套件。→ 本项目测试体系按 EXECUTION_SPEC §54 全部自建
（weight invariants / no-lookahead / cost / accounting / tradability / action dim / persistence / seed）。

### 16. 哪些 upstream assumptions 明显不适合中国 ETF？

1. 数据源 FMP/WRDS/Yahoo + SQLite：无 A股/港股通数据、无复权/除权细节、无溢价/IOPV。
2. 回测 `bt` + SPY/QQQ benchmark + 季度再平衡 + flat 0.1% 成本：无 A股/港股日历、
   无 T+0/T+1、无 lot size、无 next-open 成交语义。
3. 执行只对接 Alpaca：无 QMT、无港股通、无 FX/结算汇率处理。
4. 允许 fractional shares：A股 ETF 按 100 份/手。
5. 无停牌/涨跌停/港股通资格/折溢价/流动性处理。
6. DRL 依赖经典 `finrl`+gym，requirements.txt 未声明，且存在 monkey-patch，不可直接复现。
7. adaptive_rotation 的 walk_forward "train_end=decision_date" 语义与我们
   "T 收盘决策 → T+1 执行" 的语义不同，只能作参考。

# 附录 B：最小扩展点清单（供 Reviewer 确认）

| 模块 | 策略 | 依据 |
|---|---|---|
| `StrategyResult`/`generate_weights` contract | 复用/对齐上游 | `base_strategy.py:8-27` |
| `WalkForwardRunner` | 自建（参考 adaptive_rotation 思路） | spec §42 |
| `ChinaETF PortfolioEnv` | 自建（gymnasium） | spec §29-§34 |
| `CostModel` Mainland/Southbound | 自建 | spec §20-§24 |
| `RiskOverlay` | 自建（参考 TradeExecutor checks） | spec §36/§59 |
| `TradabilityMask` / `PremiumGuard` / `FXModel` | 自建 | spec §18/§19/§25/§26 |
| `InstrumentSelector` / `OrderGenerator` | 自建 | spec §5/§49/§51 |
| `QMTBrokerAdapter` | 自建（参考 reverse_repo 模式） | spec §18/§50 |
| `Baselines`（EW/RP/MinVar/MV/Momentum） | 自建（pypfopt 可用） | spec §37 |
