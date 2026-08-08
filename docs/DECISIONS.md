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

### D-009 双价格体系（Gate 1 修正冻结）

- `execution_price_series` = raw 可成交价（PnL/成交/溢价基准）。
- `research_total_return_series` = 复权序列（收益/相关/特征）。
- 依据：QMT front 对 515070(AI) 早期历史施加常数 0.5 因子（份额折算），raw 在折算日有假跳变；
  QMT front 与 AkShare qfq 的调整语义须在 Phase 1 `instrument_master` 逐只审计。

### D-010 规模口径

- `aum_nav_based = TotalVolume(份额) × NAV`；`market_cap = TotalVolume × 收盘价`；两者分开。
- QDII 溢价时 AUM≠市值（513500：AUM 250.31亿 vs 市值 272.70亿）；禁止用市值冒充基金规模。

### D-011 513500 溢价口径

- 历史 `close/NAV-1` 统一命名 `close_to_official_nav_gap`（异步口径），非 "premium"。
- `HISTORICAL_REALTIME_PREMIUM = NOT_AVAILABLE`（历史 IOPV 不可得）。
- 禁止用异步 gap 的 P90/P95 直接设定 Live PremiumGuard 阈值；实时阈值需 IOPV 对齐验证或
  FairNAV 研究（`NAV_{t-1}×(1+SPX/FuturesMove_t)×FXMove_t`，单独 RFC）。

### D-012 03110 官方元数据

- board_lot=50（2026-07-24 生效，原 100→50；Global X/HKEX）；Broker 支持 = UNKNOWN_PENDING_GATE6。
- T+0/当日回转能力按 HKEX/Southbound 规则验证，不以 SSE 跨境 ETF 规则为依据。

### D-013 风险尾部指标定义

- 废弃 union-tail Pearson（选择偏差）。
- 冻结：`CN_LARGE_DOWNSIDE_CORR`（CN_LARGE<0）、`CN_LARGE_STRESS_CORR`（CN_LARGE≤q10）、
  lower-tail co-exceedance（P(Ii|Ij)、P(Ij|Ii)）、`TailDependenceScore = P(Ii∩Ij)/0.1²`。
- 旧 tail=-0.646 等数值不得再用于"极端暴跌对冲"结论。

### D-014 CASH_LIKE 风险类别

- 511360 = `risk_class=SHORT_CREDIT, cash_equivalent=false`；与 Broker Cash 分开。
- preferred 暂不更换；切换 511880/511990 等货币 ETF 需 RFC。

### D-015 Gate 1 验收 + Carry-Forward 登记（2026-08-08）

- `GATE_1 = APPROVED_WITH_CARRY_FORWARD_CONDITIONS`；`GATE_2 = AUTHORIZED`。
- **C1**：03110 当日回转规则未完成官方验证 → `same_day_reversal=UNKNOWN_PENDING_RULE_VERIFICATION`，
  Instrument Master 保留 unknown；Gate 6 前完成 HKEX/Southbound 规则 + 券商能力验证。
- **C2**：未验证 proxy（HSHYLDI/中债国债总财富/H30184/930713/H30590/931152/399967 等）：
  `PROXY_STATUS != VERIFIED → STRICT_PIT_PIPELINE = FORBIDDEN`；Gate 2 只用真实 ETF 历史；
  Proxy 审计在 Gate 3（RL Sanity）前完成。
- **C3**：QMT front/qfq 不得当作 Point-in-Time Truth；Gate 2 实现
  `test_adjustment_point_in_time_semantics`（510300/512890/511260/515070），
  内部数据层保留 `raw_market_price / distribution_cash / split_factor / conversion_factor`，
  研究收益用 TR 公式（含现金分红与拆分因子），或已验证无未来信息的 total-return series。
- Gate 2 范围：canonical contracts、PortfolioAccounting、MockBroker、CostModel skeleton、
  Tradability、PremiumGuard（接口+新鲜度+fail-closed）、FX skeleton、ChinaETFPortfolioEnv(11)。
- Gate 2 禁止：TD3/SAC/PPO 性能比较、Optuna、多种子研究、Theme Sleeve、真实 QMT 下单、
  动态 Instrument 排序、未验证 proxy 进严格 PIT。
- Gate 2 报告要求：任何 correlation/stress 数字必须附带 overlap N 与日期区间（不依赖本地 CSV）。

### D-016 Gate 3 依赖与 GPU 决策（2026-08-08）

- GPU：NVIDIA GTX 1060 6GB（Pascal，sm_61），驱动 581.80（CUDA 13.0 驱动级，向后兼容）。
- torch 锁 **2.7.1+cu118**：PyTorch 2.8+ 已放弃 Pascal/sm_61；cu118 轮子明确含 sm_61
  （`torch.cuda.get_arch_list()` 实测含 sm_61，GPU matmul 验证通过）。
- stable-baselines3 锁 **2.8.0**：SB3 2.9.0 要求 torch>=2.8（与 Pascal 约束冲突）。
- gymnasium 1.2.3（随 SB3 2.8.0 解析）。
- 镜像策略：普通 PyPI 包走阿里源（`.venv/pip.ini`）；cu118 torch 只能从
  `download.pytorch.org/whl/cu118`（国内镜像不提供 cu118 轮子）。
- 上游包：`finrl-trading`（FinRL-X）@ e65d6f0（`--no-deps --no-build-isolation`，需 `PYTHONUTF8=1`，
  中文 Windows 上 setup.py 读 README 有编码 bug）；`finrl`（经典）@ 2334a5f。
- 经典 finrl 的完整运行时依赖（alpaca_trade_api/websockets 等）**不安装**：
  本项目 allocator 直接使用 SB3 + 自建 `ChinaETFPortfolioEnv`，不经经典 finrl legacy DRL 路径。
- 上游 `strategies.base_strategy`（weight contract）可导入；`ml_strategy` 等需上游可选依赖，本项目不需要。
- 锁定文件：`requirements-gate3.txt`。

### D-017 执行摩擦与成本币种约定（Gate 2 修正冻结）

- `Fill.price` = reference 执行价；spread/slippage/impact 以显式现金成本计入 `CostBreakdown`；
  禁止成交价内隐含摩擦（防 double count）。
- `CostBreakdown` 全部字段一律为 **base 币种**；SouthboundCostModel 内部按 `fx_to_base` 折算。
- 港股通 ETF 印花税 = 0（暂免）；含 AFRC 0.00015%。
- Mainland 0.004% 交易所经手费不直接叠加：`broker_commission_includes_exchange_fee=
  UNKNOWN_PENDING_BROKER_FEE_AUDIT`（防 double count，Gate 4 前冻结）。
- 费率规则带 `effective_from`/`source`（FeeRule），避免历史回测被当前费率污染。

### D-018 EnvironmentMode（Reviewer §19）

- 冻结 4 模式：`METHOD_RESEARCH / INSTRUMENT_BACKTEST / PAPER / LIVE`。
- 研究模式不启用实时 PremiumGuard（历史无 IOPV）；PAPER/LIVE fail-closed。
- Run Manifest 必须输出 mode 与 Slot→Instrument 映射。
- C3 状态：`PARTIALLY_RESOLVED`（算法已用 QMT 真实事件验证 14/14；
  正式关闭在真实 Data Loader 接入环境主循环时）。
