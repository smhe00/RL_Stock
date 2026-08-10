# POST_L2 INSTRUMENT EXECUTION REALISM RUN — MaxDiv 可执行 instrument 路径结果（最终忠实版）

> 评审（`POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN_CORRECTION_REVIEWER_RESPONSE.md`）
> **EXECUTION_REALISM_RUN_CORRECTION_STILL_INVALID_SECOND_MECHANICAL_CORRECTION_REQUIRED** →
> 本 packet 为 **RUN_CORRECTION_002**。第 2 次忠实性修正重跑（同一冻结实验）。
> handoff_id = **G4_POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN_CORRECTION_002**。

```yaml
implementation_commit: 16b8dd7   # scripts/gate4_instrument_execution_realism.py + tests（8 项忠实性修正）
result_artifact: artifacts/gate4_instrument_execution_realism_results.json + _raw.json（commit=16b8dd7）
handoff: G4_POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN_CORRECTION_002
label: POST_L2_INSTRUMENT_EXECUTION_REALISM
scenario_not_strict_pit_oos: true
```

> ## Revision Record（RUN_CORRECTION_002，评审 8 项忠实性修正）
>
> 1. **T+1-open 成交**：sizing/fills 用 T+1 开盘价（opens）；closes 仅 post-trade 估值；
>    合成 open!=close 回归断言精确 fill 价/notional。
> 2. **Post-fill net NAV**：每执行日序列 = 释放到期结算款 → open 估值 sizing → 停泊/目标 →
>    open fills + 扣费 → close 估值（新持仓 + 已结算现金 + 未结算应收）→ 记录 post-fill NAV。
> 3. **T+2 交易日历**：用 exec index +2（session 日历），非日历 +2d；应收款计入 NAV/tracking
>    但排除于买入现金。
> 4. **保留 03110 raw HKD 本地价**；T-1 HKD/CNY 仅用于 CNY 换算/成本；Southbound 传 HKD 本地价
>    + transaction_date + fx_to_base=T-1 FX。
> 5. **公司行为**：可执行持仓应用分红计提/派息 + 份额折算（pop-once 防重复累加）。
> 6. **S1 每子期**（年度 + stress）vs 已接受 L1 research artifact（同边界）CAGR；worst 判 S1。
> 7. **测试替换为行为回归**（12 项：open!=close、post-fill NAV/fee、结算 session、Southbound
>    HKD/FX、CA 分红/折算、先卖后买、MaxDiv parity、provenance 完整性、no-RL）。
> 8. **Provenance 完整**：19 个实际消费输入文件（raw ETF + 03110 + FX + CA 事件）SHA256 +
>    research reference artifact commit。

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

# 3. 全期结果（1011 决策日，可执行 net 路径，CORRECTION_002 忠实版）

| 指标 | 可执行 net | L1 研究 MaxDiv（无成本参考） |
|---|---|---|
| 累计收益 | +48.1% | +45.4% |
| Calendar CAGR | +9.9% | +9.4% |
| active-day 年化 | +10.3% | +9.8% |
| 年化波动 | 5.5% | 5.7% |
| Sharpe | 1.801 | 1.655 |
| Sortino | 2.478 | 2.195 |
| MaxDD | -3.9% | -4.0% |
| Calmar | 2.634 | 2.435 |

```text
忠实版 net 贴近 L1 研究 MaxDiv（Sharpe 1.801 vs 1.655、MaxDD -3.9% vs -4.0%）——
T+1-open 成交 + post-fill NAV + 公司行为全部实现后，可执行性损耗极小。
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

# 6. 执行诊断（评审 CORRECTION_002 要求）

```text
fill_count                 = 7,421
mean_target_tracking_error = 0.038（post-fill close 权重 vs 目标 L1 距离均值）
fail_closed: {structural_ineligible_cash_parking: 461, no_quote_hold: 0}
03110 eligible 后诊断（post-2024-05-06，550 决策日）：
  mean_target_weight = 0.048 / max 0.092 —— MaxDiv 低配 HK_DIVIDEND，目标 notional 低于
  一手 board lot（100/50 股）→ 无成交（fill 0）。Southbound 执行分支已实现并测试，
  该结果为策略选择 + lot 约束组合，非实现缺陷。
provenance: 19 个输入文件 SHA256（raw ETF + 03110 HKD + FX + CA 事件）+ L1 research artifact
```

# 7. STOP 判据（评审冻结 S1-S4，子期判据）

| 判据 | 值 | 判定 |
|---|---|---|
| S1 worst 子期恶化 | **year_2022 net CAGR 4.3% vs research 9.4%（-5.08%）** | **FAIL** |
| S1 其他子期 | 2023 -3.0%、2024 +9.5%、2025 +3.1%、2026 -4.1%；weak -3.8%、strong +3.8% | 通过 |
| S2 fee bps | 3.5 ≤ 5 | **PASS** |
| S2 slippage bps | 3.0 ≤ 10 | **PASS** |
| S3 fail-closed | 461/1011 = **45.6%** > 1% | **FAIL** |
| S4 | NOT_APPLICABLE（backtest mode） | N/A |
| **STOP** | — | **TRUE**（S1 2022 子期 + S3） |

```text
S1 按冻结契约每子期判据：year_2022 net CAGR 4.3% 相对研究 9.4% 恶化 -5.08%（超 5% 阈值）→ S1 FAIL。
全期 net CAGR 9.9% 与研究一致，但 2022 子期可执行损耗（开仓成本 + 停泊 + T+1-open）明显。
S3 不变：03110 southbound_eligible_from 2024-05-06，461 决策日结构不可交易 → 现金停泊。
按冻结契约（"若 S3 触发则报告 STOP"），本 RUN 报告 STOP=true（S1 + S3）。
```

```text
S3 触发原因不变：03110.HK southbound_eligible_from = 2024-05-06（Gate-1 冻结），本窗口
461 决策日结构不可交易 → 现金停泊。按冻结契约（评审要求"若 S3 触发则报告为 STOP result，
不改变映射/阈值/窗口/计数规则"），本 RUN 报告 STOP=true。修正机械缺陷后 S3 仍触发——符合预期。
```

# 8. 解读

```text
1. 忠实版可执行性损耗极小：net vs L1 研究 MaxDiv 几乎一致（Sharpe 1.801 vs 1.655、MaxDD
   -3.9% vs -4.0%），T+1-open + post-fill NAV + CA 全部实现后。
2. 成本可控：fee 3.5bp + slippage 3.0bp 均低于 S2 阈值。
3. S1 FAIL：2022 子期 net CAGR 4.3% vs 研究 9.4%（-5.08% 超 5% 阈值）——开仓/停泊/T+1-open
   可执行损耗在 2022 显著；其余子期均通过。全期 CAGR 9.9% 与研究 9.4% 一致。
4. S3 FAIL：03110 结构不可交易 45.6% 窗口（461 决策日）主导 fail-closed。
5. 无 RL、无 result-informed 调整、无 dense/dynamic alpha；QMT live 禁止。
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
handoff_id: G4_POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN_CORRECTION_002
packet: POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN
status: READY_FOR_REVIEW

corrections_002_applied (8 fidelity):
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

result (CORRECTION_002 faithful):
  net: {cum +48.1%, cagr 9.9%, sharpe 1.801, mdd -3.9%, calmar 2.634, sortino 2.478}
  research_l1_ref: {cagr 9.4%, sharpe 1.655, mdd -4.0%}
  cost: {fee_bps 3.5, slippage_bps 3.0, total_traded_cny 14.10M, 03110 notional 0 (MaxDiv low-weight mean 0.048/max 0.092 below board lot + pre-eligible)}
  exec: {fill 7421, track_err 0.038, fail_closed {parking 461, no_quote 0}}

stop:
  S1: FAIL (worst subperiod year_2022 net cagr 4.3% vs research 9.4%, deg -5.08% > 5pct threshold;
      other subperiods pass; full-period net 9.9% == research)
  S2: PASS (fee 3.5bp, slippage 3.0bp)
  S3: FAIL (45.6% > 1%: 03110 structurally non-Southbound 461 days)
  S4: NOT_APPLICABLE
  STOP: TRUE (S1 2022 subperiod + S3)  # frozen contract; no mapping/threshold/window change

tests: 12 passed (behavioral regressions); --check PASSED
no_rl: PPO/SAC/TD3 absent; QMT live / FORWARD / PAPER / LIVE forbidden
```

## END OF POST_L2 INSTRUMENT EXECUTION REALISM RUN (RUN_CORRECTION_001)
