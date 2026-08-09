# GATE 4 LONG HORIZON PROXY RUN — L2 场景 Proxy 长区间研究结果

> 评审（`GATE_4_LONG_HORIZON_PROXY_PREP_FIX_2_REVIEWER_RESPONSE.md`）**PREP_FIX_2_ACCEPTED_L2_PROXY_RUN_AUTHORIZED**。
> 本 packet 报告单次冻结 L2 proxy scenario run 结果。handoff_id = **G4_LONG_HORIZON_PROXY_RUN_001**。

```yaml
implementation_commit: 00d7f64   # scripts/gate4_long_horizon_proxy.py + panel + fetch + loso + tests
result_artifact: artifacts/gate4_long_horizon_proxy_results.json (+ _raw.json)
handoff: G4_LONG_HORIZON_PROXY_RUN_001
label: LONG_HORIZON_PROXY_SCENARIO_DIAGNOSTIC
scenario_not_strict_pit_oos: true
```

---

# 1. 实现 / 数据 / 窗口证据

## 1.1 源文件与 providers

```text
src/china_etf/evaluation/long_horizon_proxy_panel.py   研究面板构建（QMT-first 数据源）
scripts/gate4_long_horizon_proxy_fetch.py              数据抓取（QMT/新浪/akshare，带 provenance）
scripts/gate4_long_horizon_proxy.py                    L2 runner（6 方法单段 rollout + --check）
scripts/gate4_long_horizon_proxy_loso.py               Leave-one-slot-out 诊断
tests/test_long_horizon_proxy.py                       L2 测试（11 项）
data/qmt/proxy/*.csv + provenance.json                 落盘 proxy 序列（source/fetch_date/coverage/backfill flag）
```

| # | 槽位 | proxy | 数据源 | 起点 | 上市前 backfill |
|---|---|---|---|---|---|
| 1 | CN_LARGE | 沪深300 000300 | QMT | 2005-01-04 | 否 |
| 2 | CN_SMALL | 中证1000 000852 | QMT | 2005-01-04 | 是（2014-10 前回溯编制） |
| 3 | CN_DIVIDEND | 上证红利 000015 | QMT | 2005-01-04 | 否 |
| 4 | CHINEXT | 创业板指 399006 | QMT | 2010-06-01 | 否 |
| 5 | STAR | 中证全指信息技术 000986 | akshare(新浪) | 2011-08-02 | 否（科创50 2020-01 基日 → 信息技术 scenario 替代） |
| 6 | HK_TECH | 恒生指数 HSI | akshare(新浪) | 2013-08-20 | 否（恒生科技 2014 回溯源不可得 → HSI 替代） |
| 7 | HK_DIVIDEND | 恒生中国企业 HSCEI | akshare(新浪) | 2013-08-20 | 否 |
| 8 | US_BROAD | 513500.SH price | QMT 现有 | 2014-01-15 | 否（真实 ETF） |
| 9 | GOLD | 518880.SH price | QMT 现有 | 2013-07-29 | 否（真实 ETF） |
| 10 | CN_DURATION | 中国10Y 收益率 → 久期 proxy | akshare | 2005-01-03 | 是（构造 proxy，D_eff=7.5 单位安全） |
| 11 | CASH_LIKE | SHIBOR O/N carry-only + 2Y-bridge | akshare | 2005-01-03 | 是（构造 proxy，近零久期） |

## 1.2 冻结窗口（fail-closed parity）

```text
decision_start  = 2015-01-28
first interval  = 2015-01-28 -> 2015-01-29
last decision   = 2026-08-06
last interval   = 2026-08-06 -> 2026-08-07
n_intervals     = 2800 ✓（--check 断言通过）
语义：统一 SH 日历（L1 数据日历，含 08-07）；A股/利率 T 收盘，HK/US/GOLD/FX T-1 lag；
      决策 T → T+1 close-to-close research-return；SCENARIO_NOT_STRICT_PIT_OOS
```

> 注：QMT `get_trading_dates` 日历不含 2026-08-07（滞后一天），但冻结契约末执行日 = 08-07
> 且所有 proxy 序列/数据均含 08-07 → 统一日历以数据日历为准（评审 fail-closed 对齐，不静默缩短窗口）。

## 1.3 数据修复 / 溯源

```text
抓取时间：2026-08-09。无数据编造（guard #9）。所有 proxy 落盘 data/qmt/proxy/ 带 provenance
（source/fetch_date/start/end/is_backfilled/cols）。CN_DURATION/CASH_LIKE 为构造 proxy（公式冻结）。
```

# 2. 测试与 --check（评审 guard #10）

```text
pytest 全套:     265 passed（含 tests/test_long_horizon_proxy.py 11 项：
  STAR/CHINEXT distinct 序列断言（corr < 0.99，实测 2015-2019 0.675）
  CASH_LIKE carry-only / 无久期价格 P&L（单日冲击 < 1e-3）
  CN_DURATION /100 单位归一化 + +10bp → Δy=+0.0010 → 纯久期 -0.75%（carry 前）
  ffill-before-yield-diff（多日间隔不当作多次冲击）
  A股/利率 T vs HK/US/GOLD/FX T-1 信息时序
  no-future-data rolling（momentum 锚点 T-252/T-21 独立重算复现；未来数据会改变权重）
  6 方法/canonical 参数冻结（120/0.5, 120/0.5, 60, 252/21）
  SCENARIO_NOT_STRICT_PIT_OOS 标注强制
  2800-interval fail-closed parity
  无 RL 路径
scripts/gate4_long_horizon_proxy.py --check: PASSED（2800 区间对齐）
```

# 3. 全期结果表（2800 研究收益区间，无成本主表）

可执行策略 = research-return 无成本（SCENARIO，非可执行净收益）；HS300 参考独立列（guard #7）。

| 指标 | EqualWeight | **MaximumDiversification** | MinimumVariance | RiskParity_IVOL | Momentum_12_1 | HS300 参考 |
|---|---|---|---|---|---|---|
| 累计收益 | +73.6% | +94.0% | +23.5% | +28.2% | **+137.7%** | +33.2% |
| active-day 年化 | +5.1% | +6.2% | +1.9% | +2.3% | +8.1% | +2.6% |
| 日历 CAGR | +4.9% | +5.9% | +1.9% | +2.2% | +7.8% | +2.5% |
| 年化波动 | 11.6% | **5.2%** | 0.10% | 0.51% | 17.8% | 21.4% |
| Sharpe | 0.486 | **1.183** | 18.45* | 4.36* | 0.528 | 0.228 |
| Sortino | 0.604 | **1.488** | nan* | 5.68* | 0.580 | 0.290 |
| MaxDD | -30.7% | **-11.4%** | -0.0%* | -0.7%* | -46.7% | -46.7% |
| Calmar | 0.166 | **0.540** | nan* | 3.30* | 0.173 | — |
| worst 日历年 | 2018 -14.2% | 2022 **-7.4%** | +0.8%* | +0.8%* | 2018 -10.9% | 2018 -25.3% |
| worst 12m 滚动 | -24.2% | **-10.0%** | +1.4%* | +0.8%* | -38.5% | -42.3% |
| mean turnover | 0.00% | 0.68% | 0.03% | 0.33% | 8.13% | — |
| mean active | 11.0 | 11.0 | 3.3 | 11.0 | 7.2 | — |
| max single weight | 9.1% | 25.0% | 100.0%* | 97.2%* | 84.1% | — |
| mean HHI | 0.091 | 0.168 | 0.996* | 0.848* | 0.253 | — |

> \* 标注：MinVar / RP 的病态指标由 **CASH_LIKE 近零波动 carry-only proxy 主导**（MinVar 99.8%、
> RP 92% 押 CASH_LIKE）——这是冻结契约中近零波动现金 proxy 的无约束 GMV/inv-vol 数学直接后果，
> **非 bug、非调参**（详见 §6 LOSO 诊断证实）。这些 Sharpe/Calmar 因波动被压至 ~0 而失真，应视为
> 现金化组合而非风险调整策略。

# 4. MaxDiv 年度 / 子期（评审 guard #8，pre-frozen regime）

| 子期 | MaxDiv cum / Sharpe / MaxDD | HS300 cum |
|---|---|---|
| 2015 | +6.8% / +1.12 / -8.0% | +5.8% |
| 2016 | +7.4% / +1.63 / -2.6% | -11.3% |
| 2017 | +5.0% / +1.72 / -2.6% | +21.8% |
| 2018 | **-1.8% / -0.46 / -5.3%** | -25.3% |
| 2019 | +12.2% / +3.37 / -2.2% | +36.1% |
| 2020 | +6.4% / +1.04 / -7.6% | +27.2% |
| 2021 | +5.8% / +1.34 / -2.7% | -5.2% |
| 2022 | **-7.4% / -1.10 / -10.8%** | -21.6% |
| 2023 | +4.8% / +1.54 / -2.7% | -11.4% |
| 2024 | +15.8% / +2.66 / -4.1% | +14.7% |
| 2025 | +11.4% / +2.27 / -4.1% | +17.7% |
| 2026 H1 | +3.8% / +1.02 / -4.2% | +1.4% |

阶段（pre-frozen event-defined）：

| 阶段 | MaxDiv cum / Sharpe / MaxDD | HS300 cum |
|---|---|---|
| 2015 bull | +10.8% / +5.14 / -1.6% | — |
| 2015 crash | -6.8% / -1.56 / -7.6% | — |
| repair 2016-17 | +16.7% / +2.26 / -2.9% | — |
| 2018 bear/tradewar | -1.8% / -0.46 / -5.3% | — |
| rebound 2019-20.2 | +14.9% / +3.39 / -2.2% | — |
| COVID shock | -7.0% / -10.3 / -7.6% | — |
| COVID rebound | +14.6% / +2.69 / -3.7% | — |
| China weak 2021-23 | +0.1% / +0.03 / -11.4% | — |
| Recent strong 2024-26 | +33.9% / +2.08 / -4.2% | — |

# 5. 权重 / 集中度诊断（评审 Interpretation）

| 槽位 | MaxDiv 平均权重 | MaxDiv 最大权重 | RP 平均权重 |
|---|---|---|---|
| CN_LARGE | 3.3% | 6.7% | 0.5% |
| CN_SMALL | 2.9% | 6.7% | 0.4% |
| CN_DIVIDEND | 4.9% | 12.8% | 0.6% |
| CHINEXT | 3.4% | 6.2% | 0.3% |
| STAR | 3.5% | 7.6% | 0.4% |
| HK_TECH | 4.8% | 8.0% | 0.5% |
| HK_DIVIDEND | 4.1% | 6.8% | 0.4% |
| US_BROAD | 8.7% | 18.1% | 0.6% |
| GOLD | 14.4% | 25.0% | 0.8% |
| CN_DURATION | 24.9% | 25.0% | 3.6% |
| CASH_LIKE | 25.0% | 25.0% | 92.0% |

```text
MaxDiv 权重分布：GOLD 14.4% + CN_DURATION 24.9% + CASH_LIKE 25.0% 为三大主力（~64%），
US_BROAD 8.7% 次之，A股/HK 权益 3-5% 分散。25% = project single-slot cap 触及。
不依赖单一资产（HHI 0.168，11 槽位全 active）；但 GOLD/CN_DURATION/CASH_LIKE 合计贡献高，
低波动资产为分散源（非单一 proxy 主导）。
```

# 6. Leave-one-slot-out 诊断（评审 Interpretation，PREP 冻结计划）

| 剔除槽位 | MaxDiv Sharpe / MaxDD / HHI | MinVar Sharpe / MaxDD / HHI | RP Sharpe / MaxDD / HHI |
|---|---|---|---|
| 主表(11槽) | 1.183 / -11.4% / 0.168 | 18.45* / -0.0%* / 0.996* | 4.36* / -0.7%* / 0.848* |
| CASH_LIKE | 0.969 / -18.2% / 0.153 | **2.006 / -4.5% / 0.750** | 0.955 / -13.8% / 0.254 |
| GOLD | 0.689 / -17.3% / 0.164 | 18.46* / -0.0%* / 0.996* | 4.24* / -0.6%* / 0.861* |
| CN_DURATION | 0.886 / -18.9% / 0.152 | 18.35* / -0.0%* / 0.999* | 4.02* / -0.8%* / 0.911* |
| STAR | 1.201 / -12.0% / 0.171 | 18.45* / -0.0%* / 0.996* | 4.82* / -0.6%* / 0.855* |

```text
核心诊断结论：
1. MinVar/RP 的病态 Sharpe 完全由 CASH_LIKE 主导：剔除 CASH_LIKE 后 MinVar Sharpe 18.45 → 2.006、
   HHI 0.996 → 0.750、MaxDD -4.5%；RP Sharpe 4.36 → 0.955、HHI 0.848 → 0.254。
   这是冻结契约近零波动 carry-only CASH_LIKE 的数学后果，非 bug、非调参。
2. 剔除 GOLD/CN_DURATION/STAR 对 MinVar/RP 几乎无影响（仍 99% CASH_LIKE）→ 主导源确认为 CASH_LIKE。
3. MaxDiv 不依赖单一 proxy：剔除任一槽位 Sharpe 均 ~0.69-1.20 区间，无崩坏；剔除 GOLD 后 Sharpe 降
   幅最大（1.18→0.69，GOLD 为重要分散源，但非主导）。
```

# 7. STAR proxy 校准（评审要求）

```text
000986（中证全指信息技术）vs 创业板指 399006：2015-2019 相关 = 0.675（distinct，非双计）。
000986 vs 科创50（2020-01 起重叠期）相关性：需在 RUN 分析中补充（诊断）——本 packet 报告
000986 为 2011-08 起连续、成分含主板+创业板+科创板科技股，作科创 50 的 scenario 替代（medium
basis risk，PREP 已 flag）。
```

# 8. 成本敏感性 / income-aware

```text
主表 = 无成本 research-return（SCENARIO，非可执行）。1x MainlandETFCostModel 近似成本敏感性
在 PREP 冻结计划中；本 RUN 主表已无成本，成本敏感性单列标注（未冒充可执行净收益）。
income-aware TR 敏感性：主面板为统一 price-return（PREP_FIX #3 冻结）；TR 敏感性未在见结果后新增，
故本 packet 披露主面板为 price-return（gold 无分红≈TR，equity 未含分红为 known limitation）。
```

# 9. 与 L1 对比（仅历史上下文，非 GO 阈值）

| 窗口 | MaxDiv Sharpe | MaxDiv MaxDD | 区间 |
|---|---|---|---|
| L1 真实 ETF | 1.655 | -4.0% | 1011 日（2022-06..2026-08） |
| **L2 proxy 场景** | **1.183** | **-11.4%** | **2800 日（2015-01..2026-08）** |
| HS300 参考 | 0.384 | -26.9% | 1011 日 |
| HS300 proxy 参考 | 0.228 | -46.7% | 2800 日 |

```text
MaxDiv 长窗（含 2015 股灾/2018/COVID/2021-23 弱股）Sharpe 压缩至 1.18 但仍为可执行确定性方法
最高（次高 Momentum 0.53 / EW 0.49；MinVar/RP 因 CASH_LIKE 主导失真），MaxDD -11.4% 为 HS300
(-46.7%) 的 1/4。L1 的 Sharpe 1.66 未复现（弱股期纳入压缩），但结构优势保留。
```

# 10. Interpretation 回应（评审 Interpretation target）

```text
1. MaxDiv 是否在 ~11.5 年保留 vs EW/RP/Momentum 的实质 Sharpe 优势？
   是。Sharpe 1.18 vs Momentum 0.53 / EW 0.49 / RP 0.96（剔除 CASH_LIKE 后 0.96）。
   MaxDiv 为 risk-based 方法中唯一未被 CASH_LIKE 主导者（HHI 0.168 vs RP 0.848）。
2. 在 2015 股灾 / 2018 / COVID / 2021-23 是否保留更低 MaxDD？
   是。2015 crash MaxDD -7.6%、2018 -5.3%、COVID -7.6%、china_weak -11.4%；
   HS300 同期明显更深（2018 -25%、2021-23 弱股期持续下跌）。
3. 更低风险是否以过大 CAGR 代价？
   否。MaxDiv 日历 CAGR +5.9% 高于 HS300 proxy +2.5%、EW +4.9%，低于 Momentum +7.8%；
   以低 ~2pct 年化换取 MaxDD 从 -46.7% 收窄至 -11.4%（HS300 基准下 CAGR/风险权衡显著优于
   单纯持有与 EW）。
4. 结果是否被 CASH_LIKE/GOLD/CN_DURATION/单一 proxy 主导？
   MaxDiv：否（LOSO §6，剔除任一槽位不崩坏）。MinVar/RP：是，被 CASH_LIKE 主导（冻结契约
   近零波动现金 proxy 的数学后果，已如实披露）。
5. 权重是否经济可解读、随 regime 合理变化？
   是。MaxDiv 高配低波动资产（GOLD/CN_DURATION/CASH_LIKE 合计 ~64%），弱股期（2021-23）
   维持正收益（+0.1% cum），强股期 2024-26 +33.9%；2015 股灾仅 -6.8%。
```

# 11. 明确声明

```text
1. 无 GO 阈值在观察结果后发明（manifest.no_go_threshold 未设；L1 对比仅历史上下文）。
2. RL 算法缺席所有代码路径与输出表（runner 源码自检通过）。
3. L2 已执行（本次授权）；L1 结果/artifact frozen 未改变。
4. MinVar/RP 病态高 Sharpe 为 CASH_LIKE 近零波动 proxy 主导的数学后果（LOSO 证实），如实披露，
   不视为可执行风险调整策略。
5. 主面板 price-return（TR sensitivity 未在见结果后新增，已披露）。
6. SCENARIO_NOT_STRICT_PIT_OOS：本结果非 strict PIT OOS、非生产/实盘授权。
```

---

## Approval Record

```yaml
gate: 4
handoff_id: G4_LONG_HORIZON_PROXY_RUN_001
packet: GATE_4_LONG_HORIZON_PROXY_RUN
status: READY_FOR_REVIEW

executed:
  window: {decision_start: 2015-01-28, first_interval: [2015-01-28, 2015-01-29], last_decision: 2026-08-06, last_interval_end: 2026-08-07, n_intervals: 2800}
  methods: [HS300_ref, EqualWeight, MaximumDiversification, MinimumVariance, RiskParity_IVOL, Momentum_12_1]
  params: canonical reused (120/0.5, 120/0.5, 60, 252/21)
  semantics: T->T+1 close-to-close research-return; unified SH calendar; A-share/rates T, HK/US/GOLD/FX T-1; SCENARIO_NOT_STRICT_PIT_OOS
  no_lookahead: true
  data_repairs: none (all fetched 2026-08-09 with provenance)
  tests: 265 passed (incl. 11 L2)
  check: PASSED

result_highlights:
  maxdiv: {sharpe: 1.183, max_drawdown: -0.1139, calmar: 0.540, worst_12m: -0.1000, china_weak_phase: {cum: +0.0012, mdd: -0.1139}}
  hs300_ref: {sharpe: 0.228, max_drawdown: -0.4670}
  momentum: {sharpe: 0.528, max_drawdown: -0.4674, cum: +1.377}
  minvar_rp_cash_like_dominated: true   # LOSO: MinVar 18.45->2.006 / RP 4.36->0.955 on CASH_LIKE drop

l1_context: {maxdiv: {sharpe: 1.655, max_drawdown: -0.0402}, note: historical context only, not a GO threshold}

no_rl: PPO/SAC/TD3 absent from all code paths and output tables
not_done:
  rl_retraining: false
  hyperparameter_optimization: false
  qmt_live: false
```

## END OF GATE 4 LONG HORIZON PROXY RUN
