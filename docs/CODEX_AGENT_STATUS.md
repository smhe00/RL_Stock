# CODEX_AGENT_STATUS

<!-- 按 EXECUTION_SPEC §73 格式维护。Agent 每次恢复工作先读本文件。 -->

## Current Phase

Phase 3 — First RL Sanity（Gate 3 final corrections 已完成，等待复核）

## Last completed task

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

`main` @ `c4dd562`（Gate 2 实现；后续存档 `3ca7db4` / `948fae7`）

## Tests

尚未开始（Gate 0 为只读审计，上游仓库亦无 tests/ 目录）。

## Current Gate

Gate 0 — APPROVED_WITH_REQUIRED_CORRECTIONS → CORRECTIONS_COMPLETE（`GATE_0_CORRECTIONS.md`）

Gate 1 — **APPROVED**（`GATE_1_CORRECTIONS_REVIEWER_RESPONSE.md`）

Gate 2 — **APPROVED**（`GATE_2_CORRECTIONS_REVIEWER_RESPONSE.md`）

Gate 3 — FINAL_CORRECTIONS_COMPLETE（`GATE_3_FINAL_CORRECTIONS.md`），等待 Reviewer 确认才可进入 Gate 4

## Blockers

等待 Reviewer 对 `GATE_3_FINAL_CORRECTIONS.md` 复核。

## Deviations

Carry-Forward 条件（详见 DECISIONS.md）：
- C1: 03110 same-day trading rule — Gate 6 前验证（当前 UNKNOWN）
- C2: proxy launch/backfill 审计 — Gate 3 前完成（当前未验证的 proxy 禁入严格 PIT 管线）
- C3: adjusted price PIT 语义 — Gate 2 必须覆盖（test_adjustment_point_in_time_semantics）
- F1: 历史费率规则 PIT（mainland/southbound 各费项生效日）— Gate 4 前
- F2: 港股通券商佣金是否 0.00005 — Gate 4 真实成本比较 / Gate 6 执行前

## Next intended step

Reviewer 确认后进入 Gate 4 — Core Walk-Forward（Track A 主证据；先 1 seed fold runner →
3-seed pilot → 10 seeds；baselines 先行；F1/H1/C3 前置）。

## Reviewer approval

PENDING
