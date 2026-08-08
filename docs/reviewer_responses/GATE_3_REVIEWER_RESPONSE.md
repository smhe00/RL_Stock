# GATE 3 Reviewer Response
## FinRL-X 中国 ETF 项目 — RL Sanity 审核意见

**Reviewed artifact:** `GATE_3_RL_SANITY.md`  
**Review date:** 2026-08-08  
**Decision:** `REVISIONS_REQUIRED_BEFORE_GATE_4`  
**Gate 3 pipeline status:** `FUNCTIONAL_BUT_ACTION_SEMANTICS_NOT_YET_FAIR`  
**Gate 4 authorization:** `NOT AUTHORIZED`

---

# 1. Reviewer Decision

Gate 3 已经证明了一件重要的事情：

> **TD3 / SAC / PPO 都可以在当前 ChinaETFPortfolioEnv 中完成训练、推理、保存/加载，且没有 NaN/Inf、现金穿透或会计崩溃。**

这说明前两个 Gate 的工程基础总体正确。fileciteturn28file0

但是当前 Gate 3 **不能通过到 Gate 4**，因为 TD3 / SAC 的单资产集中现象暴露出一个比超参数更基础的问题：

```text
action_space = Box(-10, 10)^11
          ↓
softmax
          ↓
portfolio weights
```

这一动作参数化会强烈放大不同 RL 算法原始 action 的尺度差异。

当前观察到：

```text
TD3 max weight mean = 0.846
SAC max weight mean = 0.926
PPO max weight mean = 0.107
```

更像是：

> **Action Transform / exploration-scale artifact**

而不是可以解释为：

> TD3/SAC 学会了集中持仓，而 PPO 学会了等权。

因此当前三个算法还没有在一个足够公平、稳定的 Portfolio Action Contract 下比较。

正式状态：

```text
GATE_3_STATUS = REVISIONS_REQUIRED_BEFORE_GATE_4
```

Agent 需要完成一次 **Gate 3 Corrections**，但不允许进入大规模训练或参数优化。

---

# 2. BLOCKER-1：`Box(-10,10) + softmax` 会机械地产生极端权重

当前：

$$
a_i\in[-10,10]
$$

然后：

$$
w_i=
\frac{e^{a_i}}
{\sum_j e^{a_j}}
$$

softmax 对 logit 差非常敏感。

假设一个资产的 action 比另外 10 个资产高：

$$
\Delta=4
$$

那么该资产权重：

$$
w_{max}
=
\frac{e^4}
{e^4+10}
\approx0.845
$$

这几乎**精确对应当前 TD3 的 0.846**。

因此当前 TD3 的集中程度可以仅仅由：

```text
raw action logit gap ≈ 4
```

解释。

而 action space 允许最大差：

$$
\Delta=20
$$

其 softmax 几乎是 one-hot：

$$
w_{max}\approx1
$$

---

# 3. Stable-Baselines3 官方建议也与当前设置不一致

SB3 对自定义连续动作环境的建议是：

```text
continuous action space should be symmetric and normalized
recommended range = [-1, 1]
```

当前：

```text
[-10, 10]
```

不是理想设置。

因此这不是：

```text
“TD3参数不够好”
```

的问题。

必须先修 Action Contract，再讨论算法行为。

---

# 4. Required Fix：统一 Action Space

Gate 3 Correction 必须改为：

```python
action_space = Box(
    low=-1.0,
    high=1.0,
    shape=(11,),
    dtype=np.float32,
)
```

然后统一：

$$
w^{raw}=Softmax(a)
$$

V1 不允许为：

```text
TD3
SAC
PPO
```

分别设置不同 softmax temperature。

否则又会破坏算法公平比较。

---

# 5. ActionTransform 必须成为显式模块

建议：

```python
class ActionTransform:
    def transform(
        self,
        action: np.ndarray,
    ) -> TargetAssetWeights:
        ...
```

V1：

```text
clip [-1,1]
→ stable softmax
→ raw asset weights
```

必须保存：

```text
raw_action
raw_policy_weights
```

用于诊断。

不要把 softmax 隐藏在 Environment 深处而无法审计。

---

# 6. Required Action Transform Tests

新增：

```text
test_action_space_is_normalized_symmetric
test_action_transform_sum_to_one
test_action_transform_is_monotonic
test_action_transform_extreme_bounds
```

对于：

```text
one action = +1
other 10 actions = -1
```

V1 softmax 最大原始权重应为：

$$
\frac{e^1}
{e^1+10e^{-1}}
=
\frac{e^2}{e^2+10}
\approx0.425
$$

而不是接近：

```text
1.0
```

---

# 7. BLOCKER-2：Mandatory RiskOverlay 没有在实际 rollout 中得到证明

项目 Frozen Risk Rules 包括：

```yaml
single_core_max: 0.25
china_growth_max: 0.50
long_only: true
leverage_max: 1.0
```

但 Gate 3 报告实际出现：

```text
TD3 max weight = 84.6%
SAC max weight = 92.6%
```

所以至少存在以下两种情况之一：

### Case A

```text
RiskOverlayV0 没有进入 Environment transition
```

### Case B

报告的：

```text
weight_max
```

是 pre-overlay raw target，而没有与：

```text
post-overlay
actual holdings
```

分开。

无论是哪一种：

> Gate 4 都不能在当前状态下开始。

---

# 8. Gate 3 Correction 必须正式接入 RiskOverlayV0

流程必须固定：

```text
RL action
   ↓
ActionTransform
   ↓
Raw Policy Weights
   ↓
RiskOverlayV0
   ↓
Constrained Target Weights
   ↓
Execution / Lot / Tradability
   ↓
Actual Holdings
```

必须明确三个对象：

```text
raw_policy_weights
post_risk_target_weights
actual_portfolio_weights
```

不得都叫：

```text
weights
```

---

# 9. RiskOverlayV0 的 Core-only 必须约束

Gate 3 Core-only 至少：

```text
single_core_max = 0.25
china_growth_max = 0.50
long_only = true
leverage <= 1
```

其中 Core-only：

$$
ChinaGrowth=
CHINEXT+STAR
$$

主题还未进入，因此不包含：

```text
SEMICONDUCTOR
AI
ROBOTICS
```

---

# 10. Capped-Simplex Projection 不允许 naive clip

禁止：

```python
w = np.minimum(w, cap)
w = w / w.sum()
```

因为第二次 renormalize 可能重新超过 cap。

需要实现确定性的：

```text
bounded simplex projection / water filling
```

满足：

$$
w_i\ge0
$$

$$
w_i\le u_i
$$

$$
\sum_iw_i=1
$$

同时满足 group constraint：

$$
w_{CHINEXT}+w_{STAR}\le0.50
$$

如果约束集合不可行：

```text
RAISE
```

不能 silently relax。

---

# 11. Required Risk Overlay Tests

至少：

```text
test_single_core_cap
test_china_growth_group_cap
test_projection_sum_to_one
test_projection_caps_after_renormalization
test_projection_idempotent
test_infeasible_constraints_raise
```

并加入：

```text
10000 random actions
```

property-style smoke test：

```text
post-risk max <= 0.25 + eps
post-risk ChinaGrowth <= 0.50 + eps
sum = 1
```

---

# 12. Gate 3 Correction 必须重新报告三层权重

每个算法：

| Metric | Raw Policy | Post-Risk Target | Actual Holdings |
|---|---:|---:|---:|
| max weight mean | | | |
| HHI | | | |
| single >25% fraction | | | |
| ChinaGrowth mean | | | |
| turnover | N/A/optional | | |
| cash residual | N/A | N/A | |

这样才能看清：

> 集中来自 Policy、Risk Projection，还是 Execution。

---

# 13. BLOCKER-3：Observation Scaling 尚未冻结

SB3 对 custom continuous-control environment 同样建议：

```text
normalize observations when possible
```

当前实际 104 维 observation：

```text
min = -0.5034
max = 0.9841
mean = 0.0245
std = 0.1498
```

整体范围并不离谱，但不同 feature 的经济尺度明显不同：

```text
returns
volatility
drawdown
percentile
correlation
weights
```

对于 TD3 / SAC / PPO 的公平比较，应在 Gate 4 之前冻结统一 normalization。

---

# 14. Required Observation Normalization

推荐选择之一：

## Option A — Custom Train-Fit Scaler

```text
fit scaler on Train only
freeze
Validation/Test transform only
```

## Option B — SB3 VecNormalize

可以使用，但必须：

```text
Train: update stats
Validation/Test: training=False
Save normalization stats
Load same stats with model
```

---

# 15. 禁止全样本 fit

严格禁止：

```text
2012~2026 全部数据 fit scaler
↓
再切 train/test
```

必须：

$$
ScalerFitRange
\subseteq
TrainRange
$$

---

# 16. Gate 3 Correction 只需要验证 normalization pipeline

现在不需要优化：

```text
clip_obs
epsilon
feature-by-feature transform
```

只需要：

1. 选择一个一致方案；
2. Train-only fit；
3. 保存 / 加载；
4. deterministic inference 使用同一 scaler；
5. no-lookahead test。

---

# 17. BLOCKER-4：Gate 3 没有明确报告 Train / Evaluation 时间隔离

当前 Packet 给了总体数据：

```text
2011-12-09 → 2026-08-07
warmup = 2022-05-18
```

但没有明确写：

```text
TD3/SAC/PPO training interval
200-step diagnostic evaluation interval
```

因此现在：

```text
reward_mean
turnover
HHI
```

到底是：

```text
in-sample
```

还是：

```text
held-out
```

不清楚。

Gate 3 虽然不做性能结论，但仍应建立正确实验纪律。

---

# 18. Gate 3 Correction 必须使用一个简单 chronological holdout

不需要复杂 Walk-Forward。

只需要：

```text
Train
→ Sanity Evaluation
```

按时间顺序。

例如：

```text
Train = earlier portion
Eval = final ~200 trading days
```

具体日期由数据决定。

规则：

```text
NO SHUFFLE
NO EVAL DATA IN SCALER FIT
NO EVAL DATA IN TRAINING
```

所有 diagnostic：

```text
weight concentration
turnover
reward
cost
```

主表使用：

```text
held-out sanity evaluation
```

训练期 diagnostics 可另列。

---

# 19. BLOCKER-5：需要运行 SB3 `check_env`

Gate 3 报告没有说明是否执行：

```python
stable_baselines3.common.env_checker.check_env(env)
```

在进入正式 Walk-Forward 前必须运行。

同时确认 Gymnasium termination semantics：

```text
terminated
truncated
```

尤其 episode 达到数据结尾属于：

```text
terminated/truncated
```

必须有清晰定义。

---

# 20. Required Environment API Tests

增加：

```text
test_sb3_check_env
test_episode_end_semantics
test_reset_returns_valid_obs
test_step_after_terminal_not_allowed_or_defined
```

并在 Correction Packet 给 exact output。

---

# 21. TD3/SAC/PPO 当前表现不能用于算法判断

当前：

```text
TD3 reward_mean = +0.0025
SAC = +0.0003
PPO = +0.0010
```

不得进一步解释。

原因至少包括：

- action scaling 不公平；
- RiskOverlay 层次不清；
- train/eval interval 不清；
- observation normalization 未冻结；
- 仅 one seed / 12k steps。

所以当前：

```text
TD3 > PPO > SAC
```

没有统计或经济意义。

Gate 3 已正确没有宣称 winner，这点批准。

---

# 22. PPO 近等权也不能直接叫“探索不足”

当前：

```text
PPO action_std = 0.105
max weight ≈ 0.107
```

在 `Box(-10,10)` + softmax 体系下，PPO 输出的小 logits 天然会接近等权。

因此：

> 当前 PPO 近等权可能主要是 action scale difference。

不应该在 Gate 3 先归因：

```text
exploration不足
```

或：

```text
learning rate不合适
```

先修 Action Contract。

---

# 23. TD3/SAC 集中也不能先归因于策略偏好

同理：

```text
TD3/SAC >50% 单资产 = 99.5%
```

当前首先应解释为：

```text
Action parameterization red flag
```

而不是：

```text
learned concentration preference
```

---

# 24. Gate 3 Correction 的训练预算

修正 action / risk / normalization 后：

仍然只运行：

```text
one seed = 42
one chronological split
12k timesteps / algorithm
```

允许根据算法 API 必要性做小调整，但：

```text
NO Optuna
NO searching for best parameters
```

目的仍是：

> Sanity re-run。

---

# 25. PPO Device

Gate 3 已记录：

```text
PPO MlpPolicy on GPU warning
```

Correction 可以把 PPO 改为：

```text
device=cpu
```

TD3/SAC 可保留 GPU。

这不是算法公平性问题，因为 Gate 3 不比较 wall-clock efficiency。

但必须记录。

---

# 26. C3 Adjustment PIT — ACCEPTED FOR GATE 3, NOT CLOSED FOR GATE 4

当前：

```text
14 events
median diff = 0.26bp
max diff = 13.8bp
```

已经按要求：

```text
STOP AND EXPLAIN
```

执行。

Reviewer 接受：

> Gate 3 可以使用 QMT front 作为研究收益序列。

但 C3 仍然：

```text
OPEN / PARTIALLY_RESOLVED
```

---

# 27. C3 Gate 4 Requirement

在正式 Walk-Forward 前，对：

```text
max diff 13.8bp
```

的最坏事件至少增加一个**独立来源**交叉验证：

```text
official fund distribution announcement
or
independent NAV / adjusted return source
```

不能只：

```text
QMT raw/events
vs
QMT front
```

同源互证。

---

# 28. HK_DIVIDEND Total Return — NEW CARRY-FORWARD H1

Gate 3 当前：

```text
03110 sina qfq × HKD/CNY
```

作为 CNY research series。

对于一个：

```text
High Dividend ETF
```

分红处理非常重要。

因此 Gate 4 前必须验证：

```text
Sina qfq
```

对 03110 的：

```text
cash distributions
splits
```

是否形成正确 total-return-consistent series。

至少选择：

```text
2~3 distribution dates
```

与：

```text
Global X / HKEX official distribution data
```

交叉验证。

在此之前：

```text
HK_DIVIDEND series suitable for sanity
```

但不能作为正式严格 OOS 收益结论的完全验证数据。

---

# 29. GATE 4 DATA HORIZON — MAJOR METHODOLOGY ISSUE

Gate 3 暴露了一个必须在 Gate 4 前处理的结构性问题。

11 Core 使用真实 ETF 的共同有效 observation 起点是：

```text
2022-05-18
```

到：

```text
2026-08-07
```

只有约四年多历史。

对于：

```text
10~20 seeds
walk-forward
TD3/SAC/PPO
multiple regimes
```

这是非常短的样本。

---

# 30. Gate 4 不得直接假设 2022~2026 足以证明长期 RL Alpha

在进入正式 Core Walk-Forward 前，Agent 必须先生成一个简短：

```text
docs/review_packets/GATE_4_DATA_HORIZON_PLAN.md
```

但不需要现在执行 Gate 4。

至少比较三个方案：

## Track A — Real Instrument OOS

```text
11 actual ETF instruments
common valid history
~2022 onwards
```

优点：

```text
最接近真实 ETF
```

缺点：

```text
样本极短
regime 少
fold 少
```

只能称：

```text
REAL-INSTRUMENT OOS / limited-history
```

---

## Track B — Point-in-Time Proxy Method Research

使用已经完成：

```text
launch-date / backfill audit
```

并且当时真实可获得的 proxy。

目标：

```text
延长 Method Research 历史
```

禁止使用：

```text
pre-launch backfilled index
```

冒充 PIT。

---

## Track C — Scenario Proxy Research

允许更长的 retrospective/backfilled proxy：

```text
SCENARIO
```

但必须明确：

```text
not strict PIT OOS
```

---

# 31. Gate 4 可能最终需要“双轨结论”

最稳妥的研究输出可能是：

```text
Method / Scenario Long-History Study
+
Real-ETF Short-History OOS Study
```

而不是试图用一个数据集同时证明：

```text
算法长期有效
+
具体 ETF 可执行
```

这与前面项目设计的：

```text
Asset Slot != Instrument
```

是一致的。

---

# 32. RiskOverlay 与 ActionTransform 的诊断顺序

修正后必须依次记录：

```text
raw_action
↓
raw_policy_weights
↓
post_risk_weights
↓
post_execution_actual_weights
```

例如：

```text
TD3 raw max = 0.38
post-risk max = 0.25
actual max = 0.247
```

才是可解释的。

如果：

```text
post-risk <=25%
actual >25%
```

说明：

```text
price movement / execution drift
```

需要单独解释。

---

# 33. Actual Weight 超过 Target Cap 的容忍语义

即使 target：

```text
<=25%
```

成交以后价格变化可以让 actual weight：

```text
>25%
```

所以 RiskOverlay cap 定义必须明确：

```text
cap applies to target weights at rebalance
```

还是：

```text
cap applies continuously to actual holdings
```

V1 推荐：

```text
target-at-rebalance constraint
```

如果 actual 因市场波动超过 cap：

```text
next rebalance corrects
```

不要模拟不必要的盘中强制卖出。

---

# 34. Required Gate 3 Correction Packet

生成：

```text
docs/review_packets/GATE_3_CORRECTIONS.md
```

必须包含：

## 1. Action-space correction

```text
[-10,10] → [-1,1]
```

## 2. ActionTransform exact formula

## 3. RiskOverlayV0 integration

## 4. bounded-simplex tests

## 5. Raw / Post-Risk / Actual weight diagnostics

## 6. Observation normalization

## 7. Train-only scaler proof

## 8. Chronological Train / Sanity-Eval split

## 9. SB3 check_env + Gym termination semantics

## 10. Re-run TD3/SAC/PPO sanity

## 11. Equal Weight same-environment baseline

## 12. Exact pytest output

## 13. C3/H1/F1/F2 carry-forward register

## 14. Gate 4 data-horizon proposal summary

## 15. Git commit

---

# 35. Gate 4 Authorization Criteria

Gate 4 只有满足以下条件才会被授权：

```text
normalized action space
algorithm-neutral ActionTransform
RiskOverlayV0 actually applied
single-core target <=25%
ChinaGrowth target <=50%
raw/post-risk/actual diagnostics separated
train-only observation normalization
chronological held-out sanity evaluation
SB3 check_env passes
termination semantics correct
TD3/SAC/PPO all stable after correction
```

同时必须有：

```text
Gate 4 data-horizon plan
```

---

# 36. Gate 3 当前逐项裁决

| Item | Decision |
|---|---|
| Cash solvency | PASS |
| Sell-before-buy | PASS |
| Fee-aware sizing | PASS |
| CNY HK_DIVIDEND | PASS for sanity |
| Multi-market timestamp | PASS |
| 11-slot mapping | PASS |
| 100 real finite observations | PASS |
| ActionDim=11 | PASS |
| No NaN/Inf | PASS |
| Save/load deterministic | PASS |
| C3 event audit | PASS for sanity / carry-forward |
| Action space `[-10,10]` | **FAIL / BLOCKER** |
| Softmax action semantics | **REVISE** |
| RiskOverlayV0 integration | **NOT PROVEN / BLOCKER** |
| Single-core cap | **VIOLATED in reported weights** |
| Observation normalization | **REQUIRED BEFORE GATE 4** |
| Held-out sanity evaluation | **NOT PROVEN** |
| SB3 `check_env` | **NOT REPORTED** |
| Gate 4 data horizon | **MUST PLAN BEFORE GATE 4** |

---

# 37. Reviewer Interpretation of Current TD3/SAC/PPO Behavior

当前最合理的解释是：

### TD3

```text
raw action magnitude较大
+
softmax指数放大
→ nearly one-hot
```

### SAC

```text
bounded stochastic policy产生较大 action spread
+
softmax指数放大
→ even more concentrated
```

### PPO

```text
raw logits接近0
+
softmax
→ near equal weight
```

因此三个模型现在主要展示的是：

> **算法 action distribution × 当前 softmax parameterization 的交互**

还不是：

> **算法真正的资产配置偏好。**

这正是 Gate 3 Sanity 应该发现的问题。

所以从研究流程角度：

> Gate 3 并没有“失败”；它成功暴露了一个必须在正式实验前修正的动作设计问题。

---

# 38. External Technical Verification

Stable-Baselines3 官方 Custom Environment / RL Tips 明确建议：

```text
continuous action space should be normalized and symmetric
good practice: [-1, 1]
```

因此本次要求：

```text
Box(-10,10) → Box(-1,1)
```

不是为了让回测更漂亮，而是为了符合连续控制环境的标准数值设计。

---

# 39. Reviewer Approval Record

```yaml
gate: 3
decision: REVISIONS_REQUIRED_BEFORE_GATE_4
date: 2026-08-08

passed:
  cash_solvency: true
  next_open_timing: true
  multi_market_timestamp: true
  cny_hk_series_for_sanity: true
  finite_observations: true
  model_train_save_load: true

blockers:
  action_space_scaling: true
  action_transform_fairness: true
  risk_overlay_not_proven: true
  single_core_cap_violation: true
  heldout_sanity_not_proven: true

required:
  normalized_action_space: [-1, 1]
  risk_overlay_v0: true
  observation_normalization: train_only
  chronological_eval: true
  sb3_check_env: true
  gate4_data_horizon_plan: true

carry_forward:
  C1_03110_same_day_rule: before_gate6
  C2_proxy_PIT: before_proxy_use
  C3_adjustment_independent_validation: before_gate4_formal_results
  F1_historical_fee_rules: before_gate4
  F2_southbound_broker_commission: before_gate4_realistic_cost_or_gate6
  H1_03110_total_return_validation: before_gate4_formal_results

permissions:
  patch_gate3: true
  rerun_one_seed_sanity: true
  optuna: false
  multiseed: false
  walk_forward: false
  theme_sleeve: false
  qmt_live_orders: false

required_next_packet:
  GATE_3_CORRECTIONS.md
```

---

# 40. Agent Next Instruction

```text
1. DO NOT start Gate 4.
2. Change continuous action space to [-1,1]^11.
3. Make ActionTransform explicit and algorithm-neutral.
4. Integrate mandatory RiskOverlayV0 into environment transition.
5. Add bounded-simplex / group-cap tests.
6. Separate raw policy / post-risk / actual holdings diagnostics.
7. Add train-only observation normalization.
8. Add chronological held-out sanity evaluation.
9. Run SB3 check_env and verify terminated/truncated semantics.
10. Re-run only one-seed / one-split TD3, SAC, PPO sanity.
11. Do not tune hyperparameters for performance.
12. Add Gate 4 data-horizon plan summary.
13. Generate GATE_3_CORRECTIONS.md.
14. Commit.
15. STOP.
16. Return packet to Reviewer / ChatGPT.
```

---

## END OF REVIEWER RESPONSE
