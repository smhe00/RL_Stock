# GATE 4 EVAL FIX — CORRECTIONS

> Reviewer（`GATE_4_EVAL_FIX_REVIEWER_RESPONSE.md`）：E1/E2/E3 PASS，fallback sensitivity ACCEPTED；
> **BENCHMARK_PARITY FAIL**（B1/B2/B3）+ FEATURE_SPEC 两处定义漂移 → `NEXT = GATE_4_EVAL_FIX_CORRECTIONS`。
> 本 packet 只含评审 §15 十项；**不重跑 36-run pilot**。handoff_id = **G4_EVAL_FIX_CORRECTIONS_001**。

---

# 1. Fold-Local Executable 510300 Benchmark Implementation（B1/B2/B3）

`evaluation/benchmark.py` 重写：

- **`cn_large_buy_hold_stitched(raw_open, raw_close, events, folds, ...)`**：正式 stitched 对比用，
  每 fold 独立：
  ```text
  在 val_end 重置：初始现金 1,000,000 + 零持仓 + 零应收款（B1：不跨 fold carry）
  test_start：先 apply CA（基于开盘前零持仓）→ open 全仓买入 510300 + 1x 成本 → mark close
  记录首日 transition（open→close 对 initial equity，含成本）（B2）
  段内逐 test 执行日：CA（settle→折算→计提，基于开盘前持仓）→ mark close
  段末丢弃状态，不进入下一 fold 的 val gap
  拼接 F1→F4 → 510300_EXECUTABLE_NET_STITCHED_BUY_HOLD
  ```
- `cn_large_buy_hold_net_return` 保留为**连续日历参考**（label `510300_CONTINUOUS_CALENDAR_REFERENCE`），
  明确标注**不等价 stitched mask**，不得作正式对比。

# 2. Independent Benchmark-vs-Strategy Date/Count Parity Proof

```text
strategy_stitched_steps（exact_test_mask 独立计算）= 475
benchmark_stitched_steps（fold-local 拼接独立生成） = 475
execution_dates == exact Test 执行日期（逐日期比对，测试证明）
parity_assert = True（独立计数相等，非同一 len 赋值）
```

`exact_test_mask` 内部不再把同一 `len(dates)` 赋给两个标签；strategy 步数由 mask 独立给出，
benchmark 步数由 fold-local 拼接独立产生，测试 `test_benchmark_return_count_equals_strategy_stitched_steps`
比对两个独立来源。

# 3. First-Day Return Proof

`test_benchmark_first_test_day_return_includes_open_to_close_and_cost`：
构造 test_start 日 open=10→close=11（+10%），断言首日 net 收益 ≈ 9.6%（10% − ~3.5bp 成本），
且 `n_returns == 段执行日数`（含首日 transition，修复 B2 的 474 vs 475）。

# 4. No Validation-Gap Exposure Proof

`test_benchmark_has_no_validation_gap_exposure`：每 fold 首日收益独立于前一 fold 结束状态
（都从 1e6 现金开始），gap 期间无 510300 暴露（B1 修复）。

# 5. Benchmark CA-Ordering Proof

`test_benchmark_exdate_open_purchase_does_not_receive_same_day_dividend`：ex-date 当日 open 买入
不享该日分红（CA 基于开盘前零持仓）；对照已持跨 ex 应享分红。
`test_benchmark_corporate_actions_inside_test_are_processed_in_order`：段内 CA 按 settle→折算→计提→execute
顺序，应收款→现金无跳变，分红收益量级正确（B3 修复）。

# 6. Corrected 510300 Stitched Benchmark Metrics

smoke 实测（fold-local，1x cost + CA + 475 执行日）：

```text
510300_EXECUTABLE_NET_STITCHED_BUY_HOLD: cum = +50.06%  n = 475 = strategy 475  parity = True
```

对照：旧连续版（跨 gap carry、474 返回）`510300_CONTINUOUS_CALENDAR_REFERENCE: +35.30%`——
两者口径不同（fold-local 每折重新满仓、计入首日 transition），正式对比**只用 fold-local stitched**。

# 7. Corrected / Final FEATURE_ABLATION_SPEC Formulas

`docs/features/FEATURE_ABLATION_SPEC.md` 修正（评审 §11/§12/§13）：

```text
F1 修正：
  corr_pc1_share_60 = λ1(Corr_60) / trace(Corr_60)   # 相关矩阵 PC1，非协方差（评审 §11）
  equity_bond_corr_change_20_60 = Corr20(CN_LARGE,CN_DURATION) - Corr60(...)  # 符号反转（评审 §12）
  equity_gold_corr_change_20_60 = Corr20(CN_LARGE,GOLD) - Corr60(...)         # 符号反转

新增精确公式表（评审 §13）：
  全部 12 特征（F1×6 + F2×6）冻结：exact formula / as-of / 单位 / 符号 convention
  F2：usdcny 直接标价（升=人民币贬值）；cgb10y 存小数、Δ 用百分点；VIX 用前一完成 US session
  missing-data：train 段缺失行排除 scaler fit；eval 段 NaN 用 train-fit 均值填充（非静默 ffill 未来）
  normalization：纳入现有 train-only scaler
F0 `equity_average_corr_60` 命名问题：评审 §14 记录为 RFC/ablation note，本轮不改 F0。
```

# 8. Full Pytest

```text
collected 128 items  →  128 passed（新增 7 个 benchmark parity/CA 测试；含修正后的 first-day/ex-date）
```

# 9. Deterministic Benchmark Smoke / No 36-Run Retraining

`scripts/gate4_eval_fix.py`（F1 3 algos 低 passes + fold-local benchmark；**未重跑 36**）：

```text
test-mask steps=475  first=2023-11-24  last=2026-08-07  excluded_val=240
510300_EXECUTABLE_NET_STITCHED_BUY_HOLD: cum=+50.06%  n=475  parity=True
TD3  cum=-1.0%  SAC +4.1%  PPO +4.0%（低 passes 机制冒烟；E1/E2/E3 assert 通过）
```

# 10. Git Commit

`GATE_4_EVAL_FIX_CORRECTIONS` 提交 SHA：**（commit 后填写）**

```text
src/china_etf/evaluation/benchmark.py   ← fold-local stitched buy-hold + 连续参考分离
tests/test_eval_fix.py                  ← +7 benchmark 测试（parity/first-day/gap/CA ordering）
scripts/gate4_eval_fix.py               ← smoke 用 fold-local benchmark
docs/features/FEATURE_ABLATION_SPEC.md  ← corr_pc1 相关矩阵 + 符号修正 + 精确公式表
docs/review_packets/GATE_4_EVAL_FIX_CORRECTIONS.md  ← 本 packet
docs/agent_state/CLAUDE_STATUS.yaml     ← 协议状态
```

---

## Approval Record

```yaml
gate: 4
handoff_id: G4_EVAL_FIX_CORRECTIONS_001
packet: GATE_4_EVAL_FIX_CORRECTIONS
status: READY_FOR_REVIEW

closed:
  B1_fold_local_benchmark_reset: true
  B2_first_day_transition_and_parity: true   # n=475==475, dates 精确相等
  B3_benchmark_ca_ordering: true             # ex-date open 买入不享当日分红
  feature_spec_formula_freeze: true          # corr_pc1 相关矩阵 + corr20-corr60 + 12 公式表

not_rerun:
  36_run_pilot: false

authorized_next: GATE_4_EVAL_FIX_CORRECTIONS → review → 10-seed formal（仍 not authorized）
```

## END OF GATE 4 EVAL FIX CORRECTIONS
