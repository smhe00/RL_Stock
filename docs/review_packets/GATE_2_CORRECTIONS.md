# GATE 2 Corrections

> Reviewer: `GATE_2_STATUS = REVISIONS_REQUIRED_BEFORE_GATE_3`（2026-08-08）。
> 本文件落实 §30 Required Corrections Checklist 全部项目。

## 1. Southbound ETF fee correction（BLOCKER-1）

### 已改（`cost/southbound.py`）

- **港股通 ETF 印花税 = 0**（上交所港股通税费说明：Stock Connect ETF 印花税暂免；修正原 0.1% 错误）。
- 新增 **AFRC Transaction Levy 0.00015%**。
- 保留：Trading Fee 0.00565%、SFC Levy 0.0027%、settlement 0.002%（min2/max100 HKD，Gate 6 再冻结）。

### Reviewer 示例核对（notional 300,000 HKD，fx=1）

```text
HKEX trading fee  300,000×0.00565%  = 16.95
SFC levy          300,000×0.0027%   =  8.10
AFRC levy         300,000×0.00015%  =  0.45
Stamp duty        0（港股通 ETF 暂免）
Settlement        6.00
Broker commission 15.00
Spread            30.00
Slippage          60.00
total             = 136.50 HKD ✓（test_southbound_fee_03110_reviewer_numbers）
```

## 2. Fee source / effective-date configuration

- 新增 `FeeRule` dataclass（`cost/base.py`）：name/rate/min/max/currency/effective_from/effective_to/source/applies_to。
- `MainlandETFCostModel` / `SouthboundETFCostModel` 增加 `effective_from`（2026-08-08）与 `source` 字段。
- **Mainland 0.004% 交易所经手费不直接叠加**：新增
  `broker_commission_includes_exchange_fee = "UNKNOWN_PENDING_BROKER_FEE_AUDIT"`，
  防止与券商万0.5 佣金 double count（Gate 4 前必须冻结券商口径）。

## 3. Actual-vs-target weight semantics（BLOCKER-2）

- `ChinaETFPortfolioEnv._actual_weights(t)`：observation 的 "当前权重" 一律来自
  **实际成交后持仓**（accounting.positions × 最新收盘 mark / 组合价值），而非 target。
- cash 隐含在权重残差 `1 − Σw_actual`（保持 frozen obs dim=104；显式 cash 进 obs 需 RFC）。
- 新测试 `test_observation_uses_actual_holdings_not_target`：
  B 槽位 buy-disabled 时 target B≈50% 而 obs 中 B 实际权重 = 0。

## 4. End-to-end environment transition test（BLOCKER-3）

`test_environment_end_to_end_transition`（3 资产：1 禁买 + 1 整手 + 1 正常成交，非零成本）：

- 会计 identity：`V = cash + Σ qty×price`（t+1 收盘 mark）✓
- buy-disabled 资产持仓不增加 ✓
- 成交数量均为 100 份整手 ✓
- **费用只按成交数量计费**：fills 费用合计 == accounting.fees_paid；被拒订单不计费 ✓

## 5. Overnight holding timing test

`test_old_positions_hold_through_overnight_gap_before_rebalance`：
决策日收盘 10 → T+1 开盘 9 买入 → T+1 收盘 9 → T+2 开盘 8.1 卖出。
组合先承受 `qty×(8.1−9.0)` 隔夜亏损，再按 8.1 成交（断言成交价=8.1、净收益≈−8.9%）——
禁止在 T 收盘按 9.0 "提前卖出" 使隔夜损失消失。

## 6. Spread / slippage accounting convention（D-017）

冻结 V1 约定：**`Fill.price = reference 执行价`；spread/slippage/impact 以显式现金成本计入
`CostBreakdown`**（便于分解/stress/归因）。禁止成交价内再隐含摩擦（防 double count）。
测试 `test_no_double_count_execution_friction`：fill @ 10.0，成本单独 346.5（例），
现金变化 = notional + cost.total，无隐藏扣费。

## 7. Cost currency convention（D-017）

冻结：**`CostBreakdown` 全部字段一律为 base 币种**；`SouthboundETFCostModel` 增加 `fx_to_base`，
内部 HKD 计算后统一折算。测试 `test_southbound_cost_converts_to_base`（fx=0.9 → total×0.9）。

## 8. Environment modes（D-018）

`contracts.EnvironmentMode`：`METHOD_RESEARCH / INSTRUMENT_BACKTEST / PAPER / LIVE`。

- 研究模式（前两者）：**不启用实时 PremiumGuard**（历史无 IOPV；513500 不会被永久禁买）。
- PAPER/LIVE：实时价格 + IOPV + **fail-closed** PremiumGuard。
- MockBroker 增加 `premium_enforced`；env 按 mode 设置。
- 测试：`test_environment_mode_research_allows_buy_without_iopv` /
  `test_environment_mode_live_blocks_buy_without_iopv`。
- Run Manifest 将输出 mode 与 Slot→Instrument 映射（见 §10）。

## 9. Observation warm-up / finite tests

- 冻结 `min_history = 252`；`ChinaETFPortfolioEnv._find_warmup_index` 找到首个**全 finite** 观测。
- 禁止 NaN 静默填 0（缺失 GOLD/CN_DURATION 锚点的缩略宇宙用有限占位 0 并注释）。
- 测试：`test_observation_is_finite_after_warmup`（obs 全 finite、warmup ≥ 251）、
  `test_observation_requires_full_lookback`（历史不足 → ValueError）。

## 10. Adjustment PIT carry-forward（C3）

`scripts/gate2_c3_realdata_check.py`：用 **QMT 真实数据**（raw 收盘 + `get_divid_factors` 事件表）
构造 TR，与 QMT front 复权收益在事件日对比：

```text
510300.SH  8/8  匹配（例：2024-01-18 raw −0.73% → TR +1.37% = front +1.37%）
512890.SH  1/1  2021-10-25 送股 raw −51.13% → TR −2.26% = front −2.26%
511260.SH  4/4  季度分配全部匹配
515070.SH  1/1  2026-07-06 折算 raw −50.43% → TR −0.85% = front −0.85%
合计 14/14 事件，|TR − front| < 1%
```

**C3 状态：PARTIALLY_RESOLVED → 算法已在真实事件上验证；**
正式关闭条件（真实 Data Loader 接入环境主循环）在 Gate 3 数据接入时完成。

## 11. Exact pytest output

```text
collected 40 items
29 个既有测试 + 11 个新增修正测试，全部 PASSED
============================= 40 passed in 1.78s ==============================
```

新增测试：southbound fee（Reviewer 数字 136.50）、fee metadata、southbound fx 折算、
actual-holdings observation、end-to-end transition、overnight timing、no-double-count、
finite-after-warmup、requires-full-lookback、mode research/live premium ×2。

## 12. Files changed

```text
src/china_etf/cost/southbound.py     # stamp=0、AFRC、fx_to_base、effective_from/source
src/china_etf/cost/mainland.py       # includes_exchange_fee=UNKNOWN、effective_from/source
src/china_etf/cost/base.py           # FeeRule
src/china_etf/contracts.py           # CostBreakdown 币种约定；EnvironmentMode
src/china_etf/environment/portfolio_env.py  # actual-weights obs、warm-up、mode
src/china_etf/execution/broker/mock.py      # premium_enforced
src/china_etf/features/etf_features.py      # 缺失锚点槽位有限占位 0
tests/test_gate2_corrections.py      # 11 个新测试
tests/test_cost.py / test_timing_and_no_lookahead.py  # 适配
scripts/gate2_c3_realdata_check.py   # C3 真实数据验证
docs/DECISIONS.md（D-017/D-018）、docs/CODEX_AGENT_STATUS.md
```

## 13. Git commit

（提交后填写）

---

## END OF GATE 2 CORRECTIONS
