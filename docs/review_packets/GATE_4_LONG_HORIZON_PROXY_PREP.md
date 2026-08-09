# GATE 4 LONG HORIZON PROXY PREP — L2 场景 Proxy 长区间研究（冻结契约，修正版）

> 评审（`GATE_4_LONG_HORIZON_PROXY_PREP_REVIEWER_RESPONSE.md`）**PREP_REVISIONS_REQUIRED_L2_RUN_NOT_AUTHORIZED**。
> 本 packet 为 **PREP_FIX**（handoff `G4_LONG_HORIZON_PROXY_PREP_FIX_001`）：修正评审 4 项设计问题，其余已接受元素保持冻结。**不执行 L2 run**。

> ## Revision Record（PREP_FIX_001，评审 4 项修正）
>
> 1. **STAR 不再复用 CHINEXT**：2015-2019 改为**中证全指信息技术 000986**（新浪，2011-08-02 起，连续；2015-2019 与创业板指相关仅 **0.675**，非相同序列双计）。2020-01 起**不切换科创50**（避免拼接 discontinuity），全程统一 000986；L2 RUN 报告 000986 vs 科创50（2020 后）相关性作校准诊断。科创 50 2020-01 基日 → 2015 无官方历史，000986 为最贴近的信息技术/硬科技 scenario proxy。
> 2. **CASH_LIKE 真正现金化**：主 proxy = **SHIBOR O/N carry-only**（近零久期，2015-05-08 起）；2015-01-28..2015-05-07 用 **2Y 国债收益率 carry-only bridge**（近零久期，无价格 P&L）。2Y 久期价格版仅作 labeled sensitivity。
> 3. **统一 price-return 面板**：全部权益槽位（含 US_BROAD/GOLD 用 513500/518880 **price** 序列）统一 **price-return** research 收益；income-aware（TR）sensitivity 单列，不改变主面板 basis。
> 4. **因果时序 lag**：HK（HSI/HSCEI）+ US（513500 price）+ GOLD（518880 price）输入 **lag 1 天**（收盘晚于上海 15:00 决策时刻）；A股指数 + 利率用 T 收盘。决策 T 收盘 → 收益 T→T+1 close-to-close（无 T+1 open 执行主张）。窗口重推导：**decision_start 2015-01-28，n_decision=2800**（因 US_BROAD lag 后移 1 天，不保留 2801）。

---

# 0. 性质声明（全局）

```text
L2 = SCENARIO_NOT_STRICT_PIT_OOS
全部序列为 retrospective/backfilled scenario proxy（Track C），允许 pre-launch/backfilled
index 历史，必须明确标注，不得冒充真实工具/严格 point-in-time。不构成生产/实盘授权。
L1 真实工具结果（frozen）不改变。
```

# 1. 目标与标签

```text
验证确定性方法在多轮牛熊（2015 牛熊 / 2018 熊 / COVID / 2021-2023 弱股 / 2024-2026 强股）
长历史场景下是否保留结构性回撤/风险调整优势。
label = LONG_HORIZON_PROXY_SCENARIO_DIAGNOSTIC
主问题：MaxDiv 的 Sharpe 稳定性 / MaxDD 控制 / 是否过度牺牲 CAGR / 是否依赖单一资产
        / 权重集中度与 regime 依赖（评审 Interpretation target）。
```

# 2. 11 槽位 → Proxy 映射 + Provenance（全部实测验证）

> 数据源优先级：**miniQMT（QMT/xtdata）优先**；QMT 无则 akshare（新浪）；真实 ETF 覆盖 2015 时直接用真实。

| # | 槽位 | 真实 ETF | L2 Proxy | 数据源 | 数据起点 | 基日/发布 | 上市前 retrospective/backfilled |
|---|---|---|---|---|---|---|---|
| 1 | CN_LARGE | 510300.SH | 沪深300 000300.SH | QMT | 2005-01-04 | 基日 2004-12-31 | 否 |
| 2 | CN_SMALL | 512100.SH | 中证1000 000852.SH | QMT | 2005-01-04 | 基日 2004-12-31（发布 2014-10） | 是（2014-10 前回溯编制） |
| 3 | CN_DIVIDEND | 512890.SH | 上证红利 000015.SH | QMT | 2005-01-04 | 基日 2005-01-04 | 否 |
| 4 | CHINEXT | 159915.SZ | 创业板指 399006.SZ | QMT | 2010-06-01 | 基日 2010-06-01 | 否 |
| 5 | STAR | 588000.SH | **中证全指信息技术 000986**（全程统一） | akshare(新浪) | 2011-08-02 | 基日 2011-08-02 | 否（指数历史）；科创 50 2020-01 基日 → 000986 为信息技术/硬科技 scenario proxy |
| 6 | HK_TECH | 513180.SH | 恒生指数 HSI | akshare(新浪) | 2013-08-20 | 恒生 1964 | 否；恒生科技(2014-12 官方回溯)源不可得 → HSI 替代 |
| 7 | HK_DIVIDEND | 513690.SH | 恒生中国企业 HSCEI | akshare(新浪) | 2013-08-20 | 1994-08-08 | 否 |
| 8 | US_BROAD | 513500.SH | **真实 513500.SH price**（price-return） | QMT 现有 data/qmt/raw | 2014-01-15 | ETF 2014 上市 | 否（真实）；2015 全覆盖 |
| 9 | GOLD | 518880.SH | **真实 518880.SH price**（price-return；无分红≈TR） | QMT 现有 data/qmt/raw | 2013-07-29 | ETF 2013 上市 | 否（真实）；2015 全覆盖 |
| 10 | CN_DURATION | 511260.SH | 中国 10Y 国债到期收益率 → 久期价格 proxy | akshare bond_zh_us_rate | 2005-01-03 | 收益率曲线 2002 起 | 是（构造 proxy） |
| 11 | CASH_LIKE | 511360.SH | **SHIBOR O/N carry-only**（2015-05-08 起）+ **2Y 收益率 carry-only bridge**（2015-01-28..2015-05-07） | akshare macro_china_shibor_all / bond_zh_us_rate | bridge 2005-01-03 | 收益率/利率 | 是（构造 proxy；近零久期 cash-like） |

### 2.1 关键映射决策与 basis risk（修正）

```text
(a) STAR：评审修正 #1。2015-2019 不得复用创业板指 399006（会双计同一成长收益流）。
    改用中证全指信息技术 000986（2011-08 起连续）：
      - distinct 序列：不同编制/成分（全指信息技术含主板+创业板+科创板科技股）
      - 实证相关：000986 vs 399006 在 2015-2019 相关 = 0.675（中证信息技术 000993 相关 0.967 被否；
        军工 0.828、创业板50 0.989 均更高/起点更晚）
      - 全程统一 000986（2020-01 起不切换科创50，避免拼接收益 discontinuity）
      - L2 RUN 校准诊断：000986 vs 科创50（2020-01 后）相关性
      - flag：科创 50 2020-01 基日，2015-2019 无官方历史 → 000986 为信息技术/硬科技 scenario
        替代（medium basis risk，已在 freeze 前声明）
(b) CASH_LIKE：评审修正 #2。主 proxy = SHIBOR O/N carry-only（近零久期，货币市场）。
      carry 公式冻结：r_t = (rate_t/100) × Δt_days/365。
      2015-01-28..2015-05-07（SHIBOR 起始前）用 2Y 国债收益率 carry-only bridge（近零久期，
      无价格 P&L；r_t = (y2y_t/100) × Δt_days/365）。
      2Y 久期价格版仅作 labeled sensitivity，非主 CASH_LIKE 序列。
(c) HK_TECH：恒生科技官方回溯 2014-12 但可及源（新浪 2020-08；东财接口网络不可达）无 2015 历史
      → HSI（2013-08 起）作港股 equity beta scenario proxy。basis risk medium。
(d) CN_DIVIDEND：中证红利 000922 QMT 无代码、新浪中断于 2019-01 → 上证红利 000015。basis low-medium。
(e) CN_DURATION：10Y 收益率 → 久期价格 proxy，公式冻结并测试：
      P_t = P_{t-1} × exp(-D_eff × Δy_t) + carry，D_eff = 7.5（冻结）。
(f) US_BROAD/GOLD：直接真实 ETF **price**（非 TR），统一 price-return 面板（评审修正 #3）。
```

### 2.2 验证证据（2026-08-09 probe）

```text
QMT(xtdata 127.0.0.1:58610): 沪深300/中证1000/中证500/上证红利 2005-01-04 起 5245 行；
  创业板指 2010-06-01 起；科创50/科创100 2019-12-31 起。港股/美股/期货/债券指数代码 QMT 均 EMPTY。
新浪: 中证全指信息技术 000986 2011-08-02 起 3647 行（连续至 2026-08-07）；HSI/HSCEI 2013-08-20 起。
akshare: 中国国债收益率 bond_zh_us_rate 2005-01-03 起（含 2Y/5Y/10Y/30Y）；SHIBOR
  macro_china_shibor_all 2015-05-08 起（O/N-利率列）。东财接口全部网络不可达。
现有 data/qmt/raw: US_BROAD_513500 price 2014-01-15 起 3053 行；GOLD_518880 price 2013-07-29 起 3168 行。
hkd_cny_boc.csv: 2013-01-04 起 3865 行。
```

# 3. 冻结窗口与数据（重推导，评审修正 #4）

```text
统一 SH 交易日历（QMT SH 2013-01-04..2026-08-07，3301 交易日）为主决策日历。

各槽位决策可用首日（A股+利率用 T 收盘；HK/US/GOLD 用 T-1 lag）：
  A股（300/1000/红利/创业板/信息技术）+ 利率（10Y/2Y/SHIBOR）：T 收盘可用
  HK（HSI/HSCEI）：T-1 close（16:00 收盘晚于上海 15:00）
  US_BROAD（513500 price）：T-1（QDII 价格反映前夜美股）
  GOLD（518880 price）：T-1（金价）
  → 全输入有限首决策日 T* = 2014-01-16（limiting = US_BROAD 2014-01-15 + lag1）

warm-up：最长 lookback 252 交易日（Momentum）。
decision_start（reset_at） = T* 后第 252 个交易日 = 2015-01-28
首收益区间 T→T+1            = 2015-01-28 → 2015-01-29
末决策日                    = 2026-08-06
末收益区间                  = 2026-08-06 → 2026-08-07
n_decision_days             = 2800
label                       = LONG_HORIZON_PROXY_SCENARIO_DIAGNOSTIC
2015 全年进入决策窗口（2015 牛熊覆盖）。≈11.5 年。
```

# 4. 同步 / 收益构造 / FX / missing-day / no-lookahead（评审修正 #4 因果约定）

```text
因果约定（单一明确时间线，runner/tests 强制）：
  决策时刻 = T 日上海收盘（15:00）。
  A股指数（300/1000/红利/创业板/信息技术）用 T 收盘（15:00 已知）。
  利率（10Y/2Y 收益率、SHIBOR）用 T 收盘（收益率曲线 T 日发布）。
  HK 指数（HSI/HSCEI）用 T-1 收盘（16:00 收盘晚于上海，同日不可用）。
  US_BROAD（513500 price）用 T-1（QDII 价格反映前夜美股，T 收盘后才知）。
  GOLD（518880 price）用 T-1（金价）。
  权重于 T 收盘决策 → 收益 = T→T+1 close-to-close（research-return；无 T+1 open 执行主张）。
对齐：各序列按 SH 日历 reindex + ffill（休市日补前值）；起点前保持 NaN。
收益：权益 price-return（pct_change）；CASH_LIKE/CN_DURATION 用冻结 carry/久期公式。
FX：HKD→CNY 用现有 hkd_cny_boc（2013-01-04 起，日频 ffill）；USD→CNY 已含于 513500（人民币 QDII）。
no-lookahead：决策 T 仅用 ≤T 可用输入（A股 T / 非A股 T-1）；rolling cov/vol/momentum 只用这些；
  不跨段重置。
```

# 5. 成本处理（评审 guard #6）

```text
proxy/index 数据非可执行 ETF → L2 主表 = research-return 无成本对比（全部槽位统一）。
另设单独成本敏感性：对 2015+ 可执行权重变化应用 1x MainlandETFCostModel 近似，仅描述性，
不冒充可执行净收益。主表与敏感性分开标注。HS300_ref 恒为无成本研究参考。
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

# 7. 指标（评审 guard #9 + Interpretation）

```text
每方法（research-return）：
  cum / active-day ann / 日历 CAGR / annualized vol / Sharpe / Sortino / MaxDD / Calmar /
  worst calendar year / worst rolling 12m / mean turnover / cost-sensitivity（§5）/
  mean active assets / max single weight / mean HHI
评审 Interpretation 附加：
  平均/最大权重（按槽位）——检测是否依赖单一资产（尤其 CASH_LIKE / GOLD / CN_DURATION）；
  leave-one-slot-out 诊断（如实现简单）——每槽位剔除后指标变化，仅诊断不改策略。
```

# 8. 子期报告（pre-frozen regime，评审 guard #8）

```text
日历年度：必报（2015..2026 每年度 Sharpe/MaxDD）。
阶段（event-defined，pre-frozen——见结果前冻结，非客观 regime 分类器）：
  2015-01-28..2015-06-12  2015 牛市
  2015-06-15..2016-01-29  2015 股灾
  2016-02-01..2017-12-29  修复期
  2018-01-02..2018-12-28  2018 熊市/贸易战
  2019-01-02..2020-02-21  反弹
  2020-02-24..2020-03-23  COVID 冲击
  2020-03-24..2021-02-19  COVID 反弹
  2021-02-22..2023-12-29  中国权益弱期
  2024-01-02..2026-08-07  近期强股期
每阶段报告 cum / Sharpe / MaxDD。边界为近似、pre-frozen。
```

# 9. 测试 / Invariants（评审 guard #10 + 修正 #4）

```text
tests/test_long_horizon_proxy.py（新）：
  - 因果 lookback + 时序对齐：A股 T / 非A股 T-1 断言（HK/US/GOLD 输入 lag 1）；
    rolling cov/vol/momentum 只用 ≤ 决策可用输入
  - 日期对齐（统一 SH 日历；缺日 ffill 有记录；无 future 数据）
  - proxy provenance 完整性（每槽位 source/start/end/is_backfilled 断言）
  - SCENARIO_NOT_STRICT_PIT_OOS 标注强制（runner 源码含该 label）
  - STAR 与 CHINEXT 序列 distinct 断言（2015-2019 不共享同一收益序列）
  - CASH_LIKE 近零久期断言（主序列为 carry-only，无价格 P&L 项）
  - 6 方法集精确 + canonical 参数精确（复用 long_horizon_contract）
  - 无 RL 引入（runner 源码无 RL 导入/字面量）
  - 窗口 parity fail-closed（derive 后断言 == 冻结窗口 2800；失败 → stop）
scripts/gate4_long_horizon_proxy.py --check：契约验证通过后执行完整 L2。
failed invariant = stop condition（评审 guard #10），不得绕过。
```

# 10. 明确声明

```text
PPO/SAC/TD3 缺席所有代码路径与输出表。
无超参/lookback 优化；canonical 参数原样复用（L1 冻结）。
L2 执行未授权（本 packet 为 PREP_FIX）；L1 结果/artifact frozen，不改变。
数据源失败/重大缺口 → blocker/revision，不 improvise。
```

# 11. 执行计划（L2 RUN 授权后）

```text
1. fetch + 落盘：QMT 指数(300/1000/红利/创业板)、新浪(000986/HSI/HSCEI)、akshare(国债收益率/SHIBOR)，
   写入 data/qmt/proxy/（含 source/fetch_date/raw-vs-adj/provenance 字段）。
2. 构建 price-return 研究面板（SH 日历对齐 + 非A股 lag1 + FX + 冻结 carry/久期公式 + SCENARIO 标注）。
3. 复用 6 方法 + long_horizon 语义（单段连续，决策 T → 收益 T+1）。
4. tests + --check 通过 → 完整 L2 run → GATE_4_LONG_HORIZON_PROXY_RUN packet。
```

---

## Approval Record

```yaml
gate: 4
handoff_id: G4_LONG_HORIZON_PROXY_PREP_FIX_001
packet: GATE_4_LONG_HORIZON_PROXY_PREP
status: READY_FOR_REVIEW

fixes_applied:
  #1 STAR distinct proxy: 中证全指信息技术 000986 (2011-08-02, corr 0.675 vs ChiNext 2015-2019), NOT ChiNext; no 2020 switch (no splice)
  #2 CASH_LIKE cash-like: SHIBOR O/N carry-only (near-zero duration) + 2Y carry-only bridge before 2015-05-08; 2Y-duration version only labeled sensitivity
  #3 uniform price-return panel (all equity incl. US_BROAD/GOLD price); income-aware TR sensitivity separate
  #4 causal timing: A-share+rates T close, HK/US/GOLD T-1 lag; decision T close -> T->T+1 close-to-close; re-derived window

frozen:
  label: LONG_HORIZON_PROXY_SCENARIO_DIAGNOSTIC
  window: {decision_start: 2015-01-28, last_decision: 2026-08-06, last_execution: 2026-08-07, n_decision_days: 2800}
  proxies: 11 slots mapped (QMT-first; 000986/HSI/HSCEI sina; SHIBOR+2Y-bridge CASH_LIKE; 10Y-duration CN_DURATION; real price 513500/518880)
  methods: [HS300_ref, EqualWeight, MaximumDiversification, MinimumVariance, RiskParity_IVOL, Momentum_12_1]
  params: canonical reused from L1 (120/0.5, 120/0.5, 60, 252/21)
  semantics: T->T+1 causal; research-return main table + 1x cost sensitivity; unified SH calendar; non-A-share lag 1; SCENARIO_NOT_STRICT_PIT_OOS
  no_lookahead: true
  sub_periods: calendar-year + pre-frozen event-defined phases (2015 boom/crash, 2018 bear, COVID, 2021-2023 weak, 2024-2026 strong)

no_rl: PPO/SAC/TD3 absent from all code paths and output tables
not_done:
  l2_execution: false   # PREP_FIX only; wait for review
  rl_retraining: false
  hyperparameter_optimization: false
  qmt_live: false
```

## END OF GATE 4 LONG HORIZON PROXY PREP (PREP_FIX_001)
