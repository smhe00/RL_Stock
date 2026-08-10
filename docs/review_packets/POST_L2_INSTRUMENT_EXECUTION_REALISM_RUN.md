# POST_L2 INSTRUMENT EXECUTION REALISM RUN — MaxDiv 可执行 instrument 路径结果

> 评审（`POST_L2_INSTRUMENT_EXECUTION_REALISM_PREP_CONSISTENCY_CLEANUP_REVIEWER_RESPONSE.md`）
> **EXECUTION_REALISM_PREP_CONSISTENCY_CLEANUP_ACCEPTED_FROZEN_RUN_AUTHORIZED** → 本 packet 报告单次冻结执行真实化 RUN。
> handoff_id = **G4_POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN_001**。

```yaml
implementation_commit: 13e29ac   # scripts/gate4_instrument_execution_realism.py + tests
result_artifact: artifacts/gate4_instrument_execution_realism_results.json + _raw.json（commit=13e29ac）
handoff: G4_POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN_001
label: POST_L2_INSTRUMENT_EXECUTION_REALISM
scenario_not_strict_pit_oos: true
```

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
成本路由: Mainland -> MainlandETFCostModel（commission 0.00005, stamp 0, half_spread 1bp+slippage 2bp）；
  03110 -> SouthboundETFCostModel（commission 0.0003+min HKD5 NOT ACCOUNT-VERIFIED, stamp 0, date-effective HK fees）
结算: A股 T+1；03110 T+2（未结算款不用于后续买入）
PremiumGuard: INSTRUMENT_BACKTEST = NOT_EVALUABLE_HISTORICALLY（N/A）
S2: CNY base 聚合
```

# 2. 测试与 --check

```text
pytest tests/test_instrument_execution_realism.py -q: 7 passed
  （mapping 510300/03110 断言、三日期分离、date-effective lot、成本路由 Mainland/Southbound、
    结算 T+2 无未结算复用、PremiumGuard N/A、no-RL）
python scripts/gate4_instrument_execution_realism.py --check: PASSED
  （slot->instrument、hk_dividend_dates、board_lot、cost routing、settlement、no-RL）
```

# 3. 全期结果（1011 决策日，可执行 net 路径）

| 指标 | 可执行 net | L1 研究 MaxDiv（无成本参考） |
|---|---|---|
| 累计收益 | +64.9% | +45.4% |
| Calendar CAGR | +12.8% | +9.4% |
| active-day 年化 | +13.3% | +9.8% |
| 年化波动 | 14.9% | 5.7% |
| Sharpe | 0.911 | 1.655 |
| Sortino | 1.584 | 2.195 |
| MaxDD | -13.2% | -4.0% |
| Calmar | 1.006 | 2.435 |

```text
net CAGR（12.8%）高于研究（9.4%）——因 03110 结构不可交易停泊现金（461 天）避开了部分弱股期
回撤；但波动/回撤更深（MaxDD -13.2% vs -4.0%）、Sharpe 0.911 vs 1.655（可执行性损耗，评审 emphasis）。
```

# 4. 成本聚合（CNY base，S2 冻结定义）

```text
total_fee_cny            = 3,697 元
total_slippage_cny       = 3,169 元（含 spread 1bp + slippage 2bp，模型内置）
total_traded_notional_cny= 10,563,339 元
fee_bps_of_traded_notional = 3.5 bps   ✓ ≤5bp
slippage_bps_of_traded_notional = 3.0 bps ✓ ≤10bp
cost_by_instrument: 各 Mainland ETF 300-500 元；03110.HK = 0（pre-eligible 停泊未交易）
```

# 5. Fail-closed / STOP 判据（评审冻结 S1-S4）

| 判据 | 值 | 判定 |
|---|---|---|
| S1 net vs research CAGR | net 12.8% vs research 9.4%（+3.4pct） | **PASS**（无恶化） |
| S2 fee bps | 3.5 ≤ 5 | **PASS** |
| S2 slippage bps | 3.0 ≤ 10 | **PASS** |
| S3 fail-closed | 461/1011 = **45.6%** > 1% | **FAIL** |
| S4 | NOT_APPLICABLE（backtest mode） | N/A |
| **STOP** | — | **TRUE**（S3 触发） |

```text
S3 触发原因：03110.HK southbound_eligible_from = 2024-05-06（Gate-1 冻结），本 L1 窗口
2022-06-09..2026-08-06 中 461 决策日（45.6%）为结构不可交易期 → HK_DIVIDEND 权重现金停泊。
按冻结契约（评审明确要求"若 S3 触发则报告为 STOP result，不改变映射/阈值/窗口/计数规则"），
本 RUN 报告 STOP=true。这是 03110.HK 在该窗口内实质不可执行性的直接证据，非实现缺陷。
```

# 6. 解读

```text
1. 可执行性损耗（net vs research）：CAGR +3.4pct（现金停泊避回撤），但 Sharpe 1.655→0.911、
   MaxDD -4.0%→-13.2%。研究收益与可执行 instrument 性能差异显著，需分开报告（评审 emphasis）。
2. 成本可控：fee 3.5bp + slippage 3.0bp 均低于 S2 阈值（模型内置 half_spread 1bp + slippage 2bp，
   无额外 overlay）。
3. S3 STOP：03110.HK 结构不可交易 45.6% 窗口 → 该 instrument 在 L1 窗口实质不可执行。
   HK_DIVIDEND 槽位在 eligible（2024-05-06）后 550 决策日可交易（成本路由 Southbound 生效），
   但 pre-eligible 期停泊主导了 fail-closed 计数。
4. 无 RL、无 result-informed 调整、无 dense/dynamic alpha；QMT live 禁止。
```

# 7. 明确声明

```text
1. STOP=true 为冻结契约预期结果（S3 因 03110 结构不可交易触发），未改变映射/阈值/窗口/计数规则。
2. 无 GO/NO-GO 阈值发明；S1-S4 判定全部由冻结契约驱动。
3. SCENARIO_NOT_STRICT_PIT_OOS：非 strict PIT OOS、非生产/实盘授权。
4. PPO/SAC/TD3、QMT live、FORWARD/PAPER/LIVE 均未授权。
5. Southbound 佣金万3 + min 5 HKD 为 NOT ACCOUNT-VERIFIED 标注（保守场景）。
```

---

## Approval Record

```yaml
gate: 4
handoff_id: G4_POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN_001
packet: POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN
status: READY_FOR_REVIEW

executed:
  strategy: MaximumDiversification 120/0.5 project-constrained overlay
  window: 1011 decision days (2022-06-09..2026-08-06), exec 2022-06-10..2026-08-07
  instruments: 11 real ETFs (CN_LARGE=510300.SH, HK_DIVIDEND=03110.HK)
  hk_03110: {listing 2013-06-17, data 2021-01-11, southbound_eligible 2024-05-06, lot 100->50 @2026-07-24, same_day UNKNOWN}
  cost: MainlandETFCostModel (0.00005/0/1bp/2bp) + SouthboundETFCostModel (0.0003+min5HKD, stamp 0)
  settlement: A股 T+1, 03110 T+2 no unsettled reuse; PremiumGuard backtest N/A; S2 CNY base

result:
  net: {cum +64.9%, cagr 12.8%, sharpe 0.911, mdd -13.2%, calmar 1.006, sortino 1.584}
  research_l1_ref: {cagr 9.4%, sharpe 1.655, mdd -4.0%}
  cost: {fee_bps 3.5, slippage_bps 3.0, total_traded_cny 10.56M, 03110 cost 0 (pre-eligible parked)}

stop_evaluation:
  S1: PASS (net cagr 12.8% > research 9.4%, no degradation)
  S2: PASS (fee 3.5bp<=5, slippage 3.0bp<=10)
  S3: FAIL (45.6% > 1%: 03110 structurally non-Southbound 461 pre-eligible decision days, cash-parked)
  S4: NOT_APPLICABLE (backtest mode)
  STOP: TRUE (S3)  # frozen contract: report as STOP, no mapping/threshold/window change

tests: 7 passed (mapping/3-date/lot/cost/settlement/premiumguard-na/no-rl); --check PASSED
no_rl: PPO/SAC/TD3 absent; QMT live forbidden; FORWARD/PAPER/LIVE unauthorized
```

## END OF POST_L2 INSTRUMENT EXECUTION REALISM RUN
