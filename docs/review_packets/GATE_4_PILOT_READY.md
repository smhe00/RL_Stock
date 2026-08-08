# GATE 4 PILOT READY

> Reviewer 决策：`TARGETED_CORRECTIONS_REQUIRED_BEFORE_3_SEED_PILOT`（2026-08-08，
> `GATE_4_PRECHECK_REVIEWER_RESPONSE.md`）。Track A 改为**境内上市 ETF only**。
> 本 packet 按评审 §33 的 A–N 段提交；批准后才进入 G4.3 3-seed pilot（评审 §34）。

## 状态总结

| 前置项 | 状态 |
|---|---|
| M1 `HK_DIVIDEND → 513690` 迁移 | ✅ CLOSED |
| M2 513690 wrapper-equivalence | ✅ CLOSED（日相关 0.83，如实标注差异） |
| 重算 Track A horizon | ✅ `effective_obs_start = 2022-06-06`，决策日 1015 |
| CA1 境内 ETF 公司行为记账 | ✅ CLOSED（双价 contract + 应收款 + 折算） |
| WF1 Train → Validation → Test | ✅ CLOSED（4 folds，val 60） |
| WF2 t→t+1 fold 边界 | ✅ CLOSED（边界测试证明） |
| TB1 fold 训练预算 | ✅ CLOSED（TRAIN_PASSES × train_decision_steps） |
| 3-seed pilot | **NOT YET AUTHORIZED**（待本 packet 批准） |

---

# A. Scope Migration — `HK_DIVIDEND: 03110.HK → 513690.SH`

```text
HK_DIVIDEND:
  03110.HK  →  DEFERRED_TO_GATE6 / SECONDARY_TRACK（研究保留）
  513690.SH →  Track A 境内执行 wrapper（上交所，人民币）
```

- `SLOT_MAP["HK_DIVIDEND"] = {"instrument": "513690.SH", "source": "QMT raw + official events TR", "currency": "CNY"}`。
- **ActionDim 恒 11 不变**；ObsDim / ActionTransform / RiskOverlay / TD3/SAC/PPO 架构未动（评审 §3）。
- 03110 研究序列（`_hk_cny_series`）与全部数据**保留不删**，仅供 wrapper audit 与未来 Gate 6。
- Loader 精确选文件：`_slot_raw_file(slot)` 按 instrument 构造文件名，避免 glob 同时命中
  `HK_DIVIDEND_03110_HK_raw.csv` 与 `HK_DIVIDEND_513690_SH_raw.csv`。

---

# B. 513690 Evidence

## B.1 官方身份 / Listing

```text
博时恒生港股通高股息率 ETF（513690.SH）
fund contract effective : 2021-05-11
SSE listing date        : 2021-05-20
trading currency        : CNY
```

## B.2 Raw data availability（QMT，本地固化）

```text
rows      : 1267（2021-05-20 → 2026-08-07）
columns   : open / high / low / close / volume / amount / suspendFlag
liquidity : 最新交易日 volume≈1.6M、amount≈180M CNY（充足）
```

## B.3 Corporate actions（QMT get_divid_factors → divid_events/513690.SH.csv）

```text
2022-06-21  cash 0.0100
2023-12-22  cash 0.0070
2024-12-17  cash 0.0085
2025-12-17  cash 0.0113
（全部现金分红，无送股/折算）
```

## B.4 特征完备性

Track A 全 11 槽位 `effective_obs_start = 2022-06-06`（warmup 完成），研究序列全 finite，无异常收益尖峰。

## B.5 513690 vs 03110 wrapper-equivalence audit（评审 §5）

共同区间 2021-05-20 → 2026-08-07（1228 交易日，4.87 年），结果（`runs/gate4_wrapper_audit.json`）：

| 指标 | 513690 | 03110 |
|---|---:|---:|
| daily return correlation | — | **0.832** |
| rolling 120D corr median / min | — | **0.861 / 0.583** |
| annualized return | +18.2% | +57.4% |
| annualized vol | 19.9% | 18.2% |
| max drawdown | -38.1% | -26.4% |
| tracking error（ann） | — | 11.2% |

**结论（如实）**：513690 与 03110 跟踪**不同指数**（恒生港股通高股息率 vs 恒生高股息率），
相关性 0.83 / 滚动中位 0.86 属**中强相关但非等同**；收益幅度差异显著（+18% vs +57%，
来源：指数成分口径差异 + 03110 的 HKD→CNY 折算历史）。513690 足以代表 `HK_DIVIDEND`
经济风险 Slot 作为 **Track A 境内 wrapper**；若正式 pilot 中 513690 相对 03110 的相关性
长期明显失效，将重新评估 Slot wrapper（不改 RL action space）。03110 精确行为留待 Gate 6。

---

# C. Recomputed Track A Horizon

```text
raw_data_start        : 2011-12-09
effective_obs_start   : 2022-06-06   ← 新 11-Instrument universe（非继承 2022-05-18）
data_end              : 2026-08-07
decision_days         : 1015
TrainEnd < EvalStart  : 逐 fold 保证
```

原因：513690（2021-05-20 上市）自身 252 日 warmup 完成于 2022-06-06，晚于原 03110
（2013 起即有完整历史）约束下的 2022-05-18。**decision_days 1069 → 1015**（-54 日）。

---

# D. Dual-Price Contract

```text
features / historical returns  → total-return research series（QMT raw + 官方事件 TR）
orders / fills                → raw market OHLC（open 执行）
portfolio valuation           → raw prices + corporate-action accounting
```

`V_t = Cash_t + Receivable_t + Σ qty_i · P^{raw}_{i,t}`。研究序列与执行价严格分离；
**禁止用复权价成交**（`test_execution_uses_raw_price_not_total_return_price` 证明）。

---

# E. Mainland ETF Corporate-Action Accounting（CA1）

## E.1 事件流（`data/corporate_actions.py`）

```text
CorporateActionEvent:
  instrument, ex_date, pay_date, cash_per_share, unit_factor
  unit_factor = 1 + stockBonus + stockGift（送股/折算；默认 1.0）
  pay_date：事件表缺失时默认 ex_date + 2 交易日（文档近似；显式 pay_date 优先）
```

覆盖 6 只境内 ETF：510300 / 511260 / 512100 / 512890 / 513500 / 513690（现金分红 + 送股/折算）。

## E.2 记账（`accounting.py`）

```text
accrue_dividend(qty, cash)        : ex_date 计提应收款（价值中性）
settle_dividend()                 : pay_date 应收款 → cash（价值中性）
apply_unit_conversion(factor)     : 折算 qty×=factor, avg_cost/=factor（价值中性）
snapshot.portfolio_value          : cash + market_value + dividend_receivable
```

## E.3 Env 集成（`portfolio_env.py`）

t→t+1 推进序列（在决策 t 收盘 → 执行 t+1 开盘之间）：

```text
1. settle（pay_date == t+1）→ 应收款转现金
2. 折算（ex_date == t+1）→ qty ×= factor（t+1 开盘前持仓）
3. 计提分红（ex_date == t+1）基于 t+1 开盘前持仓（当日新买入不享分红；已持部分当日卖出仍享）
4. 执行 fills（t+1 开盘 raw 价）
5. mark（t+1 收盘 raw + 应收款）
```

- 折算日订单规划：折算后 qty 用调整后价格（`close/factor`）保证 notional 一致，避免 2.74× 误配。
- ex-date reward 无人为损失：raw 价机械下跌被应收款抵消。

## E.4 Required Tests（评审 §18，`tests/test_corporate_actions.py` 7 个全过）

```text
test_execution_uses_raw_price_not_total_return_price       PASS
test_ex_dividend_creates_receivable                        PASS
test_dividend_receivable_not_spendable_before_payment      PASS
test_dividend_payment_moves_receivable_to_cash_without_pnl_jump  PASS
test_ex_dividend_reward_has_no_artificial_loss             PASS
test_unit_conversion_preserves_portfolio_value             PASS
test_walkforward_uses_dual_price_contract                  PASS
```

---

# F. Train / Validation / Test Folds（WF1）

新日历（1015 决策日，2022-06-06 起）：`make_folds(n_folds=4, min_train_days=300, val_days=60)`。

| Fold | Train core 日 | Val 日 | Test 日 | Train→Val→Test 日期 |
|---|---|---|---:|---|
| F1 | 300 | 60 | 118 | 2022-06-06 → 2023-08-23 → 2023-11-23 → 2024-05-23 |
| F2 | 478 | 60 | 118 | 2022-06-06 → 2024-05-23 → 2024-08-16 → 2025-02-18 |
| F3 | 656 | 60 | 118 | 2022-06-06 → 2025-02-18 → 2025-05-19 → 2025-11-10 |
| F4 | 834 | 60 | 121 | 2022-06-06 → 2025-11-10 → 2026-02-04 → 2026-08-07 |

（各段日期为：train_start → train_end → val_end → test_end，均为含当日。）

每 fold：`train（expanding，scaler 只 fit train core）→ validation（transform-only）→ test（全冻结）`。
fold 间严格 tiling 无重叠无空隙（`test_make_folds_partition_non_overlapping_expanding`）。

---

# G. t→t+1 Boundary Proof（WF2，评审 §22-§24）

- Train env 数据止于 `train_end`（val_start 前一交易日）；末决策执行于 train_end，**绝不用 val 首日价格**。
- Val env 数据止于 `val_end`（test_start 前一交易日）；末决策执行于 val_end，不用 test 首日。
- Test env 末行 = terminal mark（非决策）：`test 决策数 = 测试区日历行数 - 1`。

```text
test_train_last_decision_does_not_use_validation_price    PASS
test_validation_last_decision_does_not_use_test_price     PASS
test_test_decision_count_equals_calendar_rows_minus_one   PASS（smoke 实测 rows=121, decisions=120）
test_fold_segment_terminal_mark_semantics                 PASS
```

---

# H. Training Budget Rule（TB1，评审 §25）

```text
TRAIN_PASSES = 20
total_timesteps = train_decision_steps × TRAIN_PASSES
```

每 fold 的 `train_decision_steps`（smoke 实测）：

| Fold | train_decision_steps | total_timesteps（×20） |
|---|---:|---:|
| F1 | 299 | 5,980 |
| F2 | 477 | 9,540 |
| F3 | 655 | 13,100 |
| F4 | 833 | 16,660 |

run manifest 记录 `train_decision_steps / train_passes / total_timesteps`。不再固定 12,000/fold
（避免早期 fold 对同一历史重复训练）。

---

# I. Baseline Inverse-Action Roundtrip Test

`test_baseline_target_action_roundtrip`（`tests/test_walkforward.py`）：

```text
target weight → inverse ActionTransform (a=2w-1) → ActionTransform (score=w) → 同权重
```
对 EW / RiskParity / MinimumVariance / Momentum 全部通过（含 0 权重可表达）。

---

# J. Train/Eval Normalization-Equivalence Test

`test_training_and_evaluation_share_same_observation_transform`：train env 与 eval env 用同一
train-fit scaler，对同一天 raw obs 输出**逐位一致**（eval 无 scaler 更新）。配合
`test_rollout_policy_sees_normalized_obs` 证明 eval policy 输入与训练同构。

---

# K. Exact pytest Output

```text
collected 102 items  →  102 passed in 37.1s
```

新增（相对 precheck 88）：

- `tests/test_corporate_actions.py`（7：CA1 双价 contract）
- `tests/test_walkforward.py` 扩充（15：含 4 边界 + roundtrip + 归一化等价）
- `tests/test_adjustment_pit.py` 更新（03110 保留研究 + 513690 Track A 派息）

---

# L. Mechanics Smoke（`scripts/gate4_pilot_ready.py`）

F4（test 窗口含 513690 2025-12-17 派息），EW + TD3（train_passes=2，机制冒烟）：

```text
decision_start=2022-06-06  decision_days=1015
fold 表：train core [300,478,656,834] + val 60 + test [118,118,118,121]

CA 513690 2025-12-17 派息在 F4 test 窗口计提: True
EW  F4: test n_eval=120  cum=+1.57%  nan=0
TD3 F4: train_steps=833  timesteps=1666  save_load=True  train=69.6s
        val n_eval=59  cum=+0.84%  nan=0  |  test n_eval=120  cum=+1.15%  nan=0
boundary: test rows=121  decisions=120 = rows-1  ✓
```

冒烟只验证 runner 机制（fold 切片 / val 段 / scaler 隔离 / CA / 边界 / save-load），**非正式训练结论**。
正式 pilot（4 folds × 3 algos × 3 seeds，train_passes=20）需本 packet 批准。

---

# M. Revised Compute Budget

每 algo-seed 4 folds = 45,280 timesteps（×20 passes）。按 Gate 3 实测速率（TD3 0.022s/step、
SAC 0.030s/step、PPO 0.014s/step）：

```text
3-seed pilot（36 RL trainings，评审 §34）
  TD3 3×16.8min + SAC 3×22.9min + PPO 3×10.3min ≈ 2.5h RL
  + 4 baselines × 4 folds rollouts + eval ≈ 0.5h
  ≈ 3h 总计（单卡 1060）

10-seed formal（120 RL trainings）
  ≈ 8.3h RL + 1x/2x/3x cost sensitivity（×3 retrain）≈ 25h + eval
  ≈ 26-28h（可分 3 个 cost 场景串行）
```

不含 Optuna / Track B / Track C。

---

# N. Git Commit

`GATE_4_PILOT_READY` 实现提交 SHA：**（commit 后填写）**

包含：

```text
docs/review_packets/GATE_4_PILOT_READY.md     ← 本 packet
src/china_etf/data/loader.py                  ← HK_DIVIDEND→513690 + 精确文件选择 + 03110 保留
src/china_etf/data/corporate_actions.py       ← 事件流（新）
src/china_etf/accounting.py                   ← 应收款 + 折算 + Snapshot.receivable
src/china_etf/environment/portfolio_env.py    ← CA 集成（settle/折算/计提，pay_date 索引）
src/china_etf/evaluation/walkforward.py       ← Train/Val/Test + 边界 + train_passes 预算
scripts/gate4_513690_wrapper_audit.py         ← M2 audit
scripts/gate4_pilot_ready.py                  ← 机制冒烟
tests/test_corporate_actions.py               ← CA1 7 测试
tests/test_walkforward.py                     ← 4 边界 + roundtrip + 归一化等价
tests/test_adjustment_pit.py                  ← 03110 保留 + 513690 派息
data/qmt/raw/HK_DIVIDEND_513690_SH_raw.csv    ← 513690 raw（data/ 不入库，仅记录）
data/qmt/meta/divid_events/513690.SH.csv      ← 513690 事件（data/ 不入库）
runs/gate4_wrapper_audit.json / gate4_pilot_ready_smoke.json
```

---

# Out of Scope（本轮明确不做）

```text
✗ 3-seed / 10-seed / 20-seed pilot（待本 packet 批准）
✗ 正式 walk-forward 结论 / 算法对比结论
✗ Optuna / 超参搜索 / reward selection
✗ 03110 / Southbound / HKD 执行（defer Gate 6）
✗ Track B / C 执行；Theme Sleeve；QMT live
✗ Mean-Variance / Trend+RiskParity baselines（评审 §27：正式 GATE_4_CORE_WALKFORWARD 前补或 RFC）
```

## Approval Record

```yaml
gate: 4
packet: GATE_4_PILOT_READY
status: SUBMITTED_FOR_REVIEW

closed_before_pilot:
  migrate_hk_dividend_to_513690: true
  validate_513690_wrapper: true      # corr 0.83 / 如实标注差异
  recompute_track_a_horizon: true    # 2022-06-06, 1015 决策日
  mainland_corporate_action_accounting: true
  train_validation_test_contract: true
  next_day_fold_boundary: true
  training_budget_semantics: true    # TRAIN_PASSES × train_decision_steps

authorized_next:
  three_seed_pilot: pending_approval   # 评审 §34: 4 folds × TD3/SAC/PPO × seeds 42/2026/7 × 1x cost
  ten_seed_formal: false
  cost_sensitivity: pilot=1x, formal=1x/2x/3x
  optuna: false
```

## END OF GATE 4 PILOT READY
