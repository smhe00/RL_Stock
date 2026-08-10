# POST_L2 INSTRUMENT EXECUTION REALISM PREP — Instrument 级执行真实化实验（冻结契约，最终修正版）

> 评审（`POST_L2_INSTRUMENT_EXECUTION_REALISM_PREP_CORRECTION_REVIEWER_RESPONSE.md`）
> **EXECUTION_REALISM_PREP_CORRECTION_PARTIAL_PASS_SOUTHBOUND_CONTRACT_FIX_REQUIRED** → 本 packet 为 **最终修正**。
> **PREP only，不运行实验。** handoff_id = **G4_POST_L2_INSTRUMENT_EXECUTION_REALISM_PREP_CORRECTION_002**。

> ## Revision Record（CORRECTION_002，评审 6 项 Southbound 契约修正）
>
> 1. **03110.HK 三日期分离**：`listing_date = 2013-06-17`、`local_data_start = 2021-01-11`（数据集可用性，
>    非 listing/资格）、`southbound_eligible_from = 2024-05-06`。2022-06-09..2024-05-03 为
>    **结构不可交易期** → HK_DIVIDEND 权重停泊于现金（冻结 parking 资产），计 S3 fail-closed。
> 2. **Date-effective board lot**：`t < 2026-07-24 → lot 100`；`t >= 2026-07-24 → lot 50`
>    （Gate-1 D-012：Global X/HKEX 官方；Broker 支持 UNKNOWN_PENDING_GATE6——历史仿真用官方 lot，
>    不代表券商支持）。
> 3. **Same-day reversal = UNKNOWN/NOT_RELIED_UPON**（D-015 C1 carry-forward）：策略冻结 T 收盘 →
>    T+1 开盘执行，不依赖同日回转；invariant 禁止历史 runner 使用同 session 回转。
> 4. **成本路由**：Mainland-listed → `MainlandETFCostModel`；`03110.HK` → `SouthboundETFCostModel`
>    （佣金万3 双边 + min 5 HKD **NOT ACCOUNT-VERIFIED** 标注；ETF 印花税 **0**——移除 packet 的 0.1% 声明；
>    date-effective HKEX 交易费/SFC/AFRC/结算费档保留；敏感性可加但不替换 base 路由）。
> 5. **结算**：03110.HK 按 Southbound/HK 结算滞后期（T+2）；未结算卖出款不得用于后续买入
>    （ledger invariant 防未结算现金复用）；"T+1 统一并称 conservative" 移除（更早现金可用非保守）。
> 6. **PremiumGuard 历史语义**：`INSTRUMENT_BACKTEST` mode = `NOT_EVALUABLE_HISTORICALLY`
>    （历史无实时 IOPV，D-011）→ 排除于历史 PnL，报告 N/A；PAPER/LIVE 保持 fail-closed。
>    **S2 基准货币**：`total_traded_notional_base_cny = Σ|qty×exec_price_local|×fx_to_base_at_execution`；
>    fee/slippage bps 用 CNY base（不混 HKD/CNY notional）。

> ## Revision Record（EXECUTION_REALISM_PREP_CORRECTION，评审 4 项契约修正）
>
> 1. **HK_DIVIDEND 映射**：冻结已审计 **03110.HK**（Gate-1 冻结 universe；有审计 listing/Southbound/lot/
>    provenance；data/qmt/raw/HK_DIVIDEND_03110_HK_raw.csv 2021-01-11 起 + divid_events/03110.HK.csv
>    官方派息）。显式建模 HKEX/Southbound 执行约束（Southbound eligible、T+0、HK lot、FX HKD->CNY）。
>    513690.SH 为替代 instrument（不采用为执行路径；避免 instrument 替换需额外 provenance）。
> 2. **费用契约 = 仓库 MainlandETFCostModel 现状**：commission 0.00005（万0.5）、ETF 印花税 0、
>    exchange_fee 0（inclusion = UNKNOWN_PENDING_BROKER_FEE_AUDIT，待账户核实）、half_spread 1bp +
>    slippage 2bp（**已含滑点**）。不虚构"万1~万3 + 印花税 0.05%"；不新增 5bp 滑点 overlay
>    （避免与 half_spread/slippage_bps 双计）。
> 3. **PremiumGuard = availability-only 历史语义**：IOPV 缺失/过期 → fail-closed 禁买（允许持有/卖出）；
>    **无 premium-magnitude threshold**（当前实现不触发转 cash）；`close_to_official_nav_gap` 不得
>    伪装成实时 premium 阈值。本历史执行真实化轨道不做"premium>阈值→cash"。
> 4. **S2 分母冻结**：`fee_bps_of_traded_notional = total_fee/total_traded_notional × 1e4`；
>    `slippage_bps_of_traded_notional = total_slippage/total_traded_notional × 1e4`（runner/artifact/
>    STOP 同一约定）。

---

# 0. 已接受上下文（固定输入，不重开）

```text
架构门已关闭：静态 MaxDiv/Momentum 混合不满足"有用架构"定义（C2-C4 全 R2-R4 失败）；
纯 MaxDiv（C0）为冻结策略核心（Sharpe 1.024 / MaxDD -10.4% / CAGR 6.0%，L2 gen3 接受）。
本 PREP 将 MaxDiv 核心映射到可执行真实 ETF instrument 路径，区分 research-return vs 可执行性能。
L1（真实 ETF 短窗）/ L2（scenario proxy 长窗）结果 frozen；PPO/SAC/TD3、QMT live 禁止。
```

# 1. 冻结策略核心（评审 emphasis）

```text
策略 = MaximumDiversification（lookback 120, shrinkage 0.5, project-constrained RiskOverlayV0）
决策：T 收盘 → T+1 开盘执行（下一可交易 session）
权重：RiskOverlayV0（single≤25%、CHINEXT+STAR≤50%、long-only、sum=1）
父参数冻结；不引入 Momentum 混合（架构门已判）；不调参。
```

# 2. Slot → 真实 Instrument 映射 + 上市可用性（冻结）

```text
真实工具映射（现有 data/qmt/raw，上市日期硬边界；pre-launch 不可交易）：
  CN_LARGE     -> 510300.SH（沪深300ETF，2012-05-28 起数据）
  CN_SMALL     -> 512100.SH（中证1000ETF，2016-11-04）
  CN_DIVIDEND  -> 512890.SH（红利ETF，2019-01-18）
  CHINEXT      -> 159915.SZ（创业板ETF，2011-12-09）
  STAR         -> 588000.SH（科创50ETF，2020-11-16）
  HK_TECH      -> 513180.SH（恒生科技ETF，2021-05-25）
  HK_DIVIDEND  -> 03110.HK（恒生高股息，2021-01-11 起 raw 数据；审计冻结 universe）
  US_BROAD     -> 513500.SH（标普500ETF，2014-01-15）
  GOLD         -> 518880.SH（黄金ETF，2013-07-29）
  CN_DURATION  -> 511260.SH（十年国债ETF，2017-08-24）
  CASH_LIKE    -> 511360.SH（短融ETF，2020-09-25）
可执行窗口：全部 11 工具 finite 首日 + 252d warmup（= L1 窗口：决策 2022-06-09..2026-08-06，
  执行 2022-06-10..2026-08-07，1011 决策日）——复用已接受 L1 真实窗口，不重推。
上市前：对应槽位不可交易 → 若窗口内某工具未上市，用 cash-like 停泊（fail-closed，见 §6）。

## 2b. HK_DIVIDEND 执行约束（评审修正 #1，03110.HK 冻结）

```text
instrument: 03110.HK（恒生高股息，HKEX 上市；审计冻结 universe）
三日期分离（Gate-1 冻结）:
  listing_date              = 2013-06-17
  local_data_start          = 2021-01-11（数据集可用性，非 listing/资格）
  southbound_eligible_from  = 2024-05-06
  → 2022-06-09..2024-05-03 为结构不可交易期：HK_DIVIDEND 权重停泊现金（冻结 parking 资产），计 S3。
数据: data/qmt/raw/HK_DIVIDEND_03110_HK_raw.csv + divid_events/03110.HK.csv（官方派息）→ 研究复权 TR
FX: HKD->CNY hkd_cny_boc（T-1，与 L2 一致）
执行约束（冻结）:
  - Southbound 资格: eligible_from 2024-05-06（Gate-1 审计）；此前结构不可交易
  - Same-day reversal = UNKNOWN/NOT_RELIED_UPON（D-015 C1；不依赖同日回转）
  - Lot（date-effective，D-012）: t < 2026-07-24 → 100 股；t >= 2026-07-24 → 50 股
    （港股通整手；碎股不可市价；Broker 支持 UNKNOWN_PENDING_GATE6，历史仿真用官方 lot）
  - 结算: HK T+2；未结算卖出款不得用于后续买入（ledger invariant）
  - 成本: SouthboundETFCostModel（佣金万3 双边 + min 5 HKD NOT ACCOUNT-VERIFIED 标注；
    ETF 印花税 0；date-effective 交易费/SFC/AFRC/结算费档）
  - 缺失/停牌: fail-closed（同 §6）
```

> 注：513690.SH（境内 Track A wrapper）在 L1/L2 作研究序列；本执行真实化轨道采用 03110.HK
> 对齐审计冻结 universe。成本经 SouthboundETFCostModel（非 Mainland base case），佣金未账户核实
> 如实标注；敏感性可加但不替换 base 路由。

# 3. 执行日历 / next-session 语义（冻结）

```text
决策日历：SH 交易日历（L1 数据日历，含 2026-08-07）。
next-session 执行：T 收盘决策 → T+1 该工具可交易首 session 开盘成交（非跨段同日）。
T+0/T+1：A股 ETF 场内 T+0 回转受标的限制——本实验按"次日开盘执行、T+1 交收"建模
  （简化：买入 T+1 到账，卖出 T+1 资金可用，下一决策可用）。
HK/QDII（513180/513690/513500）：QDII 净值/价格反映前夜海外，T-1 信息（同 L2 信号 lag）。
缺失/停牌报价：fail-closed——若 T+1 开盘无有效报价，权重保持不变（不强制成交），
  连续 N 日无报价则记 STOP 信号（见 §6）。
```

# 4. 成本 / 费用 / 滑点 / 手数 / 结算（冻结，评审修正 #2）

```text
成本路由（冻结）:
  Mainland-listed（510300/512100/512890/159915/588000/513180/513500/518880/511260/511360）
    （CN_LARGE = 510300.SH；runner 映射断言防错码）
    → MainlandETFCostModel 现状（不虚构）:
      broker_commission_rate = 0.00005   # 单边万0.5
      stamp_duty_rate = 0.0              # ETF 免印花税
      exchange_fee_rate = 0.0            # inclusion = UNKNOWN_PENDING_BROKER_FEE_AUDIT
      half_spread_bps = 1.0              # 已含
      slippage_bps = 2.0                 # 已含
      → 不新增滑点 overlay（无双计）。
  03110.HK → SouthboundETFCostModel（评审修正 #4）:
      佣金 0.0003 双边 + min 5 HKD（NOT ACCOUNT-VERIFIED 标注）
      ETF 印花税 0（移除 0.1% 声明）
      date-effective HKEX 交易费 / SFC / AFRC / 结算费档（保留）
      → base 路由为 Southbound 模型；敏感性可加但不替换 base。
PremiumGuard：INSTRUMENT_BACKTEST mode = NOT_EVALUABLE_HISTORICALLY（评审修正 #6，D-011：
  历史无实时 IOPV）→ 排除于历史 PnL，报告 N/A；PAPER/LIVE 保持 fail-closed。
  不伪造 IOPV；close_to_official_nav_gap 不作实时阈值。
手数：A股 ETF 100 份整数倍；03110.HK date-effective lot（100→50 @ 2026-07-24）；
  金额舍入到最小手数（不产生碎股）。现金残差保留。
结算：A股 T+1；03110.HK 按 HK/Southbound 结算滞后期（T+2）——未结算卖出款不得用于后续买入
  （ledger invariant 防未结算现金复用；不称"T+1 更保守"）。T 决策用已结算现金 + 持仓。
费用入账：成交时扣（commission + half_spread + slippage / Southbound 模型各项）；无 premium→cash。
```

# 5. 数据 / 报价（冻结）

```text
执行价：现有 data/qmt/raw open/close（A股 + HK/QDII）。
研究收益：现有研究复权 adj（含公司行为：分红/拆分；与 corrected 路径一致）。
FX：HKD->CNY hkd_cny_boc（T-1，与 L2 一致）；USD 已含于 QDII 人民币份额。
公司行为：复用 corporate_actions（ex_date 计提/折算、settle_date 派息，官方 pay_date + 保守 fallback）。
缺失/坏行：真实上市期内可 re-fetch/repair（保留 provenance）；pre-launch backfill 禁止。
```

# 6. Fail-closed 行为 + STOP 判据（冻结）

```text
Fail-closed：
  - 某工具上市前/结构不可交易期（03110.HK southbound_eligible_from 2024-05-06 前）→ 该槽位
    权重现金停泊（冻结 parking 资产），计 S3 fail-closed；
  - T+1 无有效报价 → 权重保持不变（不强制成交），连续 ≥5 session 无报价 → STOP 信号；
  - PremiumGuard：INSTRUMENT_BACKTEST = NOT_EVALUABLE_HISTORICALLY（无实时 IOPV，D-011）→
    排除历史 PnL、报告 N/A，不阻塞历史买入；PAPER/LIVE fail-closed；
  - 任何 NaN/非有限观察 → 抛错（不静默填 0）。
STOP 判据（满足任一 → 停止并返回 blocker，不推进 forward/paper）：
  S1: 可执行净收益对任意子期（年度/stress regime）相对无成本 research 收益恶化 > 5pct CAGR
      （成本+滑点不可吸收）；
  S2（CNY base，评审澄清）：
      total_traded_notional_base_cny = Σ|qty × exec_price_local| × fx_to_base_at_execution
      fee_bps_of_traded_notional = total_fee_base_cny / total_traded_notional_base_cny × 1e4
      slippage_bps_of_traded_notional = total_slippage_base_cny / total_traded_notional_base_cny × 1e4
      （不混 HKD/CNY notional；runner/artifact/STOP 同一 FX 约定）；S2 通过 iff
      fee_bps <= 5bp 且 slippage_bps <= 10bp；
  S3: fail-closed 事件 > 1% 决策日（上市前/结构不可交易停泊/无报价）；
  S4: INSTRUMENT_BACKTEST mode = NOT_APPLICABLE / NOT_EVALUATED（历史无实时 IOPV，D-011）——
      排除于 STOP 评估；>5% IOPV fail-closed 触发率仅保留于未来 PAPER/LIVE 门（有实时 IOPV）。
```

# 7. 评估指标 / 子期（冻结）

```text
每策略（可执行 net 路径）：cum / Calendar CAGR / active-day ann / vol / Sharpe / Sortino /
  MaxDD / Calmar / worst year / worst 12m / mean turnover / total cost / cost/traded /
  cost/initial / slippage / premium events / fail-closed counts / 平均 active assets / HHI。
子期：年度 + 已接受 stress regimes（2022H2-2023 弱股 / 2024-2026 强股）。
对照：无成本 research MaxDiv（L1 gen3，已接受）作为"可执行性损耗"基准——报告 net vs research
  之差，区分 research-return 与 instrument-level 性能（评审 emphasis）。
```

# 8. 测试 / Invariants（冻结）

```text
tests/test_instrument_execution_realism.py（新，CONSISTENCY_CLEANUP 后）：
  - slot->instrument 映射精确（HK_DIVIDEND = 03110.HK；CN_LARGE = 510300.SH 断言防错码）
    + 三日期分离断言（listing 2013-06-17 /
    data-start 2021-01-11 / southbound_eligible_from 2024-05-06）
  - 结构不可交易期权重现金停泊 + 计 S3（2022-06-09..2024-05-03）
  - next-session 执行（决策 T → T+1 开盘；无同日/跨段）；same_day_reversal 不依赖 invariant
  - date-effective board lot（03110: 100→50 @ 2026-07-24 过渡）
  - 成本路由：Mainland->MainlandETFCostModel；03110->SouthboundETFCostModel（ETF 印花税 0，
    min 5 HKD NOT ACCOUNT-VERIFIED 标注）；无双计
  - 结算：03110 T+2；未结算卖出款不得用于后续买入（ledger invariant）
  - PremiumGuard backtest mode = NOT_EVALUABLE_HISTORICALLY（不阻塞历史买入，报告 N/A）
  - S2 CNY base 聚合（不混 HKD/CNY；fee/slippage bps of traded notional × 1e4）
  - 现金残差守恒 + 无研究收益冒充可执行收益（net 路径独立）
  - 无 RL（runner 源码无 RL 导入/字面量）
scripts/gate4_instrument_execution_realism.py --check：契约验证通过后执行（RUN 授权后）。
failed invariant = STOP condition。
```

# 9. 明确声明

```text
本 PREP 不运行实验。授权下一门：POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN（需单独评审）。
FORWARD/PAPER/LIVE 未授权；PPO/SAC/TD3 禁止；QMT live 禁止；无 result-informed 调整。
L1/L2 结果 frozen；本研究不升级为 strict PIT OOS 或 live 证据。
```

---

## Approval Record

```yaml
gate: 4
handoff_id: G4_POST_L2_INSTRUMENT_EXECUTION_REALISM_PREP_CONSISTENCY_CLEANUP_001
packet: POST_L2_INSTRUMENT_EXECUTION_REALISM_PREP
status: READY_FOR_REVIEW

consistency_cleanup_applied:
  stale_freeze_block: removed (single canonical frozen summary only, matching Sections 2b/4/6/8)
  typo_fix: CN_LARGE 513300 -> 510300.SH + mapping assertion test planned
  s4_normalized: backtest mode = NOT_APPLICABLE/NOT_EVALUATED, excluded from STOP; >5% IOPV criterion preserved only for PAPER/LIVE gate

correction_002_applied:
  southbound_dates: 03110 listing 2013-06-17 / data-start 2021-01-11 / southbound_eligible_from 2024-05-06; pre-eligibility weight parked in cash, counts toward S3
  board_lot_date_effective: 100 (t<2026-07-24) -> 50 (t>=2026-07-24); broker support UNKNOWN_PENDING_GATE6
  same_day_reversal: UNKNOWN/NOT_RELIED_UPON (D-015 C1); invariant: runner never depends on same-session reversal
  cost_routing: Mainland -> MainlandETFCostModel; 03110.HK -> SouthboundETFCostModel (commission 0.0003 + min HKD5 NOT ACCOUNT-VERIFIED; ETF stamp duty 0, 0.1% claim removed; date-effective HK fees)
  settlement: 03110 HK T+2; no unsettled-cash reuse (ledger invariant); T+1-not-conservative removed
  premium_guard: INSTRUMENT_BACKTEST mode = NOT_EVALUABLE_HISTORICALLY (excluded from historical PnL, reported N/A; PAPER/LIVE fail-closed); no fabricated IOPV
  s2_currency: total_traded_notional_base_cny = sum|qty*exec_price_local|*fx_to_base; fee/slippage bps in CNY base (no HKD/CNY mixing)

frozen:   # 单一 canonical 冻结记录（CORRECTION_002 最终契约；无残留旧语义）
  strategy_core: MaximumDiversification (120/0.5, project-constrained RiskOverlayV0); no Momentum blend (architecture gate closed)
  slot_to_instrument: 11 real ETFs mapped (listed dates hard boundaries); CN_LARGE=510300.SH; HK_DIVIDEND=03110.HK
  hk_dividend_dates: {listing: 2013-06-17, data_start: 2021-01-11, southbound_eligible_from: 2024-05-06}
  pre_eligibility: 2022-06-09..2024-05-03 HK_DIVIDEND parked to cash, counts S3
  window: L1 real-instrument window reused (decision 2022-06-09..2026-08-06, exec 2022-06-10..2026-08-07, 1011 days)
  execution: T close decision -> T+1 next-session open execution; same_day_reversal UNKNOWN/NOT_RELIED_UPON; T-1 info for HK/QDII
  board_lot: 03110 100 (t<2026-07-24) -> 50 (t>=2026-07-24); Mainland 100
  costs: Mainland -> MainlandETFCostModel (commission 0.00005, stamp 0, exchange_fee 0 UNKNOWN, half_spread 1bp + slippage 2bp, no extra overlay);
        03110.HK -> SouthboundETFCostModel (commission 0.0003 + min HKD5 NOT ACCOUNT-VERIFIED, ETF stamp 0, date-effective HK fees)
  settlement: A股 T+1; 03110.HK T+2, no unsettled-cash reuse (ledger invariant)
  premium_guard: INSTRUMENT_BACKTEST = NOT_EVALUABLE_HISTORICALLY (excluded PnL, N/A; PAPER/LIVE fail-closed); no fabricated IOPV; no close_to_official_nav_gap threshold
  data: existing data/qmt/raw open/close + research adj + CA + hkd_cny T-1
  fail_closed: pre-listing/structural-ineligible cash parking, no-quote hold weights (>=5 sessions STOP), NaN raise
  stop_criteria: S1 net CAGR degradation >5pct vs research (per subperiod); S2 fee/slippage bps of traded notional (CNY base, fee<=5bp & slippage<=10bp);
                S3 fail-closed >1% days; S4 NOT_APPLICABLE in backtest mode (PAPER/LIVE only: IOPV fail-closed >5%)
  s2_currency: total_traded_notional_base_cny = sum|qty*exec_price_local|*fx_to_base; fee/slippage bps in CNY base
  metrics: full net table + annual/stress subperiods + net-vs-research loss attribution
  tests: mapping/listing (incl. 510300 assertion), next-session exec, date-effective lot, cost routing, settlement T+2 no-unsettled-reuse, PremiumGuard backtest N/A, S2 CNY base, no-RL

not_done:
  execution_realism_run: false   # PREP only; wait for review
  forward_paper_validation: false
  paper: false
  live: false
  rl: false
  qmt_live: false
```

## END OF POST_L2 INSTRUMENT EXECUTION REALISM PREP
