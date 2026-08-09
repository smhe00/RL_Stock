# GATE 4 LONG HORIZON PROXY PREP — L2 场景 Proxy 长区间研究（冻结契约）

> 评审（`GATE_4_LONG_HORIZON_NON_RL_RUN_DOC_FIX_REVIEWER_RESPONSE.md`）**DOC_FIX_ACCEPTED_L1_CLOSED_L2_PROXY_PREP_AUTHORIZED**。
> 本 packet 冻结 **L2 Scenario Proxy PREP**（Track C，`GATE_4_DATA_HORIZON_PLAN.md`）。**不执行 L2 run**。
> handoff_id = **G4_LONG_HORIZON_PROXY_PREP_001**。

---

# 0. 性质声明（全局）

```text
L2 = SCENARIO_NOT_STRICT_PIT_OOS
本研究的全部序列均为 retrospective/backfilled scenario proxy（Track C），
允许 pre-launch index/backfill 历史，但必须明确标注，不得冒充真实工具/严格 point-in-time。
不构成生产/实盘授权。L1 真实工具结果（frozen）不因本 PREP 改变。
```

# 1. 目标与标签

```text
验证确定性方法在跨越多轮牛熊（2015 牛熊 / 2018 熊 / COVID / 2021-2023 弱股 / 2024-2026 强股）
的长历史场景下是否保留结构性的回撤/风险调整优势。
label = LONG_HORIZON_PROXY_SCENARIO_DIAGNOSTIC（scenario/method research，非 pristine OOS）
主问题：MaxDiv 的 Sharpe 稳定性 / MaxDD 控制 / 是否过度牺牲 CAGR / 是否依赖单一资产
        / 权重集中度与 regime 依赖（评审 Interpretation target）。
```

# 2. 11 槽位 → Proxy 映射 + Provenance（全部实测验证）

> 数据源优先级（用户指示 + 评审授权）：**miniQMT（QMT/xtdata）优先**；QMT 无则 akshare（新浪）；
> 真实 ETF 存在且覆盖 2015 时直接用真实（含 FX/分红，无需 proxy）。

| # | 槽位 | 真实 ETF | L2 Proxy | 数据源 | 数据起点 | 基日/发布 | 上市前是否 retrospective/backfilled |
|---|---|---|---|---|---|---|---|
| 1 | CN_LARGE | 510300.SH | 沪深300 指数 000300.SH | QMT/xtdata | 2005-01-04 | 基日 2004-12-31 | 否（真实指数历史） |
| 2 | CN_SMALL | 512100.SH | 中证1000 指数 000852.SH | QMT/xtdata | 2005-01-04 | 基日 2004-12-31（发布 2014-10） | 是（2014-10 前为指数回溯编制） |
| 3 | CN_DIVIDEND | 512890.SH | 上证红利 指数 000015.SH | QMT/xtdata | 2005-01-04 | 基日 2005-01-04 | 否 |
| 4 | CHINEXT | 159915.SZ | 创业板指 399006.SZ | QMT/xtdata | 2010-06-01 | 基日 2010-06-01 | 否 |
| 5 | STAR | 588000.SH | 创业板指（2015-01..2019-12）+ 科创50 000688.SH（2020-01 起） | QMT/xtdata | 2010-06-01（替代期）/ 2019-12-31（科创50） | 科创50 基日 2019-12-31 | **是（2015-2019.12 为创业板指替代；high basis risk）** |
| 6 | HK_TECH | 513180.SH | 恒生指数 HSI | akshare(新浪) | 2013-08-20 | 恒生 1964 基日 | 否（真实指数历史）；恒生科技(2014-12 官方回溯)源不可得→HSI 替代 |
| 7 | HK_DIVIDEND | 513690.SH | 恒生中国企业指数 HSCEI | akshare(新浪) | 2013-08-20 | 1994-08-08 | 否 |
| 8 | US_BROAD | 513500.SH | **真实 ETF 513500.SH 研究复权 TR**（含 USD/CNY） | QMT 现有 data/qmt/raw | 2014-01-15 | ETF 2014 上市 | 否（真实）；2015 全覆盖 |
| 9 | GOLD | 518880.SH | **真实 ETF 518880.SH 研究复权 TR** | QMT 现有 data/qmt/raw | 2013-07-29 | ETF 2013 上市 | 否（真实）；2015 全覆盖 |
| 10 | CN_DURATION | 511260.SH | 中国 10Y 国债到期收益率 → 久期 proxy | akshare bond_zh_us_rate | 2005-01-03 | 收益率曲线 2002 起 | 是（收益率→价格构造 proxy；methodology discontinuity） |
| 11 | CASH_LIKE | 511360.SH | 中国 2Y 国债到期收益率 → 短债 proxy | akshare bond_zh_us_rate | 2005-01-03 | 同上 | 是（构造 proxy；SHIBOR 2015-05 起作校准参考） |

### 2.1 关键映射决策与 basis risk

```text
(a) STAR（科创50）：科创50 指数 2019-12-31 基日，无 2015 官方历史 → limiting real proxy。
    2015-2019.12 以创业板指（399006，2010 起）作境内科技成长 scenario 替代；
    2020-01 起切换科创50 指数（收益序列经 pct_change 拼接，2019-12-31→2020-01-02 用科创50 首收益）。
    flag：替代期 high basis risk（创业板 vs 科创板经济暴露差异）；2020-01 后映射置信度高。
    L2 RUN 时报告 2020-01 后科创50 vs 创业板指收益相关性作为校准诊断。
(b) HK_TECH：恒生科技指数官方回溯至 2014-12，但当前可及数据源（新浪 2020-08 起；东财接口网络不可达）
    无法提供 2015 起历史 → 以恒生指数 HSI（2013-08 起）作港股 equity beta 场景 proxy。
    flag：HSI 为综合指数，非科技专属；basis risk medium（港股 beta 近似）。
    若评审要求恒生科技，需另行数据获取（恒生官网/授权源）。
(c) CN_DIVIDEND：中证红利 000922 在 QMT 无代码、新浪数据中断于 2019-01 → 用上证红利 000015（红利风格 proxy）。
    flag：上证红利 vs 中证红利成分差异；basis risk low-medium。
(d) CN_DURATION / CASH_LIKE：国债到期收益率（10Y/2Y）为日度序列，构造 proxy 价格：
    P_t = P_{t-1} × exp(-D_eff × Δy_t)，D_eff（CN_DURATION ≈ 7.5y；CASH_LIKE ≈ 1.8y 短久期近似）
    + 每日累计年化收益率 y/252（carry）。这是构造 proxy（methodology discontinuity 已 flag）。
    CASH_LIKE 另以 SHIBOR O/N（2015-05 起）作敏感性/校准。
(e) US_BROAD/GOLD 直接用真实 ETF 研究复权（现有 data/qmt/raw，含官方分红/公司行为处理）→ 2015 起
    无 proxy 需求，映射置信度最高。
```

### 2.2 验证证据（2026-08-09 probe）

```text
QMT(xtdata, 127.0.0.1:58610): 沪深300/中证1000/中证500/上证红利 均 2005-01-04 起 5245 行；
  创业板指 2010-06-01 起 3931 行；科创50/科创100 2019-12-31 起 1600 行。
  港股(HSI.HK/HSTECH.HK)/美股(SPX.N)/期货(AU0.SHF/T0.CCF)/债券指数(H11077/H11025.CSI) 代码均 EMPTY。
新浪(akshare stock_hk_index_daily_sina): HSI/HSCEI 2013-08-20 起 3190 行；HSTECH 仅 2020-08 起。
akshare: 中国国债收益率 bond_zh_us_rate 2005-01-03 起 5758 行（含中国 2Y/5Y/10Y/30Y）；
  SHIBOR macro_china_shibor_all 2015-05-08 起 2341 行；东财(eastmoney)接口全部网络不可达。
现有 data/qmt/raw: US_BROAD_513500 2014-01-15 起、GOLD_518880 2013-07-29 起（研究复权 TR）。
hkd_cny_boc.csv: 2013-01-04 起 3865 行（港股 FX）。
```

# 3. 冻结窗口与数据

```text
数据起点（每槽位）：见 §2 表。最晚数据起点 = US_BROAD 2014-01-15（真实 ETF）。
warm-up：最长 lookback 252 交易日（Momentum）。
决策起点（reset_at） = 最晚数据起点后第 252 个交易日 = 2015-01-27
首执行日            = 2015-01-28
末决策日            = 2026-08-06
末执行日            = 2026-08-07（数据末日）
n_decision_days     = 2801
n_execution_dates   = 2801
label               = LONG_HORIZON_PROXY_SCENARIO_DIAGNOSTIC
2015 全年进入决策窗口（2015 牛熊覆盖）。≈11.3 年，远长于 L1 的 1011 日。
```

# 4. 同步 / 日历 / 收益构造 / FX / missing-day / no-lookahead

```text
日历：统一 SH 交易日历（QMT SH 2013-01-04..2026-08-07 3301 交易日）为主决策日历。
对齐：HK/US/金/债序列按日期 reindex 到 SH 日历 + ffill（最近前值）补休市日；缺失日 ffill；
     数据起点前的 NaN 保持 NaN（warm-up 检查全部 finite 后进入决策）。
收益：研究收益 = 各 proxy 序列 close-to-close 对数/简单 pct_change（T→T+1，决策于 T 收盘）。
     真实 ETF（513500/518880）用现有研究复权 TR。
     equity 指数（300/1000/红利/创业板/科创50/HSI/HSCEI）= price-return（未含分红；
     flag：TR 处理为 known limitation，L2 RUN 敏感性中可选加分红估算）。
     国债收益率 → 久期价格 proxy + carry（§2.1d）。
FX：HKD→CNY 用现有 hkd_cny_boc（中行折算价，2013-01-04 起，日频，ffill）。
    USD→CNY 已含于真实 513500（人民币 QDII 份额）。
no-lookahead：决策日 T 仅用 ≤T 数据（rolling cov/vol/momentum、收益率、FX 均 ≤T）；
     执行于 T+1 开盘（research-return 语义下为 T+1 收益）。不跨段重置。
```

# 5. 成本处理（评审 guard #6）

```text
proxy/index 数据不是可直接执行 ETF，pretend 可执行成本不可防御。
L2 主表 = research-return 对比（无成本），全部 11 槽位统一 research 收益语义。
另设单独成本敏感性：对 2015+ 可执行的权重变化应用 1x MainlandETFCostModel 近似
  （基于 proxy 组合换手 × 比例成本），仅作描述性敏感性，不冒充可执行净收益。
主表与敏感性分开标注。HS300_ref 恒为无成本研究参考（guard #7 同样适用）。
```

# 6. 6 方法（canonical 参数冻结自 L1，不得事后增删/tuning）

| # | 方法 | 实现 | 参数 |
|---|---|---|---|
| 1 | HS300 参考 | CN_LARGE proxy 研究收益（同执行日） | — |
| 2 | EqualWeight | `equal_weight_policy` | — |
| 3 | MaximumDiversification | `maximum_diversification_policy` | lookback 120, shrinkage 0.5 |
| 4 | MinimumVariance | `minimum_variance_policy` | lookback 120, shrinkage 0.5 |
| 5 | RiskParity_IVOL | `risk_parity_policy` | lookback 60 |
| 6 | Momentum_12_1 | `momentum_policy` | lookback 252, skip 21 |

# 7. 指标（评审 guard #9）

```text
每方法（research-return）：
  cum return / active-day ann / 日历 CAGR / annualized vol / Sharpe / Sortino / MaxDD / Calmar /
  worst calendar year / worst rolling 12m / mean turnover / cost-sensitivity（§5）/
  mean active assets / max single weight / mean HHI（集中度诊断）
评审 Interpretation 附加：
  平均/最大权重（按槽位）——验证是否依赖单一资产（尤其 GOLD / CN_DURATION / CASH_LIKE）；
  leave-one-slot-out 诊断（如实现简单）——每槽位剔除后指标变化，仅诊断不改策略。
```

# 8. 子期报告（pre-frozen regime，评审 guard #8）

```text
日历年度：必报（2015..2026 每年度 Sharpe/MaxDD）。
阶段（event-defined，pre-frozen——在见策略结果前冻结，非客观 regime 分类器）：
  2015-01-27..2015-06-12  2015 牛市
  2015-06-15..2016-01-29  2015 股灾
  2016-02-01..2017-12-29  修复期
  2018-01-02..2018-12-28  2018 熊市/贸易战
  2019-01-02..2020-02-21  反弹
  2020-02-24..2020-03-23  COVID 冲击
  2020-03-24..2021-02-19  COVID 反弹
  2021-02-22..2023-12-29  中国权益弱期
  2024-01-02..2026-08-07  近期强股期
每阶段报告 cum / Sharpe / MaxDD。阶段边界为近似、pre-frozen。
```

# 9. 测试 / Invariants（评审 guard #10）

```text
tests/test_long_horizon_proxy.py（新）：
  - 因果 lookback（rolling cov/vol/momentum 只用 ≤T；T→T+1）
  - 日期对齐（统一 SH 日历；无 future 数据；缺日 ffill 有记录）
  - proxy provenance 完整性（每槽位 source/start/end/is_backfilled 断言）
  - SCENARIO_NOT_STRICT_PIT_OOS 标注强制（runner 源码含该 label）
  - 6 方法集精确 + canonical 参数精确（复用 long_horizon_contract 或新 proxy contract）
  - 无 RL 引入（runner 源码无 RL 导入/字面量）
  - 窗口 parity fail-closed（derive 数据后断言 == 冻结窗口；失败 → stop）
scripts/gate4_long_horizon_proxy.py --check：契约验证通过后执行完整 L2。
failed invariant = stop condition（评审 guard #10），不得绕过。
```

# 10. 明确声明

```text
PPO/SAC/TD3 缺席所有代码路径与输出表。
无超参/lookback 优化；canonical 参数原样复用（L1 冻结）。
L2 执行未授权（本 packet 为 PREP）；L1 结果/artifact frozen，不改变。
数据源失败/重大缺口 → blocker/revision，不 improvise。
```

# 11. 执行计划（L2 RUN 授权后）

```text
1. fetch + 落盘：QMT 指数(300/1000/红利/创业板/科创50) 2005-2014 段、新浪 HSI/HSCEI、akshare 国债收益率/SHIBOR，
   写入 data/qmt/proxy/（含 source/fetch_date/raw-vs-adj 等 provenance 字段）。
2. 构建研究复权 proxy 面板（SH 日历对齐 + FX + 收益构造 + SCENARIO 标注）。
3. 复用 6 方法 + long_horizon 语义（单段连续，决策 T → 收益 T+1）。
4. tests + --check 通过 → 完整 L2 run → GATE_4_LONG_HORIZON_PROXY_RUN packet。
```

---

## Approval Record

```yaml
gate: 4
handoff_id: G4_LONG_HORIZON_PROXY_PREP_001
packet: GATE_4_LONG_HORIZON_PROXY_PREP
status: READY_FOR_REVIEW

frozen:
  label: LONG_HORIZON_PROXY_SCENARIO_DIAGNOSTIC
  window: {decision_start: 2015-01-27, first_execution: 2015-01-28, last_decision: 2026-08-06, last_execution: 2026-08-07, n_decision_days: 2801, n_execution_dates: 2801}
  proxies: 11 slots mapped (QMT-first; 2 real-ETF TR; HSI/HSCEI sina; 10Y/2Y treasury-yield constructed; STAR limiting with 2015-2019 ChiNext substitution)
  methods: [HS300_ref, EqualWeight, MaximumDiversification, MinimumVariance, RiskParity_IVOL, Momentum_12_1]
  params: canonical reused from L1 (120/0.5, 120/0.5, 60, 252/21)
  semantics: T->T+1 causal; research-return main table + 1x cost sensitivity (labeled); unified SH calendar; hkd_cny FX; SCENARIO_NOT_STRICT_PIT_OOS
  no_lookahead: true
  sub_periods: calendar-year + pre-frozen event-defined phases (2015 boom/crash, 2018 bear, COVID, 2021-2023 weak, 2024-2026 strong)

limiting_proxy: STAR 科创50 index (base 2019-12-31); 2015-2019 substituted by ChiNext 399006 (high basis risk, flagged); HK_TECH uses HSI (HSTECH 2014 source unavailable)

no_rl: PPO/SAC/TD3 absent from all code paths and output tables
not_done:
  l2_execution: false   # PREP only; wait for review
  rl_retraining: false
  hyperparameter_optimization: false
  qmt_live: false
```

## END OF GATE 4 LONG HORIZON PROXY PREP
