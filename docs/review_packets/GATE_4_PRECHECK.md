# GATE 4 PRECHECK

> Reviewer 决策：`GATE_3 = APPROVED_WITH_PRE_GATE4_CONDITIONS`（2026-08-08）
> `GATE_4_PREPARATION = AUTHORIZED`；正式 10-seed Walk-Forward **仍未授权**。
> 本 packet 按 Reviewer §17 的 12 项清单提交，供 Reviewer 批准后再进入 G4.3 3-seed pilot。

## 状态总结

| 前置项 | 状态 |
|---|---|
| 1. observation index proof | ✅ 闭环（commit `91d2588`，代码 mask 正确） |
| 2. C3 独立 corporate-action 验证 | ✅ 闭环（本 packet） |
| 3. H1 03110 总收益验证 | ✅ 闭环（本 packet） |
| 4. F1 历史费率表 | ✅ 闭环（南向分段 + 大陆保守假设） |
| 5. F2 南向券商佣金 | ✅ 闭环（conservative 万3 + min 5 HKD） |
| 6. Track A 日期范围 | ✅ 2022-05-18 → 2026-08-07（1069 决策日） |
| 7. Walk-Forward folds | ✅ 提议 4-fold expanding（待批准） |
| 8. baseline 配置 | ✅ EW / RP / MV / Momentum + RL 配置 |
| 9. WalkForwardRunner smoke | ✅ 机制冒烟（EW + TD3@2000，F3） |
| 10. 测试 | ✅ 88 tests 全过 |
| 11. 计算预算 | ✅ 估算（见 §11） |
| 12. Git commit | ✅ 见 §12 |

---

# 1. Observation Index Proof — CLOSED

**Reviewer 要求**：正式 Gate 4 前必须展示 `MARKET_FEATURE_INDICES = [0..87]+[99..103]`、
`PORTFOLIO_WEIGHT_INDICES = [88..98]`，并增加 4 个测试。

**结论：代码 mask 正确，非文档“末 N 维”措辞笔误。**

- obs 布局（`portfolio_env._observe`）：`[0:88] per-asset market | [88:99] actual weights | [99:104] global`。
- scaler mask（`gym_wrapper._market_positions`）= `[0..87] ∪ [99..103]`（93 维外生），
  只归一化外生；`[88:99]` 11 维 actual weights **位级不变**。
- 4 个必需测试已于 `91d2588` 提交并全过（`tests/test_observation_index.py`）：
  `test_observation_index_partition` / `test_only_exogenous_features_are_normalized` /
  `test_portfolio_weight_indices_unchanged` / `test_global_features_are_normalized`。
- 合成 obs（market=1.0、weights=[0.01..0.11]、global=2.0）证明：88+5 外生标准化，11 权重 allclose 不变。

按 Reviewer §4 判定路径：**仅文档措辞问题 → patch docs/tests，无需 RL rerun**。

---

# 2. C3 — Independent Corporate-Action Validation — CLOSED

## 2.1 公式修正（累计 split + 当前份额现金）

`src/china_etf/data/adjustments.py` `total_return_with_events`：

```text
TR_t = (P_t·S_t + Cash_t·S_t) / (P_{t-1}·S_{t-1}) - 1
S    = 累计送转/折算因子（现金分红事件不更新，per=1.0 不重置）
Cash = 当前份额口径（每份 X 元），×S 换算到旧股口径再相加
```

- 修正 1：split 由 per-event ffill 改为**累计 cumprod**（旧实现会在折算后首次分红日把
  折算因子重置回 1.0，制造虚假 +170% 收益）。
- 修正 2：份额折算（如 512100 1:0.36555）后的现金分红不被放大 1/split 倍。

## 2.2 独立来源验证（Sina raw + Sina 官方派息）

最坏事件 510300 2023-01-16（QMT front 偏差 13.8bp）归因验证：

```text
独立 TR = (4.143 + 0.064) / 4.144 - 1 = +1.5203%   ← 官方分红 0.064 + raw 价
本公式  = +1.5203%  == 独立 TR
QMT front = +1.66%（+13.8bp）→ 为 front 自身调整口径偏差，非 corporate-action 记账错误
```

## 2.3 系统性发现：QMT front 不可用于研究序列

- 510300 在 **2015-07-08** 显示 **-12.48%**（超过 A 股 ±10% 涨跌停上限）→ 系统性失真。
- 2012→2026 累计：QMT front 高估 **+4464bp**。
- 512100（折算+后续分红）组合下 front 累计与官方 TR 差 ≤8bp —— 单事件品种 front 尚可。

**决策：生产研究序列改用 `QMT raw + 官方事件 TR`**（`loader.load_research_adj`）。
验证数字（本机数据）：

```text
CN_LARGE 全周期累计（2012-05-28 → 2026-08-07）: +130.94%  ≈ 官方 TR +130.9%
CN_LARGE 2015-07-08 日收益                     : -10.01%   ≈ -10%（非 front -12.48%）
```

## 2.4 测试

`tests/test_adjustment_pit.py` 新增 5 个（全过）：
`test_conversion_then_cash_dividend_not_inflated` /
`test_split_cumulative_not_reset_by_cash_event` /
`test_loader_cn_large_uses_raw_plus_events_not_front` /
`test_loader_cn_large_full_history_matches_official_tr` /
`test_loader_hk_dividend_includes_official_distributions`。

`scripts/gate2_c3_realdata_check.py` 同步改为累计 split（需 QMT 环境运行，非 CI）。

---

# 3. H1 — 03110 Total-Return Validation — CLOSED

## 3.1 发现

- akshare `stock_hk_daily(adjust="qfq")` 对 03110 返回**就是 raw**（OHLC 逐列相同，未做任何
  分红调整）→ 除息日系统性漏掉派息（2025-09-24 漏 531bp、2024-09-24 漏 599bp、2022-09-26 漏 671bp）。
- 对策：研究序列 = sina raw 收盘 + **Global X/HKEX 官方派息**（`data/qmt/meta/divid_events/03110.HK.csv`，
  19 个唯一派息事件）→ total-return 指数 × HKD/CNY（中行折算价）。

## 3.2 验证

```text
2025-09-24 除息日（官方派息 1.60 HKD）：
  raw 价格收益 ≈ -5.05%  →  研究序列（raw+派息）≈ +0.24%
HK_DIVIDEND 累计（2013 → 2026）：+205%  （明显高于 raw 价格，含 19 次派息）
```

## 3.3 测试

`test_loader_hk_dividend_includes_official_distributions`（2025-09-24 收益 > -2%，含派息）+ 累计合理性断言。

---

# 4. F1 — Historical Point-in-Time Fee Rules — CLOSED

## 4.1 南向（港股通 ETF）分段费率（官方生效日）

| 费用项 | 生效日前 | 生效日 | 生效后 | 依据 |
|---|---|---|---|---|
| HKEX 交易费 | 0.005% | 2023-01-01 | 0.00565% | HKEX 通函 086/22 |
| SFC 交易征费 | 0.003% | 2014-11-01 | 0.0027% | SSE 港股通税费页 |
| FRC/AFRC 征费 | 0 | 2022-01-01 | 0.00015% | FRC 通函 CE/SEHK/CT/086/2021 |
| 股份交收费 | 0.002%（min 2 / max 100 HKD） | 2025-06-30 | 0.0042%（**无上下限**） | HKSCC |
| 印花税（ETF） | 0 | — | 0 | 港股通 ETF 豁免（Reviewer 核实） |
| 投资者赔偿/特别征费 | 0 | — | 0 | 暂不征收 |

**代码修复**：`SouthboundETFCostModel._rate_on` 原实现把生效日前的日期误用**新费率**
（如 2022 年交易费返回 0.00565% 而非历史 0.005%）。本 packet 重写为
`_rate_on(schedule, pre_rate, date)`：生效日前返回显式 `pre_rate`；`None`（研究模式）→ 最新费率；
股份交收费按 `(生效日, 费率, min, max)` 元组内嵌钳制，2025-06-30 后无上下限。

## 4.2 大陆（Mainland）假设（NOT ACCOUNT-VERIFIED）

| 费用项 | 假设 |
|---|---|
| 券商佣金 | 万0.5 恒定（账户协商费率），历史研究期假设不变；NOT ACCOUNT-VERIFIED |
| 经手费/证管费 | 是否含于佣金 `UNKNOWN_PENDING_BROKER_FEE_AUDIT`，**不自动叠加**（防 double count） |
| 印花税 | ETF 免，全程 0 |

大陆无对研究期有实质影响的官方分段费率变更，故采用明确保守常数假设；如 pilot 需要可加
piecewise（与南向同构）。

## 4.3 测试

`test_southbound_historical_rate_pit`（2022-06-01 交易费 0.005%、2021-06-01 AFRC=0）、
`test_southbound_settlement_clamp_transition`（min2/max100 → 无钳制）、
`test_fee_metadata_present` 更新。

---

# 5. F2 — Southbound Broker Commission — CLOSED

- 原 placeholder `0.00005`（万0.5）明显低于市场默认（2025-2026 多来源常见万2.5~万3）。
- 冻结 **conservative scenario**：`broker_commission_rate = 0.0003`（万3）双边 +
  `broker_min_commission_hkd = 5.0` 单笔最低。
- **NOT ACCOUNT-VERIFIED**：`source`/config manifest 均显式标注；不得表述为已核实事实。
- Gate 4 真实成本比较必须做 **1x / 2x / 3x cost sensitivity**（3x 覆盖万9 极端假设）。
- 测试：`test_southbound_cost_components`（comm=90、total=218.10）/
  `test_southbound_fee_03110_reviewer_numbers`（更新为 conservative）/
  `test_fee_metadata_present`（min 5 HKD、`NOT ACCOUNT-VERIFIED` 标注）。

---

# 6. Final Track A Date Range

```text
raw_data_start        : 2011-12-09   （研究序列最早原始数据）
effective_obs_start   : 2022-05-18   （11 槽位共同有效 + 252 日 warm-up；首个全 finite 观测）
decision_end          : 2026-08-07
decision_days         : 1069
TrainEnd < EvalStart  : 逐 fold 保证（见 §7）
```

口径（Reviewer §6）：报告一律使用 `effective_train_start = 2022-05-18`，不得再把 2011 写成 RL 有效训练起点。

---

# 7. Proposed Walk-Forward Folds（4-fold expanding）

实现：`WalkForwardRunner.make_folds(n_folds=4, min_train_days=360, test_days=177)`，
train 从决策区间起点开始增长，test 连续前移；最后一折覆盖到区间末尾（利用全部 OOS 数据）。

| Fold | Train 区间 | Train 日 | Test 区间 | Test 日 |
|---|---|---|---|---|
| F1 | 2022-05-18 → 2023-10-18 | 360 | 2023-10-19 → 2024-07-01 | 177 |
| F2 | 2022-05-18 → 2024-07-01 | 537 | 2024-07-02 → 2025-03-12 | 177 |
| F3 | 2022-05-18 → 2025-03-12 | 714 | 2025-03-13 → 2025-11-21 | 177 |
| F4 | 2022-05-18 → 2025-11-21 | 891 | 2025-11-24 → 2026-08-07 | 178 |

隔离规则（Reviewer §16）：每 fold 独立 `fit scaler（仅 train 决策区间）→ train 模型 → freeze → test`；
禁止复用未来 fold scaler、禁止用 test 选参。单元测试 `test_make_folds_partition_non_overlapping_expanding`
/ `test_fold_scaler_fit_train_only` 已覆盖无重叠与 scaler train-only。

---

# 8. Baseline & RL 配置

## 8.1 Deterministic baselines（`src/china_etf/evaluation/baselines.py`）

| Baseline | 参数 | 说明 |
|---|---|---|
| EqualWeight | — | 常权重 1/N |
| RiskParity | lookback=60 | w ∝ 1/vol_i（rolling std） |
| MinimumVariance | lookback=120, shrinkage=0.5 | 收缩协方差 → 无约束 GMV → 有界 simplex 投影（numpy only，无 scipy 依赖） |
| Momentum | lookback=252, skip=21 | w ∝ max(r[t-252, t-21], 0)，全负 → EW |

所有 baseline 走**标准 Environment path**：target weight → 逆 ActionTransform `a=2w-1` →
ActionTransform → RiskOverlay → execution（成本与 RL 完全一致）；只用 ≤t 数据（严格 PIT）。

## 8.2 RL 配置（沿用 Gate 3 sanity 冻结值）

```text
algorithms : TD3 / SAC / PPO（SB3 2.8.0）
net_arch   : [256, 256]
timesteps  : 12,000 / fold（pilot 确认后冻结）
devices    : TD3/SAC cuda（Pascal 1060）、PPO cpu
seed       : pilot=3 seeds（42/2026/7），10-seed 后续
```

---

# 9. WalkForwardRunner Smoke — MECHANICS ONLY

## 9.1 实现

- `src/china_etf/evaluation/walkforward.py`：`Fold` + `WalkForwardRunner`（train/test env 切片、
  fold-isolated scaler、RL 训练 + baseline 共路径）。
- `src/china_etf/evaluation/rollout.py`：OOS rollout 诊断（raw/post/actual 权重、overlay 干预率、
  cap 命中、NaN、reward/OOS 累计净收益）。
- `scripts/gate4_precheck.py`：真实数据 fold 划分 + 机制冒烟 + JSON 落盘。

## 9.2 冒烟结果（F3，seed=42）

```text
EW    F3: n_eval=176  oos_cum=+14.64%  nan=0  overlay_intervention=0.0
TD3   F3: n_eval=176  oos_cum=+14.52%  nan=0  save_load_deterministic=True  train=64.0s @2000步 cuda
normalized_eval_check: policy 收到归一化 obs（market−1000）、weights 位级不变 ✓
```

说明：smoke 用 2000 步 TD3 仅验证 runner 机制（fold 切片 / scaler 隔离 / 训练冻结 / 保存加载 /
test rollout / 诊断），**非正式训练结论**。正式 one-fold TD3/SAC/PPO seed=42 冒烟按用户本轮选择
延迟到 **G4.3 3-seed pilot**。

## 9.3 重要发现：Gate 3 sanity eval 归一化缺陷（已修复）

`scripts/gate3_rl_sanity.py::held_out_rollout` 对 policy 喂 **raw（未归一化）obs**
（直接 `env._observe()`），而模型训练于归一化 obs → 分布偏移。
`roll_out`（本 packet 新增）一律 `gym._normalize(obs)` 后再交 policy，并由
`test_rollout_policy_sees_normalized_obs` 强制校验。Gate 3 诊断数字保留但口径记为"近似"；
Gate 4 正式数字以归一化 eval 为准。

---

# 10. Exact Tests

```text
collected 88 items  →  88 passed in 24.4s
```

新增（GATE_4_PRECHECK）：

- `tests/test_observation_index.py`（4，commit 91d2588 已有）
- `tests/test_adjustment_pit.py`（+5：C3/H1）
- `tests/test_cost.py`（+2：`test_southbound_historical_rate_pit`、`test_southbound_settlement_clamp_transition`；更新 `test_southbound_cost_components`）
- `tests/test_gate2_corrections.py`（更新 2 个 F1/F2 断言）
- `tests/test_walkforward.py`（9：fold 划分 / scaler 隔离 / rollout 归一化 / baseline 权重性质 / EW smoke）

---

# 11. Compute-Budget Estimate

依据 Gate 3 sanity 实测（12k 步）：TD3 ≈ 266s（cuda）、SAC ≈ 363s（cuda）、PPO ≈ 163s（cpu）。

```text
4 folds × 3 algos × 3 seeds（pilot）= 36 次训练
  ≈ 36 × 264s ≈ 2.6h 训练 + ~0.4h eval rollouts ≈ 3h
4 folds × 3 algos × 10 seeds（正式）  = 120 次训练
  ≈ 8.8h 训练 + ~1.3h eval ≈ 10h
```

不含 Optuna（未授权）与 Track B/C。Pascal/1060 单卡；如需加速可 PPO 全 cpu / 减步数（不推荐降质）。

---

# 12. Git Commit

`GATE_4_PRECHECK` 实现提交 SHA：**（commit 后填写）**

包含：

```text
docs/review_packets/GATE_4_PRECHECK.md    ← 本 packet
src/china_etf/evaluation/                 ← rollout / baselines / walkforward（新模块）
scripts/gate4_precheck.py                 ← 机制冒烟脚本
scripts/gate2_c3_realdata_check.py        ← C3 累计 split 修正（原工作区未提交）
src/china_etf/data/adjustments.py         ← C3 公式修正
src/china_etf/data/loader.py              ← raw+events TR / H1 派息 / source 标注
src/china_etf/cost/southbound.py          ← F1 分段费率修复 + F2 conservative
src/china_etf/cost/mainland.py            ← F1 大陆假设 source 标注
config/fees/southbound_etf.yaml           ← F1/F2 同步
config/fees/mainland_etf.yaml             ← F1 假设同步
tests/test_adjustment_pit.py              ← C3/H1 测试
tests/test_cost.py / test_gate2_corrections.py / test_walkforward.py
runs/gate4_precheck_results.json          ← smoke 证据
```

---

# Out of Scope（本轮明确不做）

```text
✗ 正式 one-fold TD3/SAC/PPO seed=42 冒烟（延迟 G4.3 pilot）
✗ 3-seed / 10-seed / 20-seed RL
✗ 完整 walk-forward 结论 / 算法对比结论
✗ Optuna / 超参搜索
✗ Track B / C 执行
✗ QMT live / Paper / 架构改动（env / action / risk 未动）
```

## Approval Record

```yaml
gate: 4
packet: GATE_4_PRECHECK
status: SUBMITTED_FOR_REVIEW

pre_gate4_items:
  observation_scaler_index_proof: closed
  C3_independent_adjustment_validation: closed
  F1_historical_fee_schedule: closed
  F2_southbound_broker_commission: closed_conservative_not_account_verified
  H1_03110_total_return_validation: closed

authorized_next:
  - implement_walkforward_runner: done
  - implement_baselines: done
  - one_fold_smoke: done_mechanics_only
  - three_seed_pilot: pending_precheck_approval
  - ten_seed_run: false
  - optuna: false
  - theme_sleeve: false
  - qmt_live: false
```

## END OF GATE 4 PRECHECK
