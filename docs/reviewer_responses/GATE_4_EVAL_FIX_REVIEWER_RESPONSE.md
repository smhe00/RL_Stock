# GATE 4 EVAL FIX — REVIEWER RESPONSE

## Decision

```text
GATE_4_EVAL_FIX = TARGETED_CORRECTIONS_REQUIRED
E1_SEGMENT_ACCOUNTING_RESET = PASS
E2_SEGMENT_COST_RECONCILIATION = PASS
E3_RISKOVERLAY_DIAGNOSTICS = PASS
BENCHMARK_PARITY = FAIL
FEATURE_SPEC_FREEZE = CORRECTIONS_REQUIRED
GATE_4_10_SEED_FORMAL = NOT AUTHORIZED
FEATURE_ABLATION_RUNS = NOT AUTHORIZED
NEXT = GATE_4_EVAL_FIX_CORRECTIONS
```

Reviewed handoff:

```text
handoff_id  = G4_EVAL_FIX_001
packet      = docs/review_packets/GATE_4_EVAL_FIX.md
code commit = dcb1287b10b1267c38f5f0678e2039b3139aeeec
status      = READY_FOR_REVIEW
```

---

# 1. Executive Review

Claude correctly closed the three original evaluation-path blockers:

- **E1**: Validation/Test accounting state now resets at the segment boundary while retaining full PIT feature history.
- **E2**: segment cost no longer absorbs pre-segment cumulative fees; cost reconciliation is explicitly asserted.
- **E3**: RiskOverlay diagnostics are now mathematically reconcilable and use the actual overlay caps.

The corrected runner is materially better and the 121-test suite is a useful regression barrier.

However, source review found a new formal blocker in `evaluation/benchmark.py`: the claimed executable 510300 benchmark does **not** yet share the same stitched Test exposure semantics as the RL/baseline walk-forward evaluation. In addition, the supposedly frozen Feature Ablation spec contains two definition drifts versus the preregistered reviewer definitions.

Therefore do **not** start feature-ablation runs or 10-seed formal training yet.

---

# 2. E1 — PASS

Current implementation is acceptable:

```text
Validation:
train_end close decision
→ val_start open first execution
→ accounting starts cash + zero positions

Test:
val_end close decision
→ test_start open first execution
→ accounting starts cash + zero positions
```

`portfolio_env.reset(at_date=...)` resets accounting/positions while preserving the precomputed feature history. `WalkForwardRunner._rollout_segment()` uses `train_end` for Validation and `val_end` for Test. `roll_out()` records by `st.t_next >= eval_start`, so the segment-start transition is included.

This closes the retroactive-policy-replay problem.

Carry-forward requirement: retain the E1 boundary tests permanently.

---

# 3. E2 — PASS

The original cost contamination is fixed.

Current implementation initializes:

```python
prev_fees = env.accounting.fees_paid
fees_at_segment_start = prev_fees
```

and asserts:

```text
sum(segment step costs)
==
fees_at_segment_end - fees_at_segment_start
```

The new diagnostics:

```text
actual_traded_notional
cost / traded_notional
cost / initial_equity
mean_turnover_l1
total_turnover_l1
```

are appropriate for formal reporting.

The prior PPO ~2.38% cost artifact was therefore a reporting/evaluation-path bug, not evidence of realistic segment trading cost.

One minor reporting note for formal Gate 4: `estimated_one_way_traded_fraction = L1 turnover / 2` does not capture the initial cash→portfolio deployment. Use `actual_traded_notional` as the authoritative cost denominator; keep turnover as a behavior metric rather than using it to reconstruct exact cash trading volume.

---

# 4. E3 — PASS

The prior packet inconsistency (`intervention_rate > 0` with `mean L1 ~ 1e-16`) is now protected by reconciliation logic.

Required formal fields are now present:

```text
raw_single_core_violation_rate
raw_china_growth_violation_rate
risk_overlay_intervention_rate
risk_overlay_mean_l1_raw_to_post
post_single_core_at_cap_rate
post_china_growth_at_cap_rate
post_constraint_violation_rate
```

The diagnostic thresholds use `env.risk_overlay.caps` and `growth_max` rather than duplicated hard-coded values. Keep this contract.

---

# 5. BLOCKER B1 — Executable 510300 benchmark is not Test-mask equivalent

`cn_large_buy_hold_net_return()` currently:

1. buys 510300 once on the first Test date;
2. keeps the position alive through the entire multi-fold horizon;
3. skips Validation dates only when recording/marking the returned series;
4. never resets the benchmark portfolio at the next fold boundary.

This is not equivalent to the strategy evaluation, where each fold Test starts from a fresh cash account at `val_end` and first trades at that fold's `test_start`.

### Why this matters

Suppose:

```text
F1 Test ends
→ F2 Validation gap
→ F2 Test starts
```

The current benchmark still owns 510300 during the Validation gap. When it next marks a Test date, the value change contains the entire skipped gap. The RL stitched series does not have that exposure; it resets the Test account for F2.

So `+35.30%` is not yet a valid net executable comparator to the stitched RL OOS evidence.

---

# 6. BLOCKER B2 — Benchmark return count is 474 while strategy Test transitions are 475

The packet reports:

```text
strategy_stitched_steps = 475
benchmark_stitched_steps = 475
```

but `cn_large_buy_hold_net_return()` only appends a return when `prev_v is not None`.

Therefore, with 475 Test execution dates, it produces:

```text
n_returns = 474
```

and omits the first Test-day transition from:

```text
initial cash
→ buy at test_start open
→ test_start close mark
```

The RL/Test runner includes that transition.

Also, `exact_test_mask()` currently sets both:

```text
strategy_stitched_steps
benchmark_stitched_steps
```

to `len(dates)` internally. That is not a real parity assertion; it is the same number assigned to two labels.

Formal parity must compare independently produced series lengths/dates.

---

# 7. BLOCKER B3 — First-date corporate-action ordering differs from the canonical environment

In `cn_large_buy_hold_net_return()` the initial buy is executed **before** the loop applies the first Test date's corporate actions.

That means if `test_start` is an ex-date, the benchmark can buy at the ex-date open and then accrue that day's dividend to the newly purchased position.

The canonical environment does the opposite:

```text
apply t_next corporate action based on pre-open holdings
→ plan/order
→ execute at t_next open
```

A position purchased at the ex-date open must not receive the dividend.

Even if no current 510300 fold starts exactly on an ex-date, the benchmark must share the canonical ordering contract.

---

# 8. Required benchmark fix

Replace the current continuous benchmark with a **fold-local executable benchmark**.

For each fold independently:

```text
reset account at val_end:
    initial cash
    zero positions
    zero receivables

at test_start:
    process corporate actions based on pre-open holdings (= zero)
    buy 510300 at test_start open
    charge 1x execution cost
    mark test_start close
    record FIRST return versus initial equity

then:
    hold through every date inside this fold Test segment only
    process all CA dates in chronological order
    mark every Test execution date

at fold end:
    discard state
    do not carry exposure into the next Validation gap
```

Then concatenate:

```text
F1 Test returns
+ F2 Test returns
+ F3 Test returns
+ F4 Test returns
```

Expected contract:

```text
benchmark_return_count == strategy_stitched_return_count == 475
benchmark_execution_dates == exact Test execution dates
no benchmark exposure during Validation gaps
```

Suggested label:

```text
510300_EXECUTABLE_NET_STITCHED_BUY_HOLD
```

You may keep a separate continuous-calendar 510300 buy-and-hold reference, but it must be explicitly labeled as a different reference and must not be compared as if it shared the stitched OOS exposure mask.

---

# 9. Required benchmark tests

Add at minimum:

```text
test_benchmark_return_count_equals_strategy_stitched_steps

test_benchmark_execution_dates_exactly_equal_test_mask

test_benchmark_resets_to_cash_each_fold

test_benchmark_has_no_validation_gap_exposure

test_benchmark_first_test_day_return_includes_open_to_close_and_cost

test_benchmark_exdate_open_purchase_does_not_receive_same_day_dividend

test_benchmark_corporate_actions_inside_test_are_processed_in_order
```

The parity assertion must consume independently generated strategy and benchmark dates/counts. Do not assign the same `len(mask)` value to both sides and call that parity.

---

# 10. Fallback pay-date sensitivity — ACCEPTED

The +3T/+5T/+7T sensitivity is sufficient for Gate 4.

Reported maximum impact:

```text
baseline stitched cumulative difference: 0.024 pp
representative RL evaluation: 0.00000
```

This satisfies the previously authorized alternative to manually resolving all seven OOS fallback payment dates.

Carry forward the sensitivity result and do not spend additional engineering effort on those payment dates unless a later live/accounting requirement makes exact settlement timing necessary.

---

# 11. Feature Spec Correction F1 — PC1 must use correlation matrix, not covariance matrix

The preregistered definition was:

```text
corr_pc1_share_60
= lambda_1(Corr_60) / sum_i lambda_i(Corr_60)
```

For an N-asset correlation matrix this is equivalently:

```text
lambda_1(Corr_60) / N
```

The current Claude spec says "60-day return covariance matrix first principal-component share". That is a materially different feature because covariance PC1 mixes volatility scale with correlation concentration.

Freeze the intended feature as **correlation-matrix PC1 share**.

---

# 12. Feature Spec Correction F2 — correlation-change sign is reversed

The preregistered convention was:

```text
corr_change_20_60 = corr_20 - corr_60
```

Therefore freeze:

```text
equity_bond_corr_change_20_60
= Corr20(CN_LARGE, CN_DURATION) - Corr60(CN_LARGE, CN_DURATION)

equity_gold_corr_change_20_60
= Corr20(CN_LARGE, GOLD) - Corr60(CN_LARGE, GOLD)
```

The current packet states `60-day correlation - 20-day correlation`, which reverses the sign and economic interpretation.

---

# 13. Feature Spec must freeze exact formulas before implementation

Before calling the feature spec frozen, add an explicit formula/anchor table for all 12 candidate features.

At minimum define:

```text
corr_pc1_share_60:
    Corr matrix over the 11 slot daily log returns, rolling 60D
    lambda1 / trace(Corr)

cn_us_corr_60:
    Corr60(CN_LARGE, US_BROAD)
    using the existing US_BROAD research series for F1

 equity_vol_ratio_20_60:
    ann_vol20(CN_LARGE) / (ann_vol60(CN_LARGE) + eps)

 equity_downside_semivol_60:
    exact downside-return definition + sqrt/annualization convention

 VIX features:
    exact as-of mapping to previous completed US session
    exact 252D percentile and 5D change formula

 USD/CNY:
    quote convention and return sign must be explicit

 CGB10Y:
    yield unit (decimal or percentage points) and Δ20 convention

 DR007:
    exact daily field and timestamp/as-of availability rule

 A-share turnover:
    exact universe, unit, and rolling z-score formula
```

Also define missing-data policy and train-only normalization policy. No silent forward filling across unavailable publication dates unless explicitly justified.

---

# 14. Note on existing global-feature naming

Existing `global_features()` contains a field named:

```text
equity_average_corr_60
```

but its current implementation averages pairwise correlations across all columns in the 11-slot universe, not equity-only pairs.

This is a pre-existing V1 naming/semantic issue and is **not a blocker for this targeted correction gate**. Do not silently change F0 now, because that would alter the baseline observation contract.

Record it as a future RFC/ablation note instead.

---

# 15. Required next packet

Generate:

```text
docs/review_packets/GATE_4_EVAL_FIX_CORRECTIONS.md
```

It should contain only:

```text
1. fold-local executable 510300 benchmark implementation
2. independent benchmark-vs-strategy date/count parity proof
3. first-day return proof
4. no Validation-gap exposure proof
5. benchmark CA-ordering proof
6. corrected 510300 stitched benchmark metrics
7. corrected/final FEATURE_ABLATION_SPEC formulas
8. full pytest
9. deterministic benchmark smoke / no 36-run retraining
10. git commit
```

Do **not** rerun the 36-run pilot.

---

# 16. Authorization Record

```yaml
gate: 4
handoff_id: G4_EVAL_FIX_001
reviewed_commit: dcb1287b10b1267c38f5f0678e2039b3139aeeec

decision: TARGETED_CORRECTIONS_REQUIRED

passed:
  E1_segment_accounting_reset: true
  E2_segment_cost_reconciliation: true
  E3_overlay_diagnostics: true
  fallback_paydate_sensitivity: true

not_passed:
  executable_benchmark_parity: true
  feature_spec_final_freeze: true

authorized_next:
  - GATE_4_EVAL_FIX_CORRECTIONS

not_authorized:
  - FEATURE_ABLATION_RUNS
  - GATE_4_10_SEED_FORMAL
  - OPTUNA
  - TEST_INFORMED_FEATURE_SELECTION
  - THEME_SLEEVE
  - QMT_LIVE
  - SOUTHBOUND_EXECUTION
```

## END OF REVIEWER RESPONSE
