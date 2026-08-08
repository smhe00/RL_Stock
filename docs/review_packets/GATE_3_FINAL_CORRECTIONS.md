# GATE 3 Final Corrections

> Reviewer: `TARGETED_FINAL_CORRECTIONS_REQUIRED_BEFORE_GATE_4`（2026-08-08）。
> 关闭 BLOCKER-A（softmax 隐含最小权重）与 BLOCKER-B（EW 轨迹 scaler）+ Track B 量化。

## 1. ActionTransform V2（BLOCKER-A 关闭）

```python
a = clip(action, -1, 1)
score = (a + 1.0) / 2.0          # ∈ [0,1]
if score.sum() <= 1e-8:
    raw = equal_weight            # DEGENERATE_ACTION_FALLBACK（全 -1，无 NaN）
else:
    raw = score / score.sum()
```

- **可表达 0**：a=-1 → score=0 → raw weight=0（消除旧 softmax `w≳1.3%` 隐含下限）。
- 中性动作 a=0 → 等权；无指数放大；三算法同一 transform（算法中立）。
- 极端集中（one +1 / ten −1 → raw 100% 单资产）交由 Mandatory RiskOverlay 处理（post-risk ≤25%）。

## 2. Sparse / zero-weight tests

```text
test_action_zero_maps_equal_weight                PASS
test_action_minus_one_can_map_zero_weight         PASS（a=-1 → w=0）
test_action_single_positive_can_create_sparse_raw_weight  PASS（raw max=1.0）
test_action_all_minus_one_fallback                PASS（DEGENERATE_ACTION_FALLBACK，无 NaN）
test_action_transform_no_nan / _is_monotonic / _algorithm_neutral  PASS
```

## 3. Forced RiskOverlay integrated test

`test_forced_risk_overlay_in_environment_transition`：
`action=[1,-1,…]` → raw max≈**1.0** → post-risk max≤**0.25** → actual max≤0.27（执行/价格漂移容忍）。
证明 RiskOverlay 在真实 Environment transition 中被强制触发（非仅独立 property tests）。

## 4. Observation normalization V2（BLOCKER-B 关闭）

- obs 布局 `[8N per-asset][N weights][5 global]`；**只归一化 93 维外生特征**（88+5），
  末 N 维 actual weights 保持 **[0,1]** 原始含义（掩码见 `gym_wrapper._market_positions`）。
- **policy-independent**：scaler 直接从 train 有效外生特征矩阵 fit（`market_feature_frame`，
  warmup 之后行），不再用 EW trajectory（消除 Equal-Weight normalization prior）。

## 5. Policy-independent scaler proof

```text
fit 数据：train env 外生特征矩阵（warmup 后全部有效行，全 finite 断言通过）
eval：仅 transform，不更新统计（test_scaler_uses_train_dates_only_and_eval_not_updating）
未来数据变更不影响已冻结 scaler
保存/加载精确（test_scaler_save_load_exact）
```

## 6. Exact effective train/eval intervals（无重叠）

```yaml
raw_data_start:        2011-12-09
effective_obs_start:   2022-05-18   # 首个全 finite 观测（11 槽位共同有效起点）
train_range:           [2011-12-09, 2025-10-22]   # 半开 [start, eval_start)
eval_range:            [2025-10-23, 2026-08-07]   # [eval_start, end]
TrainEnd < EvalStart ✓（2025-10-22 < 2025-10-23）
```

## 7. Re-run one-seed sanity（V2；seed=42；12k 步/算法）

全部 stable：无 NaN、save/load deterministic 一致、三层权重对齐、无 >25% 步、
ChinaGrowth ≤0.5、现金残差 ~1.8-1.9%。主表见 §8。

## 8. Raw / Post-Risk / Actual diagnostics（held-out 199 步）

| 指标 | EW | TD3 | SAC | PPO |
|---|---:|---:|---:|---:|
| raw/post/actual max_mean | 0.091/0.091/0.092 | 0.152/0.152/0.152 | 0.129/0.129/0.128 | 0.104/0.104/0.103 |
| raw HHI | 0.091 | 0.131 | 0.100 | 0.092 |
| actual min_mean | 0.085 | 0.020 | 0.041 | 0.073 |
| raw_fraction_lt_1pct | 0.0 | 2.2% | 0.0 | 0.0 |
| raw_fraction_zero_or_eps | 0.0 | 0.0 | 0.0 | 0.0 |
| actual ChinaGrowth mean | 0.180 | 0.165 | 0.193 | 0.173 |
| actual cash residual | 1.94% | 1.72% | 1.83% | 1.89% |
| actual turnover | 0.012 | 0.125 | 0.070 | 0.025 |
| reward mean / std | 1.9e-4/9.1e-3 | 6.8e-5/8.8e-3 | 8.8e-5/1.1e-2 | 1.7e-4/9.0e-3 |
| NaN | 0 | 0 | 0 | 0 |

## 9. RiskOverlay intervention diagnostics

```text
overlay intervention rate        : 0.0（本轮 12k 步内 policy 未触顶；mean L1(raw,post)≈1e-16）
single_core cap hit rate         : 0.0
china_growth cap hit rate        : 0.0
```

说明：V2 动作域下 policy 权重温和，RiskOverlay 本轮为纯安全护栏（未替 RL 做配置）。
若 Gate 4 长跑中干预率显著升高，将按 Reviewer 要求再研究 action contract。

## 10. Gate 4 Track-B quantified common horizon

| Slot | Proxy | Launch Date（best-known，待验证） |
|---|---|---|
| CN_LARGE | 沪深300 | 2005-04-08 |
| CN_SMALL | 中证1000 | 2014-10-17 |
| CN_DIVIDEND | 中证红利低波 | 2013-12-16 |
| CHINEXT | 创业板指 | 2010-06-01 |
| **STAR** | 科创50 | **2020-07-22** |
| **HK_TECH** | 恒生科技 HSTECH | **2020-07-27** |
| HK_DIVIDEND | 恒生高股息率 | 2003-12-10 |
| US_BROAD | 标普500 | 1957-03-04 |
| GOLD | 上海金 Au99.99 | 2002-10-30 |
| CN_DURATION | 中债国债总财富 | ~2002（待验证） |
| CASH_LIKE | 中证短融 | ~2010（待验证） |

```text
TRACK_A_EFFECTIVE_START   = 2022-05-18（真实 ETF 共同有效，1069 交易日）
TRACK_B_COMMON_PIT_START  = 2020-07-27（STAR/HK_TECH 上市决定）
TRACK_B_AFTER_252_WARMUP  = 2021-07-22（1277 交易日）
TRACK_B_USABLE_DAYS       = 1277
TRACK_B 增量 vs A          = 208 交易日 ≈ 0.8 年
```

**结论（Reviewer §21 依据）**：Track B 只多 ~0.8 年，**不作为主实验**。
建议：Track A（真实 ETF OOS）主证据 + Track C（Scenario 长历史）机制/regime 研究 +
Option B1（11-slot PIT cross-check，独立标注）。

## 11. Carry-forward closure plan

```text
Track A 真实成本结论前必须关闭：C3（最坏 13.8bp 事件独立来源验证）、
                                F1（历史费率 PIT）、F2（港股通佣金）、H1（03110 派息交叉验证）
Track B 使用前关闭：C2（proxy PIT audit）
Gate 6 前关闭：C1（03110 same-day rule）
```

## 12. Exact pytest output

```text
collected 68 items
============================= 68 passed in 16.08s ==============================
```

## 13. Git commit

`3ed3733`

---

## END OF GATE 3 FINAL CORRECTIONS
