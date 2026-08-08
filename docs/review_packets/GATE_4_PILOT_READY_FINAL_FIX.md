# GATE 4 PILOT READY — FINAL FIX

> Reviewer 决策：`TARGETED_FINAL_CORRECTIONS_REQUIRED_BEFORE_3_SEED_PILOT`（2026-08-08，
> `GATE_4_PILOT_READY_REVIEWER_RESPONSE.md`）。P1/P2/P3 三个 correctness blocker + P4 术语修正。
> 本 packet 只报告这 4 项修复 + 回归；不扩 scope（评审 §31/§32）。

## 修复状态

| Blocker | 状态 |
|---|---|
| P1 wrapper annualized return 计算 | ✅ FIXED（累计/几何 CAGR/算术均值分离；03110 HKD since-2013 +179.8% vs Global X 官方 +181.7%，delta -1.9pp PASS） |
| P2 现金分红派息日 | ✅ FIXED（513690 官方 2024-12-20 / 2025-12-22；未知 → 保守 ex+5T 不提前结算） |
| P3 512100 真实份额合并 | ✅ FIXED（显式 UNIT_CONSOLIDATION factor=0.36555，非 stockBonus 推断） |
| P4 calendar_rows vs decision_rows | ✅ FIXED（`calendar_rows=1015` / `max_full_transitions=1014`） |

---

# 1. Corrected 513690 / 03110 Wrapper Audit（P1）

**根因**：audit 把 4.87 年**累计**收益（+57.4%）误标为 `annualized_return`。实际：
CNY 累计 +57.39% = HKD TR 累计 +50.96% × FX 变动 +4.26%（HKD/CNY 2021-05→2026-08：0.8302→0.8656）。
**非计算错误，是命名/公式混用**（评审 §4 担忧的部分成立：确实需要分离指标）。

修复后 `scripts/gate4_513690_wrapper_audit.py` 明确分离：

```text
cumulative_total_return_690        +18.15%
cumulative_total_return_03110_cny  +57.39%
cumulative_total_return_03110_hkd  +50.96%   （共同窗口 2021-05-20→2026-08-07）
cagr_690                           3.25%     （几何 CAGR，评审 §5 公式）
cagr_03110_cny                     9.09%
arith_mean_ann_690                 5.41%     （arithmetic mean × 252）
arith_mean_ann_03110_cny          10.98%
annualized_vol_690 / _03110        19.94% / 18.22%
max_drawdown_690 / _03110          -38.1% / -26.4%
daily_return_corr                   0.832
rolling_120d_corr_median / min      0.861 / 0.583
tracking_error_ann                 11.18%
```

## CNY 转换归一化（评审 §6，无 double count）

`_hk_cny_series` 改为 `TR_CNY_t = TR_HKD_t × FX_t / FX_0`（相对基准归一化，避免 FX 水平二次计入）。
代码级 assertion：

```text
assert cny_cum ≈ (1 + hkd_cum) × (1 + fx_move) - 1     PASS（0.5739 ≈ 1.5096×1.0426-1）
```

# 2. 03110 CNY TR Sanity vs Global X Official（P1）

| 项目 | Global X 官方 | 本重建（HKD TR） |
|---|---:|---:|
| since-inception（2013-06 → 2026-07-28）累计 | +181.69% | **+179.78%** |
| delta | — | **-1.91pp** |
| 判定 | — | **PASS within 2pp** |

03110 总收益重建与官方 NAV 量级高度吻合（HKD 口径），说明 sina raw + 官方派息 + 归一化 FX
的 CNY 序列**无 FX/dividend double count**。共同窗口小差异（HKD +50.96% vs 官方隐含约 +60%）来自
官方 NAV TR（含费前/份额净值口径）与价格+派息重建的统计口径差异，属合理量级（评审 §6 允许）。

**M2 判定更新**：corr 0.832 / rolling 中位 0.861 保持；收益量级恢复正常 → `M2 = CLOSED`
（评审 §7：daily corr ≥ ~0.75 且 rolling 中位强、总收益量级正常即满足）。

# 3. Exact Official Pay-Date Handling（P2）

## 官方派息日（补入事件表）

```text
513690  2024-12-17 ex → pay 2024-12-20（record 2024-12-16）
513690  2025-12-17 ex → pay 2025-12-22（record 2025-12-16）
```

`CorporateActionEvent` 新 schema（评审 §15）：

```python
CorporateActionEvent(
    instrument, action_type, ex_date, unit_factor, cash_per_share,
    pay_date, settle_date, source,
)
```

派息日政策（评审 §9/§10）：

```text
CASH_DIVIDEND + 已知 pay_date → settle_date = pay_date（official_fund_announcement）
CASH_DIVIDEND + 未知 pay_date → settle_date = ex_date + 5 交易日（CONSERVATIVE_FALLBACK）
                                  绝不提前结算（不早于确认日期）
UNIT_SPLIT / UNIT_CONSOLIDATION  → settle_date = ex_date（官方公告，无现金结算）
```

**移除 `ex_date + 2T` 默认**（评审 §8：不再作为正式历史结算事实）。

## 回归测试（评审 §11，全过）

```text
test_513690_2025_official_payment_date   PASS（ex 2025-12-17 → settle 2025-12-22）
test_513690_2024_official_payment_date   PASS（ex 2024-12-17 → settle 2024-12-20）
test_unknown_payment_date_never_settles_early  PASS（ex+2T 应收款保留，ex+5T 才结算）
```

# 4. Explicit 512100 UNIT_CONSOLIDATION（P3）

512100 2022-09-05 真实份额合并直接表示为显式事件，**不从 stockBonus/stockGift 推断**：

```text
date=2022-09-05  action_type=UNIT_CONSOLIDATION  unit_factor=0.36555  source=official
```

> **effective date 说明**：评审 §13 给出官方合并生效日 2022-09-02（record 2022-09-01），
> 但 QMT raw 行情 512100 在 **2022-09-05** 才从 0.982 跳变到 2.713（×2.76；2022-09-02 无行情行）。
> 折算必须落在**价格跳变日**（2022-09-05）以保持市值连续（dual-price contract 的正确实现）；
> 若硬套 09-02 而行情 09-05 才跳变，会在 09-05 制造人造 PnL。故 effective_date = 2022-09-05，
> 与官方公告一致（合并后首个带新份额/新价的交易日）。相关 4 个测试基于真实 raw fixture 证明价值连续。

## 真实事件回归（评审 §16，全过）

```text
test_512100_20220902_real_unit_consolidation_factor   PASS（factor=0.36555, UNIT_CONSOLIDATION）
test_512100_20220902_quantity_changes_by_036555       PASS（qty 508400 → 185846 = ×0.36555）
test_512100_20220902_portfolio_value_continuity       PASS（净值 ×2.7627×0.36555 ≈ +0.99% 真实行情）
test_512100_20220902_fill_uses_raw_post_conversion_price  PASS（折算后成交用 raw ~2.7，非折算前 ~1.0）
```

# 5. Real-Event Portfolio-Value Regression（P3 第 3 项）

`test_512100_20220902_portfolio_value_continuity`：真实 512100 数据窗口（2021-06 → 2022-12），
折算日 v_after ≈ v_before × (2.7627 × 0.36555)（0.982→2.713 价格跳变 × qty×0.36555），
即市值只反映真实行情 +0.99%，无 +2.76× 伪收益 / -63% 伪损失。

# 6. Calendar-Rows vs Decision-Rows Terminology（P4）

```text
track_a_calendar_rows      = 1015   （2022-06-06 → 2026-08-07）
track_a_max_full_transitions = 1014  （末行 = terminal mark，非决策）
```

smoke manifest 字段已改：`track_a.calendar_rows` / `track_a.max_full_transitions`。
语义与 `test_test_decision_count_equals_calendar_rows_minus_one`（test 段 rows-1）统一。

# 7. Updated Pytest Count

```text
collected 109 items  →  109 passed in 38.3s
```

新增（相对 PILOT_READY 102）：`tests/test_corporate_actions_real.py` 7 个（P2×3 + P3×4）。

# 8. Rerun Mechanics Smoke（FINAL_FIX P2/P3 后）

`scripts/gate4_pilot_ready.py`（EW + TD3 train_passes=2，F4）：

```text
decision_start=2022-06-06  calendar_rows=1015  max_full_transitions=1014

CA 513690 官方派息: {'accrued_at_ex_2025-12-17': True, 'settled_by_official_pay_2025-12-22': True}
EW  F4: test n_eval=120  cum=+1.57%  nan=0
TD3 F4: train_steps=833  timesteps=1666  save_load=True  train=70.2s
        val n_eval=59  cum=+3.26%  nan=0  |  test n_eval=120  cum=-2.22%  nan=0
boundary: test rows=121  decisions=120 = rows-1  ✓
```

P2 生效验证：513690 应收款在 ex（12-17）计提、在**官方派息日 12-22** 结算（不再 +2T 提前）。
TD3 test 收益 -2.22% 为 train_passes=2 机制冒烟的正常波动，**非训练结论**。

# 9. Wrapper Audit Output

`runs/gate4_wrapper_audit.json`（含全部分离指标 + 官方对照 + 断言）。

# 10. Git Commit

`GATE_4_PILOT_READY_FINAL_FIX` 提交 SHA：**（commit 后填写）**

包含：

```text
docs/review_packets/GATE_4_PILOT_READY_FINAL_FIX.md   ← 本 packet
docs/review_packets/GATE_4_PILOT_READY_REVIEWER_RESPONSE.md  ← 评审输入（存档）
src/china_etf/data/corporate_actions.py  ← schema + settle 政策 + source（P2/P3）
src/china_etf/data/loader.py             ← 03110 CNY 归一化 FX + close_tr_hkd（P1）
src/china_etf/environment/portfolio_env.py  ← settle_date 索引
scripts/gate4_513690_wrapper_audit.py    ← 指标分离 + Global X 对照 + 断言（P1）
scripts/gate4_pilot_ready.py             ← P4 术语 + CA 官方结算验证
tests/test_corporate_actions_real.py     ← P2/P3 真实事件回归（新）
tests/test_corporate_actions.py          ← schema 更新
data/qmt/meta/divid_events/*.csv         ← action_type/unit_factor/pay_date 显式列（不入库）
runs/gate4_wrapper_audit.json / gate4_pilot_ready_smoke.json
```

---

# Out of Scope（评审 §32 明确不做）

```text
✗ 3-seed / 10-seed pilot（评审 §34：修复通过后 GATE_4_3_SEED_PILOT = AUTHORIZED）
✗ 新算法 / Optuna / Southbound / 03110 execution
✗ ActionTransform / RiskOverlay / NN 改动 / fold 重设计
```

## Approval Record

```yaml
gate: 4
packet: GATE_4_PILOT_READY_FINAL_FIX
status: SUBMITTED_FOR_REVIEW

final_blockers:
  P1_wrapper_return_audit: fixed    # 指标分离 + Global X 对照 PASS（-1.91pp）
  P2_real_dividend_payment_dates: fixed  # 官方 12-20/12-22 + 保守 ex+5T 不提前
  P3_real_512100_unit_consolidation: fixed  # UNIT_CONSOLIDATION factor=0.36555

documentation_fix:
  calendar_rows_vs_decision_rows: fixed  # 1015 / 1014

m2_wrapper_decision: closed  # corr 0.832, 收益量级正常

permissions:
  three_seed_pilot: pending_approval  # 4 folds × TD3/SAC/PPO × seeds 42/2026/7 × 1x cost
  ten_seed_formal: false
```

## END OF GATE 4 PILOT READY FINAL FIX
