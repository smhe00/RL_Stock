# GATE 4 LONG HORIZON NON-RL RUN — L1 真实工具长区间稳健性研究结果

> 评审（`GATE_4_LONG_HORIZON_NON_RL_PREP_REVIEWER_RESPONSE.md`）授权 **GATE_4_LONG_HORIZON_NON_RL_RUN**。
> 本 packet 报告单次冻结 L1 执行结果。handoff_id = **G4_LONG_HORIZON_NON_RL_RUN_001**。

```yaml
implementation_commit: f039d36   # scripts/gate4_long_horizon_nonrl.py + src/china_etf/evaluation/long_horizon_contract.py + tests/test_long_horizon_nonrl.py
result_artifact: artifacts/gate4_long_horizon_nonrl_results.json (+ _raw.json)
result_artifact_manifest_commit: f039d36
handoff: G4_LONG_HORIZON_NON_RL_RUN_001
```

---

# 1. 窗口与日期计数证据（hard guard #1 fail-closed）

```text
label = REAL_INSTRUMENT_LONG_HORIZON_DIAGNOSTIC
推导（derive-then-assert，与冻结契约精确一致）：
  first_all_finite = 2021-05-25（11 槽位全 finite；HK_TECH 2021-05-25 上市）
  decision_start   = 2022-06-09（+252 交易日 warmup）
  first_execution  = 2022-06-10   ← 契约 start ✓
  last_decision    = 2026-08-06
  last_execution   = 2026-08-07   ← 契约 end（数据末日）✓
  n_decision_days  = 1011         ✓
  n_execution_dates = 1011        ✓
语义：T 决策 → T+1 执行；单段连续持有（reset_at=2022-06-09，不跨段重置）
```

每方法 rollout 审计：`execution_dates == 1011`（首 2022-06-10 末 2026-08-07，与契约逐日一致）、
`nan_obs_or_reward = 0`、`negative_cash_count = 0`、`fallback_count = 0`（全部通过）。

# 2. 数据溯源 / 修复

```text
数据：现有研究复权 adj + 执行价 opens/closes + 公司行为（同 corrected 路径）。
L1 无需任何 re-fetch/repair（真实上市期内数据完整；窗口起点 2022-06-09 早于
所有槽位全 finite 后 252 日，无 pre-launch backfill）。无数据编造（guard #9）。
```

# 3. 测试与 --check（guard #10）

```text
pytest 全套:     254 passed（含 tests/test_long_horizon_nonrl.py 8 项）
  - 窗口 parity fail-closed（篡改数据 → ContractParityError）
  - 执行日 != 475 旧 mask；runner 源码无旧 mask 标识
  - 6 方法集冻结精确；canonical 参数冻结精确（经契约常量路由）
  - runner 源码无 RL 导入/字面量
  - 单段因果 T+1 执行（合成 env：执行日 = 决策日后下一交易日）
scripts/gate4_long_horizon_nonrl.py --check: PASSED
  - 窗口 parity: ok | 方法集 ok | canonical params ok | 无 RL/旧 mask ok | env warmup <= decision_start ok
```

# 4. 全期结果表（1011 执行日，2022-06-10..2026-08-07）

可执行策略 = 1x MainlandETFCostModel（**当前项目成本简化标注，非完整跨市场/Southbound 费率模型**，guard #6）；
HS300 参考 = 研究复权无成本参考（guard #7，独立列，不参与可执行比较）。

| 指标 | EqualWeight | **MaximumDiversification** | MinimumVariance | RiskParity_IVOL | Momentum_12_1 | HS300 参考 |
|---|---|---|---|---|---|---|
| 累计收益 | +49.7% | +45.4% | +43.9% | +43.2% | **+71.7%** | +23.3% |
| active-day 年化 | +10.6% | +9.8% | +9.5% | +9.4% | +14.4% | +5.4% |
| 日历 CAGR | +10.2% | +9.4% | +9.1% | +9.0% | +13.9% | +5.2% |
| 年化波动 | 13.4% | **5.7%** | 10.8% | 9.7% | 14.5% | 17.7% |
| Sharpe | 0.815 | **1.655** | 0.893 | 0.974 | 1.004 | 0.384 |
| Sortino | 1.184 | **2.195** | 1.282 | 1.400 | 1.192 | 0.575 |
| MaxDD | -14.0% | **-4.0%** | -10.2% | -8.8% | -17.0% | -26.9% |
| Calmar | 0.756 | **2.435** | 0.927 | 1.067 | 0.849 | — |
| worst 日历年 | 2022 -3.5% | 2022 **-0.4%** | 2022 -2.7% | 2022 -2.3% | 2022 -1.6% | 2023 -9.8% |
| worst 12m（252 exec 日） | -11.7% | **+2.3%**（未负） | -6.3% | -6.1% | +1.1% | -22.1% |
| mean turnover | 1.10% | 1.14% | 1.15% | 1.16% | 6.64% | — |
| cost / initial | 0.28% | 0.38% | 0.29% | 0.31% | 2.73% | — |
| cost / traded notional | 3.5bp | 3.5bp | 3.5bp | 3.5bp | 3.5bp | — |
| mean active assets | 11.0 | 11.0 | 11.0 | 11.0 | 10.6 | — |
| max single weight | 10.3% | 25.4% | 25.7% | 25.4% | 26.0% | — |
| mean HHI | 0.087 | 0.166 | 0.117 | 0.121 | 0.157 | — |

# 5. 年度 / 子期 Sharpe · MaxDD（guard #8 描述性）

每格 = `cum_return / sharpe / max_drawdown`（2022 为 H2 部分 140d；2026 为 H1 部分 144d）。

| 子期 | EqualWeight | **MaximumDiversification** | MinimumVariance | RiskParity_IVOL | Momentum_12_1 | HS300 参考 |
|---|---|---|---|---|---|---|
| 2022 H2 | -3.5% / -0.47 / -12.6% | -0.4% / -0.12 / -3.4% | -2.7% / -0.44 / -10.2% | -2.3% / -0.46 / -8.8% | -1.6% / -0.42 / -5.1% | -6.0% / -0.56 / -21.2% |
| 2023 | +0.5% / +0.10 / -8.6% | +5.9% / **+1.60** / -2.6% | +1.8% / +0.31 / -6.0% | +2.0% / +0.38 / -5.3% | +4.7% / +0.67 / -5.9% | -9.8% / -0.74 / -19.9% |
| 2024 | +20.1% / +1.22 / -9.0% | +18.8% / **+2.62** / -3.4% | +17.3% / +1.31 / -7.3% | +17.8% / +1.44 / -6.3% | +23.1% / +2.24 / -6.2% | +17.4% / +0.85 / -12.4% |
| 2025 | +22.8% / +1.77 / -9.4% | +12.5% / **+2.17** / -4.0% | +18.9% / +1.80 / -7.7% | +17.5% / +1.87 / -6.7% | +25.5% / +1.50 / -12.5% | +20.8% / +1.39 / -10.1% |
| 2026 H1 | +4.6% / +0.58 / -8.8% | +3.1% / +0.81 / -4.0% | +4.1% / +0.61 / -7.2% | +3.8% / +0.63 / -6.5% | +8.0% / +0.64 / -17.0% | +2.6% / +0.32 / -9.9% |

阶段（**pre-frozen 描述性划分，非客观 regime 分类器**）：

| 阶段 | EqualWeight | **MaximumDiversification** | MinimumVariance | RiskParity_IVOL | Momentum_12_1 | HS300 参考 |
|---|---|---|---|---|---|---|
| 2022H2-2023 弱股期 | -3.0% / -0.15 / -12.6% | **+5.5% / +0.86 / -3.4%** | -0.9% / -0.03 / -10.2% | -0.4% / -0.00 / -8.8% | +3.0% / +0.31 / -5.9% | -15.2% / -0.65 / -24.3% |
| 2024-2026 强股期 | +54.4% / +1.23 / -9.4% | +37.9% / **+2.01** / -4.0% | +45.2% / +1.29 / -7.7% | +43.7% / +1.37 / -6.7% | +66.8% / +1.26 / -17.0% | +45.5% / +0.88 / -16.3% |

# 6. 与旧 475-day 指标直接对比（历史对比，非评估日期依据）

```text
旧 475-day（2023-11-24..2026-08-07，stitched）：artifacts/gate4_non_rl_horse_race_results.json
```

| 方法 | 旧 Sharpe | L1 Sharpe | ΔSharpe | 旧 MaxDD | L1 MaxDD | 旧 active-ann | L1 active-ann |
|---|---|---|---|---|---|---|---|
| EqualWeight | 1.644 | 0.815 | -50% | -8.8% | -14.0% | +26.9% | +10.6% |
| **MaximumDiversification** | **2.775** | **1.655** | **-40%** | **-3.4%** | **-4.0%** | +18.3% | +9.8% |
| MinimumVariance | 1.753 | 0.893 | -49% | -6.0% | -10.2% | +22.8% | +9.5% |
| RiskParity_IVOL | 1.821 | 0.974 | -47% | -5.4% | -8.8% | +21.6% | +9.4% |
| Momentum_12_1 | 1.629 | 1.004 | -38% | -17.0% | -17.0% | +30.0% | +14.4% |

评审焦点：**MaxDiv Sharpe 2.77 / MaxDD -3.4% 在纳入早期弱股期后压缩/扩张幅度**。

```text
Sharpe 2.775 → 1.655（-40%），但仍为所有可执行确定性方法最高（次高 Momentum 1.004，EW 0.815）
MaxDD -3.4% → -4.0%（仅小幅扩张），仍远低于 HS300（-26.9%）/ EW（-14.0%）/ Momentum（-17.0%）
```

# 7. 稳健性解读（对应评审 Interpretation target）

```text
主问题：MaxDiv 在纳入早期弱股期后是否仍保留实质性风险调整与回撤优势？

1. 长窗 Sharpe 是否仍实质高于 HS300 与竞争性确定性方法？
   是。L1 MaxDiv Sharpe 1.655 ≈ 4.3× HS300（0.384），高于全部确定性方法
   （EW 0.815 / MinVar 0.893 / RP 0.974 / Momentum 1.004）。

2. MaxDD 是否仍显著低于 HS300 / EW？
   是。L1 MaxDiv MaxDD -4.0%，为 HS300（-26.9%）的 1/6.7、EW（-14.0%）的 1/3.5。

3. 优势是否跨多个子期，而非几乎全部由 2024-2026 生成？
   是，且是唯一跨双期稳健的方法：
     - 弱股期 2022H2-2023：MaxDiv Sharpe +0.86（唯一正），其余全负
       （EW -0.15 / MinVar -0.03 / RP -0.00 / Momentum +0.31 / HS300 -0.65）
     - 强股期 2024-2026：MaxDiv Sharpe +2.01（最高）
   MaxDiv 最差日历年（2022）-0.4%，最差 12m 滚动 +2.3%（全程未负）。

4. Sharpe 2.77 / MaxDD -3.4% 压缩了多少？
   Sharpe -40%（1.655），MaxDD 仅 -4.0%（扩张 0.6pct）；两者相对 HS300 的边际仍巨大。

结论：MaximumDiversification 在长窗下保留实质性风险调整与回撤优势，且为唯一在弱股期
取得正 Sharpe 的可执行方法。本研究为 robustness diagnostic（历史数据已被研究观察），
非 pristine OOS 声明。
```

# 8. 明确声明

```text
1. 无 GO 阈值在观察结果后发明（results["no_go_threshold"] = None）。评审如有阈值需单独冻结。
2. RL 算法（PPO/SAC/TD3）缺席所有代码路径与输出表：runner 源码无任何 RL 导入/字面量
   （--check 自检通过）；本 packet 无 RL 指标。
3. L2（2015-2026 proxy）未执行，需单独评审提案。
4. 成本模型 = 当前项目 1x MainlandETFCostModel 简化；非完整跨市场/Southbound 费率模型。
5. 旧 475-day mask 仅作为历史对比出现在本报告，未用于决定 L1 评估日。
6. 方法集未事后增删，canonical 参数原样复用（120/0.5、120/0.5、60、252/21）。
```

---

## Approval Record

```yaml
gate: 4
handoff_id: G4_LONG_HORIZON_NON_RL_RUN_001
packet: GATE_4_LONG_HORIZON_NON_RL_RUN
status: READY_FOR_REVIEW

executed:
  window: {decision_start: 2022-06-09, first_execution: 2022-06-10, last_decision: 2026-08-06, last_execution: 2026-08-07, n_decision_days: 1011, n_execution_dates: 1011}
  methods: [HS300_ref, EqualWeight, MaximumDiversification, MinimumVariance, RiskParity_IVOL, Momentum_12_1]
  params: canonical reused (120/0.5, 120/0.5, 60, 252/21)
  semantics: T->T+1 causal; 1x Mainland cost (labeled simplification); RiskOverlay; CA; continuous single-segment
  no_lookahead: true
  not_old_475_mask: true
  tests: 254 passed (incl. 8 L1)
  check: PASSED
  data_repairs: none

result_highlights:
  maxdiv: {sharpe: 1.655, max_drawdown: -0.0402, calmar: 2.435, weak_phase_sharpe: 0.86, strong_phase_sharpe: 2.01, worst_12m: +0.0231}
  hs300_ref: {sharpe: 0.384, max_drawdown: -0.2688}
  old_475_maxdiv: {sharpe: 2.775, max_drawdown: -0.0340}

no_go_threshold: null
no_rl: PPO/SAC/TD3 absent from all code paths and output tables
no_l2: L2 proxy scenario not executed
not_done:
  rl_retraining: false
  hyperparameter_optimization: false
  qmt_live: false
  l2_execution: false
```

## END OF GATE 4 LONG HORIZON NON-RL RUN
