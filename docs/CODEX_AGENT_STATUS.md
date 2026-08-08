# CODEX_AGENT_STATUS

<!-- 按 EXECUTION_SPEC §73 格式维护。Agent 每次恢复工作先读本文件。 -->

## Current Phase

Phase 4 — GATE_4_PRECHECK 已提交（C3/F1/F2/H1 闭环 + WalkForwardRunner/baselines + 机制冒烟），
等待 Reviewer 批准 → 之后才可进入 G4.3 3-seed pilot（正式 one-fold TD3/SAC/PPO smoke）

## Last completed task

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

`main` @ `fefb1c7`（GATE_4_PRECHECK；此前 Gate 3 final `0e5ae7f` 等）

## Tests

88 全过（`python -m pytest tests/ -q`）。

## Current Gate

Gate 0 — APPROVED_WITH_REQUIRED_CORRECTIONS → CORRECTIONS_COMPLETE（`GATE_0_CORRECTIONS.md`）

Gate 1 — **APPROVED**（`GATE_1_CORRECTIONS_REVIEWER_RESPONSE.md`）

Gate 2 — **APPROVED**（`GATE_2_CORRECTIONS_REVIEWER_RESPONSE.md`）

Gate 3 — **APPROVED_WITH_PRE_GATE4_CONDITIONS**（`GATE_3_FINAL_REVIEWER_RESPONSE.md`）

Gate 4 — PRECHECK_SUBMITTED（`GATE_4_PRECHECK.md`，commit `fefb1c7`），等待 Reviewer 批准后进入 G4.3

## Blockers

等待 Reviewer 对 `GATE_4_PRECHECK.md` 批准（决定 3-seed pilot 是否可启动）。

## Deviations

Carry-Forward 条件（详见 DECISIONS.md）：
- C1: 03110 same-day trading rule — Gate 6 前验证（当前 UNKNOWN）
- C2: proxy launch/backfill 审计 — 未验证的 proxy 禁入严格 PIT 管线（Track B 使用前关闭）
- C3: adjusted price PIT 语义 — ✅ CLOSED（`GATE_4_PRECHECK` §2；累计 split + raw+events TR）
- F1: 历史费率规则 PIT — ✅ CLOSED（`GATE_4_PRECHECK` §4；南向分段 + 大陆保守假设）
- F2: 港股通券商佣金 — ✅ CLOSED（conservative 万3 + min 5 HKD，NOT ACCOUNT-VERIFIED）

## Next intended step

Reviewer 批准 `GATE_4_PRECHECK.md` 后 → G4.3 3-seed pilot（先正式 one-fold TD3/SAC/PPO seed=42
冒烟 runner，再 3 seeds × 4 folds × baselines；Track A 主证据，10 seeds 后续）。

## Reviewer approval

PENDING
