# POST_L2 MAXDIV LIVE CAPITAL EFFICIENCY PREP — 资本效率概念研究契约冻结（PREP only）

> 评审（`POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_PREP_AUTHORIZATION.md`）
> **USER_SELECTED_FRESH_MAXDIV_LIVE_CAPITAL_EFFICIENCY_PREP_AUTHORIZED**（REVIEW_COMPLETE）。
> 触发：用户在 POST_L2 execution-realism STOP 实验正式关闭后显式选择的新研究方向（非自动延续）。
> 本 packet = **PREP only**：冻结实验契约并返回 READY_FOR_REVIEW；**不执行任何回测/运行/结果生成**。
> handoff_id = **G4_POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_PREP_001**。

```yaml
decision: USER_SELECTED_FRESH_MAXDIV_LIVE_CAPITAL_EFFICIENCY_PREP_AUTHORIZED
authorized_next: POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_PREP
authorization_packet: docs/reviewer_responses/POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_PREP_AUTHORIZATION.md
scope: PREP ONLY (no CAPITAL_EFFICIENCY_RUN / no NEW_BACKTEST / no result generation)
```

---

# 1. 研究问题

```text
已接受 MaxDiv core 稳健，但最新目标可将 ~50% NAV 置于 CASH_LIKE + CN_DURATION（当前现金/债券
远期收益率低时不可取）。测试简单的 ex-ante 资本预算约束能否在不显著损害 MaxDiv 稳健性的前提下
提升资本效率。

这是新的 pre-registered 研究，非已关闭 execution-realism STOP 实验的修改/重跑。
```

# 2. 冻结策略核心（不变，禁止重调）

```text
- MaximumDiversification only；lookback = 120；shrinkage = 0.5
- 与已接受 L1 相同的 project-constrained / RiskOverlayV0 语义
- deterministic only；无 Momentum blend；无 dense alpha / dynamic alpha
- 优化器内无 expected-return 预测（无 Black-Litterman / mean-variance expected returns /
  盈利收益率预测 / 战术观点 / 动量预测 / 任意预期收益输入）
- PPO / SAC / TD3 保持关闭（除非用户明确重开）
```

# 3. 已接受 L1 参考绑定（parity/reference 必须绑定）

```text
accepted L1 research artifact: artifacts/gate4_long_horizon_nonrl_results.json
accepted L1 raw artifact    : artifacts/gate4_long_horizon_nonrl_raw.json
accepted L1 impl commit     : （绑定至 L1 RUN 的 implementation_commit；PREP 记录其 SHA256）
MaxDiv 参考 metrics (L1 accepted): cum +45.42% / CAGR 9.415% / active-ann 9.783% /
  vol 5.742% / Sharpe 1.655 / Sortino 2.195 / MaxDD -4.017% / Calmar 2.435 /
  worst cal-year 2022 (-0.39%) / worst rolling 12m +2.31% / mean_turnover 0.0114
MaxDiv 参考配置 (L1 accepted, post_risk): mean CASH_LIKE 0.25 / CN_DURATION 0.25 /
  defensive 0.50（处于 per-asset cap 上限——本研究的动机）
数据: 已接受 L1 11 经济槽位研究路径（load_research_adj）；L1 真实窗口
  决策 2022-06-09..2026-08-06 / 执行 2022-06-10..2026-08-07，1011 决策日；无新数据修复/backfill；
  无 result-informed 窗口变更
```

# 4. 四个候选（M0-M3）— cap 全部为 TOTAL NAV 分数

```text
除声明的防御性资本变更外，保留现有 per-risk-asset 25% cap 与所有其他已接受 MaxDiv 语义。
cap 语义: 作用于 rebalance target weights（同 RiskOverlayV0 V1 语义）；actual 超限由下次再平衡纠正。
```

## M0 — legacy control（基准）

```text
- 无外部 operational-cash sleeve（optimizer 覆盖全部 total NAV）
- 现有 11-slot MaxDiv 120/0.5
- CASH_LIKE <= 25%（total NAV；隐含于现有 per-asset 25% cap）
- CN_DURATION <= 25%（total NAV）
- 防御性资本（CASH_LIKE + CN_DURATION）可达 50%
- M0 必须复现已接受 L1 MaxDiv target path/metrics（确定性容差内）后，方可对比挑战者
```

## M1 — 轻资本效率约束

```text
- operational cash = 固定 5% of total NAV（optimizer 外）
- 战略 CASH_LIKE <= 5% of total NAV
- CN_DURATION <= 20% of total NAV
- operational_cash + CASH_LIKE + CN_DURATION <= 30% of total NAV
- 剩余 95% investable sleeve 保持 MaxDiv 120/0.5，受变换后 total-NAV 约束
```

## M2 — principal challenger（pre-designated）

```text
- operational cash = 固定 5% of total NAV（optimizer 外）
- 战略 CASH_LIKE <= 5% of total NAV
- CN_DURATION <= 15% of total NAV
- operational_cash + CASH_LIKE + CN_DURATION <= 25% of total NAV
- 剩余 95% investable sleeve 保持 MaxDiv 120/0.5
- M2 为主挑战者系设计指定，非基于任何观测结果；不得在见结果后重调这些数值
```

## M3 — 激进资本效率约束

```text
- operational cash = 固定 5% of total NAV（optimizer 外）
- 战略 CASH_LIKE = 0% of total NAV
- CN_DURATION <= 15% of total NAV
- operational_cash + CASH_LIKE + CN_DURATION <= 20% of total NAV
- 剩余 95% investable sleeve 保持 MaxDiv 120/0.5
```

# 5. Total-NAV vs investable-sleeve 约束变换（精确契约）

```text
记号: total NAV = 1。M1-M3: operational_cash = 0.05（optimizer 外）；investable sleeve = 0.95。
optimizer 在 sleeve 上输出 MaxDiv raw 权重 w_sleeve（Σ=1，仅 10 个投资槽位）。
最终 total NAV 权重:
  operational_cash: 0.05
  sleeve asset i   : w_sleeve[i] × 0.95

sleeve 内约束（由 total-NAV cap 变换）:
  per-asset cap (除 CASH_LIKE/CN_DURATION 外所有 risk asset):
      w_sleeve[i] <= (0.25 - 0)/0.95            # 保留 total-NAV 25% 语义
  CASH_LIKE: w_sleeve[CASH_LIKE] <= cap_CL_total / 0.95
  CN_DURATION: w_sleeve[CN_DURATION] <= cap_CD_total / 0.95
  防御性合计: w_sleeve[CASH_LIKE] + w_sleeve[CN_DURATION]
      <= (cap_def_total - 0.05) / 0.95
  growth group (CHINEXT+STAR): sum(w_sleeve[growth]) <= 0.50/0.95   # 保留 total-NAV 50%

实例（M1-M3 sleeve 内上限）:
  M1: CASH_LIKE <= 5/95 = 5.263%；CN_DURATION <= 20/95 = 21.053%；
      防御合计 <= (30-5)/95 = 26.316%；per-asset <= 25/95 = 26.316%
  M2: CASH_LIKE <= 5/95 = 5.263%；CN_DURATION <= 15/95 = 15.789%；
      防御合计 <= (25-5)/95 = 21.053%；per-asset <= 26.316%
  M3: CASH_LIKE = 0；CN_DURATION <= 15/95 = 15.789%；
      防御合计 <= (20-5)/95 = 15.789%；per-asset <= 26.316%
  M0: sleeve fraction = 1.0（无 op cash），退化为现有 RiskOverlayV0（per-asset 25% +
      growth 50%），CASH_LIKE/CN_DURATION <= 25% 即现有 per-asset cap。

投影器: 扩展 RiskOverlayV0 为支持 (i) per-slot cap 数组（total-NAV 分数 → /sleeve_fraction 转 sleeve），
  (ii) 可选的防御性合计 cap（CASH_LIKE+CN_DURATION 组 cap），bounded-simplex waterfill 后对
  防御组再缩放（同现有 growth 组处理）；约束不可行 → 抛 InfeasibleConstraints（不静默放松）。
  投影作用于 rebalance target weights（同现有 V1 语义）。M0 时与现有 RiskOverlayV0 完全一致。
```

# 6. Operational-cash 历史记账规则（冻结）

```text
固定 operational-cash sleeve 的历史收益代理 = 已接受 CASH_LIKE 研究收益序列（load_research_adj
CASH_LIKE 槽），sleeve 保持在 MaxDiv 优化器之外（不参与优化）。
历史可比较性：5% op-cash sleeve 用 CASH_LIKE 研究序列；战略 CASH_LIKE cap 下的配置亦用 CASH_LIKE
研究序列（同基准），CN_DURATION 用 CN_DURATION 研究序列。op_cash + CASH_LIKE 合计权重对总收益的
贡献 = 各自权重 × 各自研究序列收益。

forward sanity（见 §8）: 当前 1.4% 现金收益率 = 用户规划假设，明确标注；不追溯改写历史收益。
```

# 7. 无 expected-return 优化 / 研究-执行分离

```text
优化器内不引入任何 expected-return 模型（§2 清单）。forward-return 工作为 audit-only，非优化器输入。
研究/执行分离：
  1. 主要历史参考 = 已接受 L1 11 经济槽位研究路径；
  2. 不声称已停止的 11-instrument 执行映射 live-ready；
  3. 本 PREP 不选择替代 ETF/universe；
  4. 任何可执行 universe 重设计 = 本概念评审后的独立 fresh PREP。
```

# 8. Forward-return sanity audit（冻结 schema，RUN 时执行；sanity diagnostic only）

```text
RUN 时冻结 dated assumption snapshot（含来源/provenance）:
  - operational/strategic cash yield：用户规划假设，当前 1.4%（明确标注为规划假设，非实测）
  - 当前 CN_DURATION yield/YTM 代理：来自有文档来源的快照（RUN 时绑定）

不发明股票预期收益。计算达到各组合目标所需的残余风险资产 sleeve 年化收益:
  required_risk_return(T) = (T - defensive_carry_contribution) / risk_asset_weight

其中:
  defensive_carry_contribution = op_cash_w × cash_yield + CASH_LIKE_w × cash_yield
                                  + CN_DURATION_w × duration_yield   （按候选冻结配置权重）
  risk_asset_weight = 1 - (op_cash_w + CASH_LIKE_w + CN_DURATION_w)

对 M0-M3 报告 T = 7%, 8%, 9% 的 required_risk_return。这是跨候选 sanity 诊断，
用于回答"低防御性收益率下候选能否合理达到 7/8/9% 组合收益"，非优化器输入、非胜者选择。
```

# 9. 历史评估计划（冻结）

```text
主评估 = 已接受 L1 确定性长区间窗口 + 精确因果语义（§3）。
每 M0-M3 至少报告:
  - cumulative return / calendar CAGR / active-day annualized return / annualized volatility
  - Sharpe / Sortino / MaxDD / Calmar
  - worst calendar year / worst rolling 12m return
  - calendar-year subperiod metrics / 已接受 frozen stress/phase subperiod metrics
  - turnover / traded-notional proxy（与研究路径一致）
  - mean / median / p95 of (operational_cash + CASH_LIKE + CN_DURATION)
  - cap-hit rate：CASH_LIKE / CN_DURATION / 防御性合计 cap
  - latest target allocation / allocation time series（供后续执行研究）
资本效率诊断（冻结公式，跨候选一致）:
  - CE_current_hurdle = (historical_CAGR - current_cash_hurdle) / |MaxDD|
    （同一 frozen current cash hurdle 用于全部候选；标注为 cross-candidate diagnostic，
      非 stationary historical Sharpe 替代）
  - CAGR gained/lost per 10ppt reduction in average defensive allocation vs M0
  - MaxDD increase per 10ppt reduction in average defensive allocation vs M0
```

# 10. Pre-registered viability 判据（screening only，非胜者选择/调优许可）

```text
候选 HISTORICALLY_VIABLE_FOR_NEXT_PREP 当且仅当 ALL 成立:
  1. calendar CAGR >= 7.0%
  2. Sharpe >= 1.20
  3. MaxDD >= -12.0%
  4. Calmar >= 0.70
  5. CAGR 不差于 M0 超过 0.5 个百分点
  6. worst calendar-year 或 frozen-stress CAGR degradation vs M0 不差于 -5 个百分点
  7. turnover <= 1.5 × M0
  8. deterministic tests / provenance / parity 全部通过

M2 保持 principal challenger（无论 M1/M3 是否看起来更好）。RUN 必须报告全部候选与 Pareto tradeoff；
不允许 post-result cap search 或中间 cap 值。
STOP/FAIL 语义: 任一候选不满足全部 8 项 → 该候选不进入后续执行研究（fail-closed）；
  RUN 报告每个候选的逐项达标表与 Pareto 前沿。无 GO/NO-GO 阈值发明。
```

# 11. 延迟维度（本实验不合并）

```text
以下不得并入首个资本效率实验（可作为本概念评审后的独立门）:
  no-trade bands (1%/2%) / minimum-trade threshold 优化 / 09:35·TWAP·passive 执行策略 /
  替代 HK_DIVIDEND instrument 映射 / 新 universe 构建 / 动态防御性 cap / current-yield-aware 战术切换
```

# 12. 计划源文件/脚本/测试（RUN 授权后实现；PREP 阶段不实现）

```text
scripts/gate4_maxdiv_capital_efficiency.py      # M0-M3 runner（复用 L1 baseline policy +
                                                  RiskOverlayV0 扩展 + 研究路径指标 + CE 诊断）
src/china_etf/risk/risk_overlay.py               # 扩展 RiskOverlayV0CE（per-slot caps 数组 +
                                                  防御组 cap + sleeve 变换），M0 退化等价测试
tests/test_maxdiv_capital_efficiency.py          # 行为回归：
  - M0 parity == 已接受 L1 post_risk_weights（全 1011 日，确定性容差）
  - sleeve 变换: total-NAV cap → sleeve cap 公式（M1-M3 数值断言）
  - defensive cap-hit / 防御合计 cap 可行性
  - 无 expected-return / 无 RL token
  - provenance（输入 + L1 artifact SHA256 + commit）
```

# 13. 明确声明

```text
1. PREP only：不执行 CAPITAL_EFFICIENCY_RUN / NEW_BACKTEST / 结果生成；冻结契约后等评审。
2. 无 expected-return 优化器输入；无 BL/LDA/tactical/momentum forecast。
3. 无 result-informed cap search / window change / threshold change；M2 为 pre-designated 主挑战者。
4. 已停止的 execution-universe 映射（03110.HK）未被静默修复，也不视为 live-ready。
5. 1.4% 现金收益率为用户规划假设，明确标注，不追溯改写历史。
6. PPO/SAC/TD3 关闭；QMT live / FORWARD / PAPER / LIVE 禁止。
7. SCENARIO_NOT_STRICT_PIT_OOS：非 strict PIT OOS、非生产/实盘授权。
```

---

## Approval Record

```yaml
gate: POST_L2
handoff_id: G4_POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_PREP_001
packet: POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_PREP
status: READY_FOR_REVIEW
scope: PREP ONLY

frozen_candidates:
  M0: {op_cash: none, CASH_LIKE_cap: 0.25, CN_DURATION_cap: 0.25, def_cap: 0.50, sleeve: 1.0}
  M1: {op_cash: 0.05, CASH_LIKE_cap: 0.05, CN_DURATION_cap: 0.20, def_cap: 0.30, sleeve: 0.95}
  M2: {op_cash: 0.05, CASH_LIKE_cap: 0.05, CN_DURATION_cap: 0.15, def_cap: 0.25, sleeve: 0.95}  # principal
  M3: {op_cash: 0.05, CASH_LIKE_cap: 0.00, CN_DURATION_cap: 0.15, def_cap: 0.20, sleeve: 0.95}
  caps_unit: fraction of TOTAL NAV

frozen_core:
  maxdiv_120_0.5: true
  project_constrained_risk_overlay: true     # per-asset 25% + growth 50% total-NAV 语义保留
  deterministic_only: true
  no_momentum_blend: true
  no_expected_return_in_optimizer: true
  l1_reference_bound: true                   # results/raw artifact + commit + SHA256 绑定
  window: L1 (2022-06-09..2026-08-06, 1011 decision days)

frozen_accounting:
  op_cash_historical_proxy: accepted CASH_LIKE research series (outside optimizer)
  forward_cash_yield: 1.4% user planning assumption, labeled
  required_risk_return_formula: (T - defensive_carry) / risk_asset_weight, T = 7/8/9%

frozen_eval:
  metrics: full list per candidate (§9)
  viability: 8 pre-registered criteria (§10) -> HISTORICALLY_VIABLE_FOR_NEXT_PREP screening
  stop_semantics: fail-closed per candidate; no GO/NO-GO threshold invention
  m2_principal_pre_designated: true

not_authorized_until_prep_review:
  capital_efficiency_run: false
  new_backtest: false
  execution_universe_redesign: false
  instrument_substitution: false
  forward_paper_live_qmt_live: false
  result_informed_cap_search: false
  expected_return_optimization: false
  dense_dynamic_alpha: false
  ppo_sac_td3: false
  rl_retraining_tuning_comparison: false
```

## END OF POST_L2 MAXDIV LIVE CAPITAL EFFICIENCY PREP
