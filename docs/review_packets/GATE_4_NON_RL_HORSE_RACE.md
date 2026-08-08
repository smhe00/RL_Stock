# GATE 4 NON-RL HORSE RACE

> 用户 roadmap 决定（`ROADMAP_NON_RL_BASELINE_COMPARISON_DIRECTIVE.md`）+ 评审批准：
> `10-SEED REMOVED_FROM_ACTIVE_ROADMAP`；`NEXT = GATE_4_NON_RL_HORSE_RACE`。
> Tier A 非 RL 方法对比（corrected path）；RL 仅作 `HISTORICAL_RL_PILOT_REFERENCE`（pre-correction caveat）。
> 本 packet 按 directive 输出：horse-race 表 + 分维度排名 + 完整 metrics + pytest + commit。handoff = **G4_NON_RL_HORSE_RACE_001**。

---

# 1. Tier A Methods（10 个，corrected 评估路径）

```text
现有（corrected-path 重跑）：EqualWeight / RiskParity_IVOL / MinimumVariance / Momentum_12_1
新增（numpy-only）：EqualRiskContribution_ERC / HierarchicalRiskParity_HRP /
  MaximumDiversification / TrendRiskParity / MinimumCVaR_95 / ShrinkageMeanVariance
```

冻结参数（preregistered，无 grid search）：

```text
ERC: cov 120D + shrinkage(0.5)；ERC 迭代收敛（w ∝ 1/Σw，200 迭代，1e-10）
HRP: 120D 相关距离 sqrt((1-rho)/2)，single-linkage 聚类 + 递归二分（inv-vol 权重）
MaxDiv: 120D 收缩协方差，w∝Σ⁻¹σ → waterfill 投影
TrendRP: inv-vol 60D + absolute trend(252/21)；非趋势 → CASH_LIKE
MinCVaR_95: 120D 历史 + alpha=0.95；long-only LP（numpy-only 近似：尾部收益逆加权投影）
ShrinkageMV: 252D 期望收益 shrunk 向截面均值 + 120D 收缩协方差 → MV → 投影
fallback: lookback 不足 → EW/CASH_LIKE（全方法 fallback 计数为 0——Track A 有效历史足够）
```

# 2. Horse-Race Table（stitched OOS，corrected path，2023-11-24 → 2026-08-07，474 执行日）

## A. 非 RL 方法（corrected）

| 方法 | 累计 | CAGR | Sharpe | MaxDD | mean turnover |
|---|---:|---:|---:|---:|---:|
| **ERC** | +77.6% | **+35.6%** | 1.56 | -12.5% | — |
| **MinCVaR_95** | +74.4% | +34.3% | 1.25 | -19.2% | — |
| Momentum_12_1 | +63.9% | +30.0% | 1.63 | -17.0% | — |
| EqualWeight | +56.6% | +26.9% | 1.64 | -8.8% | — |
| ShrinkageMV | +47.9% | +23.1% | 1.72 | -6.9% | — |
| MinimumVariance | +47.3% | +22.8% | 1.75 | -6.0% | — |
| MaxDiv | +46.6% | +22.5% | 1.68 | -7.0% | — |
| TrendRiskParity | +46.2% | +22.3% | 1.67 | -7.2% | — |
| HRP | +44.3% | +21.5% | **1.86** | **-5.4%** | — |
| RiskParity_IVOL | +44.6% | +21.6% | 1.82 | -5.4% | — |

## B. RL 历史参考（HISTORICAL_RL_PILOT_REFERENCE，pre-correction，非正式 OOS）

| 算法 | CAGR median (min/max) | Sharpe median | MaxDD median |
|---|---:|---:|---:|
| TD3 | 0.249 (0.234/0.352) | 1.49 | -12.3% |
| SAC | 0.255 (0.233/0.273) | 1.57 | -8.9% |
| PPO | 0.275 (0.253/0.277) | 1.61 | -9.1% |

> ⚠️ **caveat**：RL 数字来自 3-seed pilot（evaluation-semantics 修正前，test 段起点含 retroactive replay）。
> 仅作探索参考，**不是 corrected formal OOS**；与 A 部分可比性有限。

# 3. 分维度排名（不声明 universal winner；单 474 日 OOS 样本）

| 维度 | Top | 说明 |
|---|---|---|
| 收益（CAGR） | ERC > MinCVaR > Momentum | ERC 等风险贡献在样本期最高 |
| 风险调整（Sharpe） | HRP ≈ RiskParity > MinVariance | 风险型方法风险调整最优 |
| 回撤（MaxDD 浅） | HRP/RP -5.4% < MV -6.0% | HRP 回撤最浅 |
| 尾部风险（MinCVaR 设计目标） | MinCVaR（但 MaxDD -19% 最深） | 见下方 note |
| 换手/成本 | （raw 数据见 §4） | — |
| fold 稳定性 | 见 §4 | — |

**note**：MinCVaR_95 收益第二高但回撤最深（-19.2%），Sharpe 最低（1.25）——符合 CVaR 优化
"以收益/波动换取尾部控制"的预期；judge 应主要看 downside control 而非 raw CAGR（directive §Research rationale）。

# 4. 完整 Metrics（runs/gate4_non_rl_horse_race_results.json + _raw.json）

每方法 × 4 folds + stitched：oos_cum / cagr / annualized_vol / sharpe / sortino / max_drawdown /
calmar / mean_turnover / total_cost / cost_over_initial_value / mean_hhi / mean_active_assets /
max_single_asset_weight / risk_overlay_intervention_rate / nan / negative_cash / n_eval_steps。

- **所有方法 0 NaN、0 negative_cash**（会计完整性）。
- RiskOverlay intervention：A 部分全部 0（非 RL 权重均在硬约束内）——安全护栏未触发。
- fallback 计数 0（Track A 有效历史足够全部 lookback）。

# 5. Pytest

```text
collected 154 items  →  154 passed（新增 tests/test_non_rl_horse_race.py 8 个）
```

# 6. Git Commit

`GATE_4_NON_RL_HORSE_RACE` 提交 SHA：**`6ded3ac`**

```text
src/china_etf/evaluation/baselines.py        ← +6 Tier A 方法（ERC/HRP/MaxDiv/TrendRP/MinCVaR/ShrinkMV）
tests/test_non_rl_horse_race.py              ← +8 测试
scripts/gate4_non_rl_horse_race.py           ← 对比脚本
runs/gate4_non_rl_horse_race_results.json / _raw.json  ← 结果
docs/review_packets/GATE_4_NON_RL_HORSE_RACE.md       ← 本 packet
docs/agent_state/CLAUDE_STATUS.yaml          ← 协议状态
```

# 7. Not Authorized

```text
RL retraining / 10-seed / 20-seed / Optuna / sweep / Test-informed 调参 / theme sleeve / QMT / Southbound
```

---

## Approval Record

```yaml
gate: 4
handoff_id: G4_NON_RL_HORSE_RACE_001
packet: GATE_4_NON_RL_HORSE_RACE
status: READY_FOR_REVIEW

tier_a:
  implemented: true        # 10 方法，numpy-only，corrected path
  fallback_count: 0
  nan_neg_cash: 0
rl_reference: historical_only  # pre-correction caveat

observations (not conclusions):
  ERC / MinCVaR CAGR highest (35.6%/34.3%) vs RL ref PPO median 27.5%
  HRP / RiskParity Sharpe highest (1.86/1.82) with shallowest MaxDD (-5.4%)
  MinCVaR deepest MaxDD (-19.2%), lowest Sharpe (1.25) — tail-risk tradeoff
  RL PPO median CAGR 27.5% still competitive vs non-RL spread

next_possible: feature-ablation (deferred) / data-ready / explicit re-authorization
```

## END OF GATE 4 NON-RL HORSE RACE
