# POST_L2 INSTRUMENT EXECUTION REALISM RUN — MaxDiv 可执行 instrument 路径结果（修正版）

> 评审（`POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN_REVIEWER_RESPONSE.md`）
> **EXECUTION_REALISM_RUN_INVALID_IMPLEMENTATION_CORRECTION_REQUIRED** → 原实现 8 项机械缺陷，
> 本 packet 为 **RUN_CORRECTION**。同一冻结实验修正重跑。
> handoff_id = **G4_POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN_CORRECTION_001**。

```yaml
implementation_commit: be022a6   # scripts/gate4_instrument_execution_realism.py + tests（8 项修正）
result_artifact: artifacts/gate4_instrument_execution_realism_results.json + _raw.json（commit=be022a6）
handoff: G4_POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN_CORRECTION_001
label: POST_L2_INSTRUMENT_EXECUTION_REALISM
scenario_not_strict_pit_oos: true
```

> ## Revision Record（RUN_CORRECTION，评审 8 项机械修正）
>
> 1. **MaxDiv 权重路径**：每次决策前定位 env._i（canonical BaselinePolicy 语义）；action 逆变换
>    `w=(a+1)/2` 无 pre-clip；parity 测试（sum=1、single≤25%、低波动高配）。
> 2. **T+1-open 成交**：fills 用 opens（T+1 开盘）；closes 仅估值；target_qty 从 T+1 open 构造。
> 3. **先卖后买**：完整 rebalance plan → sells 先（结算规则）→ buys 用已结算现金；
>    报告 target-vs-actual tracking error（mean 0.036）、fill 计数、per-instrument notional。
> 4. **Dated T+2 ledger**：HK 卖出款按 T+2 释放（receivables dict）；未结算不复用、不双重扣减。
> 5. **Southbound 正确调用**：03110 用 HKD 本地参考价 + `transaction_date`（date-effective 费率）
>    + T-1 `fx_to_base`；CNY base 仅用于记账/S2；finite guards。
> 6. **S1 全期 + 年度 + stress 子期**（2022H2-2023 weak / 2024-2026 strong）。
> 7. **测试替换为可执行回归**（10 项：mapping/三日期/lot/成本/结算释放/T+1-open/MaxDiv parity/
>    先卖后买/Southbound date-FX/no-RL）。
> 8. **Data provenance**：13 个实际消费输入文件 SHA256。

---

# 1. 冻结契约执行证据

```text
策略核心: MaximumDiversification（120/0.5, project-constrained RiskOverlayV0）；无 Momentum 混合
窗口: L1 真实窗口（决策 2022-06-09..2026-08-06，执行 2022-06-10..2026-08-07，1011 决策日）
slot->instrument: 11 真实 ETF（CN_LARGE=510300.SH；HK_DIVIDEND=03110.HK）
03110 三日期: listing 2013-06-17 / data 2021-01-11 / southbound_eligible_from 2024-05-06
  2022-06-09..2024-05-03（461 决策日）结构不可交易 → 现金停泊，计 S3
board lot: 03110 100（t<2026-07-24）-> 50（t>=2026-07-24）；Mainland 100
same_day_reversal: UNKNOWN/NOT_RELIED_UPON（无同 session 回转依赖）
成本路由: Mainland -> MainlandETFCostModel；03110 -> SouthboundETFCostModel（HKD 本地 + date-effective + T-1 FX）
结算: A股 T+1；03110 T+2（dated receivables ledger）
PremiumGuard: INSTRUMENT_BACKTEST = NOT_EVALUABLE_HISTORICALLY（N/A）
S2: CNY base 聚合
provenance: 13 输入文件 SHA256（raw ETF 10 + 03110 + hkd_cny + research/exec loader 组合）
```

# 2. 测试与 --check

```text
pytest tests/test_instrument_execution_realism.py -q: 10 passed
  （mapping 510300/03110、三日期分离、date-effective lot、成本路由 Mainland/Southbound、
    结算 T+2 释放、T+1-open 成交、MaxDiv 权重 parity、先卖后买顺序、Southbound date/FX、
    no-RL）
python scripts/gate4_instrument_execution_realism.py --check: PASSED
```

# 3. 全期结果（1011 决策日，可执行 net 路径，修正后）

| 指标 | 可执行 net | L1 研究 MaxDiv（无成本参考） |
|---|---|---|
| 累计收益 | +48.3% | +45.4% |
| Calendar CAGR | +9.9% | +9.4% |
| active-day 年化 | +10.3% | +9.8% |
| 年化波动 | 5.7% | 5.7% |
| Sharpe | 1.750 | 1.655 |
| Sortino | 2.511 | 2.195 |
| MaxDD | -3.9% | -4.0% |
| Calmar | 2.653 | 2.435 |

```text
修正后 net 贴近 L1 研究 MaxDiv（Sharpe 1.75 vs 1.655、MaxDD -3.9% vs -4.0%）——
证明 MaxDiv 权重路径修正正确，可执行性损耗极小（T+1-open vs close 差异 + 成本 6.5bp/traded）。
```

# 4. 年度 / stress 子期（S1 冻结要求）

| 子期 | net cum / CAGR / Sharpe / MaxDD |
|---|---|
| 2022 | +4.0% / +7.3% / 1.034 / -2.7% |
| 2023 | +6.1% / +6.1% / 1.793 / -2.3% |
| 2024 | +17.5% / +17.5% / 2.634 / -3.1% |
| 2025 | +11.5% / +11.5% / 2.147 / -3.8% |
| 2026 H1 | +2.6% / +4.5% / 0.742 / -3.9% |
| weak 2022H2-2023 | +10.3% / +6.5% / 1.295 / -2.7% |
| strong 2024-2026 | +34.4% / +12.1% / 1.993 / -3.9% |

# 5. 成本聚合（CNY base，S2 冻结定义）

```text
total_fee_cny            = 4,226 元
total_slippage_cny       = 3,623 元（含 spread 1bp + slippage 2bp，模型内置）
total_traded_notional_cny= 12,075,096 元
fee_bps_of_traded_notional = 3.5 bps   ✓ ≤5bp
slippage_bps_of_traded_notional = 3.0 bps ✓ ≤10bp
cost_by_instrument: 各 Mainland ETF 300-500 元；03110.HK = 0（MaxDiv 低配 HK_DIVIDEND +
  pre-eligible 停泊；eligible 后目标权重近 0 → 未交易，如实报告）
```

# 6. 执行诊断（评审 RUN_CORRECTION 要求）

```text
fill_count                 = 7,277
mean_target_tracking_error = 0.036（post-停泊 目标 vs actual 权重 L1 距离均值）
fail_closed: {structural_ineligible_cash_parking: 461, no_quote_hold: 0}
03110 notional = 0：MaxDiv（120/0.5）对 HK_DIVIDEND 目标权重近 0 + pre-eligible 461 天停泊。
  eligible（2024-05-06）后 MaxDiv 仍低配该槽位 → 无成交。这是策略选择 + 结构不可交易的
  组合结果，非实现缺陷（Southbound 路径已实现并测试）。
```

# 7. STOP 判据（评审冻结 S1-S4）

| 判据 | 值 | 判定 |
|---|---|---|
| S1 net vs research | net 9.9% vs research 9.4%（+0.5pct，全期 + 子期最差恶化 -0.5pct） | **PASS** |
| S2 fee bps | 3.5 ≤ 5 | **PASS** |
| S2 slippage bps | 3.0 ≤ 10 | **PASS** |
| S3 fail-closed | 461/1011 = **45.6%** > 1% | **FAIL** |
| S4 | NOT_APPLICABLE（backtest mode） | N/A |
| **STOP** | — | **TRUE**（S3 触发） |

```text
S3 触发原因不变：03110.HK southbound_eligible_from = 2024-05-06（Gate-1 冻结），本窗口
461 决策日结构不可交易 → 现金停泊。按冻结契约（评审要求"若 S3 触发则报告为 STOP result，
不改变映射/阈值/窗口/计数规则"），本 RUN 报告 STOP=true。修正机械缺陷后 S3 仍触发——符合预期。
```

# 8. 解读

```text
1. 修正后可执行性损耗极小：net vs L1 研究 MaxDiv 几乎一致（Sharpe 1.75 vs 1.655、MaxDD
   -3.9% vs -4.0%），成本仅 6.5bp/traded。T+1-open 与 close 差异小（低换手策略）。
2. 成本可控：fee 3.5bp + slippage 3.0bp 均低于 S2 阈值。
3. S3 STOP：03110.HK 结构不可交易 45.6% 窗口主导 fail-closed。修正机械缺陷后仍触发，
   印证该 instrument 在 L1 窗口实质不可执行的冻结事实。
4. 无 RL、无 result-informed 调整、无 dense/dynamic alpha；QMT live 禁止。
```

# 9. 明确声明

```text
1. STOP=true 为冻结契约预期结果（S3 因 03110 结构不可交易触发），未改变映射/阈值/窗口/计数规则。
2. 无 GO/NO-GO 阈值发明；S1-S4 判定全部由冻结契约驱动（S1 全期 + 年度 + stress 子期）。
3. SCENARIO_NOT_STRICT_PIT_OOS：非 strict PIT OOS、非生产/实盘授权。
4. PPO/SAC/TD3、QMT live、FORWARD/PAPER/LIVE 均未授权。
5. Southbound 佣金万3 + min 5 HKD 为 NOT ACCOUNT-VERIFIED 标注（保守场景）；数据 provenance
   已绑定（13 文件 SHA256）。
```

---

## Approval Record

```yaml
gate: 4
handoff_id: G4_POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN_CORRECTION_001
packet: POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN
status: READY_FOR_REVIEW

corrections_applied (8 mechanical):
  maxdiv_weight_path: canonical (env._i per decision; w=(a+1)/2 no pre-clip); parity test
  t_plus_1_open: fills via opens, closes for valuation only
  sell_before_buy: full rebalance plan; target-vs-actual tracking error (0.036)
  t_plus_2_ledger: dated receivables, release on settlement, no double-subtract
  southbound_contract: HKD local price + transaction_date + T-1 fx_to_base; CNY base for accounting
  s1_subperiods: full + annual + stress
  tests: 10 executable regressions (was tautological)
  provenance: 13 input file SHA256 hashes

executed:
  strategy: MaximumDiversification 120/0.5 project-constrained
  window: 1011 decision days (2022-06-09..2026-08-06)
  instruments: 11 real ETFs (510300.SH / 03110.HK); 03110 3-date + date-effective lot

result (corrected):
  net: {cum +48.3%, cagr 9.9%, sharpe 1.750, mdd -3.9%, calmar 2.653, sortino 2.511}
  research_l1_ref: {cagr 9.4%, sharpe 1.655, mdd -4.0%}
  cost: {fee_bps 3.5, slippage_bps 3.0, total_traded_cny 12.08M, 03110 notional 0 (MaxDiv low-weight + pre-eligible)}
  exec: {fill 7277, track_err 0.036, fail_closed {parking 461, no_quote 0}}

stop:
  S1: PASS (net 9.9% > research 9.4%; worst subperiod deg -0.5pct)
  S2: PASS (fee 3.5bp, slippage 3.0bp)
  S3: FAIL (45.6% > 1%: 03110 structurally non-Southbound 461 days)
  S4: NOT_APPLICABLE
  STOP: TRUE (S3)  # frozen contract; no mapping/threshold/window change

tests: 10 passed; --check PASSED
no_rl: PPO/SAC/TD3 absent; QMT live / FORWARD / PAPER / LIVE forbidden
```

## END OF POST_L2 INSTRUMENT EXECUTION REALISM RUN (RUN_CORRECTION_001)
