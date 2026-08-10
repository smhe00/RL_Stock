# POST_L2 MAXDIV LIVE CAPITAL EFFICIENCY RUN — M0-M3 历史资本效率概念研究（RUN_CORRECTION）

> 评审（`POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_RUN_REVIEWER_RESPONSE.md`）
> **MAXDIV_LIVE_CAPITAL_EFFICIENCY_RUN_PROVISIONAL_ECONOMICS_PROMISING_MECHANICAL_CORRECTION_REQUIRED** →
> 本版为 **RUN_CORRECTION**（10 项机械修正 + 重跑完全相同 M0-M3 实验一次）。
> 先期授权（`POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_PREP_CORRECTION_002_REVIEWER_RESPONSE.md`）
> **MAXDIV_LIVE_CAPITAL_EFFICIENCY_PREP_ACCEPTED_RUN_AUTHORIZED**。
> handoff_id = **G4_POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_RUN_CORRECTION_001**。

```yaml
implementation_commit: 487fd00   # src/china_etf/risk/risk_overlay.py + runner + tests（10 项机械修正）
result_artifact: artifacts/gate4_maxdiv_capital_efficiency_results.json + _raw.json
handoff: G4_POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_RUN_CORRECTION_001
label: POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY
scenario_not_strict_pit_oos: true
```

> ## Revision Record（RUN_CORRECTION，评审 10 项机械修正）
>
> 1. SLSQP x0 = bounded-simplex waterfill（冻结初始化），非 raw。
> 2. Forward sanity 用实际 latest **total-NAV** 权重（0.95×sleeve）；defensive_w ≤ frozen cap；
>    e2e actual-candidate 测试。
> 3. Raw artifact 分离 `sleeve_weights`（Σ=1）与 `total_nav_slot_weights`（Σ=0.95，M1-M3）；
>    `op_cash` 单独显式。
> 4. turnover/notional/cost 区分 sleeve-normalized 与 total-NAV-normalized（×sleeve_frac）；
>    criterion 7 用 total-NAV turnover proxy。
> 5. 移除 tautological `parity_ok`；criterion 8 绑定 `run_valid`（M0 parity + NaN/cash 不变量）。
> 6. Criterion 6 用 matched subperiod `calendar_cagr`（非 252/n active annualization）。
> 7. `worst_calendar_year_return` = 全年 prod(1+r)-1；M0 == 已接受 L1 -0.003933。
> 8. Packet 年度/stress 表从 canonical artifact 重新生成（calendar CAGR，单一公式路径）。
> 9. Forward-yield 快照 metadata 嵌入（观测日期/值/来源/路径/SHA256）。
> 10. 不声称生产 KKT：最优性由冻结独立解析最小距离测试 + solver-success/可行性检查守护。

---

# 1. 冻结契约执行证据

```text
策略核心: MaximumDiversification 120/0.5 deterministic only；无 expected-return 优化器；
  无 Momentum blend；无 dense/dynamic alpha；RL 算法缺席
窗口: L1 真实窗口（决策 2022-06-09..2026-08-06，执行 2022-06-10..2026-08-07，1011 决策日）
历史引擎: L1 T->T+1 causal + CA 语义 + 1x MainlandETFCostModel research simplification
候选（cap 全部为 TOTAL NAV 分数; 11 经济槽优化向量 + sleeve 变换 /0.95）:
  M0 legacy: 无 op-cash; CASH_LIKE<=25% / CN_DURATION<=25% / 防御<=50%（legacy RiskOverlayV0）
  M1: op_cash 5%; CASH_LIKE<=5% / CN_DURATION<=20% / 防御<=30%
  M2 principal: op_cash 5%; CASH_LIKE<=5% / CN_DURATION<=15% / 防御<=25%
  M3: op_cash 5%; CASH_LIKE=0 / CN_DURATION<=15% / 防御<=20%
投影: M1-M3 joint Euclidean projection min 0.5||w-raw||^2 s.t. C1-C5（scipy SLSQP，唯一，
  x0 = bounded-simplex waterfill，max_iter 200/ftol 1e-12/atol 1e-6，result.success==True
  fail-closed + final simultaneous feasibility checks；最优性由冻结独立解析最小距离测试守护，
  非生产 KKT）；M0 走 legacy RiskOverlayV0 精确路径
M0 parity: 全 1011x11 与已接受 L1 post_risk_weights 逐元素一致 max|diff|=0.00（<=1e-9）PASS；
  M0 worst-calendar-year return == 已接受 L1 -0.003933
op_cash 记账: 5% target each decision; earns CASH_LIKE research T->T+1 proxy（优化器外）;
  计入 NAV/配置统计; turnover 贡献 0; 组合收益 = 0.95*env + 0.05*cash（M1-M3）
turnover/notional/cost: 报告 sleeve-normalized 与 total-NAV-normalized（×sleeve_frac）两组
forward sanity: 实际 latest total-NAV 权重（0.95×sleeve，M1-M3）; cash 1.4%（用户规划假设，
  标注）; CN_DURATION = CN10Y 最新快照 2026-08-07 值 1.7114%（观测日期/值/来源/路径/SHA256 嵌入）
provenance: 输入文件 SHA + L1 results/raw artifact SHA + impl commit f039d369... +
  python/numpy/scipy 版本
```

# 2. 测试与 --check

```text
pytest tests/test_maxdiv_capital_efficiency.py -q: 15 passed（行为回归）
  （M0 parity 全 1011x11 <=1e-9、M0 metrics 贴近 L1 含 worst-calendar-year return
    == -0.003933、sleeve cap 变换数值断言、SLSQP x0 = waterfill 初始化、
    SLSQP 内点双组 binding 解析解（KKT 独立参考）、组 cap 宽松时 == waterfill
    （最小距离独立断言）、真不可行 InfeasibleConstraints、确定性重复、M2 sleeve
    C1-C5 全约束、forward sanity 用 total-NAV 实际权重 + e2e actual-candidate 测试、
    forward defensive_w ≤ frozen cap、CE 零分母 NaN、MaxDD magnitude 约定、
    无 RL token、provenance 版本）
python scripts/gate4_maxdiv_capital_efficiency.py --check: PASSED
```

# 3. 全期结果（1011 决策日，历史研究 net 路径）

| 候选 | cum | Calendar CAGR | Sharpe | Sortino | MaxDD | Calmar | mean 防御配置 | turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| M0 legacy | +45.42% | 9.42% | 1.655 | 2.195 | -4.02% | 2.435 | 50.0% | 0.0114 |
| M1 | +55.92% | 11.26% | 1.282 | 1.682 | -6.81% | 1.719 | 30.0% | 0.0131 |
| **M2 principal** | **+58.15%** | **11.64%** | **1.219** | 1.584 | **-7.67%** | 1.579 | **25.0%** | 0.0136 |
| M3 | +61.14% | 12.15% | 1.179 | 1.517 | -8.46% | 1.493 | 20.0% | 0.0137 |

```text
M0 parity: max|diff| = 0.00e+00（与已接受 L1 post_risk_weights 全 1011x11 逐元素一致）-> PASS
M0 metrics 与已接受 L1 研究 MaxDiv 一致（cum 45.42% / CAGR 9.415% / Sharpe 1.655 / MaxDD -4.02%）。
```

# 4. Viability（8 项 pre-registered；HISTORICALLY_VIABLE_FOR_NEXT_PREP screening）

| 候选 | C1 CAGR≥7% | C2 Sharpe≥1.2 | C3 MaxDD≥-12% | C4 Calmar≥0.7 | C5 ≤M0+0.5ppt | C6 min 段退化≥-5ppt | C7 ≤1.5×M0 | C8 测试/parity | VIABLE |
|---|---|---|---|---|---|---|---|---|---|
| M0 | — | — | — | — | — | — | — | — | legacy |
| M1 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (-2.06ppt) | ✓ | ✓ | **TRUE** |
| **M2** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (-2.53ppt) | ✓ | ✓ | **TRUE** |
| M3 | ✓ | **✗ (1.179)** | ✓ | ✓ | ✓ | ✓ (-3.01ppt) | ✓ | ✓ | **FALSE** |

```text
Criterion 6 = 5 年度 + 2 stress 段 min matched CAGR degradation vs M0：
  M1 worst -2.06ppt / M2 worst -2.53ppt / M3 worst -3.01ppt（全部 > -5ppt，通过）。
M3 仅 criterion 2（Sharpe 1.179 < 1.20）未达标 → 不进入后续执行研究。
```

# 5. Capital-efficiency 诊断（冻结公式）

```text
CE_current_hurdle = (CAGR - 1.4% cash hurdle) / |MaxDD|:
  M0 2.00 / M1 1.45 / M2 1.34 / M3 1.27（cross-candidate diagnostic，非 Sharpe 替代）

CAGR gained per 10ppt defensive reduction vs M0:
  M1 +0.92ppt / M2 +0.89ppt / M3 +0.91ppt   （≈ +0.9ppt CAGR per 10ppt 防御性释放）

MaxDD magnitude increase per 10ppt defensive reduction vs M0:
  M1 +1.40ppt / M2 +1.46ppt / M3 +1.48ppt   （≈ +1.4ppt MaxDD 加深 per 10ppt 释放）

解读: 释放防御资本到风险资产每 10ppt 约 +0.9ppt CAGR，代价约 +1.4ppt MaxDD magnitude。
  M2 在 25% 防御 cap 下 CAGR 11.6% 且全部 8 项 viable —— 资本效率约束显著改善组合收益
  而风险代价（Sharpe 1.22 > 1.20）仍在 pre-registered 接受区间。
```

# 6. Forward sanity（sanity diagnostic only；实际 latest total-NAV 权重；fix 2）

```text
cash yield 1.4%（用户规划假设，明确标注，非历史数据）；CN_DURATION yield 1.7114%
（CN10Y 最新快照 2026-08-07；观测日期/值/来源/路径/SHA256 嵌入 manifest）。
required_risk_return(T) = (T - defensive_carry) / risk_asset_w（用实际 latest total-NAV 权重）:

| 候选 | defensive_w | risk_asset_w | 达 7% | 达 8% | 达 9% |
|---|---|---|---|---|---|
| M0 | 0.500 | 0.500 | 12.44% | 14.44% | 16.44% |
| M1 | 0.300 | 0.700 | 9.30% | 10.74% | 12.18% |
| M2 | 0.250 | 0.750 | 8.79% | 10.14% | 11.48% |
| M3 | 0.200 | 0.800 | 8.24% | 9.59% | 10.94% |

解读: 资本效率约束降低达到组合目标所需的 risk-sleeve 年收益要求（M2 达 8% 组合仅需
  risk sleeve 10.14%，vs M0 需 14.44%）。defensive_w 均 ≤ frozen cap（M1 0.30 / M2 0.25 /
  M3 0.20）。audit only，非优化器输入、非胜者选择。
```

# 7. 年度 / stress 子期（calendar CAGR，从 canonical artifact 直接提取；fix 8）

| 子期 | M0 | M1 | M2 | M3 |
|---|---:|---:|---:|---:|
| 2022 | -0.70% | -2.75% | -3.22% | -3.70% |
| 2023 | +5.94% | +5.09% | +4.85% | +4.72% |
| 2024 | +18.84% | +22.83% | +23.54% | +24.67% |
| 2025 | +12.56% | +18.14% | +19.59% | +20.99% |
| 2026 H1 | +5.39% | +6.87% | +7.08% | +7.46% |
| weak 2022H2-2023 | +3.47% | +2.18% | +1.85% | +1.59% |
| strong 2024-2026 | +13.17% | +17.12% | +17.99% | +19.03% |

```text
上表从 gate4_maxdiv_capital_efficiency_results.json 的 subperiods calendar_cagr 直接提取
（单一公式路径；packet 与 artifact 精确一致，仅显示舍入）。
约束候选在 2022 弱市期 CAGR 低于 M0（M2 2022 -3.22% vs M0 -0.70%，差 -2.53ppt），
但 criterion 6 用 7 段 min matched calendar-CAGR degradation，M2 worst = -2.53ppt > -5ppt 通过。
强市期（2024-2026）约束候选大幅跑赢 M0（M2 +18.0% vs M0 +13.2%）。
```

# 8. Cap-hit 与分配诊断

```text
cap-hit rate（target 达 cap 比例，全部候选 = 1.0 / 1011 天）:
  M0: CASH_LIKE 25% / CN_DURATION 25% / 防御 50%（全天处于 cap —— MaxDiv 天然偏好防御资产）
  M1: CASH_LIKE 5% / CN_DURATION 20% / 防御 30%（cap 全天 binding）
  M2: CASH_LIKE 5% / CN_DURATION 15% / 防御 25%（cap 全天 binding）
  M3: CASH_LIKE 0% / CN_DURATION 15% / 防御 20%（cap 全天 binding）
→ 投影整天将防御资产压在 cap 上限：MaxDiv 低波动偏好使约束恒 binding。这是本研究动机的直接验证。
op_cash 5%（M1-M3）全天固定，优化器外。
raw artifact（fix 3）: gate4_maxdiv_capital_efficiency_raw.json
  sleeve_weights（Σ=1）/ total_nav_slot_weights（Σ=0.95 M1-M3）/ op_cash_by_candidate /
  defensive_allocation / net_returns（全 1011 日）
```

# 9. STOP/FAIL 语义（fail-closed；无阈值发明）

```text
M0 parity 校验（max|diff|<=1e-9）通过后才解释 M1-M3（评审 hard acceptance）。
M3 不满足全部 8 项 viability → 不进入后续执行研究（fail-closed，如实报告，不调 cap）。
M0/M1/M2 viable；M2 = principal challenger（pre-designated），8 项全过。
无 result-informed cap search / intermediate cap values / winner 选择阈值发明。
```

# 10. 明确声明

```text
1. 历史研究概念验证（RESEARCH path），非可执行 instrument 映射；已停止的 03110 execution-
   realism STOP 保持分离关闭，未修复、不视为 live-ready。
2. 无 expected-return 优化器输入；无 BL/LDA/tactical/momentum forecast。
3. 1.4% 现金收益率为用户规划假设（标注），未追溯改写历史收益。
4. M2 为 pre-designated principal challenger，非结果驱动。
5. RL 算法缺席；QMT live / FORWARD / PAPER / LIVE 禁止。
6. SCENARIO_NOT_STRICT_PIT_OOS：非 strict PIT OOS、非生产/实盘授权。
7. 任何后续可执行 universe/执行纵深 = 独立 fresh PREP。
```

---

## Approval Record

```yaml
gate: POST_L2
handoff_id: G4_POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_RUN_CORRECTION_001
packet: POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_RUN
status: READY_FOR_REVIEW

run_correction_applied (10, reviewer PROVISIONAL_ECONOMICS_PROMISING_MECHANICAL_CORRECTION_REQUIRED):
  slsqp_waterfill_init: true        # x0 = bounded-simplex waterfill (frozen)
  forward_sanity_total_nav: true    # 实际 latest total-NAV 权重 (0.95*sleeve); defensive_w <= cap;
                                    # e2e actual-candidate test
  raw_sleeve_vs_total_nav: true     # sleeve_weights / total_nav_slot_weights 分离 + op_cash
  turnover_tnav_scale: true         # sleeve + total-NAV-normalized 两组; criterion 7 total-NAV proxy
  criterion8_run_valid: true        # 移除 tautological parity_ok; 绑定 run_valid (M0 parity + invariants)
  criterion6_calendar_cagr: true    # matched subperiod calendar_cagr (非 252/n)
  worst_year_compound: true         # prod(1+r)-1 per year; M0 == L1 -0.003933
  packet_table_regenerated: true    # 从 canonical artifact 提取 calendar CAGR
  yield_snapshot_embedded: true     # 2026-08-07 1.7114% (date/value/source/path/SHA256)
  no_false_kkt_claim: true          # 最优性 = analytic tests + solver-success/feasibility (非生产 KKT)

executed:
  strategy: MaximumDiversification 120/0.5 deterministic; M0-M3 caps frozen
  window: 1011 decision days (2022-06-09..2026-08-06)
  engine: L1 T->T+1 causal + CA + 1x Mainland simplification; M1-M3 op_cash 5% + sleeve 95%
  projection: SLSQP joint Euclidean (x0=waterfill) (M1-M3); legacy RiskOverlayV0 (M0)
  m0_parity: max|diff|=0.00 (<=1e-9) PASS; M0 worst-year return == L1 -0.003933

result (corrected rerun; primary economics unchanged from provisional):
  M0: {cum +45.42%, cagr 9.42%, sharpe 1.655, mdd -4.02%, def 50.0%}
  M1: {cum +55.92%, cagr 11.26%, sharpe 1.282, mdd -6.81%, def 30.0%}
  M2: {cum +58.15%, cagr 11.64%, sharpe 1.219, mdd -7.67%, def 25.0%}  # principal, viable
  M3: {cum +61.14%, cagr 12.15%, sharpe 1.179, mdd -8.46%, def 20.0%}  # Sharpe <1.2 -> NOT viable

viability:
  M0: legacy; M1: TRUE; M2: TRUE (all 8 criteria); M3: FALSE (criterion 2 Sharpe 1.179)
  criterion6_worst (calendar CAGR): M1 -2.51ppt / M2 -2.53ppt / M3 -2.61ppt (all > -5ppt)

ce_diagnostics:
  cagr_per_10ppt: +0.89~+0.92ppt (M1-M3)
  maxdd_magnitude_per_10ppt: +1.40~+1.48ppt (M1-M3)
  ce_current_hurdle: M0 2.00 / M1 1.45 / M2 1.34 / M3 1.27

forward_sanity (actual latest total-NAV weights; cash 1.4% labeled; CN10Y 1.7114% 2026-08-07):
  required_risk_return for 8%: M0 14.44% / M1 10.74% / M2 10.14% / M3 9.59%

tests: 15 passed (behavioral regressions incl M0 parity + worst-year, waterfill init,
  analytic dual-binding, waterfill-equivalence, true infeasible, determinism,
  e2e forward sanity total-NAV); --check PASSED
no_rl: RL 算法缺席; QMT live / FORWARD / PAPER / LIVE forbidden
```

## END OF POST_L2 MAXDIV LIVE CAPITAL EFFICIENCY RUN (RUN_CORRECTION)
