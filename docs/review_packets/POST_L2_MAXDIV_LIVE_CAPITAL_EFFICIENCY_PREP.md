# POST_L2 MAXDIV LIVE CAPITAL EFFICIENCY PREP — 资本效率概念研究契约冻结（PREP CORRECTION_002）

> 评审（`POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_PREP_CORRECTION_001_REVIEWER_RESPONSE.md`）
> **MAXDIV_LIVE_CAPITAL_EFFICIENCY_PREP_CORRECTION_001_NEARLY_ACCEPTED_FINAL_PROJECTION_SPEC_CLEANUP_REQUIRED** →
> 本版为 **PREP_CORRECTION_002**（窄契约清理 only，不实现、不运行 M0-M3）。
> 先期评审（`POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_PREP_REVIEWER_RESPONSE.md`）
> **MAXDIV_LIVE_CAPITAL_EFFICIENCY_PREP_CONTRACT_CLEANUP_REQUIRED**；先期授权
> （`POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_PREP_AUTHORIZATION.md`）
> **USER_SELECTED_FRESH_MAXDIV_LIVE_CAPITAL_EFFICIENCY_PREP_AUTHORIZED**。
> handoff_id = **G4_POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_PREP_CORRECTION_002_001**。

```yaml
decision: MAXDIV_LIVE_CAPITAL_EFFICIENCY_PREP_CORRECTION_001_NEARLY_ACCEPTED_FINAL_PROJECTION_SPEC_CLEANUP_REQUIRED
authorized_next: POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_PREP_CORRECTION_002
scope: PREP CORRECTION_002 ONLY (docs/contract; no CAPITAL_EFFICIENCY_RUN / no NEW_BACKTEST)
```

---

# 1. 研究问题

```text
已接受 MaxDiv core 稳健，但最新目标可将 ~50% NAV 置于 CASH_LIKE + CN_DURATION（当前现金/债券
远期收益率低时不可取）。测试简单的 ex-ante 资本预算约束能否在不显著损害 MaxDiv 稳健性的前提下
提升资本效率。新 pre-registered 研究，非已关闭 execution-realism STOP 实验的修改/重跑。
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

# 3. 已接受 L1 参考绑定（精确，无占位符）

```text
accepted L1 results artifact: artifacts/gate4_long_horizon_nonrl_results.json
  SHA256 = 917fe9663878990598a50ca13313beca7c4e367da2f7042234cb01fcfb6753a2
accepted L1 raw artifact    : artifacts/gate4_long_horizon_nonrl_raw.json
  SHA256 = e1b9b32b78f2adecc60134faec18720574536d8e0c04436ae91fdf5864719fe9
accepted L1 implementation commit: f039d369d94295433132e17cf981b2eb6243c17a
  （feat(gate4-long-horizon-nonrl): L1 runner + frozen contract + anti-lookahead tests）
已接受 L1 结果/packet commit（区别于 impl）: （L1 RUN packet 提交，若适用——PREP 记录其 hash；
  不将 impl commit 与 packet commit 混为一谈）

M0 parity 对比对象: 已接受 L1 post-risk target path 全 1011 x 11（raw artifact post_risk_weights）
  与已接受 metrics（results artifact MaximumDiversification.metrics）。

MaxDiv 参考 metrics (L1 accepted): cum +45.42% / CAGR 9.415% / active-ann 9.783% /
  vol 5.742% / Sharpe 1.655 / Sortino 2.195 / MaxDD -4.017% / Calmar 2.435 /
  worst cal-year 2022 (-0.39%) / worst rolling 12m +2.31% / mean_turnover 0.0114
MaxDiv 参考配置 (L1 accepted, post_risk): mean CASH_LIKE 0.25 / CN_DURATION 0.25 /
  defensive 0.50（处于 per-asset cap 上限——本研究的动机）

数据: 已接受 L1 11 经济槽位研究路径（load_research_adj）；L1 真实窗口
  决策 2022-06-09..2026-08-06 / 执行 2022-06-10..2026-08-07，1011 决策日；无新数据修复/backfill；
  无 result-informed 窗口变更。
```

# 4. 四个候选（M0-M3）— cap 全部为 TOTAL NAV 分数；**11 经济槽优化向量不变**

```text
canonical 表示（评审修正 #1）:
  - M1/M2/M3 优化器向量 = 原有 11 经济槽（含战略 CASH_LIKE 槽），保持槽顺序与维度；
  - 外部 5% operational-cash sleeve = 独立记账 sleeve，不替代战略 CASH_LIKE 经济槽；
  - M3 保持同一 11 槽向量，仅 CASH_LIKE cap = 0（不改变向量维度）。
  这保持跨候选 parity、槽顺序与确定性测试一致。

除声明的防御性资本变更外，保留 per-risk-asset 25% cap 与所有其他已接受 MaxDiv 语义。
cap 语义: 作用于 rebalance target weights（同 RiskOverlayV0 V1 语义）；actual 超限由下次再平衡纠正。
```

## M0 — legacy control（基准）

```text
- 无外部 operational-cash sleeve（optimizer 覆盖全部 total NAV）
- 现有 11-slot MaxDiv 120/0.5
- CASH_LIKE <= 25% / CN_DURATION <= 25%（total NAV；隐含于现有 per-asset 25% cap）
- 防御性资本（CASH_LIKE + CN_DURATION）可达 50%
- M0 必须复现已接受 L1 MaxDiv target path/metrics（确定性容差内）后，方可对比挑战者
```

## M1 — 轻资本效率约束

```text
- operational cash = 固定 5% of total NAV（独立记账 sleeve，optimizer 外）
- 战略 CASH_LIKE <= 5% of total NAV（优化器内，11 槽向量）
- CN_DURATION <= 20% of total NAV
- operational_cash + CASH_LIKE + CN_DURATION <= 30% of total NAV
- 剩余 95% investable sleeve 保持 MaxDiv 120/0.5，受变换后 total-NAV 约束
```

## M2 — principal challenger（pre-designated）

```text
- operational cash = 固定 5% of total NAV（独立记账 sleeve，optimizer 外）
- 战略 CASH_LIKE <= 5% of total NAV（优化器内，11 槽向量）
- CN_DURATION <= 15% of total NAV
- operational_cash + CASH_LIKE + CN_DURATION <= 25% of total NAV
- 剩余 95% investable sleeve 保持 MaxDiv 120/0.5
- M2 为主挑战者系设计指定，非基于任何观测结果；不得在见结果后重调这些数值
```

## M3 — 激进资本效率约束

```text
- operational cash = 固定 5% of total NAV（独立记账 sleeve，optimizer 外）
- 战略 CASH_LIKE = 0% of total NAV（11 槽向量，CASH_LIKE cap = 0，维度不变）
- CN_DURATION <= 15% of total NAV
- operational_cash + CASH_LIKE + CN_DURATION <= 20% of total NAV
- 剩余 95% investable sleeve 保持 MaxDiv 120/0.5
```

# 5. Total-NAV vs investable-sleeve 约束变换（精确契约）

```text
记号: total NAV = 1。M1-M3: operational_cash = 0.05（独立记账 sleeve，optimizer 外）；
investable sleeve = 0.95。optimizer 在 11 槽向量上输出 MaxDiv raw 权重 w_sleeve（Σ=1）。
最终 total NAV 权重:
  operational_cash: 0.05（独立，不属任何经济槽）
  slot i (含战略 CASH_LIKE / CN_DURATION): w_sleeve[i] × 0.95

sleeve 内约束（由 total-NAV cap 变换）:
  per-asset cap（11 槽全部）:
      w_sleeve[i] <= cap_total[i] / 0.95
  growth group (CHINEXT+STAR): sum(w_sleeve[growth]) <= 0.50/0.95   # 保留 total-NAV 50%
  defensive group (CASH_LIKE+CN_DURATION): w_sleeve[CASH_LIKE] + w_sleeve[CN_DURATION]
      <= (cap_def_total - 0.05) / 0.95                               # 排除外部 op-cash

实例（M1-M3 sleeve 内上限）:
  M1: CASH_LIKE <= 5/95 = 5.263%；CN_DURATION <= 20/95 = 21.053%；
      防御合计 <= (30-5)/95 = 26.316%；per-asset <= 25/95 = 26.316%
  M2: CASH_LIKE <= 5/95 = 5.263%；CN_DURATION <= 15/95 = 15.789%；
      防御合计 <= (25-5)/95 = 21.053%；per-asset <= 26.316%
  M3: CASH_LIKE = 0；CN_DURATION <= 15/95 = 15.789%；
      防御合计 <= (20-5)/95 = 15.789%；per-asset <= 26.316%
  M0: sleeve fraction = 1.0（无 op cash），退化为现有 RiskOverlayV0（per-asset 25% +
      growth 50%），CASH_LIKE/CN_DURATION <= 25% 即现有 per-asset cap。
```

# 6. 联合可行投影契约（评审修正 #2：非顺序组缩放）

```text
投影目标: 将 MaxDiv raw 权重投影到以下约束的 JOINT INTERSECTION（同时满足，非顺序）:
  C1 long-only: 0 <= w
  C2 simplex: sum(w) = 1
  C3 per-slot caps: w[i] <= cap[i]（11 槽全；M3 中 CASH_LIKE cap = 0）
  C4 growth-group cap: sum(w[CHINEXT+STAR]) <= growth_max
  C5 defensive-group cap: sum(w[CASH_LIKE+CN_DURATION]) <= def_max

唯一确定性投影算法（冻结，评审 CORRECTION_001 #1）:
  - 求解凸二次投影:
      min_w  0.5 * ||w - raw||_2^2
      s.t.   C1 long-only: w >= 0
             C2 simplex: sum(w) = 1
             C3 per-slot caps: w <= caps
             C4 growth 组 cap: sum(w[CHINEXT+STAR]) <= growth_max
             C5 defensive 组 cap: sum(w[CASH_LIKE+CN_DURATION]) <= def_max
  - 唯一命名方法（不得选用其他）: scipy.optimize.minimize(method='SLSQP')，
    初值 = bounded-simplex waterfill（= 现有 RiskOverlayV0 第一步），
    constraints: C1-C5（等式 + 不等式）；目标 = 0.5*||w-raw||^2。
  - 固定容差与迭代:
      max_iter = 200（SLSQP 迭代上限）；ftol = 1e-12；xtol 默认；容差 atol=1e-6（终检）。
  - 收敛/KKT/可行性 fail-closed:
      - 若求解器返回非收敛状态（slsqp 迭代达上限未收敛）→ InfeasibleConstraints
        （fail-closed，不静默接受近似可行点）
      - 终检（final simultaneous assertions）全部必须通过:
          sum(w) ≈ 1（atol 1e-6）
          w >= -1e-9 且 w <= caps + 1e-6（逐槽）
          growth 组和 <= growth_max + 1e-6
          defensive 组和 <= def_max + 1e-6
      - 任一终检失败 → InfeasibleConstraints（fail-closed，不静默放松）
      - KKT 检查: 计算拉格朗日残差 max|w - P_C(w - grad)| 在投影算子 P_C 下
        <= 1e-6（该式在收敛点成立）；不满足 → fail-closed
  - 无 fallback：不得在观测失败/结果后切换到另一投影方法。
  - M0 路径: M0 严格走现有 legacy RiskOverlayV0 精确路径（waterfill 仅 C1-C3），
    不路由经上述 QP 求解器（避免数值差异）。M0 parity = 已接受 L1 post_risk_weights
    全 1011 x 11 逐元素一致（max |diff| <= 1e-9，预冻结容差）。
  - M1-M3 走上述 QP 投影；M0 与 M1-M3 的投影器分离但共享契约。

行为测试（RUN 授权后实现，PREP 阶段仅契约）:
  - M0 parity == 已接受 L1 post_risk_weights（全 1011 x 11，max|diff| <= 1e-9）
  - 合成：growth 与 defensive 两组 cap 同时 binding 的可行情形 → 投影满足 C1-C5 全部，
    且为最小距离投影（独立参考/解析断言: 与已知封闭解/二分法解比较，非仅可行性）
  - 独立最小距离断言（非仅可行性）: 构造已知最优的合成用例（如只 2 个 active cap、
    可解析解），断言投影点 == 解析最小距离投影点（容差内）
  - 合成：真不可行情形（caps 之和 < 1）→ InfeasibleConstraints
  - 确定性重复性: 同输入两次运行输出逐元素一致
  - 数值 cap 断言：M1-M3 sleeve 内 CASH_LIKE / CN_DURATION / 防御合计上限精确
```

# 7. 历史收益/成本/因果记账（评审修正 #5，与已接受 L1 引擎一致）

```text
M0-M3 全部使用与已接受 L1 相同的引擎（保证 M0 parity 有意义）:
  - 因果约定: T 决策 -> T+1 执行/收益（T->T+1 research return path）
  - 公司行为语义: 同已接受 L1（total-return 指数；可执行路径公司行为不在此概念研究，
    仅研究收益路径）
  - 成本: 已接受 L1 标注的 1x MainlandETFCostModel research simplification（非无成本
    直接收益，非可执行 Southbound/日期有效成本模型）
  - 状态: RESEARCH (non-executable)；非 execution-realism / 非 live-ready

5% operational-cash sleeve 记账（M1-M3 一致，明确简化标注）:
  - 每次决策/再平衡 target operational cash = 5% of TOTAL NAV
  - T 目标持有 earn 已接受 CASH_LIKE 的 T->T+1 research return proxy
  - 计入 total-NAV 收益与配置统计；但不参与 MaxDiv covariance/优化
  - 进入研究 turnover / traded-notional proxy 的规则（冻结）:
    op-cash 为固定权重，不产生 rebalance 交易；其 traded-notional 贡献 = 0。
    该简化跨 M1-M3 一致标注。strategic CASH_LIKE/CN_DURATION 槽位正常计入 turnover。
  - 明确: 这是 research simplification，不声称 live 执行可行性
```

# 8. Forward-return sanity audit（评审修正 #3：用实际候选配置，非 cap）

```text
RUN 时冻结 dated assumption snapshot（含来源/provenance）:
  - operational/strategic cash yield：用户规划假设，当前 1.4%（明确标注为规划假设，非实测）
  - 当前 CN_DURATION yield/YTM 代理：来自有文档来源的快照（RUN 时绑定）

主计算（primary）用每个候选的 RUN 实际 latest post-risk TOTAL-NAV target weights:
  defensive_w = op_cash + strategic CASH_LIKE + CN_DURATION   （实际权重，非 cap）
  risk_asset_w = 1 - defensive_w
  defensive_carry_contribution = op_cash × cash_yield + strategic_CASH_LIKE × cash_yield
                                  + CN_DURATION × duration_yield   （实际权重）
  required_risk_return(T) = (T - defensive_carry_contribution) / risk_asset_w
  对 M0-M3 报告 T = 7%, 8%, 9% 的 required_risk_return（用实际 latest 权重 + dated snapshot）。

separate at-cap stress diagnostic（允许，但明确标注，不替代主计算、不成为选择判据）:
  在防御性权重达 cap 的边界情形下重复上述计算（labeled "at-cap stress, diagnostic only"）。
sanity audit only；非优化器输入、非胜者选择。
```

# 9. 历史评估计划（冻结）

```text
主评估 = 已接受 L1 确定性长区间窗口 + 精确因果语义（§3/§7）。
每 M0-M3 至少报告:
  - cumulative return / calendar CAGR / active-day annualized return / annualized volatility
  - Sharpe / Sortino / MaxDD / Calmar
  - worst calendar year / worst rolling 12m return
  - calendar-year subperiod metrics / 已接受 frozen stress/phase subperiod metrics
  - turnover / traded-notional proxy（与研究路径一致；op-cash 贡献 0 标注）
  - mean / median / p95 of (operational_cash + CASH_LIKE + CN_DURATION)
  - cap-hit rate：CASH_LIKE / CN_DURATION / 防御性合计 cap（target 达 cap 的比例）
  - latest target allocation（total-NAV 权重）/ allocation time series（供后续执行研究）
```

# 10. 资本效率诊断（冻结公式；评审修正 #5 精确化）

```text
CE_current_hurdle = (historical_CAGR - current_cash_hurdle) / |MaxDD|
  - current_cash_hurdle = 同一 frozen current cash yield（1.4% 规划假设）用于全部候选
  - 标注为 cross-candidate diagnostic，非 stationary historical Sharpe 替代

CAGR gained/lost per 10ppt reduction in average defensive allocation vs M0:
  delta_CAGR_per_10ppt = (CAGR_candidate - CAGR_M0) / (def_M0 - def_candidate) × 0.10
  其中 def_X = mean over time of (op_cash + CASH_LIKE + CN_DURATION) for X
  单位: percentage points of CAGR per 10 percentage-point defensive reduction。

MaxDD magnitude increase per 10ppt reduction in average defensive allocation vs M0
（评审 CORRECTION_001 #2 符号约定）:
  delta_MaxDD_magnitude_per_10ppt =
      (abs(MaxDD_candidate) - abs(MaxDD_M0)) / (def_M0 - def_candidate) × 0.10
  - 标注为 drawdown-magnitude increase（绝对值增量）；
  - signed difference（MaxDD_candidate - MaxDD_M0，带符号）如需要可单独报告，
    但不得标注为 magnitude increase。

零分母处理（冻结）:
  - 若 |def_M0 - def_candidate| < 1e-9（无防御性配置变化）:
      delta_CAGR_per_10ppt = NaN（标注 N/A：无防御性下降）；
      delta_MaxDD_magnitude_per_10ppt = NaN。
  - 不除以零；NaN 明确标注，不参与候选比较。
```

# 11. Pre-registered viability 判据（评审修正 #5：criterion 6 精确化）

```text
候选 HISTORICALLY_VIABLE_FOR_NEXT_PREP 当且仅当 ALL 成立:
  1. calendar CAGR >= 7.0%
  2. Sharpe >= 1.20
  3. MaxDD >= -12.0%
  4. Calmar >= 0.70
  5. CAGR 不差于 M0 超过 0.5 个百分点（CAGR_candidate - CAGR_M0 >= -0.005）
  6. min matched CAGR degradation across ALL 5 calendar-year segments + 2 frozen stress
     segments: min_seg(CAGR_candidate_seg - CAGR_M0_seg) >= -0.05
     （即每一段 matched segment 均须 >= -5pct；取所有 7 段中最差者）
  7. turnover <= 1.5 × M0
  8. deterministic tests / provenance / parity 全部通过

M2 保持 principal challenger（无论 M1/M3 是否看起来更好）。RUN 必须报告全部候选与 Pareto
tradeoff；不允许 post-result cap search 或中间 cap 值。
STOP/FAIL 语义: 任一候选不满足全部 8 项 → 该候选不进入后续执行研究（fail-closed）；
  RUN 报告每个候选的逐项达标表与 Pareto 前沿。无 GO/NO-GO 阈值发明。
```

# 12. 延迟维度（本实验不合并）

```text
以下不得并入首个资本效率实验（可作为本概念评审后的独立门）:
  no-trade bands (1%/2%) / minimum-trade threshold 优化 / 09:35·TWAP·passive 执行策略 /
  替代 HK_DIVIDEND instrument 映射 / 新 universe 构建 / 动态防御性 cap / current-yield-aware 战术切换
```

# 13. 计划源文件/脚本/测试（RUN 授权后实现；PREP 阶段不实现）

```text
scripts/gate4_maxdiv_capital_efficiency.py      # M0-M3 runner（复用 L1 baseline policy +
                                                  RiskOverlayV0CE 扩展 + 研究路径指标 + CE 诊断 +
                                                  forward sanity）
src/china_etf/risk/risk_overlay.py               # 扩展 RiskOverlayCE（per-slot caps 数组 +
                                                  growth 组 cap + defensive 组 cap + sleeve 变换 +
                                                  joint-feasible 投影），M0 退化等价测试
tests/test_maxdiv_capital_efficiency.py          # 行为回归：
  - M0 parity == 已接受 L1 post_risk_weights（全 1011 x 11，确定性容差）
  - sleeve 变换: total-NAV cap -> sleeve cap 公式（M1-M3 数值断言）
  - joint projection: growth+defensive 双组 cap 同时 binding 可行情形 + 真不可行情形
    (InfeasibleConstraints)
  - defensive cap-hit / 防御合计 cap 可行性
  - forward sanity 用实际 latest 权重（非 cap）
  - CE per-10ppt 公式 + 零分母 NaN
  - criterion 6 用 5 年度 + 2 stress 段 min degradation
  - 无 expected-return / 无 RL token
  - provenance（输入 + L1 artifact SHA256 + commit）
```

# 14. 明确声明

```text
1. PREP CORRECTION only：不执行 CAPITAL_EFFICIENCY_RUN / NEW_BACKTEST / 结果生成；
   契约修正后等评审。
2. 无 expected-return 优化器输入；无 BL/LDA/tactical/momentum forecast。
3. 无 result-informed cap search / intermediate cap values / window change / threshold change；
   M2 为 pre-designated 主挑战者。
4. 已停止的 execution-universe 映射（03110.HK）未被静默修复，也不视为 live-ready。
5. 1.4% 现金收益率为用户规划假设，明确标注，不追溯改写历史。
6. M0-M3 历史比较保留已接受 L1 T->T+1 因果引擎 + 公司行为语义 + 1x MainlandETFCostModel
   research simplification，保证 M0 parity 有意义。
7. PPO/SAC/TD3 关闭；QMT live / FORWARD / PAPER / LIVE 禁止。
8. SCENARIO_NOT_STRICT_PIT_OOS：非 strict PIT OOS、非生产/实盘授权。
```

---

## Approval Record

```yaml
gate: POST_L2
handoff_id: G4_POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_PREP_CORRECTION_002_001
packet: POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_PREP
status: READY_FOR_REVIEW
scope: PREP CORRECTION_002 ONLY

prep_correction_002_applied (2, reviewer FINAL_PROJECTION_SPEC_CLEANUP):
  unique_joint_projection_frozen: true  # convex QP min 0.5||w-raw||^2 s.t. C1-C5, SLSQP named;
                                        # max_iter 200 / ftol 1e-12 / atol 1e-6; KKT + feasibility
                                        # fail-closed; no fallback after results
  m0_legacy_path_preserved: true        # M0 严格走现有 RiskOverlayV0（waterfill C1-C3），
                                        # 不路由经 QP 求解器；M0 parity all-1011-day <= 1e-9
  min_distance_projection_test: true    # 独立参考/解析最小距离断言（非仅可行性）
  maxdd_sign_convention_fixed: true     # delta_MaxDD_magnitude = (abs(MaxDD_cand)-abs(MaxDD_M0))/
                                        # (def_M0-def_cand)*0.10；signed diff 单独报告

prep_corrections_applied (5 reviewer groups / 11 items):
  canonical_11_slot_vector: true    # M1/M2/M3 保留 11 经济槽优化向量；op-cash 独立记账 sleeve；
                                    # M3 CASH_LIKE cap=0 维度不变
  joint_feasible_projection: true   # 唯一确定性凸 QP 投影 (SLSQP, min 0.5||w-raw||^2, C1-C5)；
                                    # 固定容差/迭代/KKT fail-closed；无 fallback；
                                    # 行为测试含双组 cap binding + 真不可行 + M0 parity +
                                    # 独立最小距离断言
  forward_sanity_actual_weights: true  # 用 RUN 实际 latest post-risk total-NAV 权重；at-cap
                                    # 仅 labeled stress diagnostic
  l1_reference_bound_exact: true    # results/raw SHA256 (917fe96/e1b9b32) + impl commit
                                    # f039d369... + 无占位符
  historical_engine_frozen: true    # L1 T->T+1 因果 + CA 语义 + 1x Mainland 简化；M0 parity 有意义
  op_cash_accounting: true          # 5% target at each decision; earns CASH_LIKE T->T+1 proxy;
                                    # in NAV/alloc stats, excluded from cov/optimization;
                                    # turnover contribution = 0 (labeled)
  ce_formulas_exact: true           # CE_current_hurdle + CAGR per-10ppt + MaxDD magnitude
                                    # per-10ppt (abs convention) + 零分母 NaN
  criterion6_min_matched_degradation: true  # 5 年度 + 2 stress 段 min(CAGR_cand_seg - M0_seg) >= -0.05

frozen_candidates:
  M0: {op_cash: none, CASH_LIKE_cap: 0.25, CN_DURATION_cap: 0.25, def_cap: 0.50, sleeve: 1.0}
  M1: {op_cash: 0.05, CASH_LIKE_cap: 0.05, CN_DURATION_cap: 0.20, def_cap: 0.30, sleeve: 0.95}
  M2: {op_cash: 0.05, CASH_LIKE_cap: 0.05, CN_DURATION_cap: 0.15, def_cap: 0.25, sleeve: 0.95}  # principal
  M3: {op_cash: 0.05, CASH_LIKE_cap: 0.00, CN_DURATION_cap: 0.15, def_cap: 0.20, sleeve: 0.95}
  caps_unit: fraction of TOTAL NAV; 11-slot optimizer vector for M1/M2/M3 (op_cash separate)

frozen_core:
  maxdiv_120_0.5: true
  project_constrained_risk_overlay: true     # per-asset 25% + growth 50% total-NAV 语义保留
  deterministic_only: true
  no_momentum_blend: true
  no_expected_return_in_optimizer: true
  l1_reference_bound: {results_sha256: 917fe9663878990598a50ca13313beca7c4e367da2f7042234cb01fcfb6753a2,
                       raw_sha256: e1b9b32b78f2adecc60134faec18720574536d8e0c04436ae91fdf5864719fe9,
                       impl_commit: f039d369d94295433132e17cf981b2eb6243c17a}
  window: L1 (2022-06-09..2026-08-06, 1011 decision days)
  historical_engine: L1 T->T+1 causal + CA semantics + 1x MainlandETFCostModel research simplification

frozen_accounting:
  op_cash_historical_proxy: accepted CASH_LIKE research series (outside optimizer)
  op_cash_target: 5% of total NAV at each decision/rebalance
  op_cash_turnover_contribution: 0 (fixed weight; labeled)
  forward_cash_yield: 1.4% user planning assumption, labeled
  required_risk_return_formula: (T - defensive_carry_actual) / risk_asset_w_actual, T = 7/8/9%

frozen_eval:
  metrics: full list per candidate (§9)
  ce_diagnostics: CE_current_hurdle + CAGR per-10ppt + MaxDD magnitude per-10ppt
                  (abs convention, exact formulas, zero-denominator NaN)
  viability: 8 pre-registered criteria (§11); criterion 6 = min matched CAGR degradation
             across 5 calendar years + 2 stress segments
  stop_semantics: fail-closed per candidate; no GO/NO-GO threshold invention
  m2_principal_pre_designated: true

not_authorized_until_prep_review:
  capital_efficiency_run: false
  new_backtest: false
  result_informed_cap_search: false
  intermediate_cap_values: false
  execution_universe_redesign: false
  instrument_substitution: false
  no_trade_band_search: false
  execution_time_optimization: false
  forward_paper_live_qmt_live: false
  expected_return_optimization: false
  dense_dynamic_alpha: false
  ppo_sac_td3: false
  rl_retraining_tuning_comparison: false
```

## END OF POST_L2 MAXDIV LIVE CAPITAL EFFICIENCY PREP (PREP_CORRECTION)
