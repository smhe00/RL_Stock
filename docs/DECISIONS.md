# DECISIONS

本文档记录冻结决策与已批准变更。冻结项以 `EXECUTION_SPEC.md` 为准；此处只记录增量决策。

## 2026-08-08

### D-001 RL_Stock 作为独立仓库

- 本目录独立于 miniQMT 主工程，后续单独上传 gitee。
- 主规范复制自 ChatGPT 整理的 `FINRL_X_CHINA_ETF_EXECUTION_SPEC_V1.0.md`（原始文件保留在仓库根，作为交付物来源）。

### D-002 QMT 参考代码来源

- `docs/references/miniqmt/` 下文件复制自 miniQMT 工程 `reverse_repo/`（GC001 国债逆回购执行系统）。
- 用途：Phase 5/6 实现 `QMTBrokerAdapter` 时的连接/预检/账户绑定/行情新鲜度模式参考。
- 约束：研究核心（`src/china_etf/`）不得 import `xtquant`（EXECUTION_SPEC §50）；参考代码不做集成，仅作参考。

### D-003 初始配置草稿

- `config/` 下 YAML 依据 EXECUTION_SPEC §59/§88/§89 冻结值建立；费用类参数标记为 `pending verification`，
  Gate 1（数据审计）与 Gate 6（QMT Paper）前必须核实，不得把草案当事实。

### D-004 Gate 0 上游快照

- 固定 FinRL-X upstream snapshot：AI4Finance-Foundation/FinRL-Trading，HEAD `e65d6f0`（2026-05-02）。
- 审计结论：复用 weight contract 与 S/A/T/R 分层概念；中国 ETF 核心模块在 `src/china_etf/` 自建；
  不深度依赖 upstream 运行时（其 requirements.txt 未声明 DRL 依赖）。
- 详细证据见 `docs/review_packets/GATE_0_UPSTREAM_AUDIT.md`（待 Reviewer 批准）。

### D-005 Canonical Weight Contract（Reviewer 强制）

- 冻结唯一 Source of Truth：

```python
@dataclass(frozen=True)
class TargetAssetWeights:
    decision_time: pd.Timestamp
    weights: pd.Series          # index=AssetSlot ID, value=target weight
    metadata: Mapping[str, Any]
```

- 约束：`w_i >= 0`、`sum(w)=1`。上游 `StrategyResult.weights` 仅为 `pd.DataFrame`，无 concrete schema
  （TradeExecutor 读 long-form `gvkey/weight`，BacktestEngine 要 wide-form `date×ticker`，二者不一致）。
- 所有下游（Backtest/Paper/Live）只能从 `TargetAssetWeights` 转换：
  `to_backtest_frame()` → wide frame；`InstrumentSelector` → `TargetInstrumentWeights`；
  `FinRLXStrategyAdapter` → `StrategyResult`（上游边界兼容）。

### D-006 FAIL CLOSED（Reviewer 强制安全规则）

- 行情缺失/过期 → **NO ORDER**，reason=`QUOTE_UNAVAILABLE`。
- 禁止复制上游行为：`_get_current_price()` 失败返回默认 `100.0`
  （`trade_executor.py:394-404`、`alpaca_manager.py:507/575`）。

### D-007 上游版本口径

- 三口径并存：GitHub release `v1.0.0`（2026-03-25, `0b5b4235`）、master `e65d6f0`（2026-05-02）、
  `setup.py version=2.0.2`。reproducibility 以 audited_commit 为准。

### D-008 上游 BacktestEngine 定位

- 仅作 reference / smoke comparison / compatibility adapter（D-008）。
- 原因：`weight_signals.reindex(...).ffill()`（`backtest_engine.py:145-153`）与 `price_data.ffill()`（`:241`）
  无法表达 ETF 未上市/港股休市/港股通 sell-only/停牌/QDII 溢价禁买/T+0/T+1/lot/next-open/cash 可用性。
- Gate 2 之后中国 ETF 正式 OOS 以 `PortfolioAccounting + ExecutionSimulator/MockBroker +
  CostModel + TradabilityMask` 为准。
