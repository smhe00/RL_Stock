# POST_L2 DETERMINISTIC ARCHITECTURE PREP — MaxDiv Core × Momentum Engine 共存架构（冻结契约，修正版）

> 评审（`POST_L2_DETERMINISTIC_ARCHITECTURE_PREP_REVIEWER_RESPONSE.md`）
> **ARCH_PREP_SUBSTANTIALLY_CORRECT_SEMANTIC_FIX_REQUIRED** → 本 packet 为**架构 PREP 修正**。
> **PREP only，不运行任何 combined-strategy 结果。** handoff_id = **G4_POST_L2_DETERMINISTIC_ARCH_PREP_CORRECTION_001**。

> ## Revision Record（ARCH_PREP_CORRECTION，评审 3 项语义修正 + 控制处理）
>
> 1. **HK FX 时序措辞修正**：明确 `return_level_hk_cny(t) = raw_hk_index_hkd(t) × hkd_cny(t)`
>    （**未 lag 的当日 CNY 经济水平**）；`signal_hk_cny(T) = return_level_hk_cny(T-1)`（含 T-1 HK + T-1 FX）；
>    `realized_return(决策 T) = return_level_hk_cny(T+1)/return_level_hk_cny(T) - 1`（CNY T→T+1）。
>    **不在 raw return-level 构造中插入 T-1 FX lag**（即信号/收益分离，与 FX 修正 L2 gen3 完全一致）。
> 2. **R4 成本不等式符号修正**：`cost_cum_delta = net_cum_return - gross_cum_return`（零或负），
>    R4 通过 iff `cost_cum_delta >= -3.0pct`（原写 `<= -3.0pct` 反向）。等价正拖累形式：
>    `cost_drag = gross - net`，R4 iff `cost_drag <= 3.0pct`。全 packet/runner/artifact/pass-fail 用同一约定。
> 3. **R1/R2 绑定精确 C0 值**（非舍入显示值）：gen3 C0 = `calendar_cagr 0.059496`、`max_drawdown -0.103874`。
>    R1: `candidate_cagr - 0.059496 >= 0.005`（阈值 = **0.064496**）；
>    R2: `candidate_mdd >= -0.103874 - 0.05`（阈值 = **-0.153874**）。显示可舍入，pass/fail 用精确值。
> 4. **C0/C1 控制处理**：采用"重建 + parity 断言"——用未变更的已接受实现确定性重建 C0/C1，
>    评估 C2-C4 前断言其 metrics 与 gen3 artifact 精确 parity（时序/fallback/FX/overlay 语义不变）。

---

# 0. 已接受上下文（固定输入，不重开）

```text
L2 FX 修正 gen3 已接受（GATE_4_LONG_HORIZON_PROXY_RUN_FX_FIX_RERUN）：
  MaxDiv：Calendar CAGR ~6.0%、Sharpe 1.024、MaxDD ~-10.4%（risk-control/core allocator）
  Momentum_12_1：Calendar CAGR ~8.4%、Sharpe 0.571、MaxDD ~-44.3%（long-horizon return engine）
  STAR Track-C basis-risk 警告（000986 vs 科创50 corr 0.1475）保持披露
  L1 frozen；PPO/SAC/TD3、QMT live 禁止
本 PREP 在见任何 combined 结果前冻结所有候选架构/阈值（评审要求）。
```

# 1. 父策略不可变（评审 §1）

```text
MaximumDiversification: lookback 120, shrinkage 0.5, project-constrained 实现（已接受）
Momentum_12_1: lookback 252, skip 21, positive-score weighting, accepted fallback semantics
同一 11 槽位、同一 signal timing（A股/利率 T，HK/US/GOLD/FX T-1）、同一 CNY/FX 处理
（HK = HKD × hkd_cny）、同一 RiskOverlayV0、同一 2800 区间 Track-C scenario 面板
无 proxy 替换、无参数搜索。
```

# 2. 候选架构集（评审 §2：小、有限、rationale-driven，非 dense sweep）

```text
静态 alpha 混合（sleeve weights 精确冻结；纯 MaxDiv / 纯 Momentum 为对照）：
  C0: MaxDiv 100%（对照，接受结果）
  C1: Momentum 100%（对照，接受结果）
  C2: alpha = 0.75（75% MaxDiv + 25% Momentum）
  C3: alpha = 0.50（50% / 50%）
  C4: alpha = 0.25（25% MaxDiv + 75% Momentum）
rationale：探索风险控制核（MaxDiv）与收益引擎（Momentum）之间 4 个离散加权点，
  覆盖核心偏重→平衡→收益偏重，避免任何 dense/efficient-frontier 搜索。
无动态架构（不做 dynamic-overlay 规则——若未来提出，须另 PREP 冻结公式/阈值/节奏）。
```

# 3. 精确混合语义（评审 §3）

```text
w_maxdiv(T) = 已接受可执行 MaxDiv target（决策 T）
w_mom(T)    = 已接受可执行 Momentum target（决策 T）
w_blend_raw(T) = alpha * w_maxdiv(T) + (1-alpha) * w_mom(T)
w_final(T)     = RiskOverlayV0(w_blend_raw(T))     # 在混合后统一 overlay
换手与成本在最终可执行权重路径上计算（非平均各自独立换手）。
```

# 4. 再平衡与时序契约（评审 §4）

```text
完全复用已接受 L2 时序路径（不更改）：
  decision cadence: 每交易日（2800 决策日）
  information cutoff: T 上海收盘；A股/利率 T，HK/US/GOLD/FX T-1（signal）
  CNY return-level treatment（修正，与 gen3 完全一致）:
    return_level_hk_cny(t) = raw_hk_index_hkd(t) × hkd_cny(t)   # 未 lag 的当日 CNY 经济水平
    signal_hk_cny(T)       = return_level_hk_cny(T-1)            # 决策 T 信号含 T-1 HK + T-1 FX
    realized_return(决策 T) = return_level_hk_cny(T+1)/return_level_hk_cny(T) - 1   # CNY T→T+1
    # 不在 raw return-level 构造中插入 T-1 FX lag（信号/收益分离保留）
  已实现收益: 决策 T 权重 → 原始 CNY 经济水平 T->T+1（return 面板无信号 lag）
  no lookahead: rolling cov/vol/momentum 只用 ≤T 决策可用输入
  missing-data/fallback: 与 L2 相同（ffill；方法 fallback → 1/N）
```

## 4b. C0/C1 控制处理（评审澄清）

```text
采用"确定性重建 + parity 断言"：用未变更的已接受实现（MaxDiv 120/0.5 project-constrained；
Momentum 252/21 positive-score）在架构 RUN 中重建 C0/C1，评估 C2-C4 前断言其 metrics 与
gen3 artifact 精确 parity（calendar_cagr 0.059496 / max_drawdown -0.103874 等）。若 parity
不通过 → stop condition（不得静默创建不同时序/fallback/FX/overlay 的新父基线）。
```

# 5. 评估表（评审 §5）

```text
每个候选 + 两个父对照报告：
  cumulative return / Calendar CAGR / active-day annualized return / annualized volatility /
  Sharpe / Sortino / MaxDD / Calmar / worst calendar year / worst rolling 12m return /
  mean turnover / 1x approximate cost sensitivity（cum Δ + est cost/initial）/
  average + maximum slot weights / HHI / post-overlay feasibility violations
  （预期 post=0；报告 pre/post 计数）
子期: 复用已接受 L2 pre-frozen stress regimes（2015 bull/crash、2018 bear、COVID、2021-23 weak、2024-26 strong）
  + 每候选每阶段 Sharpe/MaxDD。
```

# 6. Ex-ante 成功标准（评审 §6，冻结于见结果前）

```text
对每个候选，相对纯 MaxDiv（C0）定义评估准则。C0 绑定精确 gen3 值（非舍入显示值）：
  C0_calendar_cagr = 0.059496
  C0_max_drawdown  = -0.103874

  R1（收益改进）：candidate_calendar_cagr - C0_calendar_cagr >= 0.005
     即候选 calendar_cagr >= 0.064496（6.4496%）
  R2（回撤保护）：candidate_max_drawdown >= C0_max_drawdown - 0.05
     即候选 max_drawdown >= -0.153874（-15.3874%）
  R3（风险调整）：Sharpe >= 0.80 且 Calmar >= 0.40
  R4（成本容忍）：cost_cum_delta = net_cum_return - gross_cum_return（零或负）
     R4 通过 iff cost_cum_delta >= -0.03（-3.0pct）；等价 cost_drag = gross - net <= 0.03
  R5（Pareto）：若候选被任一父（C0 或 C1）Pareto 支配（在 cum/Sharpe/MaxDD 上全部不劣且至少一项更优）
    → 标记为 dominated，不作为推荐
  R6（terminal wealth vs Sharpe 权衡）：允许 terminal-wealth 改进换取更低 Sharpe 的情形——
    仅当该候选满足 R2/R3（回撤与风险调整底线），CAGR 提升才算有效。
决策：任一候选同时满足 R1-R4 且非 Pareto-dominated（R5）→ 视为"有用架构"候选。
  若所有候选均被父支配或未达 R1-R4 → 结论 = 静态混合无实质增益，架构建议保持纯 MaxDiv 核心
  （无 result-informed 调整）。
```

# 7. 禁止项（评审 §7）

```text
RUN 阶段禁止：
  扫描大量 alpha 选历史最优；在已接受 2015-2026 历史上优化 blend 权重；
  改变 MaxDiv/Momentum 参数；候选表现不佳时引入新信号；
  观察结果后更改 stress 期/成本/数据/槽位/proxy。
允许：pre-declared 有限候选集（本 packet §2）。
```

# 8. 下一阶段路径（评审 §8）

```text
即使架构 RUN 成功，也不授权 live trading。预期序列：
  architecture PREP（本 packet）
  -> 一次冻结 architecture RUN（后续评审授权）
  -> instrument-level execution realism
  -> forward/paper validation
  -> 仅此后才考虑小资金部署
```

# 9. 明确声明

```text
无 RL（PPO/SAC/TD3）、无超参/lookback 优化、无 QMT live。
L2 gen3 / L1 frozen 结果作为父策略输入，不重跑。
本 PREP 不运行 combined 结果；等评审批准后执行一次冻结 RUN。
```

---

## Approval Record

```yaml
gate: 4
handoff_id: G4_POST_L2_DETERMINISTIC_ARCH_PREP_CORRECTION_001
packet: POST_L2_DETERMINISTIC_ARCHITECTURE_PREP
status: READY_FOR_REVIEW

corrections_applied:
  hk_fx_timing: return_level_hk_cny(t)=raw_hk_hkd(t)*fx(t) unlagged; signal=return(T-1); realized=CNY T->T+1; no FX lag in return-level construction
  r4_sign: cost_cum_delta = net - gross; R4 passes iff >= -0.03 (was reversed)
  r1_r2_exact: C0 cagr 0.059496 (R1 threshold 0.064496), C0 mdd -0.103874 (R2 threshold -0.153874)
  c0_c1_control: reconstruct with unchanged accepted impl + parity assert to gen3 artifact before C2-C4

frozen:
  parents_immutable: {maxdiv: {lookback: 120, shrinkage: 0.5}, momentum: {lookback: 252, skip: 21}, same panel/overlay/timing/FX}
  candidates: [C0 MaxDiv 100%, C1 Momentum 100%, C2 alpha 0.75, C3 alpha 0.50, C4 alpha 0.25]
  blend_semantics: w_final = RiskOverlayV0(alpha*w_maxdiv + (1-alpha)*w_mom); cost on final executable path
  timing: reuse accepted L2 (T decision, T-1 non-A signal, CNY HK signal/return separation, T->T+1 realized)
  evaluation: full table + pre-frozen stress regimes
  success_criteria: {R1 candidate_cagr - 0.059496 >= 0.005, R2 candidate_mdd >= -0.153874, R3 Sharpe >= 0.80 & Calmar >= 0.40, R4 cost_cum_delta >= -0.03, R5 Pareto non-dominated, R6 terminal-wealth allowed only if R2/R3 hold}
  no_dense_search: small pre-declared set only; no result-informed tuning

not_done:
  architecture_run: false   # PREP only; wait for review
  result_informed_blend_search: false
  instrument_execution_realism: false
  forward_paper_validation: false
  qmt_live: false
  rl: false
```

## END OF POST_L2 DETERMINISTIC ARCHITECTURE PREP
