# GATE 4 LONG HORIZON NON-RL PREP — L1 真实工具长区间稳健性研究（冻结契约）

> 评审（`LONG_HORIZON_NON_RL_ROBUSTNESS_DIRECTIVE.md`）**LONG_HORIZON_NON_RL_PREP_AUTHORIZED**。
> 本 packet 冻结 L1 契约（PREP only，**不执行 L1 horse race**）。handoff_id = **G4_LONG_HORIZON_NON_RL_PREP_001**。

---

# 1. 目标与标签

```text
验证确定性方法（EW / MaxDiv 等）在更长窗口 + 多市场 regime 下是否稳健（非复现 Sharpe 2.77）。
label = REAL_INSTRUMENT_LONG_HORIZON_DIAGNOSTIC（robustness diagnostic，非 pristine OOS——
历史数据已被研究观察）。
```

# 2. 冻结区间与数据

```text
区间: 决策 2022-06-10 → 2026-08-07，1011 决策日（~4.2 年）
起点依据: 11 槽位全 finite 首日（2021-05-26，HK_TECH 2021-05-25 launch 后）
  + 最长 lookback 252d（momentum）warmup
数据: 现有研究复权 adj + 执行价 opens/closes + CA（同 corrected 路径）
数据授权: L1 真实上市期内的缺失/坏行可 re-fetch/repair（保留 source/fetch date/raw-vs-adj/CA provenance）；
  pre-launch backfill 禁止冒充真实历史
```

# 3. 6 方法（canonical 参数原样复用，不得事后加）

| # | 方法 | 实现 | 参数 |
|---|---|---|---|
| 1 | HS300 参考 | CN_LARGE 研究复权（同执行日收益） | — |
| 2 | EqualWeight | `equal_weight_policy` | — |
| 3 | MaximumDiversification | `maximum_diversification_policy` | lookback 120, shrinkage 0.5 |
| 4 | MinimumVariance | `minimum_variance_policy` | lookback 120, shrinkage 0.5 |
| 5 | RiskParity_IVOL | `risk_parity_policy` | lookback 60 |
| 6 | Momentum_12_1 | `momentum_policy` | lookback 252, skip 21 |

# 4. 评估语义（corrected path 复用，防 lookahead + 防旧 475 mask）

```text
T 决策 → T+1 执行；rolling cov/vol/momentum 只用 ≤T 数据（causal）
成本: 1x Mainland；RiskOverlay；公司行为（复用 roll_out / _build_env_upto / fit_scaler）
连续持有: 单段从现金开始（reset_at=2022-06-09 决策日），不跨段重置
防旧 475 mask: L1 runner 不用 exact_test_mask / RESEARCH_BENCHMARK_TEST；
  断言执行日 = 1011 决策段（≠ 475）
```

# 5. 指标 + 子期报告

```text
每方法: cum / active-day ann（+日历 CAGR 如适用）/ annualized vol / Sharpe / Sortino /
  MaxDD / Calmar / worst calendar-year / worst 12m rolling / turnover / cost per traded /
  平均 active assets / 集中度诊断
子期: 年度 + 阶段（2022H2-2023 弱股 / 2024-2026 强）+ 每子期 Sharpe/MaxDD
```

# 6. 脚本 / artifact / 测试（PREP 交付，不跑完整 L1）

```text
scripts/gate4_long_horizon_nonrl.py   L1 runner（6 方法单段 rollout；--check 只验契约不跑）
artifacts/gate4_long_horizon_nonrl_results.json + _raw.json（L1 执行时写，tracked）
tests/test_long_horizon_nonrl.py:
  - 无 lookahead（cov/vol/momentum 用 ≤T）
  - 执行日 = 1011 决策段（≠ 旧 475 mask）
  - 6 方法集合精确、无 RL 引入
  - 成本/记账语义同 corrected
```

# 7. 明确声明

```text
PPO/SAC/TD3 缺席所有代码路径与输出表
无超参/lookback 优化；canonical 参数原样复用（除非严格必需，改动须声明并评审）
不执行 L2（2015-2026 proxy；需单独评审提案）
```

# 8. Git Commit

`GATE_4_LONG_HORIZON_NON_RL_PREP` 提交 SHA：**`PENDING_SHA`**

```text
docs/review_packets/GATE_4_LONG_HORIZON_NON_RL_PREP.md  ← 本 packet
docs/agent_state/CLAUDE_STATUS.yaml                       ← 协议状态
（L1 runner/测试在下一实现提交；PREP 先冻结契约）
```

---

## Approval Record

```yaml
gate: 4
handoff_id: G4_LONG_HORIZON_NON_RL_PREP_001
packet: GATE_4_LONG_HORIZON_NON_RL_PREP
status: READY_FOR_REVIEW

frozen:
  window: {start: 2022-06-10, end: 2026-08-07, n_decision_days: 1011, label: REAL_INSTRUMENT_LONG_HORIZON_DIAGNOSTIC}
  instruments: 11 core ETF (real launch dates hard boundaries; HK_TECH 2021-05-25 latest)
  methods: [HS300_ref, EqualWeight, MaxDiv, MinVar, RiskParity_IVOL, Momentum_12_1]
  params: canonical reused (no tuning)
  semantics: T->T+1 causal; 1x cost; RiskOverlay; CA; continuous single-segment
  no_lookahead: true
  not_old_475_mask: true
  metrics: full (cum/ann/vol/Sharpe/Sortino/MaxDD/Calmar/worst-year/turnover/cost/concentration)
  sub_periods: yearly + phase (2022H2-2023 weak / 2024-2026 strong)

no_rl: PPO/SAC/TD3 absent from all code paths and output tables
no_l2: L2 proxy scenario not executed (separate reviewed proposal)
not_done:
  l1_execution: false   # PREP only; wait for review
  rl_retraining: false
  hyperparameter_optimization: false
  qmt_live: false
```

## END OF GATE 4 LONG HORIZON NON-RL PREP
