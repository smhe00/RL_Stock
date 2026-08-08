# Gate Review Packet

## GATE_2_ENVIRONMENT

> Reviewer 授权：`GATE_1=APPROVED, GATE_2=AUTHORIZED`（`GATE_1_CORRECTIONS_REVIEWER_RESPONSE.md`）。
> 本 Gate 目标：证明 Environment 的金融会计与时间语义正确（**不是产生收益**）。

## 1. Canonical object schemas

实现于 `src/china_etf/contracts.py`（D-005 唯一 Source of Truth）：

```python
@dataclass(frozen=True)
class AssetSlot:            # 经济风险槽位（RL 只学 Slot，不学 ETF 代码）
    name: str; asset_class: str; region: str
    style: str | None; theme: str | None; currency: str = "CNY"

@dataclass(frozen=True)
class TargetAssetWeights:   # 唯一上游权重对象
    decision_time: pd.Timestamp
    weights: pd.Series      # index=AssetSlot ID；w>=0；sum=1（构造时校验）
    metadata: Mapping[str, Any]

@dataclass(frozen=True)
class TargetInstrumentWeights:   # InstrumentSelector 输出
    decision_time: pd.Timestamp; weights: pd.Series; metadata: Mapping[str, Any]

@dataclass(frozen=True)
class TradabilityDecision:       # buy_allowed / sell_allowed / reason_codes
    instrument: str; timestamp: pd.Timestamp
    buy_allowed: bool; sell_allowed: bool; reason_codes: tuple[str, ...]

@dataclass(frozen=True)
class PremiumDecision:           # premium_pct / iopv / data_age / buy/hold/sell / warning_level
    instrument: str; timestamp: pd.Timestamp
    premium_pct: float | None; iopv: float | None; data_age_seconds: float | None
    buy_allowed: bool; hold_allowed: bool; sell_allowed: bool; warning_level: str; reason: str

@dataclass(frozen=True)
class CostBreakdown:             # commission/exchange_fee/tax/spread/slippage/impact/fx_cost；total 为和
    commission: float = 0.0; exchange_fee: float = 0.0; tax: float = 0.0
    spread: float = 0.0; slippage: float = 0.0; impact: float = 0.0; fx_cost: float = 0.0
    @property
    def total(self) -> float: ...

@dataclass(frozen=True)
class Order:                     # instrument / side(buy|sell) / quantity / 类型
@dataclass(frozen=True)
class Fill:                      # order_id / instrument / side / quantity / price(ccy) / cost(base) / timestamp
@dataclass(frozen=True)
class OrderPlan:                 # decision_time / target_asset_weights / target_instrument_weights / orders
```

辅助：`softmax_weights(raw, slots)`（simplex 映射，数值稳定，自动校验）与
`assert_weight_invariants`（finite / non-negative / sum=1）。

## 2. State / action shape

- `ActionDim = 11`（11 Core slots；Phase 1 永远 11，Phase 3 才到 12）。
- `ObsDim = 8×11 + 11 + 5 = 104`：每资产 8 个特征（log_return_5/20/60/120、
  realized_vol_20/60、drawdown_60/250）+ 当前权重 11 + 全局 5
  （cross_sectional_dispersion_20、equity_average_corr_60、cn_large_vol_percentile_252、
  gold_equity_corr_60、bond_equity_corr_60）。
- Long-only（softmax 保证 w≥0）、无杠杆（sum=1）、无 Theme Sleeve。

## 3. Hand-calculated accounting example（可人工复算）

参数：期初现金 1,000,000 CNY；MainlandETFCostModel（佣金万0.5、半价差 1bp、滑点 2bp）。

```text
V0（2026-01-02，全现金）= 1,000,000.00
2026-01-05 开盘买入 99,000 股 @10.00（投入 990,000）：
  commission = 990,000 × 0.00005 = 49.50
  spread     = 990,000 × 0.0001  = 99.00
  slippage   = 990,000 × 0.0002  = 198.00
  total cost = 346.50
成交后 cash = 1,000,000 − 990,000 − 346.50 = 9,653.50
2026-01-05 收盘 mark @10.50：
  market_value = 99,000 × 10.50 = 1,039,500.00
  V1 = 9,653.50 + 1,039,500.00 = 1,049,153.50
identity：V1 − V0 = 49,153.50 = market_pnl(99,000×0.5=49,500) − fees(346.50) ✓
```

实现：`tests/test_accounting.py::test_hand_calculated_accounting_identity`（精确断言）。
卖出已实现盈亏：(12.0−10.0)×400 = 800（`test_sell_realized_pnl_and_oversell_guard`）；
超卖被拒绝（ValueError）。

## 4. Cost breakdown example

Mainland（510300.SH 买 100,000 股 @4.0）：

```text
notional = 400,000
commission = 20.0（万0.5）；spread = 40.0（1bp 半价差）；slippage = 80.0（2bp）
exchange_fee = 0.0（待核实）；tax = 0.0（ETF 免印花税，待核实）；impact = 0.0（Gate 2 不校准）
total = 140.0
2x stress：commission/spread/slippage 精确 ×2（可预测）
```

Southbound（03110.HK 买 10,000 @30.0 HKD，notional 300,000 HKD）：

```text
commission = 15.0；exchange_fee = 300,000×(0.00565%+0.0027%) + 股份交收费(6.0，min2/max100 内) = 31.05
tax(印花税 0.1%) = 300.0；spread/slippage = 30.0/60.0
total > commission + tax
```

## 5. Tradability example

`src/china_etf/execution/tradability.py`（纯函数状态机，reason codes 完整）：

```text
03110.HK stock_connect_sell_only → buy_allowed=False, sell_allowed=True（reason=STOCK_CONNECT_SELL_ONLY）
513500.SH premium_ok=False       → buy_allowed=False, sell_allowed=True（reason=PREMIUM_TOO_HIGH）
未上市/停牌/收盘/数据过期 → 买卖双禁（NOT_LISTED/SUSPENDED/MARKET_CLOSED/DATA_STALE）
```

## 6. PremiumGuard fail-closed example

`src/china_etf/execution/premium.py`（接口 + 新鲜度 + fail-closed；**未使用 close/nav gap 阈值**，D-011）：

```text
需要保护 + IOPV 缺失    → buy=False, hold=True, sell=True（warning=block）
需要保护 + IOPV 过期(>60s) → buy=False, hold=True, sell=True（warning=block）
需要保护 + IOPV 新鲜     → buy=True, sell=True（premium_pct 由 market_price/IOPV 计算，仅 info）
不需要保护（如 510300）  → 全允许
```

## 7. FX accounting example

`src/china_etf/fx.py`（FXSkeleton，BaseCurrency=CNY，point-in-time 前向不可用）：

```text
持有 1,000 股 HKD 资产 @30.00 HKD；HKD/CNY 由 0.90 → 0.92：
  mark 价值 = 1,000×30×0.90 = 27,000 CNY → 1,000×30×0.92 = 27,600 CNY
  FX PnL = +600 CNY（mark-to-market，含在组合 identity 的 FXPnL 项）
注册前无 PIT 汇率 → 抛错（禁止前向填充）
```

## 8. No-lookahead test

`tests/test_timing_and_no_lookahead.py::test_no_lookahead_features`：对同一序列在 t=60 处
计算 8 特征；将 t+1 之后数据 ×10 后重算 —— `assert_series_equal(f_t, f_t')`（rolling 只用 ≤t 数据）。

## 9. t→t+1 execution test

`test_fill_at_next_open_not_same_close`：等权 action 一步后，所有成交价 **== T+1 开盘价**
（open=0.999×close），且 ≠ T 收盘价 —— 禁止同日收盘成交（EXECUTION_SPEC §32）。

## 10. Adjustment PIT test（Carry-Forward C3）

`tests/test_adjustment_pit.py`（纯函数 `total_return_with_events`，不依赖 xtquant）：

```text
512890（2021-10-25 送股 1:1，split=2.0）：raw 收益 −50%（假跳变），调整后 TR = 0.00
510300（现金分红 0.1/份）：4.00→3.95，TR = (3.95+0.1)/4.00 − 1 = +1.25%
511260（季度分配）与 515070（折算，QMT front 常数 0.5 因子）：
  split 因子事件日后延续（累计因子），TR 序列无未来信息泄漏
```

## 11. Pytest exact output

```text
platform win32 -- Python 3.12.10, pytest-9.1.1
collected 29 items
tests/test_accounting.py ........ 2 passed
tests/test_adjustment_pit.py ..... 5 passed
tests/test_contracts.py .......... 4 passed
tests/test_cost.py ................ 4 passed
tests/test_fx.py .................. 2 passed
tests/test_order_generator.py .... 2 passed
tests/test_premium_guard.py ...... 4 passed
tests/test_timing_and_no_lookahead.py 3 passed
tests/test_tradability.py ........ 3 passed
============================= 29 passed in 1.00s ==============================
```

env 3 步轨迹（等权 action，合成数据，seed=7）：

```text
step1: t=2026-01-02 t+1=2026-01-05  V 1,000,000.00 → 1,000,599.85  net_ret=+0.000600  fills=11
step2: t=2026-01-05 t+1=2026-01-06  V 1,000,599.85 →   999,352.38  net_ret=-0.001247  fills=1
step3: t=2026-01-06 t+1=2026-01-07  V   999,352.38 →   993,610.47  net_ret=-0.005746  fills=4
action_dim=11  obs_dim=104
```

## 12. Known limitations

- Cost 为骨架：market impact=0、spread/slippage 为固定 bps（未校准）；费率待券商核实。
- MockBroker 单币种（fx_rate=1.0）；港股 FX 走 FXSkeleton 单独测试，未接入环境主循环。
- Environment 未接入真实数据加载器（Gate 2 用合成数据验证语义；真实数据在 Phase 1 数据层接入）。
- OrderGenerator 未实现最小订单额/价格阈值外的复杂执行（分批、冰山等留 Gate 5/6）。
- 03110 lot=50 已记录于元数据，但 Gate 2 环境不交易港股标的（无 QMT 行情）。

## 13. Carry-Forward C1/C2/C3 status

- **C1（03110 same-day rule）**：`same_day_reversal=UNKNOWN_PENDING_RULE_VERIFICATION`；
  未硬编码 True；Gate 6 前完成 HKEX/Southbound 规则 + 券商能力验证。
- **C2（proxy launch/backfill 审计）**：Gate 2 环境只用合成/真实 ETF 数据，未用任何未验证 proxy；
  proxy 审计在 Gate 3（RL Sanity）前完成。
- **C3（adjusted price PIT）**：已实现 `total_return_with_events` + 4 只标的 PIT 测试
  （test_adjustment_point_in_time_semantics 等价物）；`execution_price_series`（raw）与
  `research_total_return_series`（复权）双价格体系冻结（D-009）。

## 14. Files changed

```text
src/china_etf/contracts.py                       # canonical contracts
src/china_etf/accounting.py                      # PortfolioAccounting + identity
src/china_etf/cost/base.py, mainland.py, southbound.py
src/china_etf/execution/tradability.py           # TradabilityMask
src/china_etf/execution/premium.py               # PremiumGuard (fail-closed)
src/china_etf/execution/broker/base.py, mock.py  # BrokerAdapter + MockBroker
src/china_etf/execution/order_generator.py       # OrderGenerator
src/china_etf/fx.py                              # FXSkeleton
src/china_etf/data/adjustments.py                # TR 纯函数（C3）
src/china_etf/features/etf_features.py           # 8+5 特征
src/china_etf/environment/portfolio_env.py       # ChinaETFPortfolioEnv (11)
tests/                                           # 29 个测试
.venv/                                           # 独立 venv（pytest/numpy/pandas）
```

## 15. Git commit

Gate 2 实现提交：`c4dd562`（main 分支）

后续存档提交：`3ca7db4`（上游 v1.0.0 核实）、`948fae7`（2026-08-08 最新状态复查）。

---

## END OF GATE 2 REVIEW PACKET
