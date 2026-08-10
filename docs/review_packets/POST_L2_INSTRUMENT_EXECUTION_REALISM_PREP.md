# POST_L2 INSTRUMENT EXECUTION REALISM PREP — Instrument 级执行真实化实验（冻结契约，修正版）

> 评审（`POST_L2_INSTRUMENT_EXECUTION_REALISM_PREP_REVIEWER_RESPONSE.md`）
> **EXECUTION_REALISM_PREP_SUBSTANTIALLY_CORRECT_CONTRACT_FIX_REQUIRED** → 本 packet 为 **PREP 修正**。
> **PREP only，不运行实验。** handoff_id = **G4_POST_L2_INSTRUMENT_EXECUTION_REALISM_PREP_CORRECTION_001**。

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
instrument: 03110.HK（恒生高股息，HKEX 上市）
数据: data/qmt/raw/HK_DIVIDEND_03110_HK_raw.csv（open/close，2021-01-11 起 1116 行）
     + data/qmt/meta/divid_events/03110.HK.csv（官方派息）→ 研究复权 TR
FX: HKD->CNY hkd_cny_boc（T-1，与 L2 一致）
执行约束（冻结）:
  - Southbound 资格: 港股通可交易（Gate-1 审计）；本实验按 Southbound 可执行建模
  - T+0 回转: HK 支持 T+0（盘中买卖）；本实验决策 T → T+1 开盘买入、T+1 可卖出
  - Lot: HK 每手 100 股（港股通按整手；碎股不可市价）
  - 结算: T+2 交收（HKEX）；本实验简化 T+1 到账（与 A股一致保守）——或明确 T+2（见 §4）
  - 费用: HK 佣金 + 印花税（0.1% 双边）+ 交易费（0.00565%）+ 交易征费（0.0027%）
    ——本实验 base case = 仓库 MainlandETFCostModel（境内简化），HK 费用作为 sensitivity
    （明确标注非 Southbound 完整费率，评审 guard #6 同 L2 处理）
  - 缺失/停牌: fail-closed（同 §6）
```

> 注：513690.SH（境内 Track A wrapper）在 L1/L2 作研究序列；本执行真实化轨道采用 03110.HK
> 以对齐审计冻结 universe，避免 instrument 替换需额外 provenance。HK 完整费率仅作 sensitivity，
> 不冒充 Southbound 净收益。

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
费用契约 = 仓库 MainlandETFCostModel 现状（base case，不虚构）：
  broker_commission_rate = 0.00005   # 单边万0.5
  stamp_duty_rate = 0.0              # ETF 免印花税
  exchange_fee_rate = 0.0            # inclusion = UNKNOWN_PENDING_BROKER_FEE_AUDIT（待账户核实）
  half_spread_bps = 1.0              # 单边半价差（已含）
  slippage_bps = 2.0                 # 单边滑点（已含）
  → 不新增 5bp 滑点 overlay（避免与 half_spread/slippage_bps 双计）。
HK/QDII（03110.HK / 513180 / 513690 / 513500）：
  base case 也用 MainlandETFCostModel（境内简化，labeled）；HK 完整费率（佣金+印花税 0.1%
  双边+交易费 0.00565%+征费 0.0027%）作单独 sensitivity（评审 guard #6，非 Southbound 完整）。
PremiumGuard：availability-only 历史语义（评审修正 #3）——IOPV 缺失/过期 → fail-closed 禁买
  （允许持有/卖出）；无 premium-magnitude threshold；close_to_official_nav_gap 不作实时阈值。
手数：A股 ETF 100 份整数倍；HK 每手 100 股；金额舍入到最小手数（不产生碎股）。现金残差保留。
结算：A股/HK 统一 T+1 交收（保守简化）；T 决策用 T-1 结算后现金 + 持仓（无未到账资金用于 T 决策）。
费用入账：成交时扣（commission + half_spread + slippage）；不设"premium→cash"（当前实现不支持）。
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
  - 某工具上市前 → 该槽位现金停泊（权重转入 CASH_LIKE 槽位，若未上市则残差现金）；
  - T+1 无有效报价 → 权重保持不变（不强制成交），连续 ≥5 session 无报价 → STOP 信号；
  - PremiumGuard（availability-only）：IOPV 缺失/过期 → 禁买该槽位（允许持有/卖出），记录原因；
    不设 premium-magnitude threshold（当前实现无该语义；close_to_official_nav_gap 不作实时阈值）；
  - 任何 NaN/非有限观察 → 抛错（不静默填 0）。
STOP 判据（满足任一 → 停止并返回 blocker，不推进 forward/paper）：
  S1: 可执行净收益对任意子期（年度/stress regime）相对无成本 research 收益恶化 > 5pct CAGR
      （成本+滑点不可吸收）；
  S2: fee_bps_of_traded_notional > 5bp 或 slippage_bps_of_traded_notional > 10bp，其中
      fee_bps_of_traded_notional = total_fee / total_traded_notional × 1e4
      slippage_bps_of_traded_notional = total_slippage / total_traded_notional × 1e4
      （runner/artifact/STOP 同一约定，评审澄清 #4）；
  S3: fail-closed 事件 > 1% 决策日（上市前停泊/无报价/IOPV fail-closed）；
  S4: IOPV fail-closed 禁买触发率 > 5% 决策日（US_BROAD 可执行性证据）。
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
tests/test_instrument_execution_realism.py（新，评审修正后）：
  - slot->instrument 映射精确（HK_DIVIDEND = 03110.HK 冻结）+ 上市日期硬边界断言
  - next-session 执行（决策 T → T+1 开盘；无同日/跨段）
  - 成本/费用/滑点/手数入账 + 现金残差守恒；费用契约 = 仓库 MainlandETFCostModel（万0.5、
    印花税 0、half_spread 1bp + slippage 2bp，无双计）
  - T+1 交收时序（T 决策用 T-1 结算后现金）
  - fail-closed（上市前现金停泊、无报价保持权重、IOPV fail-closed 禁买；无 premium-magnitude
    threshold 断言）
  - S2 分母定义（fee/slippage bps of traded notional × 1e4）runner/artifact 一致
  - 无研究收益冒充可执行收益（net 路径独立）
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
handoff_id: G4_POST_L2_INSTRUMENT_EXECUTION_REALISM_PREP_CORRECTION_001
packet: POST_L2_INSTRUMENT_EXECUTION_REALISM_PREP
status: READY_FOR_REVIEW

corrections_applied:
  hk_dividend_mapping: frozen 03110.HK (audited Gate-1 universe, raw data 2021-01-11 + official events); HKEX/Southbound constraints modeled; 513690 not used as exec path
  fee_contract: = repository MainlandETFCostModel (commission 0.00005, ETF stamp 0, exchange_fee 0 UNKNOWN_PENDING, half_spread 1bp + slippage 2bp); no new slippage overlay (no double-count); HK full fees only as labeled sensitivity
  premium_guard: availability-only historical semantics (IOPV missing/stale -> fail-closed buy block; no premium-magnitude threshold; no close_to_official_nav_gap as disguised live threshold)
  s2_denominator: fee_bps_of_traded_notional = total_fee/total_traded_notional*1e4; slippage same (runner/artifact/STOP consistent)

frozen:
  strategy_core: MaximumDiversification (120/0.5, project-constrained RiskOverlayV0); no Momentum blend (architecture gate closed)
  slot_to_instrument: 11 real ETFs mapped (listed dates hard boundaries)
  window: L1 real-instrument window reused (decision 2022-06-09..2026-08-06, exec 2022-06-10..2026-08-07, 1011 days)
  execution: T close decision -> T+1 next-session open execution; T+1 settlement; T-1 info for HK/QDII
  costs: MainlandETFCostModel 1x + 5bp slippage + lot rounding + T+1 settlement; PremiumGuard US_BROAD
  data: existing data/qmt/raw open/close + research adj + CA + hkd_cny T-1
  fail_closed: pre-listing cash parking, no-quote hold weights (>=5 sessions STOP), premium->cash, NaN raise
  stop_criteria: S1 net CAGR degradation >5pct vs research, S2 fees>5bp or slippage>10bp, S3 fail-closed>1% days, S4 premium>5% days
  metrics: full net table + annual/stress subperiods + net-vs-research loss attribution
  tests: mapping/listing, next-session exec, cost/lot/settlement, T+1 timing, fail-closed, no-RL

not_done:
  execution_realism_run: false   # PREP only; wait for review
  forward_paper_validation: false
  paper: false
  live: false
  rl: false
  qmt_live: false
```

## END OF POST_L2 INSTRUMENT EXECUTION REALISM PREP
