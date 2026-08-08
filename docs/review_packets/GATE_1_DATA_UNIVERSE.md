# Gate Review Packet

## GATE_1_DATA_UNIVERSE

> **勘误通知（2026-08-08）**：本文件部分数据定义已按 Reviewer 意见修正，
> 以 `GATE_1_CORRECTIONS.md` 为准。受影响章节：附录 A（ADV 口径）、附录 B（proxy launch date）、
> 附录 D（downside/tail 命名与定义）、附录 F（03110 lot/T+0）、附录 G（513500 溢价口径）。

## 1. Goal

按 EXECUTION_SPEC §66 与 Reviewer §18-§20 授权范围，完成 **Data & Universe Audit**：
核实 16 只标的（11 Core + 5 Theme）的元数据、历史覆盖、价格字段语义、数据源可得性、
替代品筛选、相关性初筛、03110.HK 与 513500 专项。
**本 Gate 不写 PortfolioEnv / CostModel / RiskOverlay、不训练、不下单、不改 Frozen Slots。**

## 2. What was implemented

- 用券商 QMT（xtdata）拉取 16/16 只标的历史日线（raw + front）与部分合约元数据；
- 用 AkShare 交叉验证（13 只起始日完全一致）；sina 补齐 03110.HK 与 513500 历史净值；
- 读取官方港股通名单（沪深交易所 2026-07-18 快照）核实 03110 资格与起始日；
- 计算 ρ120 / ρ250 / downside / tail 相关性（含 overlap 报告）；
- 全量场内 ETF 名单 + QMT 板块做替代品筛选；
- 产出本文件与数据快照（`data/qmt/`，不入库）+ 可复现脚本 `scripts/gate1_*.py`。

## 3. Files changed

- 新增 `scripts/gate1_data_fetch.py` / `gate1_qmt_fetch.py` / `gate1_meta_alternatives.py`
  / `gate1_alternatives.py` / `gate1_correlation.py` / `gate1_hk_premium.py`
- 数据产物：`data/qmt/raw/`、`data/qmt/meta/`（gitignored）
- 新增本文件 `GATE_1_DATA_UNIVERSE.md`

## 4. Architecture decisions

- 数据主源：**QMT（券商）**；AkShare/sina 为交叉验证与补缺（03110、513500 净值）。
- QMT 无法提供港股 ETF 行情（实测 02828/03110/03033 全 0），港股 ETF 价格走 sina，
  实盘执行能力留待 Gate 6 `BrokerCapabilityAudit`。
- HK_DIVIDEND 槽位保留（Reviewer/规格 §18），但实盘 Instrument 需备选境内港股红利 ETF。

## 5. Data sources

| 源 | 内容 | 状态 |
|---|---|---|
| QMT xtdata（国金，本地 127.0.0.1:58610） | 15 只 A股 ETF 日线（raw+front）、交易日历、合约元数据 | OK |
| AkShare `fund_etf_spot_em` / `fund_etf_hist_em` | 全量场内 ETF 快照（1571 只）、历史行情 | OK（债券 ETF 不在 spot） |
| AkShare `stock_hk_daily`（sina） | 03110.HK 日线（2013-06-17 起） | OK |
| sina 基金净值 API | 513500 历史净值（2013-12-05 起） | OK |
| 官方港股通名单（沪深交易所，2026-07-18） | 03110 资格（当前合格 + 2024-05-06 纳入） | OK |
| AkShare `stock_hk_hist`（东财） | 港股 | 被限流/不可用（备用） |

## 6. Commands executed

```text
python scripts/gate1_qmt_fetch.py        # QMT 日线 + 合约
python scripts/gate1_data_fetch.py       # AkShare 交叉验证
python scripts/gate1_meta_alternatives.py  # QMT 板块 + spot 元数据
python scripts/gate1_alternatives.py     # 替代品筛选
python scripts/gate1_correlation.py      # 相关性（含 overlap）
python scripts/gate1_hk_premium.py       # 03110 sina + 513500 净值/溢价
```

## 7. Tests and exact results

无代码单元测试（本 Gate 为数据审计）；数据校验见 §9-§14（QMT vs AkShare 起始日一致等）。

## 8. Metrics / tables

见下方各节。

## 9. Known limitations

- QMT 港股 ETF 行情不可用（实测全 0）；港股通订单能力待 Gate 6 券商侧验证。
- AkShare 东财港股接口当前被限流；NAV 天天基金接口限流严重，改用 sina 净值接口。
- 03110.HK lot size 未获（QMT 合约接口对港股返回 None）；记为 UNKNOWN_PENDING_BROKER_TEST。
- 511260/511360 不在 AkShare spot 快照（债券 ETF 类别），AUM 以 QMT 板块成员 + 基金公司口径为准（Gate 1 未取到，标记 NA）。
- 各指数 proxy 基日/发布日为设计值，Phase 1 数据层需逐指数验证。

## 10. Deviations from EXECUTION_SPEC

无。未修改 Frozen Decisions；配置 `config/universe.yaml` 中 preferred 代码经核实
（159770 实为"机器人ETF天弘"、159992"创新药ETF银华"、515070"人工智能ETF华夏"、512480"半导体ETF国联安"、
512660"军工ETF国泰"）——名称与代码一致，无需改码。

## 11. Open risks

- 513500 当前溢价 +8.7%（>历史 P95 7.3%）：实盘买入需 PremiumGuard，Gate 2 前不得默认放开。
- STAR|SEMICONDUCTOR ρ250=0.97：HardTech 上限（0.30）为必需约束，非可选项。
- 政策主题（AI/半导体/机器人）与核心成长槽位高相关（0.80-0.90）：Gate 5 主题 sleeve 收益判定需严格区分 Beta。
- 03110 港股通资格 2024-05-06 起：2024-05 前的"港股高股息"历史回测只能作为 SCENARIO（资格前不可实盘）。

## 12. Recommended next action

Reviewer 批准后进入 **Gate 2 — Environment & Accounting**：按 D-005 冻结
`TargetAssetWeights` contract，实现 PortfolioAccounting + MockBroker + 成本/风控雏形 +
no-lookahead 测试。**Gate 1 不输出训练数据集的最终冻结**（指数 proxy 逐项验证在 Phase 1 数据层完成）。

## 13. Git commit / branch

`RL_Stock` main 分支（本 Gate 文档提交后更新 SHA）。

---

# 附录 A：Universe 审计总表（数据截至 2026-08-07 收盘）

| Slot | Preferred | 名称 | 交易所 | 币种 | 类型 | 上市日 | REAL_HISTORY_START | 日线行数 | turnover_value_1d(元) | 市值(元) | T+0/T+1 | QMT 行情 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CN_LARGE | 510300 | 沪深300ETF华泰柏瑞 | SH | CNY | 股票 | 2012-05-28 | 2012-05-28 | 3451 | 44.7亿 | 1221亿 | T+1 | OK |
| CN_SMALL | 512100 | 中证1000ETF南方 | SH | CNY | 股票 | 2016-11-04 | 2016-11-04 | 2370 | 67.9亿 | 328亿 | T+1 | OK |
| CN_DIVIDEND | 512890 | 红利低波ETF华泰柏瑞 | SH | CNY | 股票 | 2019-01-18 | 2019-01-18 | 1830 | 9.0亿 | 322亿 | T+1 | OK |
| CHINEXT | 159915 | 创业板ETF易方达 | SZ | CNY | 股票 | 2011-12-09 | 2011-12-09 | 3559 | 76.1亿 | 681亿 | T+1 | OK |
| STAR | 588000 | 科创50ETF华夏 | SH | CNY | 股票 | 2020-11-16 | 2020-11-16 | 1390 | 77.4亿 | 925亿 | T+1 | OK |
| HK_TECH | 513180 | 恒生科技ETF华夏 | SH | CNY | 跨境 | 2021-05-25 | 2021-05-25 | 1264 | 19.2亿 | 428亿 | T+0 | OK |
| HK_DIVIDEND | 03110.HK | GX恒生股息(GX HS HIGHDIV) | HKEX | HKD | 港股通ETF | 2013-06-17 | 2013-06-17(sina) | 3084 | 见注1 | 约59亿HKD(注1) | 见注2 | **无**(全0) |
| US_BROAD | 513500 | 标普500ETF博时 | SH | CNY | 跨境/QDII | 2014-01-15 | 2014-01-15 | 3053 | 4.7亿 | 273亿 | T+0 | OK |
| GOLD | 518880 | 黄金ETF华安 | SH | CNY | 商品 | 2013-07-29 | 2013-07-29 | 3168 | 61.5亿 | 1001亿 | T+0 | OK |
| CN_DURATION | 511260 | 十年国债ETF国泰 | SH | CNY | 债券 | 2017-08-24 | 2017-08-24 | 2172 | NA(spot) | NA | T+0 | OK |
| CASH_LIKE | 511360 | 短融ETF海富通 | SH | CNY | 债券 | 2020-09-25 | 2020-09-25 | 1420 | NA(spot) | NA | T+0 | OK |
| SEMICONDUCTOR | 512480 | 半导体ETF国联安 | SH | CNY | 股票/主题 | 2019-06-12 | 2019-06-12 | 1737 | 17.6亿 | 205亿 | T+1 | OK |
| AI | 515070 | 人工智能ETF华夏 | SH | CNY | 股票/主题 | 2019-12-24 | 2019-12-24 | 1605 | 1.5亿 | 86亿 | T+1 | OK |
| ROBOTICS | 159770 | 机器人ETF天弘 | SZ | CNY | 股票/主题 | 2021-11-08 | 2021-11-08 | 1153 | 1.5亿 | 64亿 | T+1 | OK |
| BIOTECH | 159992 | 创新药ETF银华 | SZ | CNY | 股票/主题 | 2020-04-10 | 2020-04-10 | 1535 | 18.8亿 | 188亿 | T+1 | OK |
| AEROSPACE | 512660 | 军工ETF国泰 | SH | CNY | 股票/主题 | 2016-08-08 | 2016-08-08 | 2428 | 2.8亿 | 67亿 | T+1 | OK |

注1：03110.HK 成交额/AUM 以基金公司月报口径（2026-01：发行股数 1.96 亿份、NAV≈HKD 30.33 → 市值约 59 亿 HKD）；
QMT/spot 无该数据。ADV 未在 Gate 1 获取（sina 日线有 volume/amount，见 `data/qmt/raw/HK_DIVIDEND_03110_HK_sina_qfq.csv`）。
注2：03110 为 HKEX 上市 + 港股通可交易；当日回转能力按 HKEX/Southbound 规则验证
（非上交所跨境 ETF 规则）。Board lot=50（2026-07-24 生效），Broker 支持待 Gate 6。
注4：本表 "turnover_value_1d" 为 2026-08-07 单日成交额；ADV20/ADV60 见 `GATE_1_CORRECTIONS.md §3`。
注3：T+0/T+1 依据上交所《交易规则》3.1.5（债券/债券ETF/货币ETF/黄金ETF/跨境ETF 当日回转，股票ETF T+1）；
Phase 1 `instrument_master` 逐只核实。

### 交叉验证

- QMT 与 AkShare 13 只重合标的的起始日**完全一致**（差异 0）；收盘价一致性另见父工程
  `reports/etf_defensive/qmt_health`（最大相对差 2.22e-16）。
- AkShare 缺失的 512480/512660/03110.HK 由 QMT（前两者）与 sina（后者）补齐。

# 附录 B：REAL vs PROXY 历史设计（Reviewer §19.2）

| Slot | ETF_REAL_HISTORY_START | PROXY（Method Research 用） | PROXY_HISTORY_START(设计值) |
|---|---|---|---|
| CN_LARGE | 2012-05-28 | 沪深300 (000300.SH) | 2005+（待验证） |
| CN_SMALL | 2016-11-04 | 中证1000 (000852.SH) | 2005+ |
| CN_DIVIDEND | 2019-01-18 | 中证红利低波动 (H30269) | 2005-12-30（基日） |
| CHINEXT | 2011-12-09 | 创业板指 (399006.SZ) | 2010-05-31（基日） |
| STAR | 2020-11-16 | 科创50 (000688.SH) | 2019-12-31（基日） |
| HK_TECH | 2021-05-25 | 恒生科技 (HSTECH) | 2014-12-31（基日） |
| HK_DIVIDEND | 2013-06-17 | 恒生高股息率指数 (HSHYLDI) | 2003-12-31（基日，待验证） |
| US_BROAD | 2014-01-15 | 标普500 (SPX) | 2004+（视数据源） |
| GOLD | 2013-07-29 | 上海金 Au99.99 / 伦敦金 | 2002+（SGE） |
| CN_DURATION | 2017-08-24 | 中债国债总财富指数 | 2002+（中债指数，待验证） |
| CASH_LIKE | 2020-09-25 | 货币基金指数 / 中证短融指数 | 视数据源 |
| SEMICONDUCTOR | 2019-06-12 | 中证全指半导体 (H30184) | 2016-03-11（基日，待验证） |
| AI | 2019-12-24 | 中证人工智能主题 (930713) | 2012-06-29（基日） |
| ROBOTICS | 2021-11-08 | 中证机器人 (H30590) | 2010-06-30（基日，待验证） |
| BIOTECH | 2020-04-10 | 中证创新药产业 (931152) | 2014-12-31（基日） |
| AEROSPACE | 2016-08-08 | 中证军工 (399967) | 2004-12-31（基日） |

> 原则：proxy 仅用于 Method Research；Instrument Backtest 只用真实 ETF 上市后数据；
> 代理数据必须 `is_proxy=true`（EXECUTION_SPEC §15/§16）。

# 附录 C：价格字段语义（Reviewer §19.3）

| 字段 | 含义 | 来源 | Gate 1 状态 |
|---|---|---|---|
| raw close | 未复权收盘价 | QMT `dividend_type=none` / AkShare `adjust=""` | 16/16 可用 |
| adjusted close (qfq) | 前复权收盘 | AkShare `qfq`；QMT `front` | A股 15/15 可用；**QMT 港股 front 返回全 0** → 03110 用 sina qfq |
| NAV | 单位净值 | sina 基金净值 API / 天天基金 | 513500：2013-12-05 起 3025 条可用 |
| IOPV | 实时估值 | AkShare spot 快照 | 当前值可用；**历史 IOPV 未发现免费源（标记不可得）** |
| premium/discount | 折溢价 | 由 price vs NAV/IOPV 计算 | 当前值（spot）可用；历史序列可用 price+NAV 计算（513500 已示范） |

# 附录 D：相关性分析（Reviewer §19.4/§19.5）

## 定义（冻结）

- `rho_120/rho_250`：最近 120/250 个交易日（truncate 到共同历史）日对数收益 Pearson 相关。
- `CN_LARGE_DOWNSIDE_CORR`：限定 **CN_LARGE 日收益 < 0** 的交易日，Pearson 相关（原名 downside，已更名）。
- `CN_LARGE_STRESS_CORR` / co-exceedance / TailDepScore：原 union-tail Pearson **已废弃**（选择偏差）；
  新定义见 `GATE_1_CORRECTIONS.md §6`。
- 所有指标报告 overlap 的 `start / end / obs`（完整数据见 `data/qmt/meta/correlations.csv`）。

## 关键对结果（截至 2026-08-07）

| 对 | ρ120 | ρ250 | CN_LARGE_DOWNSIDE | CN_LARGE_STRESS(q10) |
|---|---:|---:|---:|---:|
| SEMICONDUCTOR\|STAR | 0.974 | **0.972** | 0.856 | 0.592 |
| AI\|STAR | 0.897 | **0.897** | — | — |
| AI\|SEMICONDUCTOR | 0.865 | **0.863** | 0.803 | 0.583 |
| CHINEXT\|CN_LARGE | 0.886 | **0.886** | — | — |
| AI\|CHINEXT | 0.885 | **0.885** | — | — |
| CHINEXT\|STAR | 0.817 | 0.807 | 0.715 | 0.460 |
| CN_LARGE\|CN_SMALL | 0.805 | **0.805** | — | — |
| CN_SMALL\|ROBOTICS | 0.800 | **0.800** | — | — |
| AI\|CN_LARGE | 0.799 | 0.799 | — | — |
| CN_LARGE\|US_BROAD | 0.615 | 0.504 | 0.222 | -0.162 |
| CN_LARGE\|CN_DIVIDEND | 0.005 | 0.073 | 0.603 | 0.382 |
| CN_LARGE\|CN_DURATION | 0.114 | -0.106 | -0.208 | -0.646 |
| CN_LARGE\|GOLD | 0.455 | 0.385 | 0.016 | -0.373 |
| HK_DIVIDEND\|HK_TECH | 0.542 | 0.437 | 0.533 | -0.012 |
| HK_DIVIDEND\|CN_DURATION | 0.119 | -0.075 | -0.119 | -0.555 |
| HK_DIVIDEND\|GOLD | 0.544 | 0.377 | 0.020 | -0.309 |

## 结论

1. **STAR = 半导体**：ρ250=0.97、tail=0.59 → `HardTech` 上限（STAR+SEMICONDUCTOR ≤30%）为必需约束，588000 与 512480 不得视为独立风险因子。
2. **AI 主题与核心成长高度重叠**（与 STAR 0.90 / CHINEXT 0.88 / SEMICONDUCTOR 0.86）：主题 sleeve 的增量风险敞口有限，Gate 5 需报告"去除科技 Beta 后的 Alpha"。
3. **A股 Beta 聚簇**：CN_LARGE/CHINEXT/CN_SMALL/STAR/AI 间 0.77-0.89 → `ChinaGrowth` 上限（50%）与单资产上限（25%）合理。
4. **防御/资产类别有效性**：CN_DURATION 与权益负相关（-0.11~-0.21）、GOLD 与权益低相关（0.39）、HK_DIVIDEND 与 CN_DURATION 低相关（-0.08）→ 核心池的分散结构有效。
5. 短历史重叠警告：HK_TECH（2021-05 起）等主题历史较短，ρ 以 overlap 报告为准；主题 ETF 更长历史需 proxy（附录 B）。

# 附录 E：替代品筛选（Reviewer §19.1，按"代表性强/历史长/流动性好/可执行"而非 past CAGR）

| Slot | Preferred | Alt 1 | Alt 2 | Alt 3 | 备注 |
|---|---|---|---|---|---|
| CN_LARGE | 510300 | 159919 沪深300ETF嘉实(9.3亿) | 510310 沪深300ETF易方达(6.7亿) | 510330 华夏(4.0亿) | 同标的多个 |
| CN_SMALL | 512100 | 159845 中证1000ETF华夏(44亿) | 159633 易方达(12亿) | 560010 广发(8.4亿) | — |
| CN_DIVIDEND | 512890 | 515080 中证红利ETF招商(3.2亿) | 563020 红利低波ETF易方达(3.3亿) | 515450 红利低波50南方(2.8亿) | — |
| CHINEXT | 159915 | 159949 创业板50ETF华安(22.7亿) | 159952 创业板ETF广发(7.1亿) | 159967 创业板成长华夏(10.4亿) | 159949 更偏大盘成长 |
| STAR | 588000 | 588080 科创50ETF易方达(20.8亿) | 588060 广发(4.6亿) | 588050 工银(4.1亿) | — |
| HK_TECH | 513180 | 513130 恒生科技ETF华泰柏瑞(17.9亿) | 159740 大成(7.8亿) | 513010 易方达(6.2亿) | — |
| HK_DIVIDEND | 03110.HK | 159691 港股红利ETF工银(2.4亿) | 513690 港股红利ETF博时(1.8亿) | 513950 恒生红利ETF富国(1.7亿) | **境内可执行替代**；港股侧：03469.HK 南方港股通红利等 |
| US_BROAD | 513500 | 513650 标普500ETF南方(2.3亿) | 159655 标普500ETF华夏(1.0亿) | 159612 国泰(0.2亿) | 溢价需逐只审 |
| GOLD | 518880 | 159934 黄金ETF易方达(11.3亿) | 159937 博时(9.8亿) | 518800 国泰(5.6亿) | — |
| CN_DURATION | 511260 | **511010 国债ETF国泰(2013-03-25 上市，历史更长)** | 511520 政金债ETF富国 | 159649 国开债ETF华安 | QMT ETF债券型板块 |
| CASH_LIKE | 511360 | 511880 银华日利ETF(175亿) | 511990 华宝添益ETF(124亿) | 159001 货币ETF易方达(8.6亿) | 货币类更"现金"，短融为信用替代 |
| SEMICONDUCTOR | 512480 | 512760 芯片ETF国泰 | 588170 科创半导体ETF华夏(76亿) | 513310 中韩半导体ETF(166亿) | 588170/513310 与 STAR 重叠更高 |
| AI | 515070 | 159819 人工智能ETF易方达(4.9亿) | 159363 创业板AI华宝(16亿) | 159381 创业板AI华夏(7.1亿) | 创业板AI与 CHINEXT 重叠高 |
| ROBOTICS | 159770 | 159530 机器人ETF易方达(9.3亿) | 562500 机器人ETF华夏(7.4亿) | 159272 富国(2.3亿) | — |
| BIOTECH | 159992 | 515120 创新药ETF广发(14.9亿) | 513120 港股创新药广发(111亿) | 159570 港股通创新药(27.9亿) | 港股创新药为不同风险域 |
| AEROSPACE | 512660 | 512710 军工龙头ETF富国(2.7亿) | 159227 航空航天ETF华夏(2.1亿) | 512670 国防ETF鹏华(0.8亿) | — |

> 替代品数据来源：AkShare spot 全量名单（名称关键词 + 成交额排序）+ QMT 板块成员
> （`data/qmt/meta/alternative_candidates.csv`、`qmt_etf_sectors.csv`）。ADV 为 2026-08-07 当日成交额。

# 附录 F：03110.HK 专项（Reviewer §19.6）

| 项目 | 结论 |
|---|---|
| 官方港股通资格（当前） | **合格**（沪深两市均在 2026-07-18 官方名单，security_type=ETF） |
| 历史资格起始 | **2024-05-06**（SSE/SZSE include 事件，公告日未随名单提供） |
| 上市日期 | 2013-06-17（HKEX SEHK 主表 + MoneyDJ/etnet 交叉确认） |
| 名称/管理人 | GX HS HIGHDIV / Global X 恒生高股息率ETF；管理费 0.68%/年 |
| 跟踪指数 | 恒生高股息率指数（HSHYLDI） |
| 市场数据可得性 | **QMT 无港股 ETF 行情（实测全 0）**；sina 日线 2013-06-17 起可用（3084 条） |
| QMT quote 能力 | **NOT AVAILABLE**（当前券商/版本） |
| QMT order 能力 | UNKNOWN_PENDING_BROKER_TEST（Gate 6 券商侧验证） |
| 币种 | HKD（组合基币 CNY，需 FXModel；HKD/CNY 用 AkShare 中行牌价，父工程已实现） |
| Lot size | **官方 50（2026-07-24 生效，原100→50）**；Broker 元数据支持 = UNKNOWN_PENDING_GATE6 |
| 费用 | SouthboundCostModel 待 Gate 6 按券商实际结算费率冻结 |
| 建议 | 槽位保留；**实盘 Instrument 首选境内港股红利 ETF**（159691/513690/513950），
  03110.HK 作为港股通侧备选；需 RFC 后方可定实盘标的 |

# 附录 G：513500 专项（Reviewer §19.7）

| 项目 | 结论 |
|---|---|
| 历史 NAV | **可用**：sina 净值接口 2013-12-05 起，3025 条（`513500_nav_history.csv`） |
| close_to_official_nav_gap | **异步口径**（price/QMT raw vs NAV/sina）：2990 overlap 日（2014-01-15 → 2026-08-06）；mean +1.34%；P90 +5.18%；P95 +7.28%；P99 +13.98%；max +36.34%；latest +8.74% |
| 实时可交易溢价 | **NOT_AVAILABLE**（历史 IOPV 不可得；正式名 `HISTORICAL_REALTIME_PREMIUM`） |
| IOPV | 当前快照可用（spot `IOPV实时估值`）；**历史 IOPV 不可得（免费源）** |
| PremiumGuard 阈值 | Gate 1 不设定；**禁止**用异步 close/NAV gap 的 P90/P95 直接调 Live 阈值（见 `GATE_1_CORRECTIONS.md §1`） |
| 替代 S&P500 | 513650 南方（ADV 2.3亿）、159655 华夏（1.0亿）、159612 国泰（0.2亿） |
| 风险提示 | 官方公告已多次提示显著溢价风险；实盘买入必须受 PremiumGuard 约束（实时 IOPV 口径） |

# 附录 H：数据可得性汇总（EXECUTION_SPEC §66 项目）

| 项 | 状态 |
|---|---|
| 上市日期/代码/交易所/币种/类型 | 16/16 确认 |
| 成交额 / AUM | 14/16（spot；511260/511360 债券类不在 spot → NA；03110 用基金公司口径） |
| Benchmark | 部分确认（510300=沪深300、513500=标普500、03110=恒生高股息率指数等）；Phase 1 逐只入 `instrument_master` |
| 历史覆盖 | 16/16（最短 ROBOTICS 2021-11 起 1153 行） |
| QMT 数据可得性 | 15/16（A股 ETF 全可用；港股 ETF 不可用） |
| Premium 数据可得性 | 当前：可用；历史：price+NAV 可构造（513500 已验证） |
| T+0/T+1 | 规则层确认（SSE 3.1.5）；逐只入 `instrument_master` |
| Lot size | A股 100份/手（规则默认，待逐只核实）；03110 UNKNOWN_PENDING_BROKER_TEST |
| 港股通资格 | 03110 合格（2024-05-06 起）；其余 A股 ETF 无需港股通 |
| 代理方案 | 附录 B 已设计，Phase 1 数据层逐指数验证 |

---

## END OF GATE 1 REVIEW PACKET
