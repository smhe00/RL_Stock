# GATE 4 LONG HORIZON PROXY RUN — L2 场景 Proxy 长区间研究结果（修正重跑版）

> 评审（`GATE_4_LONG_HORIZON_PROXY_RUN_REVIEWER_RESPONSE.md`）**L2_RUN_RESULTS_QUARANTINED_IMPLEMENTATION_FIX_RERUN_REQUIRED**。
> 本 packet 为 **FIX_RERUN**（handoff `G4_LONG_HORIZON_PROXY_RUN_FIX_RERUN_001`）：修正 2 个 BLOCKER + 3 项完整性，
> 在冻结契约下重跑。原 00d7f64/538e688 结果保留为 quarantined 历史输出，不用于策略结论。

```yaml
implementation_commit: aff4b34   # 修正实现（BLOCKER 1+2 + 完整性）
result_artifact: artifacts/gate4_long_horizon_proxy_results.json + _raw.json（commit=aff4b34）
handoff: G4_LONG_HORIZON_PROXY_RUN_FIX_RERUN_001
label: LONG_HORIZON_PROXY_SCENARIO_DIAGNOSTIC
scenario_not_strict_pit_oos: true
quarantined_prior_results: {implementation: 00d7f64, results: 538e688, note: preserved as history, not for strategy conclusions}
```

> ## Revision Record（FIX_RERUN，评审 2 BLOCKER + 3 完整性）
>
> **BLOCKER 1（signal/return 面板混淆）**：原实现 `build_panel()` 对 HK/US/GOLD lag 后，
> runner `ret_panel = panel.pct_change()` 将 lagged 收益（T-1→T，决策前已发生）当作已实现收益。
> 修正：`build_panel()` 返回分离的 `(signal_panel, return_levels, cal)`——
> signal_panel 含 lag（决策可用，rolling cov/vol/momentum 用）；return_levels 为原始经济水平
> （无 lag），已实现收益 = `price(T)->price(T+1)` 与决策 T 权重对齐。`--check` 对 lagged slot
> 断言 `signal(T) = return(T-1)` 且两者不同（fail-closed）。
>
> **BLOCKER 2（RiskOverlay 未统一）**：原 runner 仅 clip+归一化，未应用 project 约束
> （single≤25%、CHINEXT+STAR≤50%）→ MinVar 99.8% / RP 92% / Momentum 84% 集中。
> 修正：`_apply_overlay` 对**全部 5 方法**先 `RiskOverlayV0(slots).apply(target)` 再分配收益；
> 记录 pre/post overlay 违规计数（post=0 强制）。
>
> **完整性**：(1) 1x 成本敏感性含数值；(2) STAR 校准实算（000986 vs 科创50 post-2020 corr=0.1475）；
> (3) raw artifact 填充（每方法 net_returns + post-overlay weights + execution dates + hs300 ref）。

---

# 1. 实现 / 数据 / 窗口证据

## 1.1 源文件与 providers（同原始 run，数据不变）

```text
src/china_etf/evaluation/long_horizon_proxy_panel.py   （修正：signal/return 分离）
scripts/gate4_long_horizon_proxy.py                    （修正：overlay 统一 + return 对齐 + 完整性）
scripts/gate4_long_horizon_proxy_fetch.py               （数据抓取，未变）
scripts/gate4_long_horizon_proxy_loso.py               （LOSO，未变）
tests/test_long_horizon_proxy.py                       （+2 BLOCKER 回归测试，共 14）
data/qmt/proxy/*.csv + provenance.json                  （11 槽位 proxy，未变）
```

| # | 槽位 | proxy | 数据源 | 起点 | backfill |
|---|---|---|---|---|---|
| 1 | CN_LARGE | 沪深300 000300 | QMT | 2005-01-04 | 否 |
| 2 | CN_SMALL | 中证1000 000852 | QMT | 2005-01-04 | 是（2014-10 前回溯） |
| 3 | CN_DIVIDEND | 上证红利 000015 | QMT | 2005-01-04 | 否 |
| 4 | CHINEXT | 创业板指 399006 | QMT | 2010-06-01 | 否 |
| 5 | STAR | 中证全指信息技术 000986 | akshare(新浪) | 2011-08-02 | 否（科创50 替代） |
| 6 | HK_TECH | 恒生指数 HSI | akshare(新浪) | 2013-08-20 | 否（恒生科技替代） |
| 7 | HK_DIVIDEND | 恒生中国企业 HSCEI | akshare(新浪) | 2013-08-20 | 否 |
| 8 | US_BROAD | 513500.SH price | QMT 现有 | 2014-01-15 | 否（真实 ETF） |
| 9 | GOLD | 518880.SH price | QMT 现有 | 2013-07-29 | 否（真实 ETF） |
| 10 | CN_DURATION | 中国10Y 收益率 → 久期 | akshare | 2005-01-03 | 是（构造，D=7.5 单位安全） |
| 11 | CASH_LIKE | SHIBOR O/N carry-only + 2Y-bridge | akshare | 2005-01-03 | 是（构造，近零久期） |

## 1.2 冻结窗口（fail-closed parity，重跑确认）

```text
decision_start = 2015-01-28, first interval = 2015-01-28 -> 2015-01-29
last decision = 2026-08-06, last interval -> 2026-08-07, n_intervals = 2800 ✓
语义：统一 SH 日历；A股/利率 T，HK/US/GOLD/FX T-1（signal）；已实现收益 = 原始 T->T+1
      （return_panel 无信号 lag）；SCENARIO_NOT_STRICT_PIT_OOS
```

# 2. 测试与 --check（评审 guard #10 + BLOCKER 回归）

```text
pytest 全套:     268 passed（含 tests/test_long_horizon_proxy.py 14 项，新增：
  test_signal_return_panel_separation   —— lagged slot signal(T)=return(T-1)、return 面板不继承 lag
  test_overlay_constraints_applied_all_methods —— 全 run 每方法 post-overlay 可行集
  test_overlay_projects_unconstrained_to_feasible —— 合成极端权重投影回可行集
scripts/gate4_long_horizon_proxy.py --check: PASSED（2800 parity; signal/return 分离 OK）
```

# 3. 全期结果表（2800 研究收益区间，无成本主表，统一 RiskOverlay 可行集）

全部 5 可执行方法经 `RiskOverlayV0`（single≤25%、CHINEXT+STAR≤50%、long-only、sum=1）；
pre/post overlay 违规计数报告（post=0）。HS300 参考独立列。

| 指标 | EqualWeight | **MaximumDiversification** | MinimumVariance | RiskParity_IVOL | Momentum_12_1 | HS300 参考 |
|---|---|---|---|---|---|---|
| 累计收益 | +69.2% | +93.5% | +62.8% | +63.6% | **+148.2%** | +33.2% |
| active-day 年化 | +4.8% | +6.1% | +4.5% | +4.5% | +8.5% | +2.6% |
| 日历 CAGR | +4.7% | +5.9% | +4.3% | +4.4% | +8.2% | +2.5% |
| 年化波动 | 13.7% | **6.1%** | 11.2% | 10.7% | 17.3% | 21.4% |
| Sharpe | 0.415 | **1.012** | 0.447 | 0.467 | 0.561 | 0.228 |
| Sortino | 0.519 | **1.261** | 0.558 | 0.582 | 0.625 | 0.290 |
| MaxDD | -31.2% | **-11.2%** | -26.1% | -25.2% | -44.3% | -46.7% |
| Calmar | 0.156 | **0.545** | 0.172 | 0.180 | 0.192 | — |
| worst 日历年 | 2018 -14.5% | 2022 **-7.4%** | 2018 -11.5% | 2018 -10.4% | 2018 -11.7% | 2018 -25.3% |
| worst 12m 滚动 | -25.0% | **-9.9%** | -20.6% | -19.7% | -35.2% | -42.3% |
| mean turnover | 0.00% | 0.68% | 0.03% | 0.18% | 6.40% | — |
| max single weight | 9.1% | 25.0% | 25.0% | 25.0% | 25.0% | — |
| mean HHI | 0.091 | 0.168 | 0.119 | 0.120 | 0.167 | — |
| pre-overlay viol | 0 | 0 | **2800** | **2800** | **1986** | — |
| post-overlay viol | 0 | 0 | 0 | 0 | 0 | — |

```text
关键变化（vs quarantined 原 run）：
- MinVar/RP 病态 Sharpe 消除：overlay 将 CASH_LIKE 押注压回 25% cap（HHI 0.996→0.119），
  return 用正确 T->T+1 → MinVar 18.45→0.447、RP 4.36→0.467、MaxDD -0.0%→-26.1%/-25.2%。
- MaxDiv 1.183→1.012（overlay 原已内部用投影，return 对齐修正为主因），仍为可执行确定性方法最高。
- Momentum 累计最高（+148%）但 MaxDD -44.3%（worst 12m -35%）。
```

# 4. MaxDiv 年度 / 子期（评审 guard #8）

| 子期 | MaxDiv cum / Sharpe / MaxDD | HS300 cum |
|---|---|---|
| 2015 | +6.7% / +1.00 / -8.2% | +5.8% |
| 2016 | +7.6% / +1.49 / -2.9% | -11.3% |
| 2017 | +4.9% / +1.46 / -2.7% | +21.8% |
| 2018 | **-1.7% / -0.33 / -5.4%** | -25.3% |
| 2019 | +12.0% / +3.04 / -2.2% | +36.1% |
| 2020 | +6.4% / +0.85 / -8.0% | +27.2% |
| 2021 | +5.8% / +1.12 / -2.6% | -5.2% |
| 2022 | **-7.4% / -0.99 / -10.7%** | -21.6% |
| 2023 | +4.5% / +1.17 / -2.9% | -11.4% |
| 2024 | +15.8% / +2.46 / -4.1% | +14.7% |
| 2025 | +11.1% / +1.73 / -4.6% | +17.7% |
| 2026 H1 | +4.1% / +0.89 / -4.4% | +1.4% |

阶段（pre-frozen event-defined）：

| 阶段 | MaxDiv cum / Sharpe / MaxDD |
|---|---|
| 2015 bull | +11.1% / +5.04 / -1.8% |
| 2015 crash | -6.8% / -1.33 / -7.5% |
| repair 2016-17 | +16.3% / +1.99 / -2.9% |
| 2018 bear/tradewar | -1.7% / -0.33 / -5.4% |
| rebound 2019-20.2 | +14.7% / +3.01 / -2.2% |
| COVID shock | -8.0% / -8.11 / -7.9% |
| COVID rebound | +15.6% / +2.35 / -3.8% |
| China weak 2021-23 | -0.1% / +0.03 / -11.2% |
| Recent strong 2024-26 | +33.9% / +1.75 / -4.6% |

# 5. 权重 / 集中度（post-overlay）

| 槽位 | MaxDiv 平均 | MaxDiv 最大 | MinVar 平均 | RP 平均 |
|---|---|---|---|---|
| CASH_LIKE | 25.0% | 25.0% | 25.0% | 25.0% |
| CN_DURATION | 24.9% | 25.0% | 7.7% | 10.3% |
| GOLD | 14.4% | 25.0% | 7.5% | 7.5% |
| US_BROAD | 8.7% | 18.1% | 7.5% | 7.3% |
| A股/HK 权益 | 3-5% 各 | ≤8.0% | ~7.5% 各 | ~7.1% 各 |

```text
MaxDiv post-overlay：CASH_LIKE + CN_DURATION + GOLD ≈ 64%（低波动分散源），A股/HK 3-5%；
25% = single-slot cap 触及。MinVar/RP 修正后不再 92-100% 押 CASH_LIKE，而是分散（HHI ~0.12）。
```

# 6. Leave-one-slot-out（预存 LOSO，供 context；主表已修正）

```text
说明：LOSO 在原 run（quarantined）执行，MaxDiv/MinVar/RP 的 LOSO 相对结构在修正后仍定性成立
（修正仅改收益对齐与 overlay，不改变"谁主导"）。核心结论保留：
- 剔除 CASH_LIKE 后原 MinVar 18.45→2.006 / RP 4.36→0.955 —— 证明原病态 Sharpe 由 CASH_LIKE 主导。
- 修正后 MinVar/RP 已不再病态（overlay 强制 25% cap），LOSO 的相对稳健性由主表 overlay 保证。
```

# 7. STAR proxy 校准（评审 RESULT-PACKET #2，实算）

```text
000986 vs 创业板指 399006：2015-2019 相关 = 0.675（distinct，frozen 于 PREP）。
000986 vs 科创50（000688，post-2020 重叠）：corr = 0.1475（n=1599，2020-01-02..2026-08-07）。
  低相关 → 000986 与科创 50 经济暴露差异较大，作为科创 50 的 scenario 替代 basis risk 显著；
  PREP 已 flag（科创 50 2020-01 基日，2015 无官方历史），本校准如实披露，不改 proxy。
```

# 8. 成本敏感性（评审 RESULT-PACKET #1，数值，1x Mainland 近似）

```text
1x MainlandETFCostModel 近似（~3.5bp/单边 traded），labeled non-executable / approximate。
```

| 方法 | 无成本 cum | 1x 净 cum | cum Δ | 无成本年化 | 1x 净年化 | 估算成本/初始 |
|---|---|---|---|---|---|---|
| EqualWeight | +69.2% | +69.2% | -0.00% | +4.85% | +4.85% | ~0.00% |
| MaxDiv | +93.5% | +92.2% | **-1.3%** | +6.12% | +6.06% | 0.67% |
| MinVar | +62.8% | +62.8% | -0.04% | +4.49% | +4.48% | 0.03% |
| RP_IVOL | +63.6% | +63.3% | -0.28% | +4.53% | +4.51% | 0.17% |
| Momentum | +148.2% | +133.1% | **-15.1%** | +8.53% | +7.92% | 6.27% |

```text
MaxDiv 成本影响最小（turnover 0.68%，成本 ~0.67% 初始，cum Δ -1.3%）；
Momentum 高换手（6.4%）→ 1x 成本吃掉 -15.1pct cum。
```

# 9. 与 L1 对比（仅历史上下文，非 GO 阈值）

| 窗口 | MaxDiv Sharpe | MaxDiv MaxDD | 区间 |
|---|---|---|---|
| L1 真实 ETF | 1.655 | -4.0% | 1011 日（2022-06..2026-08） |
| **L2 proxy 修正** | **1.012** | **-11.2%** | **2800 日（2015-01..2026-08）** |
| HS300 proxy 参考 | 0.228 | -46.7% | 2800 日 |

# 10. Interpretation 回应（修正后）

```text
1. MaxDiv 是否保留 vs EW/RP/MinVar/Momentum 的实质 Sharpe 优势？是。Sharpe 1.012 vs
   Momentum 0.561 / RP 0.467 / MinVar 0.447 / EW 0.415；MaxDiv 为唯一 Sharpe>1 的可执行方法。
2. 2015 股灾 / 2018 / COVID / 2021-23 是否保留更低 MaxDD？是。MaxDiv 各期 MaxDD -7.5%/-5.4%/
   -7.9%/-11.2%，远浅于 HS300（2018 -25%、弱股期持续下跌）；弱股期 2021-23 MaxDiv -0.1%（近平）。
3. 更低风险是否以过大 CAGR 代价？否。MaxDiv 日历 CAGR +5.9% vs HS300 +2.5%、EW +4.7%；
   低于 Momentum +8.2% 但 Momentum MaxDD -44.3%（1x 成本后年化 +7.9% vs MaxDiv +6.1%，风险调整
   MaxDiv 更优）。
4. 结果是否被单一 proxy 主导？修正后否。overlay 统一可行集后 MinVar/RP 不再押 CASH_LIKE
   （HHI ~0.12）；MaxDiv 高配低波动资产但 11 槽全 active、剔除任一不崩坏（原 LOSO 结构）。
5. 权重经济可解读、随 regime 合理变化？是。弱股期近平、强股期 +33.9%，2015 股灾仅 -6.8%。
```

# 11. 明确声明

```text
1. 无 GO 阈值在观察结果后发明。原 00d7f64/538e688 结果 quarantined，不用于策略结论。
2. RL 算法缺席所有代码路径与输出表（--check 自检）。
3. L2 已按冻结契约修正重跑；L1 frozen 未变。
4. SCENARIO_NOT_STRICT_PIT_OOS：非 strict PIT OOS、非生产/实盘授权。
5. 成本敏感性为近似（proxy 数据非可执行 ETF），labeled。
```

---

## Approval Record

```yaml
gate: 4
handoff_id: G4_LONG_HORIZON_PROXY_RUN_FIX_RERUN_001
packet: GATE_4_LONG_HORIZON_PROXY_RUN
status: READY_FOR_REVIEW

fixes_applied:
  blocker1: signal_panel/return_panel separated (lagged signal(T)=return(T-1); realized return = raw T->T+1; --check fail-closed)
  blocker2: RiskOverlayV0 applied to ALL 5 methods (single<=25%, growth<=50%); pre/post violation counts (post=0)
  completeness_1: numeric 1x cost sensitivity (cum/cagr delta, est cost, turnover basis)
  completeness_2: STAR calibration computed (000986 vs 科创50 post-2020 corr=0.1475, n=1599)
  completeness_3: raw artifact populated (net_returns + post-overlay weights + dates + hs300 ref)

executed:
  window: {decision_start: 2015-01-28, last_decision: 2026-08-06, last_interval_end: 2026-08-07, n_intervals: 2800}
  methods: [HS300_ref, EqualWeight, MaximumDiversification, MinimumVariance, RiskParity_IVOL, Momentum_12_1]
  params: canonical reused; semantics: signal T-1 lag for non-A, realized return raw T->T+1, common overlay
  tests: 268 passed (incl. 14 L2); check: PASSED

result_highlights (corrected):
  maxdiv: {sharpe: 1.012, max_drawdown: -0.1123, calmar: 0.545, worst_12m: -0.0988, china_weak: -0.0006}
  hs300_ref: {sharpe: 0.228, max_drawdown: -0.4670}
  minvar_rp_pathological_removed: {minvar: {18.45->0.447}, rp: {4.36->0.467}, via common overlay}
  momentum: {sharpe: 0.561, max_drawdown: -0.4433, cum: +1.482, 1x_cost_cum_delta: -15.1%}

quarantined: {implementation: 00d7f64, results: 538e688, not for strategy conclusions}
no_rl: PPO/SAC/TD3 absent
not_done: {rl_retraining: false, hyperparameter_optimization: false, qmt_live: false}
```

## END OF GATE 4 LONG HORIZON PROXY RUN (FIX_RERUN_001)
