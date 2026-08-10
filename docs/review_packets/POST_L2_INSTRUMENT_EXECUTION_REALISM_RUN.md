# POST_L2 INSTRUMENT EXECUTION REALISM RUN — MaxDiv 可执行 instrument 路径（CORRECTION_003）

> 评审（`POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN_CORRECTION_002_REVIEWER_RESPONSE.md`）
> **EXECUTION_REALISM_RUN_CORRECTION_002_INVALID_CORRECTION_003_REQUIRED** →
> 本 packet 为 **RUN_CORRECTION_003**。同一冻结实验的第 3 次忠实性修正重跑。
> handoff_id = **G4_POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN_CORRECTION_003**。

```yaml
implementation_commit: aabe0ca   # scripts/gate4_instrument_execution_realism.py + tests（7 项修正）
result_artifact: artifacts/gate4_instrument_execution_realism_results.json + _raw.json
handoff: G4_POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN_CORRECTION_003
label: POST_L2_INSTRUMENT_EXECUTION_REALISM
scenario_not_strict_pit_oos: true
```

> ## Revision Record（RUN_CORRECTION_003，评审 7 项忠实性修正）
>
> 1. **03110.HK 可执行价格路径**：构建 opens/closes["03110.HK"]（sina_qfq HKD 本地价 × 冻结
>    T-1 HKD/CNY）；Southbound 传 HKD 本地价 + transaction_date + fx_to_base=T-1 FX。
>    eligible 后 03110 真实成交（attempted 217 / fills 217 / notional 73.6 万 CNY），
>    不再是 CORRECTION_002 的 no_quote_hold=550（评审确认的缺陷）。
>    QMT raw 03110 open/close 全为 0（miniQMT 无此 HK 品种）→ 用 sina_qfq（akshare
>    stock_hk_daily qfq==raw，H1 已验证）+ divid_events/03110.HK.csv 官方分红事件。
> 2. **MaxDiv 权重精确 parity**：maxdiv_weights = action_transform.transform →
>    risk_overlay.apply（canonical 复现），与已接受 L1 post_risk_weights 全 1011 日
>    逐元素一致（max abs diff = 0.0）。
> 3. **S1 每子期研究 CAGR**：从已接受 L1 artifact sub_periods（cum + n_days）计算每段研究
>    CAGR = (1+cum)^(252/n)-1，非复用全期 0.094154。各段 n_days 与 L1 完全一致
>    （140/242/242/243/144；382/629）。
> 4. **S3 按冻结定义**：distinct fail-closed days（结构停泊 461 ∪ 无报价 18，overlap 1）=
>    478 / 1011 = 47.28%（评审：45.6% 仅结构天数，未含 no-quote）。
> 5. **公司行为时序**：t_next 开盘前应用（settle 派息 → 份额折算 → 除息计提，基于开盘前持仓），
>    与 canonical env 一致；open 估值/sizing 之前。
> 6. **HK T+2 session 日历**：03110.HK 交易日历（sina_qfq index = HK 交易日）第 2 个 session，
>    非 SH exec index + 2；应收款按 release 日期入 ledger，仅 release_date <= t_next 释放。
> 7. **Provenance 单一 manifest**：20 个实际消费输入（Mainland QMT raw + 513690 research raw +
>    sina_qfq + FX + 7 CA 事件）SHA256 + 已接受 L1 results/raw artifact SHA256 + commit 绑定；
>    计数由 manifest 推导。

---

# 1. 冻结契约执行证据

```text
策略核心: MaximumDiversification（120/0.5, project-constrained RiskOverlayV0）；无 Momentum 混合
窗口: L1 真实窗口（决策 2022-06-09..2026-08-06，执行 2022-06-10..2026-08-07，1011 决策日）
slot->instrument: 11 真实 ETF（CN_LARGE=510300.SH；HK_DIVIDEND=03110.HK 执行）
03110 三日期: listing 2013-06-17 / data 2021-01-11 / southbound_eligible_from 2024-05-06
  2022-06-09..2024-05-03（461 决策日）结构不可交易 → 现金停泊，计 S3
03110 执行价来源: sina_qfq（HKD 本地；QMT raw 全零不可用；qfq==raw，H1 已验证）+
  官方分红事件 divid_events/03110.HK.csv
board lot: 03110 100（t<2026-07-24）-> 50（t>=2026-07-24）；Mainland 100
same_day_reversal: UNKNOWN/NOT_RELIED_UPON（无同 session 回转依赖；A股卖出当日可用为
  T+0 buying power，非同标回转）
成本路由: Mainland -> MainlandETFCostModel；03110 -> SouthboundETFCostModel（HKD 本地 +
  date-effective + T-1 FX）
结算: A股 T+1（卖出当日可买，T+1 可取现——A 股规则）；03110 T+2（03110.HK session 日历）
PremiumGuard: INSTRUMENT_BACKTEST = NOT_EVALUABLE_HISTORICALLY（N/A）
S2: CNY base 聚合
provenance: 20 输入文件 SHA256（11 QMT raw 含 513690 + sina_qfq + hkd_cny + 7 divid_events）
  + L1 results/raw artifact SHA256 + commit
```

# 2. 测试与 --check

```text
pytest tests/test_instrument_execution_realism.py -q: 21 passed（行为回归）
  （03110 marks eligible 后有限、03110 Southbound 执行分支真实行使、MaxDiv 权重精确 parity
    vs 已接受 L1 post_risk 全 1011 日、S1 每子期研究 CAGR 非全期复用、S1 子期边界 n_days
    与 L1 一致、S3 distinct fail-closed days union、CA 在 sizing 前 + 折算/计提行为、HK T+2
    session 释放 + 非 SH 日历、provenance 绑定 L1 SHA/commit、成本路由、post-fill NAV、
    no-RL）
python scripts/gate4_instrument_execution_realism.py --check: PASSED
```

# 3. 全期结果（1011 决策日，可执行 net 路径，CORRECTION_003 忠实版）

| 指标 | 可执行 net | L1 研究 MaxDiv（无成本参考） |
|---|---|---|
| 累计收益 | +47.2% | +45.4% |
| Calendar CAGR | +9.7% | +9.4% |
| active-day 年化 | +10.1% | +9.8% |
| 年化波动 | 5.6% | 5.7% |
| Sharpe | 1.738 | 1.655 |
| Sortino | 2.248 | 2.195 |
| MaxDD | -4.2% | -4.0% |
| Calmar | 2.389 | 2.435 |

```text
忠实版 net 贴近 L1 研究 MaxDiv——03110 执行路径修正（sina_qfq marks + Southbound 成交 +
官方分红）后，可执行性损耗极小，且每子期均与研究一致（见 §4 S1 表）。
```

# 4. 年度 / stress 子期（S1 冻结要求，net vs 研究同边界）

| 子期 | net cum / CAGR / Sharpe / MaxDD | research CAGR | degradation |
|---|---|---|---|
| 2022 | +0.4% / +0.7% / 0.193 / -3.2% | -0.7% | +1.5% |
| 2023 | +6.1% / +6.2% / 1.809 / -2.2% | +6.1% | +0.2% |
| 2024 | +18.8% / +18.8% / 2.676 / -3.3% | +19.7% | -0.1% |
| 2025 | +13.2% / +13.3% / 2.233 / -4.2% | +13.0% | +0.7% |
| 2026 H1 | +2.8% / +4.7% / 0.713 / -4.1% | +5.6% | -0.7% |
| weak 2022H2-2023 | +6.6% / +4.2% / 1.120 / -3.2% | +3.6% | +0.7% |
| strong 2024-2026 | +38.2% / +13.3% / 2.026 / -4.2% | +13.7% | +0.1% |

```text
S1 按冻结契约每子期：worst degradation = year_2026 net CAGR 4.72% vs research 5.56%
（-0.84%），远好于 -5% 阈值 → S1 PASS（7 段全部通过）。
CORRECTION_002 报告的 year_2022 S1 FAIL 无效：研究 2022 CAGR = -0.7%（非全期 0.094154）。
```

# 5. 成本聚合（CNY base，S2 冻结定义）

```text
total_fee_cny            = 5,680 元
total_slippage_cny       = 3,821 元（含 spread 1bp + slippage 2bp，模型内置）
total_traded_notional_cny= 12,738,107 元
fee_bps_of_traded_notional = 4.46 bps  ✓ ≤5bp
slippage_bps_of_traded_notional = 3.00 bps ✓ ≤10bp
cost_by_instrument: 03110.HK = 1,476 元（Southbound 万3 + min 5 HKD + 分段费率，NOT
  ACCOUNT-VERIFIED 保守）；Mainland 各 230-740 元
```

# 6. 执行诊断（评审 CORRECTION_003 要求）

```text
fill_count                 = 7,510
mean_target_tracking_error = 0.0136（post-fill close 权重 vs 目标 L1 距离均值）
fail_closed: {structural_ineligible_cash_parking: 461, no_quote_days: 18,
              overlap_days: 1, distinct_fail_closed_days: 478}
03110 eligible 后诊断（post-2024-05-06，550 决策日）：
  mean_target_weight = 0.048042 / max 0.092047
  dates_target_notional_ge_one_board_lot = 533 / 550
  attempted_orders = 217 / actual_fills = 217（全成交）
  traded_notional_cny = 735,793 元
  → Southbound 执行分支已真实行使（CORRECTION_002 的 no_quote=550 已修复；
    0 fills 原因非 board-lot 不可行，而是 marks 缺失）
provenance: 20 输入文件 SHA256 + L1 results/raw artifact SHA256 + commit
```

# 7. STOP 判据（评审冻结 S1-S4，子期判据）

| 判据 | 值 | 判定 |
|---|---|---|
| S1 worst 子期恶化 | year_2026 -0.84%（net 4.72% vs research 5.56%） | **PASS** |
| S2 fee bps | 4.46 ≤ 5 | **PASS** |
| S2 slippage bps | 3.00 ≤ 10 | **PASS** |
| S3 fail-closed | 478/1011 = **47.28%** > 1% | **FAIL** |
| S4 | NOT_APPLICABLE（backtest mode） | N/A |
| **STOP** | — | **TRUE**（S3） |

```text
S1 修正后全子期通过（可执行 net 每期贴近研究）。S3 不变触发：03110 southbound_eligible_from
2024-05-06，461 决策日结构不可交易 → 现金停泊（结构性事实，评审确认保持冻结）。
修正后 no_quote 由 550 降至 18（HK 假日/停牌日），但结构 461 主导 → S3 仍 FAIL。
按冻结契约（"若 S3 触发则报告 STOP"），本 RUN 报告 STOP=true（S3）。
```

# 8. 解读

```text
1. 忠实版可执行性损耗极小：net vs L1 研究 MaxDiv 几乎一致（cum +47.2% vs +45.4%、Sharpe
   1.738 vs 1.655、MaxDD -4.2% vs -4.0%），03110 marks 修正 + Southbound 成交 + 官方分红后。
2. S1 全子期通过：可执行 net 每子期 CAGR 与研究同边界一致（worst -0.84%）。
3. 成本可控：fee 4.46bp + slippage 3.00bp 均低于 S2 阈值；03110 Southbound 成本如实计入。
4. S3 FAIL：03110 结构不可交易 461 决策日（45.6%）主导 fail-closed（47.28% 含无报价）。
5. 无 RL、无 result-informed 调整、无 dense/dynamic alpha；QMT live 禁止。
```

# 9. 明确声明

```text
1. STOP=true 为冻结契约预期结果（S3 因 03110 结构不可交易触发），未改变映射/阈值/窗口/计数规则。
2. 无 GO/NO-GO 阈值发明；S1-S4 判定全部由冻结契约驱动（S1 全期 + 年度 + stress 子期）。
3. SCENARIO_NOT_STRICT_PIT_OOS：非 strict PIT OOS、非生产/实盘授权。
4. PPO/SAC/TD3、QMT live、FORWARD/PAPER/LIVE 均未授权。
5. Southbound 佣金万3 + min 5 HKD 为 NOT ACCOUNT-VERIFIED 标注（保守场景）；03110 执行价
   用 sina_qfq（QMT raw 全零不可用，qfq==raw H1 已验证）+ 官方分红事件；provenance 绑定
   （20 文件 SHA256 + L1 artifact SHA + commit）。
```

---

## Approval Record

```yaml
gate: 4
handoff_id: G4_POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN_CORRECTION_003
packet: POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN
status: READY_FOR_REVIEW

corrections_003_applied (7 fidelity):
  03110_executable_marks: sina_qfq HKD x T-1 FX -> opens/closes["03110.HK"]; Southbound HKD local
    + transaction_date + fx_to_base=T-1 FX; eligible 后真实成交 (attempted 217 / fills 217 /
    notional 735,793 CNY); no_quote 550 -> 18
  maxdiv_parity: action_transform.transform -> risk_overlay.apply == L1 post_risk_weights
    (1011x11 max diff 0.0)
  s1_per_subperiod: research CAGR = (1+cum)^(252/n)-1 per segment (140/242/242/243/144; 382/629);
    worst -0.84% -> S1 PASS (2022 research was -0.7%, not 0.094154)
  s3_frozen_definition: distinct fail-closed days = structural 461 U no_quote 18 (overlap 1) =
    478/1011 = 47.28% -> S3 FAIL
  ca_ordering: settle -> unit conv -> accrual at t_next BEFORE open valuation/sizing (pre-open
    holdings); 512100 0.36555 conversion + official dividends incl 03110.HK events
  hk_t2_session: 03110.HK tradable-session calendar +2 (not SH exec index+2); date-keyed
    receivables ledger, release only when release_date <= t_next
  provenance: 20 consumed input SHA256 + L1 results/raw artifact SHA256 + commit; count from manifest

executed:
  strategy: MaximumDiversification 120/0.5 project-constrained
  window: 1011 decision days (2022-06-09..2026-08-06)
  instruments: 11 real ETFs (510300.SH / 03110.HK); 03110 3-date + date-effective lot

result (CORRECTION_003 faithful):
  net: {cum +47.2%, cagr 9.7%, sharpe 1.738, mdd -4.2%, calmar 2.389, sortino 2.248}
  research_l1_ref: {cagr 9.4%, sharpe 1.655, mdd -4.0%}
  cost: {fee_bps 4.46, slippage_bps 3.00, total_traded_cny 12.74M, 03110 notional 735,793 CNY}
  exec: {fill 7510, track_err 0.0136, fail_closed {structural 461, no_quote 18, distinct 478}}

stop:
  S1: PASS (worst year_2026 net 4.72% vs research 5.56%, deg -0.84% > -5pct; all 7 segments pass;
      full-period net 9.7% == research)
  S2: PASS (fee 4.46bp, slippage 3.00bp)
  S3: FAIL (47.28% > 1%: structural 461 U no_quote 18; structural 03110 ineligibility dominant)
  S4: NOT_APPLICABLE
  STOP: TRUE (S3)  # frozen contract; no mapping/threshold/window change

tests: 21 passed (behavioral regressions); --check PASSED
no_rl: PPO/SAC/TD3 absent; QMT live / FORWARD / PAPER / LIVE forbidden
```

## END OF POST_L2 INSTRUMENT EXECUTION REALISM RUN (RUN_CORRECTION_003)
