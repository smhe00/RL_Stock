# GATE 3 Final Reviewer Response

## Decision

```text
GATE_3 = APPROVED_WITH_PRE_GATE4_CONDITIONS
GATE_4_FORMAL_WALKFORWARD = NOT YET AUTHORIZED
GATE_4_PREPARATION = AUTHORIZED
```

本次 `GATE_3_FINAL_CORRECTIONS.md` 已解决前两轮 Gate 3 的核心问题：

- `[-10,10] + softmax` action-scale artifact 已消除；
- ActionTransform V2 可以表达接近/等于 0 的资产权重；
- ActionTransform 对 TD3 / SAC / PPO 完全一致；
- RiskOverlayV0 已强制进入 Environment transition；
- forced 100% raw-weight 测试证明 RiskOverlay 可以将目标约束到 `single_core_max=25%`；
- Observation normalization 已改成 policy-independent；
- scaler 不再依赖 Equal-Weight trajectory；
- chronological held-out sanity evaluation 已建立；
- train/eval 区间已经无重叠；
- 三种 RL 均无 NaN/Inf；
- save/load deterministic consistency 已通过；
- 68 个 tests 全部通过；
- Track B 的实际历史增益已经量化，只有约 208 个交易日 / 0.8 年。

因此 Gate 3 的核心使命已经完成。

---

# 1. ActionTransform V2 — APPROVED

当前：

```python
a = clip(action, -1, 1)
score = (a + 1) / 2

if score.sum() <= eps:
    raw = equal_weight
else:
    raw = score / score.sum()
```

批准。

其性质符合项目需求：

```text
a = -1 → 可以产生 0 exposure
a = 0  → neutral action = equal weight
no exponential amplification
same transform for TD3/SAC/PPO
```

RiskOverlay 负责硬约束，而不是 ActionTransform 隐含制造分散。

这是比原 softmax parameterization 更清晰的职责分离。

---

# 2. RiskOverlayV0 — APPROVED

当前流程：

```text
raw action
→ ActionTransform
→ raw_policy_weights
→ RiskOverlayV0
→ post_risk_target_weights
→ execution
→ actual_portfolio_weights
```

批准。

forced integration test：

```text
raw max ≈ 100%
→ post-risk <= 25%
→ actual ≈ <=27% after execution / price drift
```

证明 RiskOverlay 不只是独立工具函数，而是真正进入 Environment transition。

V1 cap 语义继续冻结为：

```text
constraint applies to target weights at rebalance
```

而不是持续强制实际市值权重始终低于 25%。

市场价格变化造成 actual weight 暂时超过 cap：

```text
next rebalance corrects
```

即可。

---

# 3. Current Policy Diagnostics — APPROVED FOR SANITY

修正后 held-out 结果：

```text
TD3 raw max_mean ≈ 15.2%
SAC raw max_mean ≈ 12.9%
PPO raw max_mean ≈ 10.4%
EW ≈ 9.1%
```

无任何算法出现旧版：

```text
85%~93% single-asset collapse
```

说明旧问题确实来自 action parameterization。

当前：

```text
RiskOverlay intervention rate = 0
```

并不是问题。

这意味着在本次短 Sanity Run 中：

> Policy 自己产生的权重已经处于硬约束以内，RiskOverlay 只是安全护栏。

Gate 4 必须继续记录：

```text
overlay intervention rate
mean L1(raw, post-risk)
single-core cap hit rate
ChinaGrowth cap hit rate
```

如果正式长跑后干预率显著提高，再重新研究 action semantics。

---

# 4. IMPORTANT PRE-GATE4 CHECK — Observation Index Layout

当前文档写：

```text
obs layout =
[88 per-asset market]
[11 actual weights]
[5 global]
```

即 index 应为：

```text
0:88     per-asset market
88:99    actual portfolio weights
99:104   global market features
```

因此：

```text
93 exogenous dimensions =
0:88 + 99:104
```

而：

```text
11 endogenous portfolio dimensions =
88:99
```

但是文档同时写：

> “末 N 维 actual weights 保持 [0,1]”

这与上述 layout 不一致。

如果 observation layout 真的是：

```text
[88][11][5]
```

那么 actual weights 不是最后 11 维。

## Required proof

正式 Gate 4 前必须增加或展示：

```text
MARKET_FEATURE_INDICES =
[0..87] + [99..103]

PORTFOLIO_WEIGHT_INDICES =
[88..98]
```

或者代码中的等价显式定义。

必须增加测试：

```text
test_observation_index_partition
test_only_exogenous_features_are_normalized
test_portfolio_weight_indices_unchanged
test_global_features_are_normalized
```

测试应构造易辨认的 synthetic observation：

```text
market features = distinct known values
weights         = [0.01 ...]
global          = distinct known values
```

然后证明：

```text
88 market features → normalized
5 global features  → normalized
11 weights          → bitwise/allclose unchanged
```

### Decision

如果只是文档里的“末 N 维”写错：

```text
patch documentation + test
NO RL rerun required
```

如果代码 mask 实际错位：

```text
fix scaler mask
rerun one-seed TD3/SAC/PPO sanity
```

因为这会改变 network input semantics。

---

# 5. Observation Normalization Architecture — APPROVED SUBJECT TO INDEX PROOF

原则批准：

```text
93 exogenous market/global features
→ train-only standardization

11 actual portfolio weights
→ remain raw [0,1]
```

这是正确设计。

Scaler 必须继续满足：

```text
fit only on effective Train observations
eval = transform only
future mutation does not change fitted scaler
scaler saved with experiment/model
```

不得恢复：

```text
policy-trajectory-based scaler
```

---

# 6. Effective Training Interval — APPROVED

以后报告不要再把：

```text
raw_data_start = 2011
```

写成 RL 有效训练开始时间。

本项目当前真实 11-Core：

```text
raw_data_start:
2011-12-09

effective_obs_start:
2022-05-18
```

因此实际训练可用区间应报告：

```text
effective_train_start = 2022-05-18
train_end             = 2025-10-22
eval_start            = 2025-10-23
eval_end              = 2026-08-07
```

并继续保证：

$$
TrainEnd < EvalStart
$$

---

# 7. Track B Horizon — REVIEWER ACCEPTS CONCLUSION

本次量化得到：

```text
Track A effective start:
2022-05-18

Track B PIT common start:
2020-07-27

Track B after 252D warm-up:
2021-07-22

Track B usable days:
1277

Track A usable days:
1069

increment:
208 trading days ≈ 0.8 year
```

因此：

> **Track B 不应作为所谓“长历史主研究集”。**

这个判断批准。

Track B 仅增加约 0.8 年，对解决 RL 的 regime/sample-size 问题帮助有限。

---

# 8. Gate 4 Evidence Architecture — FREEZE

正式 Gate 4 推荐冻结成：

## Track A — Primary

```text
REAL-INSTRUMENT OOS
LIMITED-HISTORY
```

11 个真实 ETF。

目标：

> 评估实际 Instrument 条件下 RL 与传统配置方法的表现。

任何结论必须明确：

```text
2022~2026 limited history
```

不得表述为：

```text
long-term proven alpha
```

---

## Track C — Secondary

```text
SCENARIO LONG-HISTORY
NOT STRICT PIT OOS
```

使用 retrospective / backfilled proxies。

目标：

- regime robustness；
- mechanism study；
- crash periods；
- 更长时间尺度行为分析。

不得与 Track A Sharpe 混合。

---

## Track B — Optional cross-check

```text
11-slot PIT proxy
```

只有约 0.8 年额外历史。

可以作为 cross-check，但不作为核心证据。

如果执行 Track B：

```text
C2 proxy PIT audit
```

必须先关闭。

---

# 9. Gate 4 Formal Experiment Still Has Four Blocking Data/Cost Items

虽然 Gate 3 可以批准，但 **正式 Gate 4 Walk-forward RL run 不能马上启动**。

必须先关闭：

```text
C3
F1
F2
H1
```

---

# 10. C3 — Independent Corporate-Action Validation

当前最坏事件：

```text
QMT event-derived TR vs QMT front
max difference = 13.8bp
```

Gate 4 前只需要验证这个最坏 case。

要求：

```text
QMT
vs
independent source
```

例如：

```text
基金公司官方分红公告
交易所公告
独立 adjusted-return data source
```

目标不是要求结果完全相同，而是解释 13.8bp 的来源，并确认：

> QMT front 没有把 corporate action 制造成系统性错误收益。

---

# 11. H1 — 03110 Total-Return Validation

03110 是高股息 ETF。

当前：

```text
Sina qfq × HKD/CNY
```

作为研究序列。

正式 Track A 前必须随机选择至少 2~3 个派息日，核对：

```text
Global X / HKEX official distribution
```

与：

```text
Sina qfq adjusted return
```

是否一致。

否则可能系统性低估或高估 HK_DIVIDEND 收益。

---

# 12. F1 — Historical Point-in-Time Fee Rules

Gate 3 使用：

```text
CURRENT_FEE_SCENARIO_2026
```

没有问题。

Gate 4 的正式历史 cost result 必须解决：

```text
historical effective date
```

至少覆盖：

```text
Mainland relevant exchange/broker fee assumptions
HKEX trading fee
SFC levy
AFRC levy
settlement fee
Southbound ETF stamp-duty exemption
```

允许历史上使用 piecewise fee schedule。

---

# 13. F2 — Southbound Broker Commission

03110 港股通实际券商佣金仍未冻结。

正式 Track A realistic-cost result 前：

```text
确认真实港股通ETF佣金
```

或使用明确的：

```text
conservative fee scenario
```

并标明：

```text
NOT ACCOUNT-VERIFIED
```

不得无说明地继续使用：

```text
0.00005
```

作为确定事实。

---

# 14. Gate 4 Execution Authorization

当前允许 Codex 进入：

```text
GATE_4_PREPARATION
```

允许：

```text
close C3
close F1
close F2
close H1
verify observation index mask
implement WalkForwardRunner
implement deterministic baselines
run one-fold dry/smoke test
```

暂时不允许：

```text
10-seed RL
20-seed RL
full walk-forward TD3/SAC/PPO
Optuna
algorithm winner conclusion
```

---

# 15. Recommended Gate 4 Execution Sequence

```text
Phase G4.0
Close data/cost blockers:
C3 + F1 + F2 + H1
+
observation index proof
```

然后：

```text
Phase G4.1
Equal Weight
Risk Parity
Minimum Variance
Momentum
```

先验证 deterministic baselines。

然后：

```text
Phase G4.2
One complete WalkForward fold
TD3/SAC/PPO
seed=42
```

只验证 runner。

然后：

```text
Phase G4.3
3-seed pilot
```

检查：

- reproducibility；
- runtime；
- fold boundary；
- scaler isolation；
- model persistence；
- cost consistency。

通过以后：

```text
Phase G4.4
10 seeds
```

只有 10 seeds 结果仍不稳定、统计区间过宽，才考虑：

```text
20 seeds
```

不建议一开始就直接烧 20 seeds。

---

# 16. Gate 4 Must Use Strict Fold Isolation

每个 fold：

```text
TRAIN
→ fit feature scaler
→ fit model / optimize using train+validation only
→ freeze
→ TEST
```

下一 fold 重新：

```text
fit scaler
fit model
```

禁止：

```text
reuse future fold scaler
reuse TEST information
choose hyperparameter from TEST
```

---

# 17. Recommended Gate 4 First Packet

下一个正式 Reviewer Packet 建议不是直接：

```text
GATE_4_CORE_WALKFORWARD.md
```

而是先输出：

```text
GATE_4_PRECHECK.md
```

内容：

```text
1. observation index proof
2. C3 closure
3. H1 closure
4. F1 historical fee table
5. F2 southbound commission resolution/scenario
6. final Track A date range
7. proposed walk-forward folds
8. baseline configs
9. WalkForwardRunner smoke
10. exact tests
11. compute-budget estimate
12. git commit
```

Reviewer 批准后，再启动 10-seed 正式 RL。

这可以显著降低在错误 fold/cost/data 上浪费大量训练预算的风险。

---

# 18. Current Gate 3 Final Decision Table

| Item | Decision |
|---|---|
| Action space `[-1,1]` | PASS |
| Zero-capable ActionTransform | PASS |
| Degenerate action fallback | PASS |
| Forced RiskOverlay transition | PASS |
| Single-core cap | PASS |
| ChinaGrowth cap | PASS |
| Raw/Post-risk/Actual diagnostics | PASS |
| Policy-independent scaler concept | PASS |
| Scaler train-only | PASS |
| Scaler observation index implementation | **VERIFY BEFORE GATE4** |
| Chronological held-out sanity | PASS |
| Save/load | PASS |
| No NaN/Inf | PASS |
| SB3 environment compatibility | PASS |
| Track A horizon | PASS |
| Track B quantification | PASS |
| Track C labeling | PASS |
| C3 independent validation | OPEN |
| F1 historical fees | OPEN |
| F2 Southbound commission | OPEN |
| H1 03110 total return | OPEN |

---

# 19. Reviewer Interpretation

Gate 3 现在已经达到它应该达到的目标：

> **证明三个算法可以在相同、稳定、可解释的资产配置接口上运行。**

这里没有证据说明：

```text
TD3 better
SAC better
PPO better
```

也不需要有。

Gate 3 真正成功的地方是已经连续发现并修掉：

```text
action-scale artifact
hidden minimum-weight prior
policy-dependent scaler
```

这些如果不在正式 Walk-forward 前发现，会非常容易产生错误的算法结论。

---

# 20. Approval Record

```yaml
gate: 3
decision: APPROVED_WITH_PRE_GATE4_CONDITIONS
date: 2026-08-08

gate3:
  approved: true

gate4:
  preparation_authorized: true
  full_rl_walkforward_authorized: false

must_close_before_full_gate4:
  - observation_scaler_index_proof
  - C3_independent_adjustment_validation
  - F1_historical_fee_schedule
  - F2_southbound_broker_commission_or_explicit_conservative_scenario
  - H1_03110_total_return_validation

track_strategy:
  A:
    role: primary_real_instrument_oos
  B:
    role: optional_pit_crosscheck
    incremental_history: approximately_0.8_year
  C:
    role: long_history_scenario
    strict_oos: false

permissions:
  implement_walkforward_runner: true
  implement_baselines: true
  one_fold_smoke: true
  three_seed_pilot: false_until_precheck
  ten_seed_run: false
  twenty_seed_run: false
  optuna: false
  theme_sleeve: false
  qmt_live: false

required_next_packet:
  GATE_4_PRECHECK.md
```

---

# 21. Agent Next Instruction

```text
1. Mark Gate 3 APPROVED.
2. Do not start full Gate 4 RL training.
3. Verify exact observation scaler indices.
4. If scaler index is wrong:
      fix it and rerun one-seed sanity.
   If only documentation wording is wrong:
      patch docs/tests; no RL rerun.
5. Close C3 with independent source.
6. Close H1 using 03110 official distribution dates.
7. Resolve F1 historical fee schedule.
8. Resolve F2 Southbound commission or define explicit conservative scenario.
9. Implement WalkForwardRunner and deterministic baselines.
10. Run only one-fold smoke.
11. Generate GATE_4_PRECHECK.md.
12. STOP.
13. Return to Reviewer / ChatGPT.
```

## END OF REVIEWER RESPONSE
