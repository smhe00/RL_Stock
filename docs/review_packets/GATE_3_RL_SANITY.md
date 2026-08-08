# Gate Review Packet

## GATE_3_RL_SANITY

> Reviewer 授权：`GATE_2=APPROVED, GATE_3=AUTHORIZED`（训练前须过 PREFLIGHT）。
> 本 Gate 目标：**RL pipeline 正确性与 policy 行为 sanity**（不做性能结论）。

## 1. Gate 3 Preflight（全部通过）

### P1 Cash solvency（真 bug 已修复）

- 发现：换仓时买入按决策日收盘价计额、成交在 T+1 开盘，隔夜跳空吃掉 1% buffer → 现金 −8,762（违规）。
- 修复：`MockBroker` 买入按**实际可用现金**夹取数量（`_unit_cost_rate` 预留费用 + 100 份整手），
  现金永不为负；不足则拒绝（`INSUFFICIENT_CASH`），超量则记录 `clamped_fills`。
- 测试：`test_no_negative_cash_after_max_investment` / `test_rebalance_sells_before_buys` /
  `test_buy_sizing_reserves_transaction_cost`（含 Σw_actual ≤ 1+ε）。

### P2 CNY base-currency return

- `HK_DIVIDEND` 研究序列 = sina 03110 HKD qfq × 中行折算价/100（HKD/CNY）→ CNY total-return。
- 测试：`test_hkd_to_cny_research_series`（FX 变动时 CNY 收益 ≠ HKD 收益）。
- FX 数据：AkShare `currency_boc_sina`（2013-01-04 起，3865 条）。

### P3 Multi-market decision timestamp

- 冻结（D-019）：canonical decision = 当日**全部市场收盘后**（A股 15:00 / 港股 ~16:00，记 16:30 CST EOD）；
  执行 = 下一交易日开盘。禁止用港股 16:00 数据假设 15:00 已决策。

### P4 Slot→Research Series Manifest（ActionDim 恒 11）

| Asset Slot | Research Instrument | Source | Currency | Start |
|---|---|---|---|---|
| CN_LARGE | 510300.SH | QMT front | CNY | 2012-05-28 |
| CN_SMALL | 512100.SH | QMT front | CNY | 2016-11-04 |
| CN_DIVIDEND | 512890.SH | QMT front | CNY | 2019-01-18 |
| CHINEXT | 159915.SZ | QMT front | CNY | 2011-12-09 |
| STAR | 588000.SH | QMT front | CNY | 2020-11-16 |
| HK_TECH | 513180.SH | QMT front | CNY | 2021-05-25 |
| HK_DIVIDEND | 03110.HK | sina qfq × HKD/CNY | HKD→CNY | 2013-06-17 |
| US_BROAD | 513500.SH | QMT front | CNY | 2014-01-15 |
| GOLD | 518880.SH | QMT front | CNY | 2013-07-29 |
| CN_DURATION | 511260.SH | QMT front | CNY | 2017-08-24 |
| CASH_LIKE | 511360.SH | QMT front | CNY | 2020-09-25 |

### P5 真实 11-Core 100 个连续观测

```text
shape=(100, 104)，全 finite，无 fallback 锚点补 0，无静默缺失槽位
obs: min=-0.5034  max=0.9841  mean=0.0245  std=0.1498
actual weights: min=0.0704  max=0.2144  Σw ∈ [0.9635, 0.9887]（现金残差正常）
```

### C3 corporate-action 精确 diff

```text
510300: 8 事件   512890: 1 事件   511260: 4 事件   515070: 1 事件（共 14）
max_abs_diff = 0.001376（13.8bp，510300 2023-01-16）
median_abs_diff = 0.000026（0.26bp）
```

**>1bp 事件已 STOP AND EXPLAIN**：QMT `dr` 因子为粗口径（以其反推现金与官方派息差 18bp，
用 dr 累计因子构造 TR 反而不匹配 front，diff 达 −1% ~ −2.4%）；官方 `interest` 字段（每份 0.064 等）
与 QMT front 最接近（中位 0.26bp）。残余差异来自 provider 调整约定 + 3 位小数 rounding，
属 Reviewer §16.1 允许的说明范畴。生产研究序列用 QMT front（已验证）；TR-from-events 作为审计交叉检验。

## 2. Data interval

```text
start = 2011-12-09（联合日历，含上市前 NaN）
end   = 2026-08-07
days  = 3689
warmup_idx = 2620（2022-05-18；首个全 finite 观测）
```

## 3. Environment mode

```text
EnvironmentMode = METHOD_RESEARCH
（无历史实时 PremiumGuard；fee_scenario = CURRENT_FEE_SCENARIO_2026，非 PIT 历史费率）
```

## 4. Algorithm config

```text
SB3 2.8.0；MlpPolicy；net_arch=[256,256]；seed=42；total_timesteps=12,000/算法；device=cuda
action_space = Box(-10,10)^11（softmax → 权重）；obs=104
reward = 净对数收益（R0，含全部成本）
Equal Weight baseline：同一环境路径（同成本/同 T+1 开盘成交/同整手/同 tradability）
```

## 5. Training result（sanity，非性能结论）

| 指标 | EW 基线 | TD3 | SAC | PPO |
|---|---:|---:|---:|---:|
| nan_obs_or_reward (200 步) | 0 | 0 | 0 | 0 |
| weight_mean | 0.0888 | 0.0900 | 0.0900 | 0.0890 |
| weight_max_mean | 0.092 | **0.846** | **0.926** | 0.107 |
| HHI | 0.087 | **0.772** | **0.880** | 0.088 |
| 单资产>50% 步数占比 | 0.0% | **99.5%** | **99.5%** | 0.0% |
| daily_turnover | 0.0145 | 0.136 | 0.076 | 0.032 |
| cash_residual_mean | 2.28% | 1.05% | 1.02% | 2.12% |
| reward_mean / std | +0.0010 / 0.0126 | +0.0025 / 0.0351 | +0.0003 / 0.0142 | +0.0010 / 0.0129 |
| train_seconds | — | 224 | 326 | 172 |
| save/load deterministic 一致 | — | **true** | **true** | **true** |

## 6. Weight / action diagnostics

- **TD3**：action_mean −3.87、action_std 6.91 → 探索幅度大，权重向单资产聚集（>50% 占 99.5% 步）。
  早期训练典型的权重坍缩/聚集现象（非性能结论；Gate 4 前需看曲线与更多步）。
- **SAC**：同样聚集（max 0.926、HHI 0.880）。
- **PPO**：基本停在近等权（max 0.107、HHI 0.088），action_std 0.105 → 12k 步内策略几乎未移动；
  且 PPO 配 GPU+MlpPolicy 有官方 warning（建议 CPU），SDK 行为正常但效率低。
- 均无 NaN/inf；实际权重 0≤w≤1、Σw≤1+ε（P1 约束持续成立）。

## 7. Turnover / Cost

```text
daily_turnover: EW 0.0145 < PPO 0.032 < SAC 0.076 < TD3 0.136
cash_residual_mean: TD3/SAC ~1.0%（近乎满仓） vs EW/PPO ~2.2%
rejected trades: P5/rollout 无因资金不足拒单（P1 修复后）
```

## 8. Equal Weight comparison

仅作 sanity 基准：EW 无单资产聚集、换手最低、收益分布与 PPO 相近。
**不做 winner 结论**（Gate 3 目标仅为 pipeline 正确性）。

## 9. Save / Load

三个模型 `model.save/load` 后，对同一 obs 的 deterministic action **完全一致**（`allclose` true）。

## 10. Exact pytest output

```text
collected 44 items（29 既有 + 11 Gate2 修正 + 4 Gate3 Preflight）
============================= 44 passed in 1.14s ==============================
```

## 11. Warnings / anomalies

1. PPO on GPU + MlpPolicy：SB3 官方 UserWarning（建议 CPU；已记录，不影响正确性）。
2. TD3/SAC 权重聚集到单资产（sanity 红黄灯，非结论）。
3. C3 事件级 max diff 13.8bp > 1bp → 已 STOP AND EXPLAIN（provider 调整约定/rounding）。
4. PPO 12k 步内策略接近静止（探索不足，需 Gate 4 前评估 learning rate/entropy）。

## 12. Carry-forward status

```text
C1 03110 same-day rule        : OPEN（Gate 6 前）
C2 proxy PIT audit            : OPEN（Gate 3 只用真实 ETF 序列，未用 proxy → 不阻塞）
C3 adjustment PIT             : PARTIALLY_RESOLVED（算法+真实事件验证 14/14；diff 已量化）
F1 历史费率规则 PIT           : OPEN（Gate 4 前）
F2 港股通券商佣金             : OPEN（Gate 4/6 前；Gate 3 用 placeholder 0.00005 标注）
```

## 13. Git commit

`d2f3700`

---

## END OF GATE 3 REVIEW PACKET
