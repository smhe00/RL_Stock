# RL FORMAL PROTOCOL PREP — 冻结 corrected F0 RL 正式实验契约（协议 prep，不训练）

> 评审（`GATE_4_FEATURE_ABLATION_DIAGNOSTIC_CLOSEOUT_REVIEWER_RESPONSE.md`）**APPROVED**，
> `authorized_next: RL_FORMAL_PROTOCOL_PREP`（协议冻结/prep only）。本 packet 冻结协议。
> handoff_id = **RL_FORMAL_PROTOCOL_PREP_001**。

---

# 1. 冻结协议（canonical source：docs/features/RL_FORMAL_PROTOCOL.md）

13 项契约（评审指定范围全覆盖）：目标、算法、训练预算、seed 政策、validation-only selection、
exact Test mask、corrected 语义、benchmark hurdle、metrics、GO/NO-GO、artifacts、stop conditions、范围。

```text
1. 目标      corrected 路径上 F0 RL 策略在 exact 475-Test mask 是否超越 benchmark hurdle（EqualWeight）
2. 算法      PPO / SAC / TD3（net [256,256]、TRAIN_PASSES=20、PPO cpu / SAC,TD3 cuda）
3. 训练预算  每 fold = TRAIN_PASSES × train_decision_steps（TB1）；4 folds
4. Seed 政策 seeds {42, 2026, 7} = 3 algos × 3 seeds × 4 folds = 36 runs（10-seed REMOVED）
5. Selection validation-only model selection；跨 seed median；禁止 Test 选
6. Test mask exact_test_mask = 475 执行日；stitched = fold 序拼接 test net_returns；mask parity assert
7. Corrected E1 fold-local test reset / E2 cost reconciliation / E3 RiskOverlay 诊断；1x cost；CA；t-close→t+1-open
8. Hurdle   超 EqualWeight：CAGR 0.2687 / Sharpe 1.64 / MaxDD -0.0881（corrected 路径 artifact）
9. Metrics   cagr, annualized_vol, sharpe, sortino, max_drawdown, calmar, mean_turnover,
             total_turnover, total_cost, cost_over_initial_value, n_eval_steps,
             risk_overlay_intervention_rate, nan_obs_or_reward, negative_cash_count
10. GO/NO-GO GO = 无 stop 违规 AND median(Sharpe)≥1.64 AND median(CAGR)≥0.2687 AND ≥2/3 seeds Sharpe≥1.64
             NO-GO = 任何 stop 违规或未达
11. Artifacts artifacts/gate4_rl_formal_results.json + _raw.json（tracked；runs/ gitignored）
12. Stop     NaN/Inf、negative_cash、save/load mismatch、non-finite oos（复用 pilot check_stop_conditions）
13. 范围     observation = F0（104 维）；F1 不加入（ablation 无稳健增益）；F2/F3 真实宏观 → FEATURE_DATA_READY
```

# 2. 协议可执行性验证（scripts/gate4_rl_formal_protocol_check.py，无训练）

```text
exact_test_mask = 475  [2023-11-24 .. 2026-08-07]
fold train/val/test 决策日：F1 300/60/118、F2 478/60/118、F3 656/60/118、F4 834/60/121
EqualWeight hurdle：cagr 0.2687 / sharpe 1.64 / mdd -0.0881  matches=True
total 3-seed runs = 36
rl_training_executed = False
```

# 3. 协议契约测试（tests/test_rl_formal_protocol.py，无训练）

```text
10 测试：冻结配置与 pilot 一致（TRAIN_PASSES=20、net (256,256)、seeds {42,2026,7}、3 algos）、
exact_test_mask==475、EqualWeight hurdle 与 horse-race artifact 一致、stop-condition 语义
（NaN/neg-cash/save-load/non-finite）、F0 obs dim 104、gym wrapper obs 104、GO/NO-GO 逻辑。
```

# 4. 决策点（参数化，评审可调）

```text
benchmark hurdle = 超 EqualWeight（CAGR 0.2687 / Sharpe 1.64 / MaxDD -0.0881）——强基线（DeMiguel 论点）。
seed 政策 = 3 seeds {42, 2026, 7}（pilot 一致；10-seed REMOVED）。
两项均在协议中明确参数化，评审可调整后重新冻结。
```

# 5. 边界与规避

```text
✓ 协议 prep only：不训练/重训 RL（PPO/SAC/TD3）
✓ 不跑 corrected F0 3-seed（CORRECTED_F0_RL_3SEED 仍 forbidden，未来独立执行门）
✓ 不 10-seed / Optuna / sweep / F2/F3 / Test-informed / 特征增减 / QMT_LIVE / SOUTHBOUND
✓ feature-ablation 结论（F1 无稳健增益）已纳入协议（observation=F0）
```

# 6. Pytest

```text
collected 210 items  →  210 passed（新增 tests/test_rl_formal_protocol.py 10 个）
```

# 7. Git Commit

`RL_FORMAL_PROTOCOL_PREP` 提交 SHA：**`PENDING_SHA`**

```text
docs/features/RL_FORMAL_PROTOCOL.md              ← 冻结协议（canonical source）
tests/test_rl_formal_protocol.py                 ← 10 契约测试
scripts/gate4_rl_formal_protocol_check.py        ← 协议可执行性验证（无训练）
docs/review_packets/RL_FORMAL_PROTOCOL_PREP.md   ← 本 packet
docs/agent_state/CLAUDE_STATUS.yaml              ← 协议状态
```

---

## Approval Record

```yaml
gate: 4
handoff_id: RL_FORMAL_PROTOCOL_PREP_001
packet: RL_FORMAL_PROTOCOL_PREP
status: READY_FOR_REVIEW

frozen_protocol:
  observation: F0 (104-dim)          # feature-ablation no F1 gain
  algorithms: [PPO, SAC, TD3]
  train_passes: 20
  seeds: [42, 2026, 7]               # 36 runs total
  selection: validation-only         # no Test-based selection
  test_mask: 475 execution dates
  hurdle: {cagr: 0.2687, sharpe: 1.64, max_dd: -0.0881}   # EqualWeight corrected-path
  go_no_go: defined
  artifacts: tracked artifacts/
  stop_conditions: pilot semantics

verified:
  protocol_check_passed: true        # 475 mask + fold regions + hurdle match + 36 runs
  pytest_210: true
  rl_training_executed: false

not_done:
  rl_training: false
  corrected_f0_rl_3seed: false       # future independent execution gate
  ten_seed_formal: false
  optuna_or_sweep: false
  f2_f3_real_macro: false
  test_informed_selection: false
  feature_set_change: false
```

## END OF RL FORMAL PROTOCOL PREP
