# GATE 4 LONG HORIZON PROXY RUN — L2 场景 Proxy 长区间研究结果（FX 修正最终版）

> 评审（`GATE_4_LONG_HORIZON_PROXY_RUN_FIX_RERUN_REVIEWER_RESPONSE.md`）确认 BLOCKER 1/2 已修复，
> 发现 **FX BLOCKER**（冻结的 HKD/CNY 转换未实现）→ decision `FIX_RERUN_SUBSTANTIALLY_CORRECT_FX_CONVERSION_MISSING_FINAL_RERUN_REQUIRED`。
> 本 packet 为 **FX_FIX_RERUN**（handoff `G4_LONG_HORIZON_PROXY_RUN_FX_FIX_RERUN_001`），最终一次实现修正重跑。

```yaml
implementation_commit: 7781800   # FX 修正（panel + tests）
result_artifact: artifacts/gate4_long_horizon_proxy_results.json + _raw.json（commit=7781800）
handoff: G4_LONG_HORIZON_PROXY_RUN_FX_FIX_RERUN_001
label: LONG_HORIZON_PROXY_SCENARIO_DIAGNOSTIC
scenario_not_strict_pit_oos: true
quarantined_history:
  gen1: {implementation: 00d7f64, results: 538e688, note: original run (signal/return conflation + missing overlay)}
  gen2: {implementation: aff4b34, results: 0c8b9b4, note: corrected-run-v1 (BLOCKER 1+2 fixed, FX missing)}
  # gen3 = 本 packet（FX 集成最终版），待评审接受
```

> ## Revision Record（FX_FIX_RERUN，评审 FX BLOCKER）
>
> 冻结契约：`FX: HKD->CNY 用 hkd_cny_boc，日频 ffill；决策 T 用 T-1 FX（与 HK 输入一致）`。
> 修正：`HK_TECH`/`HK_DIVIDEND` 的 return level = `raw_hk_index_hkd(t) × hkd_cny(t)`（hkd_cny_boc
> 中行折算价 /100，2013-01-04 起，日频 ffill）；signal 层对 HK 额外 shift(1) → 决策 T 用 T-1 FX。
> signal/return 分离与 T->T+1 已实现收益对齐保留。**未改变**任何其他实验维度。
> FX 方向显式：hkd_cny_boc 折算价单位 = HKD 每 100 CNY → `/100` 得 HKD/CNY（1 HKD = 0.8x CNY），
> 与现有 `load_fx_hkd_cny` 一致（非静默推断列名）。

---

# 1. 实现 / 数据 / 窗口证据

## 1.1 源文件与 providers（FX 修正后）

```text
src/china_etf/evaluation/long_horizon_proxy_panel.py   （FX 修正：HK return = HKD × HKD/CNY）
scripts/gate4_long_horizon_proxy.py                    （signal/return 分离 + overlay + 完整性，未变）
scripts/gate4_long_horizon_proxy_fetch.py / _loso.py    （未变）
tests/test_long_horizon_proxy.py                       （+5 FX 回归测试，共 19）
data/qmt/meta/hkd_cny_boc.csv                          （HKD/CNY，2013-01-04 起）
```

| # | 槽位 | proxy | 数据源 | 起点 | backfill |
|---|---|---|---|---|---|
| 1-5 | CN_LARGE/CN_SMALL/CN_DIVIDEND/CHINEXT/STAR | A股指数 | QMT/新浪 | 2005/2010/2011 | 见 PREP |
| 6 | HK_TECH | 恒生指数 HSI × HKD/CNY | akshare + hkd_cny_boc | 2013-08-20 | 否（恒生科技替代） |
| 7 | HK_DIVIDEND | 恒生国企 HSCEI × HKD/CNY | akshare + hkd_cny_boc | 2013-08-20 | 否 |
| 8 | US_BROAD | 513500.SH price | QMT 现有 | 2014-01-15 | 否（真实 ETF） |
| 9 | GOLD | 518880.SH price | QMT 现有 | 2013-07-29 | 否（真实 ETF） |
| 10 | CN_DURATION | 10Y 收益率 → 久期 | akshare | 2005-01-03 | 是（构造） |
| 11 | CASH_LIKE | SHIBOR O/N carry-only | akshare | 2005-01-03 | 是（构造） |

## 1.2 冻结窗口（fail-closed parity，FX 重跑确认）

```text
decision_start = 2015-01-28, first interval = 2015-01-28 -> 2015-01-29
last decision = 2026-08-06, last interval -> 2026-08-07, n_intervals = 2800 ✓
语义：统一 SH 日历；A股/利率 T，HK/US/GOLD/FX T-1（signal）；已实现收益 = 原始 CNY 经济水平 T->T+1
      （HK 含 HKD/CNY 换算）；SCENARIO_NOT_STRICT_PIT_OOS
```

# 2. 测试与 --check（评审 FX 回归 6 项）

```text
pytest 全套:     273 passed（含 tests/test_long_horizon_proxy.py 19 项，FX 新增 5 项：
  FX perturbation 改变 HK CNY 水平（raw_hkd 不变）
  恒定 HK 指数 + 变动 FX → HK CNY 收益 = FX 收益（合成验证）
  决策 T HK 信号 = T-1 CNY 换算水平（signal(T)=return(T-1)）
  决策 T 已实现收益 = CNY 换算 T->T+1
  FX 集成后 2800 区间 parity + 5 方法 post-overlay 零违规
scripts/gate4_long_horizon_proxy.py --check: PASSED（2800; signal/return 分离; FX 集成）
```

# 3. 全期结果表（2800 研究收益区间，无成本主表，统一 RiskOverlay + FX）

全部 5 可执行方法经 `RiskOverlayV0`；HK 槽位含 HKD/CNY。HS300 参考独立列。

| 指标 | EqualWeight | **MaximumDiversification** | MinimumVariance | RiskParity_IVOL | Momentum_12_1 | HS300 参考 |
|---|---|---|---|---|---|---|
| 累计收益 | +72.0% | +94.6% | +65.0% | +65.7% | **+153.1%** | +33.2% |
| active-day 年化 | +5.0% | +6.2% | +4.6% | +4.7% | +8.7% | +2.6% |
| 日历 CAGR | +4.8% | +6.0% | +4.4% | +4.5% | +8.4% | +2.5% |
| 年化波动 | 13.6% | **6.0%** | 11.2% | 10.7% | 17.3% | 21.4% |
| Sharpe | 0.427 | **1.024** | 0.459 | 0.479 | 0.571 | 0.228 |
| Sortino | 0.535 | **1.280** | 0.575 | 0.598 | 0.639 | 0.290 |
| MaxDD | -30.4% | **-10.4%** | -25.4% | -24.5% | -44.3% | -46.7% |
| Calmar | 0.165 | **0.595** | 0.182 | 0.190 | 0.197 | — |
| worst 日历年 | 2018 -13.7% | 2022 **-6.6%** | 2018 -10.9% | 2018 -9.8% | 2018 -10.4% | 2018 -25.3% |
| worst 12m 滚动 | -24.0% | **-9.1%** | -19.7% | -18.8% | -35.2% | -42.3% |
| mean turnover | 0.00% | 0.68% | 0.03% | 0.18% | 6.78% | — |
| max single weight | 9.1% | 25.0% | 25.0% | 25.0% | 25.0% | — |
| mean HHI | 0.091 | 0.169 | 0.119 | 0.120 | 0.168 | — |
| pre-overlay viol | 0 | 0 | **2800** | **2800** | **1958** | — |
| post-overlay viol | 0 | 0 | 0 | 0 | 0 | — |

```text
vs corrected-run-v1（gen2）：MaxDiv Sharpe 1.012→1.024、MaxDD -11.2%→-10.4%（HK FX 纳入后略优）；
其他方法小幅变化（EW/RP/Momentum cum 略升）。FX 对跨资产面板有实质贡献（非微小）。
```

# 4. MaxDiv 年度 / 子期（评审 guard #8）

| 子期 | MaxDiv cum / Sharpe / MaxDD | HS300 cum |
|---|---|---|
| 2015 | +7.2% / +1.07 / -7.9% | +5.8% |
| 2016 | +8.5% / +1.66 / -3.0% | -11.3% |
| 2017 | +4.1% / +1.23 / -2.6% | +21.8% |
| 2018 | **-1.3% / -0.26 / -4.8%** | -25.3% |
| 2019 | +12.3% / +3.12 / -2.2% | +36.1% |
| 2020 | +5.7% / +0.76 / -7.9% | +27.2% |
| 2021 | +5.4% / +1.06 / -2.6% | -5.2% |
| 2022 | **-6.6% / -0.88 / -9.8%** | -21.6% |
| 2023 | +4.5% / +1.18 / -2.9% | -11.4% |
| 2024 | +16.0% / +2.48 / -4.1% | +14.7% |
| 2025 | +10.9% / +1.70 / -4.5% | +17.7% |
| 2026 H1 | +3.7% / +0.82 / -4.4% | +1.4% |

阶段（pre-frozen event-defined）：

| 阶段 | MaxDiv cum / Sharpe / MaxDD |
|---|---|
| 2015 bull | +11.1% / +5.01 / -1.8% |
| 2015 crash | -6.3% / -1.22 / -7.2% |
| repair 2016-17 | +16.4% / +1.99 / -2.9% |
| 2018 bear/tradewar | -1.3% / -0.26 / -4.8% |
| rebound 2019-20.2 | +15.1% / +3.09 / -2.2% |
| COVID shock | -7.9% / -7.90 / -7.8% |
| COVID rebound | +14.5% / +2.21 / -4.0% |
| China weak 2021-23 | +0.6% / +0.06 / -10.4% |
| Recent strong 2024-26 | +33.4% / +1.73 / -4.5% |

# 5. 权重 / 集中度（post-overlay，FX 集成后）

| 槽位 | MaxDiv 平均 | MaxDiv 最大 |
|---|---|---|
| CASH_LIKE | 25.0% | 25.0% |
| CN_DURATION | ~24.9% | 25.0% |
| GOLD | ~14.4% | 25.0% |
| US_BROAD | ~8.7% | ~18% |
| A股/HK 权益 | 3-5% 各 | ≤8% |

```text
MaxDiv post-overlay：CASH_LIKE + CN_DURATION + GOLD ≈ 64%（低波动分散源），A股/HK 3-5%；
25% = single-slot cap 触及。HK 槽位现含 FX 经济暴露（与 L1 真实 ETF 对齐）。
```

# 6. STAR 校准（评审 RESULT-PACKET，实算）

```text
000986 vs 创业板指 399006：2015-2019 相关 = 0.675（distinct，frozen）。
000986 vs 科创50（000688，post-2020 重叠）：corr = 0.1475（n=1599，2020-01-02..2026-08-07）。
  低相关 → 000986 与科创 50 经济暴露差异大，STAR scenario 替代 basis risk 显著（评审提示重点披露）。
  proxy 冻结 ex ante，不因该警告更改；STAR 结论需在此警告下解读。
```

# 7. 成本敏感性（1x Mainland 近似，labeled non-executable）

| 方法 | 无成本 cum | 1x 净 cum | cum Δ | 无成本年化 | 1x 净年化 | 估算成本/初始 |
|---|---|---|---|---|---|---|
| EqualWeight | +72.0% | +72.0% | -0.00% | +5.00% | +5.00% | ~0.00% |
| MaxDiv | +94.6% | +93.4% | **-1.3%** | +6.18% | +6.12% | 0.67% |
| MinVar | +65.0% | +65.0% | -0.04% | +4.61% | +4.61% | 0.03% |
| RP_IVOL | +65.7% | +65.4% | -0.29% | +4.65% | +4.63% | 0.17% |
| Momentum | +153.1% | +136.8% | **-16.3%** | +8.72% | +8.08% | 6.64% |

```text
MaxDiv 成本影响最小（-1.3% cum）；Momentum 高换手（6.8%）→ 1x 成本 -16.3pct cum。
```

# 8. 与 L1 对比（仅历史上下文，非 GO 阈值）

| 窗口 | MaxDiv Sharpe | MaxDiv MaxDD | 区间 |
|---|---|---|---|
| L1 真实 ETF | 1.655 | -4.0% | 1011 日（2022-06..2026-08） |
| **L2 proxy FX 最终** | **1.024** | **-10.4%** | **2800 日（2015-01..2026-08）** |
| HS300 proxy 参考 | 0.228 | -46.7% | 2800 日 |

# 9. Interpretation 回应（FX 最终版）

```text
1. MaxDiv 是否保留 vs EW/RP/MinVar/Momentum 的实质 Sharpe 优势？是。Sharpe 1.024 vs
   Momentum 0.571 / RP 0.479 / MinVar 0.459 / EW 0.427；MaxDiv 为唯一 Sharpe>1 的可执行方法。
2. 2015 股灾 / 2018 / COVID / 2021-23 是否保留更低 MaxDD？是。-7.2%/-4.8%/-7.8%/-10.4%，
   远浅于 HS300（2018 -25%、弱股期持续下跌）；弱股期 2021-23 MaxDiv +0.6%（正）。
3. 更低风险是否以过大 CAGR 代价？否。MaxDiv 日历 CAGR +6.0% vs HS300 +2.5%、EW +4.8%；
   低于 Momentum +8.4% 但 Momentum MaxDD -44.3%（1x 成本后 +8.1% vs MaxDiv +6.1%，风险调整 MaxDiv 优）。
4. 结果是否被单一 proxy 主导？否。overlay 统一可行集后 MinVar/RP 不押 CASH_LIKE（HHI ~0.12）；
   MaxDiv 11 槽全 active、高配低波动资产但分散。
5. 权重经济可解读、随 regime 合理变化？是。弱股期 +0.6%、强股期 +33.4%、2015 股灾 -6.3%。
```

# 10. 明确声明

```text
1. 无 GO 阈值在观察结果后发明。三代结果：gen1（00d7f64/538e688）、gen2（aff4b34/0c8b9b4）均
   保留为 quarantined 历史，不用于策略结论；本 gen3（7781800）为最终 FX 修正版。
2. RL 算法缺席所有代码路径与输出表（--check 自检）。
3. L2 已按冻结契约完成最终修正重跑（BLOCKER 1/2 + FX）；L1 frozen 未变。
4. SCENARIO_NOT_STRICT_PIT_OOS：非 strict PIT OOS、非生产/实盘授权。
5. 成本敏感性为近似；STAR 000986 低相关校准（0.1475）为重要 basis risk 警告，proxy 冻结不改。
```

---

## Approval Record

```yaml
gate: 4
handoff_id: G4_LONG_HORIZON_PROXY_RUN_FX_FIX_RERUN_001
packet: GATE_4_LONG_HORIZON_PROXY_RUN
status: READY_FOR_REVIEW

fx_fix_applied:
  HK_TECH/HK_DIVIDEND return levels = raw_hk_index_hkd(t) * hkd_cny(t)   # hkd_cny_boc /100, ffill
  signal: decision T uses T-1 FX (HK shift(1)); return: CNY T->T+1 realized
  fx_direction: documented (HKD per 100 CNY -> /100 -> HKD/CNY); no silent column inference
  fx_tests: 5 regression tests pass (perturbation, constant-index==FX return, T-1 signal,
            T->T+1 realized, 2800 parity + overlay zero-violation)

executed:
  window: {decision_start: 2015-01-28, last_decision: 2026-08-06, last_interval_end: 2026-08-07, n_intervals: 2800}
  methods: [HS300_ref, EqualWeight, MaximumDiversification, MinimumVariance, RiskParity_IVOL, Momentum_12_1]
  params: canonical reused; semantics: signal T-1 lag (incl FX), realized raw CNY T->T+1, common overlay
  tests: 273 passed (incl. 19 L2); check: PASSED

result_highlights (final FX-corrected):
  maxdiv: {sharpe: 1.024, max_drawdown: -0.1039, calmar: 0.595, worst_12m: -0.0907, china_weak: +0.0055}
  hs300_ref: {sharpe: 0.228, max_drawdown: -0.4670}
  minvar_rp: {sharpe: 0.459/0.479, pathological removed via common overlay}
  momentum: {sharpe: 0.571, max_drawdown: -0.4428, cum: +1.531, 1x_cost_cum_delta: -16.3%}
  star_calibration: {info986_vs_kcb50_post2020_corr: 0.1475, n: 1599, basis-risk warning prominent}

quarantined: {gen1: 00d7f64/538e688, gen2: aff4b34/0c8b9b4, not for strategy conclusions}
no_rl: PPO/SAC/TD3 absent
not_done: {rl_retraining: false, hyperparameter_optimization: false, qmt_live: false}
```

## END OF GATE 4 LONG HORIZON PROXY RUN (FX_FIX_RERUN_001)
