# GATE 3 Corrections — Reviewer Final Review
## FinRL-X 中国 ETF 项目 — RL Sanity 二次验收

**Reviewed artifacts:**
- `GATE_3_CORRECTIONS.md`
- `GATE_4_DATA_HORIZON_PLAN.md`

**Review date:** 2026-08-08  
**Decision:** `TARGETED_FINAL_CORRECTIONS_REQUIRED_BEFORE_GATE_4`  
**Gate 3 engineering status:** `SUBSTANTIALLY_PASS`  
**Gate 4 authorization:** `NOT YET AUTHORIZED`

---

# 1. Reviewer Decision

本次修订已经成功关闭上一轮最重要的 Gate 3 问题：

- Action Space 已由 `[-10,10]^11` 改为 `[-1,1]^11`；
- TD3/SAC 原来的极端单资产集中消失；
- `raw_policy → post_risk → actual` 三层权重已经可审计；
- RiskOverlayV0 已进入 Environment transition；
- capped-simplex / group-cap property tests 已建立；
- chronological held-out sanity evaluation 已建立；
- SB3 `check_env` 已通过；
- 11-Core 真实数据 observation 已验证 finite；
- save/load deterministic consistency 已验证。

旧 Gate 3：

```text
TD3 max ≈ 0.846
SAC max ≈ 0.926
```

修正后：

```text
TD3 raw max_mean ≈ 0.152
SAC raw max_mean ≈ 0.177
PPO raw max_mean ≈ 0.101
```

证明上一轮 Reviewer 对：

> `Box(-10,10) + softmax` 导致 action-scale artifact

的判断成立。fileciteturn29file0

因此当前 RL pipeline 已经接近可以进入正式 Walk-Forward。

但是在 Gate 4 前仍有 **两个必须修正的模型接口问题**，以及一个必须补全的数据跨度决策。

这些问题不需要推翻现有 Environment，也不要求重新做 Gate 0~2。

---

# 2. BLOCKER-A：`[-1,1] + softmax` 引入了非预期的最低资产权重

当前 ActionTransform：

$$
w_i=
\frac{\exp(a_i)}
{\sum_j\exp(a_j)},
\qquad
a_i\in[-1,1]
$$

成功解决了指数爆炸问题。

但它产生了另一个结构性约束：

> **每个资产都无法真正降到 0。**

对于 11 个资产，当某资产：

```text
a_i = -1
```

其余 10 个资产：

```text
a_j = +1
```

该资产最小可达权重约为：

$$
w_{min}
=
\frac{e^{-1}}
{e^{-1}+10e^{1}}
\approx1.34\%
$$

因此当前 policy 实际学习的不是：

$$
w_i\ge0
$$

而是近似：

$$
w_i\gtrsim1.3\%
$$

这不是原始 EXECUTION_SPEC 的 Frozen Decision。

---

# 3. 为什么这个问题必须在 Gate 4 前修

长期资产配置系统需要能够表达：

```text
某资产当前不值得持有
→ weight ≈ 0
```

例如：

- US_BROAD 高溢价时期；
- 某股票风格长期弱势；
- 风险状态下减少某权益资产；
- 后续 Theme Sleeve K=0。

虽然 Tradability / Premium 可以强制某 Instrument 不买，但 RL 本身也应该能够表达接近 0 的经济风险暴露。

因此：

```text
softmax([-1,1])
```

当前隐含的 minimum-allocation prior 不应无意中进入正式 Gate 4。

---

# 4. Required ActionTransform V2

Reviewer 推荐一个简单、算法中立、可解释的 V2：

```python
a = clip(action, -1.0, 1.0)

score = (a + 1.0) / 2.0
# score ∈ [0,1]

if score.sum() <= eps:
    raw_weights = equal_weight
else:
    raw_weights = score / score.sum()

post_risk = RiskOverlayV0.project(raw_weights)
```

即：

$$
s_i=\frac{a_i+1}{2}
$$

$$
w_i^{raw}
=
\frac{s_i}
{\sum_js_j}
$$

---

# 5. ActionTransform V2 的优点

## 5.1 可以表达 0

```text
a_i = -1
→ score_i = 0
→ raw weight_i = 0
```

## 5.2 Neutral action 仍然是等权

```text
all a_i = 0
→ all score_i = 0.5
→ equal weight
```

## 5.3 不再指数放大

linear score normalization 不会产生旧 softmax 的 exponential scale artifact。

## 5.4 三算法仍完全公平

TD3 / SAC / PPO 使用相同 transform。

## 5.5 极端集中由 RiskOverlay 负责

例如：

```text
one +1
ten -1
```

可以得到：

```text
raw = 100% one asset
```

然后 Mandatory RiskOverlay 明确处理：

```text
post-risk <= 25%
```

这比把“分散化”偷偷塞进 softmax logit range 更清晰。

---

# 6. Degenerate Action 必须定义

如果：

```text
all action = -1
```

则：

```text
score.sum() = 0
```

不得出现 NaN。

V1 推荐：

```text
fallback = equal weight
reason_code = DEGENERATE_ACTION_FALLBACK
```

同时记录到 diagnostics。

如果未来发现 Agent 经常输出全 -1，再单独研究。

不要现在增加复杂规则。

---

# 7. Required ActionTransform Tests

至少增加：

```text
test_action_zero_maps_equal_weight
test_action_minus_one_can_map_zero_weight
test_action_single_positive_can_create_sparse_raw_weight
test_action_all_minus_one_fallback
test_action_transform_no_nan
test_action_transform_algorithm_neutral
```

以及 integrated test：

```text
action = [1,-1,-1,...]
```

必须证明：

```text
raw max ≈ 1.0
post-risk max <= 0.25
actual target obeys execution semantics
```

这个测试也正式证明 RiskOverlay 在真实 Environment transition 中会被触发，而不是只存在于独立 property tests。

---

# 8. BLOCKER-B：当前 Observation Scaler 依赖 Equal-Weight policy trajectory

当前报告：

```text
train 期收集 500 步 observation
using Equal Weight trajectory
→ fit mean/std scaler
```

这是一个不应进入 Gate 4 的设计。

原因是 observation 104 维包含：

```text
93 exogenous market/global features
+
11 actual portfolio weights
```

后 11 维是：

```text
endogenous portfolio state
```

它们由策略行为产生。

---

# 9. Equal-Weight Scaler 会产生 Policy-Dependent Normalization

Equal Weight trajectory 的 11 个 weight feature：

```text
长期接近 ~9%
```

方差很小。

如果用它们拟合 scaler，然后 TD3/SAC 实际产生：

```text
5%
15%
25%
```

这些合理 portfolio states 可能被映射成异常大的 z-score。

更重要的是：

> normalization statistics 不应该由某个 benchmark policy 决定。

否则模型输入预处理本身已经带有：

```text
Equal-Weight policy prior
```

---

# 10. Required Observation Normalization V2

Observation 应显式拆成：

```text
MarketStateFeatures = 93 dimensions
PortfolioState      = 11 actual weights
```

其中：

## 10.1 只 normalize 93 个 exogenous features

```text
88 per-asset market features
+
5 global market features
```

使用：

```text
Train-only scaler
```

## 10.2 11 个 actual weights 不 normalize

保持：

```text
[0,1]
```

原始经济含义。

最终 network input 仍为：

```text
104 dimensions
```

只是 normalization mask 不同。

---

# 11. Scaler 不能再用“500 步 EW trajectory”

Scaler 应从：

```text
所有有效 Train dates 的 93-d exogenous feature matrix
```

直接拟合。

即：

```text
policy-independent
time-based
train-only
```

推荐：

```python
market_scaler.fit(
    train_feature_matrix[:, MARKET_FEATURE_INDICES]
)
```

不要通过 Environment 跑某个 policy 来生成 scaler 数据。

---

# 12. Required Scaler Tests

至少：

```text
test_scaler_fits_market_features_only
test_portfolio_weights_are_not_normalized
test_scaler_uses_train_dates_only
test_eval_does_not_update_scaler
test_scaler_save_load_exact
test_future_data_mutation_does_not_change_train_scaler
```

并报告：

```text
93 normalized dimensions:
  eval mean/std/range

11 portfolio-state dimensions:
  remain in [0,1]
```

---

# 13. Train Interval 报告必须修正

当前 Gate 3 写：

```text
Train = 2011-12-09 → 2025-10-23
```

但真实 11-Core：

```text
first all-finite observation = 2022-05-18
```

因此需要区分：

```text
raw_data_start
```

和：

```text
effective_training_observation_start
```

正式 run manifest 应写：

```yaml
raw_data_start: 2011-12-09
effective_obs_start: 2022-05-18
train_end: 2025-10-22_or_exact_boundary
eval_start: 2025-10-23
eval_end: 2026-08-07
```

否则读者会误以为 RL 实际训练了 2011~2025 的十多年数据。

这是报告语义修正，不需要改金融逻辑。

---

# 14. Train / Eval Boundary 必须没有同日重叠

当前文档同时写：

```text
Train → 2025-10-23
Eval = 2025-10-23 → ...
```

必须确认 exact indexing：

$$
TrainEnd < EvalStart
$$

例如：

```text
train_end = 2025-10-22
eval_start = 2025-10-23
```

或者使用明确 half-open interval：

```text
Train = [start, 2025-10-23)
Eval  = [2025-10-23, end]
```

Gate 4 前必须在代码/manifest 中使用明确 interval semantics。

---

# 15. Gate 3 Sanity Re-run

ActionTransform V2 + Normalization V2 修改后：

再运行一次：

```text
one seed = 42
same chronological split
same ~12k timesteps
TD3 / SAC / PPO / EW
```

仍然：

```text
NO tuning
NO winner conclusion
```

主要验证：

```text
stable
no NaN
post-risk caps hold
actual holdings valid
save/load valid
held-out evaluation works
```

---

# 16. Required Diagnostics After V2

分别报告：

```text
raw_action
raw_policy_weights
post_risk_target_weights
actual_weights
```

至少：

```text
max weight mean
min weight mean
fraction raw weights < 1%
fraction raw weights == 0 or <eps
HHI
RiskOverlay intervention rate
mean L1(raw, post-risk)
single-core cap hit rate
ChinaGrowth cap hit rate
turnover
cash residual
```

这一组指标可以判断：

> RiskOverlay 是否只是安全护栏，还是实际上长期替 RL 做资产配置。

如果：

```text
RiskOverlay intervention rate 很高
```

Gate 4 需要进一步研究 action contract。

---

# 17. Current Gate 3 Results 的解释

现有 corrected Gate 3 结果仍然有价值：

```text
TD3 / SAC / PPO no NaN
save-load works
held-out inference works
cash/accounting stable
```

但由于：

```text
softmax implicit floor
+
EW-dependent scaler
```

当前的：

```text
TD3 vs SAC vs PPO weight dispersion
reward_mean
turnover
```

不应该进入 Gate 4 基线比较。

完成 V2 后才冻结算法接口。

---

# 18. Gate 4 Data Horizon Plan — Direction APPROVED

`GATE_4_DATA_HORIZON_PLAN.md` 的核心判断正确：

```text
11 Core actual ETF
common valid history ≈ 2022-05 → 2026-08
```

约 4.2 年。

这不足以单独证明：

```text
long-term RL alpha
```

因此将：

```text
Method Research
```

与：

```text
Instrument OOS
```

分开是正确方向。fileciteturn29file1

---

# 19. 但 Track B 目前仍是“假设能延长历史”，尚未证明

Track B 写：

```text
Point-in-Time Proxy Method Research
→ 延长历史
```

但还没有量化：

> 严格禁止 pre-launch backfill 后，11 个 Slot 的共同 PIT 起点到底是多少。

例如当前已知：

```text
STAR50 launch ≈ 2020
HSTECH launch ≈ 2020
```

即使使用 PIT proxy，11-Slot common history 很可能也只能从：

```text
2020+
```

开始。

再加 252 日 warm-up，可能只比 Track A 早约一年左右。

因此：

> Track B 不能在没有计算 common PIT horizon 前就被称为“长历史方案”。

---

# 20. Required Gate 4 Horizon Quantification

正式进入 Gate 4 前生成一张表：

| Slot | Proxy | Launch Date | First PIT Date | Warmup Effect |
|---|---|---|---|---|
| CN_LARGE | | | | |
| CN_SMALL | | | | |
| ... | | | | |
| STAR | | | | |
| HK_TECH | | | | |
| ... | | | | |

然后计算：

```text
TRACK_A_EFFECTIVE_START
TRACK_B_COMMON_PIT_START
TRACK_B_AFTER_252_WARMUP
TRACK_B_USABLE_TRADING_DAYS
```

必须回答：

```text
Track B 到底比 Track A 多多少年？
```

---

# 21. 如果 Track B 只多 0~1.5 年

那么不要为了形式硬做 Track B 主实验。

可以考虑三个方向，但都需要 Reviewer/RFC 后再实现：

### Option B1

```text
11-slot PIT Track B
```

即使历史仍短，也作为 method cross-check。

### Option B2

```text
Reduced legacy asset-slot universe
```

用于更长的 strictly PIT method study。

缺点：

```text
action dimension / economic problem changes
```

必须作为独立实验，不能与 11-Core 直接混为一谈。

### Option B3

```text
Fixed 11 dimensions + historical availability mask
```

某些 Slot 上市/可用前：

```text
tradability = false
```

保持 action dimension 11。

但这会引入：

```text
changing opportunity set
```

需要单独设计与验证，不建议直接在 Gate 4 临时加入。

---

# 22. Track C — APPROVED AS SCENARIO ONLY

Track C：

```text
retrospective / backfilled proxy
```

可以用于：

```text
mechanism study
stress/regime study
```

但报告必须显著标记：

```text
SCENARIO
NOT STRICT PIT OOS
```

不能进入最终的 strict OOS alpha 结论。

---

# 23. Gate 4 的推荐证据层级

当前 Reviewer 更推荐最终形成：

## Evidence A — Real ETF

```text
REAL-INSTRUMENT OOS
limited-history
```

用于：

> 可执行性与真实 ETF 行为。

## Evidence B — Strict PIT Method Track

若量化后确实提供足够增量历史：

```text
PIT METHOD OOS
```

用于：

> 算法方法论证据。

## Evidence C — Long Scenario

```text
SCENARIO LONG-HISTORY
```

用于：

> regime / stress / mechanism。

三者不得在报告中混成一个 Sharpe。

---

# 24. Gate 4 前仍必须关闭的 Data/Cost Items

当前 carry-forward：

```text
C1 03110 same-day rule
C2 proxy PIT audit
C3 adjustment independent validation
F1 historical fee rules
F2 Southbound broker commission
H1 03110 total-return validation
```

Gate 4 的要求进一步明确为：

## 必须在 Track A realistic-cost result 前关闭

```text
C3
F1
F2
H1
```

## 必须在 Track B 使用前关闭

```text
C2
```

## Gate 6 前关闭即可

```text
C1
```

因为 Gate 4 是 Daily next-session allocation，不依赖日内回转。

---

# 25. C3 独立来源验证

Gate 3 已经做到：

```text
QMT raw/events
vs
QMT front
```

Gate 4 前只需对：

```text
max diff = 13.8bp
```

最坏事件做至少一个独立来源验证。

不要求重复检查全部 14 个 event。

---

# 26. H1 — 03110 High-Dividend Total Return

Gate 4 前选择：

```text
2~3 distribution dates
```

验证：

```text
Sina qfq
```

是否正确反映：

```text
Global X / HKEX official cash distribution
```

因为高股息 ETF 的 total-return 序列若错，会直接扭曲：

- reward；
- correlation；
- defensive behavior；
- Sharpe。

---

# 27. Gate 4 不能立即开始 20 Seeds

即使最终 Gate 3 V2 通过，也建议 Gate 4 执行顺序：

```text
Step 1
freeze data/cost/history semantics

Step 2
one complete walk-forward seed
→ verify fold runner

Step 3
3-seed pilot
→ inspect runtime / stability / bugs

Step 4
10 seeds

Step 5
only if needed → 20 seeds
```

原因：

> 先验证 WalkForwardRunner，不要一开始烧大量算力重复一个潜在 bug。

这不是减少最终严谨度，而是工程执行顺序要求。

---

# 28. Gate 4 Baseline 顺序

同样先跑 deterministic baseline：

```text
Equal Weight
Risk Parity
Minimum Variance
Momentum
```

确认：

```text
same folds
same cost
same execution
same data
```

然后再启动三种 RL。

MVO 可以在 covariance/expected-return semantics 验证后加入。

---

# 29. Gate 3 Final Correction Packet

Agent 现在生成：

```text
docs/review_packets/GATE_3_FINAL_CORRECTIONS.md
```

只需要包含：

## 1. ActionTransform V2

## 2. Sparse/zero-weight tests

## 3. Forced RiskOverlay integrated test

## 4. Observation normalization V2

## 5. Policy-independent scaler proof

## 6. Exact effective train/eval intervals

## 7. Re-run one-seed sanity

## 8. Raw/post-risk/actual diagnostics

## 9. RiskOverlay intervention diagnostics

## 10. Gate 4 Track-B quantified common horizon

## 11. Carry-forward closure plan

## 12. Exact pytest output

## 13. Git commit

无需重做之前已经通过的：

```text
Cash solvency
Southbound fee
overnight timing
SB3 check_env
```

除非 regression test 失败。

---

# 30. Gate 4 Authorization Criteria

满足以下条件后，我预计可以直接批准 Gate 4：

```text
ActionTransform can express ~0 allocation
no hidden minimum-weight prior
RiskOverlay forced-path integration passes
normalization is policy-independent
portfolio weights remain unnormalized state
scaler fitted only on train exogenous features
train/eval interval is non-overlapping
one-seed V2 sanity stable
Track B common PIT horizon quantified
C3/F1/F2/H1 closure plan explicit
```

---

# 31. Current Decision Table

| Item | Decision |
|---|---|
| old action-scale artifact | RESOLVED |
| normalized SB3 action space | PASS |
| RiskOverlayV0 implementation | PASS |
| bounded-simplex property tests | PASS |
| raw/post-risk/actual diagnostics | PASS |
| chronological held-out eval | PASS |
| SB3 check_env | PASS |
| no NaN / save-load | PASS |
| `[-1,1] softmax` implicit weight floor | **BLOCKER** |
| EW-trajectory scaler | **BLOCKER** |
| effective train-start reporting | REVISE |
| Track A data-horizon reasoning | PASS |
| Track B actual horizon | **QUANTIFY BEFORE GATE 4** |
| Track C scenario labeling | PASS |

---

# 32. Reviewer Interpretation

这次 Gate 3 修订是有实质进展的。

它已经证明：

> 原先 TD3/SAC 的极端集中不是 RL 算法“本性”，而是 action representation 设计造成的。

下一步需要做的不是调 TD3/SAC/PPO 参数，而是把最后两个**隐藏先验**移除：

1. softmax 有界 logits 带来的 minimum-weight prior；
2. Equal-Weight trajectory 带来的 normalization prior。

完成后，三算法才真正共享：

```text
same action semantics
same observation semantics
same risk semantics
same execution semantics
```

那时才值得投入 Gate 4 的 Walk-Forward + multi-seed 计算预算。

---

# 33. Reviewer Approval Record

```yaml
gate: 3
decision: TARGETED_FINAL_CORRECTIONS_REQUIRED_BEFORE_GATE_4
date: 2026-08-08

resolved:
  action_explosion: true
  td3_sac_weight_collapse: true
  risk_overlay_module: true
  chronological_eval: true
  sb3_check_env: true

blockers:
  action_transform_implicit_min_weight: true
  policy_dependent_observation_scaler: true

gate4_plan:
  track_a: approved_in_principle
  track_b: requires_horizon_quantification
  track_c: scenario_only

permissions:
  patch_action_transform: true
  patch_scaler: true
  rerun_one_seed_sanity: true
  quantify_track_b: true
  gate4_walk_forward: false
  multiseed: false
  optuna: false
  theme_sleeve: false
  qmt_live: false

required_next_packet:
  GATE_3_FINAL_CORRECTIONS.md
```

---

# 34. Agent Next Instruction

```text
1. Do NOT start Gate 4.
2. Replace bounded-logit softmax with a zero-capable algorithm-neutral score transform.
3. Keep action_space = [-1,1]^11.
4. Keep RiskOverlayV0 mandatory.
5. Add forced RiskOverlay end-to-end test.
6. Normalize only 93 exogenous market/global dimensions.
7. Leave 11 actual portfolio weights unnormalized.
8. Fit scaler from all valid TRAIN exogenous rows, not an EW trajectory.
9. Freeze non-overlapping effective train/eval dates.
10. Re-run one seed TD3/SAC/PPO/EW sanity only.
11. Quantify Track B common PIT horizon.
12. Generate GATE_3_FINAL_CORRECTIONS.md.
13. STOP.
14. Return to Reviewer / ChatGPT.
```

---

## END OF REVIEWER RESPONSE
