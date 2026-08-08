# GATE 1 Corrections

> Reviewer: `GATE_1_STATUS = REVISIONS_REQUIRED_BEFORE_GATE_2`（2026-08-08）。
> 本文件落实 Required Corrections Checklist（§28）全部项目；逐项完成情况见各节。

## 1. 513500 timing / premium correction

### 已改

- 历史指标统一更名 **`close_to_official_nav_gap`**（禁止简称 "premium"）。
- 删除 "历史实时溢价已可得" 结论；历史 IOPV 记为 **`HISTORICAL_REALTIME_PREMIUM = NOT_AVAILABLE`**。
- 删除 "当前 8.74% > P95 7.28% 是实时溢价事实" 表述；改为数据集推导值。
- 保留：基金公司公告已多次提示 513500 显著二级市场溢价风险 → **PremiumGuard 必需**。

### 修正后表述

```text
close_to_official_nav_gap（异步口径，price/QMT raw close vs NAV/sina）:
  obs=2990（2014-01-15 → 2026-08-06）
  mean=+1.34%  P90=+5.18%  P95=+7.28%  P99=+13.98%  min=-7.25%  max=+36.34%
  latest=+8.74%（2026-08-06）
official premium-risk warning = confirmed（基金公告）
realtime executable premium = 需 IOPV 对齐验证（历史 IOPV 不可得）
```

### 时间不同步说明（构成 gap 的成分）

`Close_t^ETF / NAV_t - 1` 同时包含：供求溢价、美股现货时差（CN 15:00 收盘时美股未收盘）、
USD/CNY-CNH 变动、美股期货在 CN 时段变动、NAV 发布时滞、不同数据源 date label 语义。
因此该序列**不得**直接作为 Live PremiumGuard threshold 输入（决策 D-011）。

### Gate 2 起禁止

- 用 `close_to_official_nav_gap` 的 P90/P95/P99 直接设定 Live PremiumGuard 阈值。
- 候选方案（需单独 RFC）：`FairNAV_CN,t = NAV_{t-1} × (1+S&P500/FuturesMove_t) × FXMove_t`。

## 2. 03110 official metadata correction

### 已改

- Board lot：`50`（Global X 官方产品页；HKEX Trading Arrangement Notice，**2026-07-24 生效**，原 100→50）。
- T+0 依据改写：03110 为 **HKEX 上市 + 港股通（Southbound）可交易**，非上交所跨境 ETF；
  当日回转能力按 **HKEX / Southbound 交易规则**验证（D-012）。
- 区分 `OFFICIAL_BOARD_LOT=50` 与 `BROKER_METADATA_SUPPORT=UNKNOWN_PENDING_GATE6`。
- 保留：上市 2013-06-17；港股通资格起始 **2024-05-06**（SSE/SZSE 官方 include 事件）。

### 冻结元数据

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
  management_fee: 0.0068        # 基金层年费，非每笔交易费
  qmt_market_data: false        # QMT 无港股 ETF 行情（实测全 0）
  qmt_order_capability: unknown_pending_gate6
```

## 3. ADV20/ADV60 table

定义：`ADV20 = mean(Amount[-20:])`、`ADV60 = mean(Amount[-60:])`、`median60 = median(Amount[-60:])`。
数据：A股 ETF 用 QMT 日线 `amount`；03110 用 sina 日线 `amount`（HKD）。截至 2026-08-07。
（原报告中的 "ADV" 实为单日成交额，已改名 `turnover_value_1d`，不再使用。）

| Slot | code | turnover_value_1d | adv20 | adv60 | median60 |
|---|---|---:|---:|---:|---:|
| CN_LARGE | 510300.SH | 44.7亿 | **72.96亿** | 60.34亿 | 60.36亿 |
| CN_SMALL | 512100.SH | 67.9亿 | 62.32亿 | 41.01亿 | 38.66亿 |
| CN_DIVIDEND | 512890.SH | 9.0亿 | 10.63亿 | 9.07亿 | 8.69亿 |
| CHINEXT | 159915.SZ | 76.1亿 | 104.29亿 | 74.82亿 | 70.44亿 |
| STAR | 588000.SH | 77.4亿 | 117.42亿 | 87.82亿 | 79.67亿 |
| HK_TECH | 513180.SH | 19.2亿 | 36.24亿 | 36.46亿 | 36.47亿 |
| HK_DIVIDEND | 03110.HK | 0.24亿HKD | **0.29亿HKD** | 0.26亿HKD | 0.23亿HKD |
| US_BROAD | 513500.SH | 4.7亿 | 4.23亿 | 4.26亿 | 4.02亿 |
| GOLD | 518880.SH | 61.5亿 | 31.63亿 | 32.63亿 | 32.91亿 |
| CN_DURATION | 511260.SH | — | **30.45亿** | 35.36亿 | 34.80亿 |
| CASH_LIKE | 511360.SH | — | **254.14亿** | 216.66亿 | 211.62亿 |
| SEMICONDUCTOR | 512480.SH | 17.6亿 | 21.91亿 | 21.66亿 | 21.02亿 |
| AI | 515070.SH | 1.5亿 | 2.57亿 | 2.79亿 | 2.59亿 |
| ROBOTICS | 159770.SZ | 1.5亿 | 1.85亿 | 2.75亿 | 2.39亿 |
| BIOTECH | 159992.SZ | 18.8亿 | 12.91亿 | 10.11亿 | 9.23亿 |
| AEROSPACE | 512660.SH | 2.8亿 | 3.52亿 | 3.57亿 | 3.46亿 |

替代品 ADV20（QMT，44 只，节选，完整见 `data/qmt/meta/alternatives_adv20.csv`）：
159919 沪深300嘉实 13.2亿 / 510310 沪深300易方达 12.9亿 / 159845 中证1000华夏 40.0亿 /
159633 中证1000易方达 12.6亿 / 159949 创业板50华安 32.1亿 / 588080 科创50易方达 27.4亿 /
513130 恒生科技华泰柏瑞 35.4亿 / 159691 港股红利工银 2.4亿 / 513690 港股红利博时 2.6亿 /
513650 标普500南方 3.0亿 / 159655 标普500华夏 1.0亿 / 159934 黄金易方达 6.8亿 /
511880 银华日利 173.1亿 / 511990 华宝添益 108.3亿 / 515080 中证红利招商 4.3亿 /
159819 人工智能易方达 4.9亿 / 159530 机器人易方达 10.0亿 / 562500 机器人华夏 7.6亿 /
515120 创新药广发 14.9亿 / 512710 军工龙头富国 3.4亿 / 159227 航空航天华夏 2.8亿。

## 4. AUM vs market cap table

原则（D-010）：`aum_nav_based = TotalVolume(QMT 份额) × NAV(最新净值)`；
`market_cap = TotalVolume × 最新收盘价`。二者**必须分开**；QDII 溢价时 AUM≠市值。

| Slot | code | shares_outstanding | nav_latest(nav_date) | aum_nav_based | market_cap | 差异说明 |
|---|---|---:|---:|---:|---:|---|
| CN_LARGE | 510300.SH | 257.05亿份 | 4.7552(08-06) | 1222.45亿 | 1221.26亿 | ≈ |
| CN_SMALL | 512100.SH | 105.57亿份 | 3.1114 | 328.48亿 | 328.44亿 | ≈ |
| CN_DIVIDEND | 512890.SH | 278.33亿份 | 1.1582 | 322.36亿 | 322.31亿 | ≈ |
| CHINEXT | 159915.SZ | 189.78亿份 | 3.5463 | 673.02亿 | 673.04亿 | ≈ |
| STAR | 588000.SH | 502.89亿份 | 1.8410 | 925.81亿 | 925.31亿 | ≈ |
| HK_TECH | 513180.SH | 698.29亿份 | 0.6183 | 431.75亿 | 428.05亿 | 微差 |
| HK_DIVIDEND | 03110.HK | 1.96亿份(官方) | 30.33HKD(2026-01) | **59.45亿HKD** | 60.56亿HKD | 官方口径 |
| US_BROAD | 513500.SH | 101.19亿份 | 2.4738(08-06) | **250.31亿** | **272.70亿** | **溢价致 AUM≠市值** |
| GOLD | 518880.SH | 112.54亿份 | 8.8562 | 996.69亿 | 1000.67亿 | ≈ |
| CN_DURATION | 511260.SH | 1.54亿份 | 13.53(08-06) | **209.18亿** | 209.19亿 | 已补齐 |
| CASH_LIKE | 511360.SH | 7.24亿份 | 11.38(08-06) | **823.62亿** | 823.61亿 | 已补齐 |
| SEMICONDUCTOR | 512480.SH | 189.74亿份 | 1.0845 | 205.75亿 | 205.49亿 | ≈ |
| AI | 515070.SH | 72.73亿份 | 1.1803 | 85.84亿 | 85.82亿 | ≈ |
| ROBOTICS | 159770.SZ | 60.91亿份 | 1.0578 | 64.43亿 | 64.44亿 | ≈ |
| BIOTECH | 159992.SZ | 206.06亿份 | 0.9094 | 187.39亿 | 187.51亿 | ≈ |
| AEROSPACE | 512660.SH | 58.24亿份 | 1.1541 | 67.20亿 | 67.21亿 | ≈ |

> 511260/511360 AUM 已从 QMT 份额 × sina/eastmoney 净值补齐（不再是 NA）。
> 513500 使用 NAV-based AUM（250.31亿），**禁止**用二级市值 272.70亿 冒充基金规模。

## 5. Correlation script verification

### 5.1 三对独立 pandas 手算（adjusted 序列）

```text
AI|STAR            rho_120=0.9011  rho_250=0.8970  n=120(2026-02-04→08-07)  n=250(2025-07-23→08-07)
CHINEXT|CN_LARGE   rho_120=0.9029  rho_250=0.8857
SEMICONDUCTOR|STAR rho_120=0.9742  rho_250=0.9715
```

两套独立脚本（`gate1_correlation.py` 与 `gate1_corrections.py`）结果一致，且与 `correlations.csv`
最新版一致。

### 5.2 rho120≈rho250 重复值排查结论

- 当前 4 位小数下**所有关键对 rho120 ≠ rho250**（差异 0.001~0.02）。
- 早期 3 位小数显示的部分对（如 AI|STAR 0.897/0.897）为第一版 `correlations.csv` 的舍入巧合；
  已重新生成，修正后不再重复（0.9011/0.8970）。
- 两脚本一致 = 计算无 bug；`correlations.csv` 已覆盖为修正值。

### 5.3 关键对 overlap 明细（Reviewer §13 要求直接展示）

完整 18 对见 `data/qmt/meta/tail_metrics_correction.csv`（含 n/start/end per window）。

## 6. Revised stress / tail metric

### 已删除

- union-tail Pearson（`A={r_i≤q_i(0.1)} ∪ {r_j≤q_j(0.1)}` 条件相关）不再作为正式 tail metric
  （存在选择偏差，可机械制造低/负相关）。

### 新指标（冻结定义，D-013）

1. **`CN_LARGE_DOWNSIDE_CORR`** = Corr(r_i, r_j | r_CN_LARGE < 0)（原 downside 更名）。
2. **`CN_LARGE_STRESS_CORR`** = Corr(r_i, r_j | r_CN_LARGE ≤ q10(CN_LARGE))。
3. **Lower-tail co-exceedance**：`P(I_i=1|I_j=1)` 与 `P(I_j=1|I_i=1)`，`I_k = 1(r_k ≤ q_k(0.1))`。
4. **`TailDependenceScore`** = `P(I_i=1, I_j=1) / 0.1²`（=1 表示与独立同分布一致）。

### 关键对结果（adjusted 序列）

| pair | CN_LARGE_DOWNSIDE | CN_LARGE_STRESS | co-exc(P(a\|b)) | TailDepScore |
|---|---:|---:|---:|---:|
| SEMICONDUCTOR\|STAR | 0.8570 | 0.7597 | 0.7372 | 7.416 |
| AI\|STAR | 0.7948 | 0.8001 | 0.6496 | 6.525 |
| AI\|SEMICONDUCTOR | 0.7980 | 0.8202 | 0.6772 | 6.807 |
| CHINEXT\|CN_LARGE | 0.6425 | 0.6173 | 0.5605 | 5.606 |
| CHINEXT\|STAR | 0.7170 | 0.5928 | 0.6715 | 6.755 |
| CN_LARGE\|CN_DIVIDEND | 0.5588 | 0.6286 | 0.5278 | 5.295 |
| **CN_LARGE\|CN_DURATION** | -0.1557 | -0.1929 | **0.0704** | **0.705** |
| CN_LARGE\|GOLD | 0.0351 | 0.0000 | 0.1350 | 1.351 |
| CN_LARGE\|US_BROAD | 0.2187 | 0.1881 | 0.2633 | 2.639 |
| HK_DIVIDEND\|HK_TECH | 0.5330 | 0.7211 | 0.3983 | 4.003 |
| HK_DIVIDEND\|CN_DURATION | -0.1193 | -0.2394 | 0.0800 | 0.804 |

### 修正后结论

- **不再**从 CN_DURATION 的旧 union-tail Pearson（-0.646）宣称"极端暴跌对冲"；
  新口径 TailDepScore=0.705（<1）与 stress corr=-0.19 仅支持**温和避险**结论。
- GOLD/US_BROAD/HK_DIVIDEND 的负 tail 结论一并撤销，改用上表数值。
- **保留**：STAR\|SEMICONDUCTOR ρ250=0.9715 → HardTech 上限必需；AI 与成长核心高度重叠；
  CN_DURATION 与 GOLD 提供非权益风险源。

## 7. Proxy base-date vs launch-date table

| Slot proxy | index | base_date | launch_date | is_backfilled_before_launch | 状态 |
|---|---|---|---|---|---|
| 沪深300 | 000300.SH | 2004-12-31 | 2005-04-08 | 是（回溯发布前历史） | 确认 |
| 中证1000 | 000852.SH | 2004-12-31 | 2014-10-17 | 是 | 确认 |
| 中证红利低波动 | H30269 | 2005-12-30 | 2013-12-16 | 是 | 待 Phase 1 验证 |
| 创业板指 | 399006.SZ | 2010-05-31 | 2010-06-01 | 否 | 确认 |
| 科创50 | 000688.SH | 2019-12-31 | 2020-07-22 | 是 | 确认 |
| 恒生科技 HSTECH | — | 2014-12-31 | 2020-07-27 | 是 | 确认 |
| 恒生高股息率 HSHYLDI | — | 2003-12-31 | ~2003-12 | 是 | 待验证 |
| 标普500 SPX | — | 1941-43 | 1957-03-04(实盘) | 不适用 | 确认 |
| 上海金 Au99.99 | — | 2002-10-30(SGE) | 实时 | 否 | 确认 |
| 中债国债总财富 | — | 2002 | — | — | 待验证 |
| 中证全指半导体 H30184 | — | 2016-03-11 | 2019-03-20 | 是 | 待验证 |
| 中证人工智能主题 930713 | — | 2012-06-29 | 2015-07-17 | 是 | 待验证 |
| 中证机器人 H30590 | — | 2010-06-30 | 2021-04-28 | 是 | 待验证 |
| 中证创新药 931152 | — | 2014-12-31 | 2020-03-20 | 是 | 待验证 |
| 中证军工 399967 | — | 2004-12-31 | 2013-12-26 | 是 | 待验证 |

**规则（冻结）**：`index_base_date ≠ point-in-time available date`；
pre-launch backfilled 历史仅用于 `SCENARIO / METHOD PROXY`，**不得进入严格 PIT OOS**；
`instrument_master` 每个 proxy 记录 6 字段（base/launch/data_start/is_backfilled/methodology_version/source）。

## 8. ETF adjustment / dividend spot checks

### QMT `get_divid_factors`（2019 起）

| code | label | events | 说明 |
|---|---|---:|---|
| 510300.SH | 普通股票ETF | 8 | 年度分红 interest 0.059~0.123/份，dr 1.015~1.027 |
| 512890.SH | 红利低波 | 1 | **2021-10-25 送股 stockBonus=1.0，dr=1.99878（份额 1:1）** |
| 511260.SH | 债券ETF | 4 | 季度分配 interest 0.67~1.36/份，dr 1.005~1.010 |
| 159915.SZ | 创业板 | 0 | 无分红事件 |
| 511360 / 518880 / 03110.HK | — | 0 | QMT 无事件（港股分红不经 QMT） |

### 关键调整语义发现（D-009 依据）

- **QMT front ≠ 统一语义**：515070(AI) 的 front 序列对早期历史施加**常数 0.5 因子**
  （份额折算事件），raw 在折算日存在假跳变；STAR(588000) front==raw（无事件）。
- 因此**冻结双价格体系**（D-009）：
  - `execution_price_series` = raw 可成交价（PnL / 成交 / 溢价基准）；
  - `research_total_return_series` = 复权序列（收益 / 相关 / 特征）；
  - 每个 instrument 的复权语义（QMT front vs AkShare qfq、折算/拆分/分红）须在
    Phase 1 `instrument_master` 逐只审计后使用；不得无定义混用 raw/qfq/NAV。

## 9. Updated universe table

核心修正字段汇总（完整表见 GATE_1_DATA_UNIVERSE.md 附录 A + 本文件 §3/§4）：

- 所有 "ADV" 已替换为 `turnover_value_1d` + `adv20` + `adv60`（§3）。
- AUM 拆分为 `aum_nav_based` / `market_cap` / `shares_outstanding`（§4）。
- 03110：board_lot=50（2026-07-24 生效）；T+0 依据改为 HKEX/Southbound；ADV 用 HKD 口径（§2/§3）。
- 513500：历史指标更名 close_to_official_nav_gap；实时溢价 NOT_AVAILABLE（§1）。
- CASH_LIKE：`511360 risk_class=SHORT_CREDIT, cash_equivalent=false`，与 Broker Cash 分开（D-014）；
  preferred 暂不更换，如切 511880/511990 需 RFC。
- Universe 11+5 不变（Reviewer §25 批准）。

## 10. Files changed

- 新增 `scripts/gate1_corrections.py`（ADV/AUM/相关性核验/新 tail/分红抽查，可复现）
- 新增本文件 `GATE_1_CORRECTIONS.md`
- 更新 `docs/review_packets/GATE_1_DATA_UNIVERSE.md`（关键错误修正）
- 更新 `docs/DECISIONS.md`（D-009 ~ D-014）
- 更新 `docs/CODEX_AGENT_STATUS.md`
- 数据产物：`data/qmt/meta/liquidity_aum_correction.csv`、`alternatives_adv20.csv`、
  `tail_metrics_correction.csv`、`correlations.csv`（已覆盖为修正值）

## 11. Commands

```text
python scripts/gate1_corrections.py
```

## 12. Exact outputs

- ADV/AUM 表：见 §3/§4（`liquidity_aum_correction.csv`）。
- 相关性核验：§5（`tail_metrics_correction.csv`）。
- 分红抽查：§8（QMT `get_divid_factors` 原始输出）。
- 替代品 ADV20：§3（`alternatives_adv20.csv`）。

## 13. Commit SHA

`c48e9a5`

---

## END OF GATE 1 CORRECTIONS
