# POST_L2 DETERMINISTIC ARCHITECTURE RUN — MaxDiv × Momentum 静态混合架构结果

> 评审（`POST_L2_DETERMINISTIC_ARCHITECTURE_PREP_CORRECTION_REVIEWER_RESPONSE.md`）
> **ARCH_PREP_CORRECTION_ACCEPTED_FROZEN_RUN_AUTHORIZED** → 本 packet 报告单次冻结架构 RUN。
> handoff_id = **G4_POST_L2_DETERMINISTIC_ARCH_RUN_001**。

```yaml
implementation_commit: d31e384   # scripts/gate4_arch_blend.py + tests/test_arch_blend.py
result_artifact: artifacts/gate4_arch_blend_results.json + _raw.json（commit=d31e384）
parent_code_commit: 7781800   # L2 gen3 父实现（冻结）
handoff: G4_POST_L2_DETERMINISTIC_ARCH_RUN_001
label: POST_L2_DETERMINISTIC_ARCHITECTURE
scenario_not_strict_pit_oos: true
```

---

# 1. 冻结契约执行证据

```text
候选：C0=100% MaxDiv, C1=100% Momentum, C2=75/25, C3=50/50, C4=25/75（评审冻结，未增删）
混合语义：w_final = RiskOverlayV0(alpha*w_maxdiv + (1-alpha)*w_mom)；成本/换手在最终可执行路径
父策略：MaxDiv 120/0.5 project-constrained；Momentum 252/21 positive-score（未改）
面板：同一 11 槽位、2800 区间 Track-C、signal/return 分离、CNY HK FX、stress regimes（未改）
C0/C1 parity：确定性重建 + 断言与 gen3 精确 metrics parity —— 全部 0 diff（见 §3）
post-overlay 违规：全候选 = 0（pre 违规 0/1958/235/830/1474 → post 全消）
```

# 2. 全期结果表（2800 研究收益区间，无成本主表）

| 指标 | C0 MaxDiv 100% | C1 Mom 100% | C2 75/25 | C3 50/50 | C4 25/75 |
|---|---|---|---|---|---|
| 累计收益 | +94.6% | +153.1% | +112.4% | +124.3% | +140.8% |
| Calendar CAGR | **+6.0%** | +8.4% | +6.8% | +7.3% | +7.9% |
| active-day 年化 | +6.2% | +8.7% | +7.0% | +7.5% | +8.2% |
| 年化波动 | **6.0%** | 17.3% | 8.7% | 11.7% | 14.6% |
| Sharpe | **1.024** | 0.571 | 0.827 | 0.678 | 0.614 |
| Sortino | **1.280** | 0.639 | 0.974 | 0.772 | 0.690 |
| MaxDD | **-10.4%** | -44.3% | -18.5% | -28.9% | -37.5% |
| Calmar | **0.595** | 0.197 | 0.380 | 0.261 | 0.219 |
| worst 日历年 | 2022 -6.6% | 2018 -10.4% | 2022 -5.8% | 2022 -7.0% | 2018 -8.0% |
| worst 12m 滚动 | **-9.1%** | -35.2% | -10.6% | -20.4% | -28.8% |
| mean turnover | 0.68% | 6.78% | 2.35% | 4.11% | 5.54% |
| mean HHI | 0.169 | 0.168 | 0.142 | 0.138 | 0.148 |
| max single weight | 25.0% | 25.0% | 25.0% | 25.0% | 25.0% |
| pre-overlay viol | 0 | 1958 | 235 | 830 | 1474 |
| post-overlay viol | 0 | 0 | 0 | 0 | 0 |

# 3. C0/C1 parity（评审冻结，全 0 diff → PASS）

```text
C0_vs_gen3: {calendar_cagr 0.0, max_drawdown 0.0, sharpe 0.0, cum_return 0.0}  pass=True
C1_vs_gen3: {calendar_cagr 0.0, max_drawdown 0.0, sharpe 0.0, cum_return 0.0}  pass=True
→ 重建的父基线精确复现 gen3，未静默创建新父语义。
```

# 4. 成功准则评估（冻结 R1-R6，ex-ante）

基线：C0_cagr = 0.059496、C0_mdd = -0.103874。R1 阈值 = 0.064496 CAGR；R2 阈值 = -0.153874 MaxDD。

| 候选 | R1 (cagr+0.5pct) | R2 (mdd≥-15.4%) | R3 (Sharpe≥0.8 & Calmar≥0.4) | R4 (cost≥-3pct) | Pareto 支配 | 通过全部 |
|---|---|---|---|---|---|---|
| C0 MaxDiv | ✗（自身基线） | ✓ | ✓ | ✓ | — | ✗（R1 定义不适用） |
| C1 Momentum | ✓ | ✗ (-44.3%) | ✗ (0.57/0.20) | ✗ (-16.3pct) | — | ✗ |
| C2 75/25 | ✓ | ✗ (-18.5%) | ✗ (0.83/0.38) | ✗ (-4.8pct) | 无 | **✗** |
| C3 50/50 | ✓ | ✗ (-28.9%) | ✗ (0.68/0.26) | ✗ (-8.8pct) | 无 | **✗** |
| C4 25/75 | ✓ | ✗ (-37.5%) | ✗ (0.61/0.22) | ✗ (-12.7pct) | 无 | **✗** |

```text
结论（ex-ante 判定，无 result-informed 调整）：
1. 静态混合 C2-C4 均未通过 R1-R4（每个都在 MaxDD 与/或成本上失败）：
   - R2：混合 MaxDD -18.5% ~ -37.5%，全部低于 -15.4% 阈值（Momentum 权重越高越深）；
   - R3：仅 C2 的 Sharpe 0.83 ≥0.80 但 Calmar 0.38 <0.40；C3/C4 两者均不达标；
   - R4：混合换手上升（2.4-5.5%）→ 1x 成本 cum Δ -4.8 ~ -12.7pct，均超 -3pct 容忍。
2. 无候选被 Pareto 支配（C2-C4 在 cum/CAGR 上优于 C0，在 Sharpe/MaxDD 上劣于 C0——
   Pareto frontier 上不同点，非支配关系）。
3. 按冻结判定：静态 alpha 混合未产生"有用架构"（无候选满足 R1-R4）。
   → 架构结论 = 纯 MaxDiv（C0）保持风险控制核心；Momentum 加仓以显著回撤/成本恶化为代价，
     静态混合不优于核心。无 result-informed 调整。
```

# 5. 成本敏感性（1x Mainland 近似，final executable path，labeled non-executable）

| 候选 | 无成本 cum | 1x 净 cum | cum Δ | 1x 净年化 | 估算成本/初始 |
|---|---|---|---|---|---|
| C0 MaxDiv | +94.6% | +93.4% | **-1.3pct** | +6.12% | 0.67% |
| C1 Momentum | +153.1% | +136.8% | -16.3pct | +8.08% | 6.64% |
| C2 75/25 | +112.4% | +107.6% | -4.8pct | +6.77% | 2.31% |
| C3 50/50 | +124.3% | +115.4% | -8.8pct | +7.05% | 4.02% |
| C4 25/75 | +140.8% | +128.1% | -12.7pct | +7.55% | 5.43% |

# 6. 子期稳健性（pre-frozen stress regimes）

| 阶段 | C0 MaxDiv | C2 75/25 | C3 50/50 | C4 25/75 |
|---|---|---|---|---|
| 2015 crash MaxDD | ~-7% | ~-8% | ~-10% | ~-12% |
| 2018 bear MaxDD | ~-5% | ~-7% | ~-9% | ~-11% |
| COVID MaxDD | ~-8% | ~-9% | ~-10% | ~-11% |
| 2021-23 weak MaxDD | ~-10% | ~-15% | ~-21% | ~-27% |
| 2021-23 weak cum | +0.6% | ~-3% | ~-6% | ~-9% |

```text
混合越偏 Momentum，弱股期 2021-23 回撤越深、cum 转负 —— 印证 MaxDiv 核心的弱股期保护价值。
```

# 7. Interpretation 回应

```text
1. 静态混合是否带来风险调整改进？否。无候选满足 R1-R4；C0 保持唯一 Sharpe>1（1.024）且
   MaxDD 最小（-10.4%）。混合在 CAGR 上单调改善（+6.8→7.9%）但在 Sharpe（0.83→0.61）、
   MaxDD（-18.5→-37.5%）、成本（-4.8→-12.7pct）上单调恶化。
2. terminal-wealth 权衡（R6）：C2-C4 提升 CAGR 换取更低 Sharpe —— 但均未满足 R2/R3 底线
   （MaxDD 过深 / Calmar 过低），R6 不适用 → 不视为有效收益改进。
3. 架构建议：纯 MaxDiv 核心（C0）为风险调整最优；若追求 CAGR，Momentum 或混合需接受
   -18% 以上 MaxDD —— 该权衡由 R1-R6 预先冻结判定为不达标。无 result-informed 调整。
```

# 8. 明确声明

```text
1. 无 GO 阈值在观察结果后发明；判定全由冻结 R1-R6 驱动。
2. C0/C1 parity 到 gen3 全部 0 diff（父基线未漂移）。
3. 无 RL、无 dense/dynamic alpha、无 QMT live、无 result-informed 调整。
4. SCENARIO_NOT_STRICT_PIT_OOS：非 strict PIT OOS、非生产/实盘授权。
5. 架构 RUN 成功不授权 live；下一门（execution realism / forward / paper）需另评审。
```

---

## Approval Record

```yaml
gate: 4
handoff_id: G4_POST_L2_DETERMINISTIC_ARCH_RUN_001
packet: POST_L2_DETERMINISTIC_ARCHITECTURE_RUN
status: READY_FOR_REVIEW

executed:
  candidates: [C0 MaxDiv 100%, C1 Momentum 100%, C2 75/25, C3 50/50, C4 25/75]
  blend_semantics: w_final = RiskOverlayV0(alpha*maxdiv+(1-alpha)*mom); cost on final executable path
  window: 2800 intervals (2015-01-28..2026-08-07); 11 slots; CNY HK FX; signal/return separation
  c0_c1_parity: pass (all diffs 0.0 vs gen3)
  post_overlay_violations: 0 for all candidates

verdicts (ex-ante R1-R6, no result-informed):
  c0: {sharpe 1.024, mdd -10.4%, calmar 0.595}   # risk-control core, unique Sharpe>1
  c1: {cagr 8.4%, sharpe 0.571, mdd -44.3%}       # return engine, R2/R3/R4 fail
  c2-c4: all fail R1-R4 (mdd -18.5..-37.5%, cost -4.8..-12.7pct); none Pareto-dominated
  architecture_conclusion: static blends do NOT produce a useful architecture vs pure MaxDiv
                           (no candidate meets R1-R4); keep MaxDiv core; no result-informed tuning

no_rl: PPO/SAC/TD3 absent; no dense/dynamic alpha; QMT live forbidden
not_done: {instrument_execution_realism: false, forward_paper_validation: false, qmt_live: false}
```

## END OF POST_L2 DETERMINISTIC ARCHITECTURE RUN
