# GATE 4 FEATURE ABLATION PREP — CORRECTIONS

> Reviewer（`GATE_4_FEATURE_ABLATION_PREP_REVIEWER_RESPONSE.md`）：`TARGETED_CORRECTIONS_REQUIRED`，
> 5 个 blocker（P1-P5）→ `NEXT = GATE_4_FEATURE_ABLATION_PREP_CORRECTIONS`。本 packet 按评审 §9 十项；
> **不跑 RL / ablation**。handoff_id = **G4_FEATURE_ABLATION_PREP_CORRECTIONS_001**。

---

# 1. Native-Calendar-First F2 Implementation（P1）

`ablation_features.f2_features` 重构：每个 F2 源在**原生观测日历**上算窗口特征，再 PIT as-of 对齐 China。

```text
流程（每源）:
  native 源 Series（index = 源观测日）
  → 在 native index 上算窗口（rolling/shift 用源观测计数）
  → native 衍生 Series
  → align_derived_to_china(derived_native, china_index, rule)

align_derived_to_china rule:
  "asof"               → 每 China 决策日 t 取 ≤t 最新已发布值（USD/CNY、CGB10Y、DR007、成交额）
  "strict_prev_session" → 每 China 决策日 t 取 < t 最新值（VIX，前一完成 US session）
```

修复前 bug：先 ffill 到 China 再 rolling → VIX 5/252 变成 China 日而非 US session。
`test_f2_native_calendar_then_asof_alignment` / `test_f2_holiday_calendar_mismatch_does_not_duplicate_window_observations`
（7/4 缺失不改窗口计数）验证。

# 2. Explicit Availability-Time PIT Contract（P2）

```text
首选：每 macro 观测带 available_at 时间戳（timezone-aware）；China 决策有 decision_at；
      as-of 要求 available_at <= decision_at。
date-only 最低：US session date < China 决策日历日期（严格早于，非 <=）。
same-calendar-date US close 对 China close 不可见。
```

测试：
`test_macro_available_at_timestamp_controls_visibility`（vix 带 16:00 US close 时间戳 → China 同日不可见）
`test_vix_same_date_us_close_not_visible_to_china_close`（date-only 999 泄漏检测）。

# 3. VIX Previous-Completed-Session Proof（P2）

`align_derived_to_china(rule="strict_prev_session")` 强制 `< t`；VIX 用前一完成 US session。
`test_vix_same_date_us_close_not_visible_to_china_close` PASS。

# 4. Exact VIX Percentile Formula + Tie Convention（P3）

```text
pct = (rank - 1) / (N - 1)，N=252
rank = 1-based average rank（ties 取平均）
```

`_vix_percentile_native(vix, 252)` 自定义实现（替代 `rolling(252).rank(pct=True)` 的 rank/N 语义）。
`test_vix_percentile_exact_rank_formula_with_ties`（含 tie 手工断言：`[1,2,2]` → (2.5-1)/2=0.75）。

# 5. Holiday / DST Causality Tests（P2）

```text
test_vix_same_date_us_close_not_visible_to_china_close
test_f2_holiday_calendar_mismatch_does_not_duplicate_window_observations  # 7/4 缺 native 观测不复制
test_macro_available_at_timestamp_controls_visibility                     # DST/时区时间戳
```

# 6. FEATURE_ABLATION_SPEC Synchronized with Code（P4）

`docs/features/FEATURE_ABLATION_SPEC.md` 更新为 canonical formula source：
F-A1 LPM2 around zero；F-A2 train-only imputation 覆盖所有模型观测（含 fail-closed）；
F2 **native-calendar-first** + availability-time 契约 + VIX strict_prev_session；
VIX 分位 (rank-1)/(N-1)；FeaturePreprocessor **ddof=1**（F0 legacy parity）。
`test_feature_spec_contract_matches_implemented_fa1_fa2`（ascii token 断言 LPM2/imput/native/strict_prev/rank-1/ddof）。

# 7. F0 Legacy Preprocessing Parity（P5）

`FeaturePreprocessor.fit_train` std 改 **ddof=1**（sample std），与 legacy pandas `valid.std()` 一致，
保证 ablation 同 F0 transform + 额外特征（不改变基线）。
`test_f0_preprocessor_matches_legacy_scaler`：全 finite F0 train 区，preprocessor 归一化
≈ legacy pandas 归一化（atol 1e-8）。

# 8. Corrected Deterministic Feature Smoke

`scripts/gate4_ablation_prep.py`（native-first synthetic macro：VIX 用 US 日历剔除 7/4）：

```text
F0: exog=93 obs=104 OK   F1: 99/110 OK   F2: 99/110 OK   F3: 105/116 OK
F-A2: train_rows=507 val_rows=508  finite_train=True finite_val=True imputed_approx_zero=True
```

# 9. Full Pytest

```text
collected 146 items  →  146 passed（新增 8 个：P1 native×2、P2 因果×2、P3 tie、P5 parity、spec 契约、holiday）
```

# 10. Git Commit

`GATE_4_FEATURE_ABLATION_PREP_CORRECTIONS` 提交 SHA：**`a273b63`**

```text
src/china_etf/features/ablation_features.py  ← native-first F2 + align_derived_to_china + VIX 分位
src/china_etf/features/preprocessor.py       ← ddof=1（P5）
docs/features/FEATURE_ABLATION_SPEC.md       ← spec 同步（P4）
tests/test_ablation_features.py              ← +8 测试（P1/P2/P3/P5/spec 契约）
scripts/gate4_ablation_prep.py               ← native-first macro smoke
docs/review_packets/GATE_4_FEATURE_ABLATION_PREP_CORRECTIONS.md  ← 本 packet
docs/agent_state/CLAUDE_STATUS.yaml          ← 协议状态
```

---

## Approval Record

```yaml
gate: 4
handoff_id: G4_FEATURE_ABLATION_PREP_CORRECTIONS_001
packet: GATE_4_FEATURE_ABLATION_PREP_CORRECTIONS
status: READY_FOR_REVIEW

closed:
  P1_f2_native_calendar_first: true
  P2_vix_previous_completed_session_causality: true
  P3_vix_percentile_exact_formula: true      # (rank-1)/(N-1), ties average rank
  P4_feature_spec_code_sync: true            # spec = canonical formula source
  P5_f0_preprocessing_parity: true           # ddof=1, legacy parity test

not_authorized:
  feature_ablation_runs: false
  gate_4_feature_data_ready: false           # 真实宏观数据是独立门
  ten_seed_formal: false
```

## END OF GATE 4 FEATURE ABLATION PREP CORRECTIONS
