# CODEX_AGENT_STATUS

<!-- 按 EXECUTION_SPEC §73 格式维护。Agent 每次恢复工作先读本文件。 -->

## Current Phase

Phase 4 — GATE_4_PILOT_READY_FINAL_FIX 已提交（P1/P2/P3 修复 + P4 术语），
等待 Reviewer 批准 → 之后按评审 §33 直接授权 `GATE_4_3_SEED_PILOT`（不再新增 pre-pilot 方法学工作）

## Last completed task

- 2026-08-08：GATE_4_PILOT_READY_FINAL_FIX 完成 → `docs/review_packets/GATE_4_PILOT_READY_FINAL_FIX.md`
  （P1 wrapper audit 指标分离：03110 HKD since-2013 +179.8% vs Global X 官方 +181.7% PASS；
  CNY 归一化 FX 无 double count；P2 官方派息日 513690 12-20/12-22 + 未知 ex+5T 保守不提前；
  P3 512100 UNIT_CONSOLIDATION factor=0.36555 显式 + 4 真实事件测试；
  P4 calendar_rows=1015/max_full_transitions=1014；109 测试全过 + smoke 重跑）
- 2026-08-08：GATE_4_PILOT_READY 完成 → `docs/review_packets/GATE_4_PILOT_READY.md`
  （M1 HK_DIVIDEND→513690.SH 迁移 + loader 精确选文件 + 03110 研究保留；M2 wrapper audit
  日相关 0.83；重算 horizon 2022-06-06/1015；CA1 公司行为记账（应收款/折算/双价 contract）；
  WF1 Train→Val→Test 4 folds + WF2 t+1 边界测试 + TB1 TRAIN_PASSES×steps；冒烟 F4 EW+TD3
  无 NaN、CA 513690 派息计提 True、boundary rows-1；102 测试全过）
- 2026-08-08：GATE_4_PRECHECK 完成 → `docs/review_packets/GATE_4_PRECHECK.md`
  （obs index proof 闭环；C3 累计 split+raw+events TR；H1 03110 官方派息；
  F1 南向分段费率修复 `_rate_on`；F2 conservative 万3 NOT ACCOUNT-VERIFIED；
  新增 `evaluation/`（rollout 归一化 eval / EW-RP-MV-Momentum baselines / WalkForwardRunner 4-fold）；
  机制冒烟 EW+TD3@2000（F3）无 NaN；修复 `.gitignore` 误忽略 `src/china_etf/data/`；
  88 测试全过；commit `fefb1c7`）
- 2026-08-08：Gate 3 final corrections 完成 → `docs/review_packets/GATE_3_FINAL_CORRECTIONS.md`
  （ActionTransform V2 零权重可表达、93 维外生归一化 V2 policy-independent、无重叠 interval、
  Track B 量化 +0.8 年；68 测试全过）
- 2026-08-08：Gate 3 corrections 完成 → `docs/review_packets/GATE_3_CORRECTIONS.md`
  （action [-1,1]、ActionTransform、RiskOverlayV0、obs 归一化、时序 holdout、check_env、
  重跑 sanity 集中现象消失；58 测试全过）+ `GATE_4_DATA_HORIZON_PLAN.md`
- 2026-08-08：Gate 3 完成 → `docs/review_packets/GATE_3_RL_SANITY.md`
  （Preflight P1–P5 + C3 全过；TD3/SAC/PPO + EW 单 seed sanity；44 测试全过）
- 2026-08-08：Gate 2 APPROVED（Reviewer: `APPROVED_WITH_GATE3_PREFLIGHT_CONDITIONS`，Gate 3 AUTHORIZED）
- 2026-08-08：Gate 2 corrections 完成 → `docs/review_packets/GATE_2_CORRECTIONS.md`
  （港股通印花税=0+AFRC、实际持仓观测、端到端/隔夜/无双算/暖机测试、EnvironmentMode、
  C3 真实事件验证 14/14；40 测试全过）
- 2026-08-08：Gate 3 依赖预装完成（只装不训练）：
  torch 2.7.1+cu118（GPU/1060 验证通过）、SB3 2.8.0、gymnasium 1.2.3、
  finrl 0.3.8@2334a5f、finrl-trading 2.0.2@e65d6f0；锁定文件 `requirements-gate3.txt`
- 2026-08-08：Gate 1 APPROVED（Reviewer: `APPROVED_WITH_CARRY_FORWARD_CONDITIONS`，Gate 2 AUTHORIZED）
- 2026-08-08：Gate 2 完成 → `docs/review_packets/GATE_2_ENVIRONMENT.md`
  （contracts / accounting / mock broker / cost / tradability / premium / fx / env(11) + 29 测试全过）
- 2026-08-08：Gate 1 corrections 完成（Reviewer: REVISIONS_REQUIRED → `GATE_1_CORRECTIONS.md`；
  ADV20/60、AUM(NAV-based)、相关性核验、新 tail 指标、proxy launch-date、双价格体系、03110 lot=50）
- 2026-08-08：Gate 1 数据与宇宙审计完成 → `docs/review_packets/GATE_1_DATA_UNIVERSE.md`
  （QMT 16/16 日线、03110 港股通资格 2024-05-06、513500 溢价分布、相关性含 overlap、替代品清单）
- 2026-08-08：Gate 0 corrections 完成（Reviewer: APPROVED_WITH_REQUIRED_CORRECTIONS → CORRECTIONS_COMPLETE）
- 2026-08-08：Gate 0 上游审计完成 → `docs/review_packets/GATE_0_UPSTREAM_AUDIT.md`
- 2026-08-08：仓库骨架建立（独立 git 仓、docs/config/src 目录、QMT 参考代码拷贝、初始配置草稿）

## Current branch / commit

`main` @ `GATE_4_PILOT_READY_FINAL_FIX commit SHA（待 commit 后回填）`（此前 `5392fd4`）

## Tests

109 全过（`python -m pytest tests/ -q`）。

## Current Gate

Gate 0 — APPROVED_WITH_REQUIRED_CORRECTIONS → CORRECTIONS_COMPLETE（`GATE_0_CORRECTIONS.md`）

Gate 1 — **APPROVED**（`GATE_1_CORRECTIONS_REVIEWER_RESPONSE.md`）

Gate 2 — **APPROVED**（`GATE_2_CORRECTIONS_REVIEWER_RESPONSE.md`）

Gate 3 — **APPROVED_WITH_PRE_GATE4_CONDITIONS**（`GATE_3_FINAL_REVIEWER_RESPONSE.md`）

Gate 4 — PILOT_READY_FINAL_FIX_SUBMITTED（`GATE_4_PILOT_READY_FINAL_FIX.md`），等待 Reviewer 按评审 §33 授权 3-seed pilot

## Blockers

等待 Reviewer 对 `GATE_4_PILOT_READY_FINAL_FIX.md` 批准（评审 §33：P1/P2/P3 修复 + tests + smoke 通过 → `GATE_4_3_SEED_PILOT = AUTHORIZED`）。

## Deviations

Carry-Forward 条件（详见 DECISIONS.md）：
- C1: 03110 same-day trading rule — Gate 6 前验证（当前 UNKNOWN；03110 Track A 已 defer）
- C2: proxy launch/backfill 审计 — 未验证的 proxy 禁入严格 PIT 管线（Track B 使用前关闭）
- C3: adjusted price PIT 语义 — ✅ CLOSED
- F1: 历史费率规则 PIT — ✅ CLOSED（南向已 defer Gate 6，大陆假设保留）
- F2: 港股通券商佣金 — ✅ CLOSED（conservative 万3；Southbound 已 defer Gate 6）
- M1/M2: HK_DIVIDEND→513690 迁移 + wrapper audit — ✅ CLOSED（corr 0.832 + 收益量级验证）
- CA1: 境内 ETF 公司行为记账 — ✅ CLOSED（FINAL_FIX P2/P3：官方派息日 + 512100 显式折算）
- WF1/WF2/TB1: Train→Val→Test + 边界 + 训练预算 — ✅ CLOSED

## Next intended step

Reviewer 批准 `GATE_4_PILOT_READY_FINAL_FIX.md` 后 → `GATE_4_3_SEED_PILOT`（评审 §34）：
4 folds × TD3/SAC/PPO × seeds 42/2026/7 × 1x cost（36 RL trainings，≈3h）+ 4 baselines；
目标只评估 runner stability / seed+fold dispersion / accounting integrity / runtime，非算法排名。

## Reviewer approval

PENDING
