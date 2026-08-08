# GATE 4 EVAL FIX CORRECTIONS — REVIEWER RESPONSE

## Decision

```text
GATE_4_EVAL_FIX_CORRECTIONS = PASS
BENCHMARK_PARITY = PASS
FEATURE_SPEC_CORE_FORMULAS = PASS_WITH_PRE_ABLATION_CONDITIONS
GATE_4_10_SEED_FORMAL = NOT AUTHORIZED
FEATURE_ABLATION_RUNS = NOT YET AUTHORIZED
NEXT = GATE_4_FEATURE_ABLATION_PREP
```

Reviewed handoff:

```text
handoff_id = G4_EVAL_FIX_CORRECTIONS_001
packet      = docs/review_packets/GATE_4_EVAL_FIX_CORRECTIONS.md
code_commit = f2b7b4d4a7dcaadcc3174296521993b0366353c5
status      = READY_FOR_REVIEW
```

---

## 1. Overall conclusion

The targeted corrections requested in the prior review are materially closed.

Approved:

```text
B1 fold-local executable 510300 benchmark reset
B2 first-Test-day return included
B3 corporate-action ordering before same-day open purchase
independent benchmark return count / Test-date parity
no Validation-gap exposure
corr_pc1_share_60 uses correlation matrix
corr_change_20_60 uses corr20 - corr60
128-test regression suite reported PASS
no unnecessary 36-run retraining
```

The corrected benchmark now matches the walk-forward Test exposure semantics: each fold starts from cash, enters at test_start open, carries only through that fold's Test segment, and discards state before the next Validation gap.

Therefore:

```text
GATE_4_EVAL_FIX_CORRECTIONS = PASS
```

---

## 2. Benchmark review — PASS

The corrected `cn_large_buy_hold_stitched()` implementation satisfies the required fold-local contract:

```text
val_end boundary
  -> fresh 1,000,000 cash
  -> zero position / zero receivable
  -> test_start pre-open CA processing
  -> test_start open purchase
  -> test_start close first metric
  -> hold through this Test segment only
  -> discard state at fold end
```

The formal benchmark now independently generates:

```text
benchmark_stitched_steps = len(all_returns)
```

and compares against the strategy Test mask:

```text
strategy_stitched_steps = 475
benchmark_stitched_steps = 475
execution_dates == exact Test dates
```

This closes the previous 474-vs-475 and Validation-gap exposure errors.

The reported corrected reference:

```text
510300_EXECUTABLE_NET_STITCHED_BUY_HOLD
cum = +50.06%
n = 475
```

is now acceptable as the executable stitched comparison series. The old +35.30% continuous series is correctly retained only as:

```text
510300_CONTINUOUS_CALENDAR_REFERENCE
```

and must not be used as the formal stitched OOS comparator.

---

## 3. Benchmark cleanup required during next prep phase

Two small implementation cleanups remain, but neither reopens the benchmark Gate.

### 3.1 `exact_test_mask()` redundant benchmark count

`exact_test_mask()` still exposes:

```python
"strategy_stitched_steps": len(dates),
"benchmark_stitched_steps": len(dates),
```

The formal parity check is now correctly done later from independently generated benchmark returns, so this old duplicate field is only misleading legacy metadata.

During the next prep phase:

```text
remove benchmark_stitched_steps from exact_test_mask()
```

or rename it so it cannot be mistaken for an independently measured benchmark count.

### 3.2 Benchmark settlement should use `settle_date`

The main environment settles dividends from `CorporateActionEvent.settle_date`, whereas the benchmark helper currently keys settlement on `pay_date`.

For current buy-and-hold portfolio value this normally does not change equity because receivable is already included 1:1, but the accounting path should remain contract-identical.

During the next prep phase, change benchmark settlement lookup to:

```text
settle_date
```

not `pay_date`.

These are cleanup requirements, not blockers for this correction packet.

---

## 4. Feature formulas — main corrections PASS

The two prior definition drifts are correctly fixed:

### PC1 concentration

```text
corr_pc1_share_60
= lambda_1(Corr_60) / trace(Corr_60)
```

This is the desired correlation-concentration measure, not covariance PCA.

### Correlation regime change

```text
equity_bond_corr_change_20_60
= Corr20 - Corr60

equity_gold_corr_change_20_60
= Corr20 - Corr60
```

The sign convention is now frozen in the intended direction.

Other F1/F2 conventions are sufficiently explicit for implementation:

```text
US_BROAD = 513500.SH research series
USD/CNY rise = RMB depreciation = positive
CGB10Y stored as decimal yield
VIX uses previous completed US session
new features use train-only normalization
```

---

## 5. PRE-ABLATION CONDITION F-A1 — downside semivol definition

The current spec defines `equity_downside_semivol_60` as the standard deviation of the negative-return subset around the negative-subset mean.

That removes part of the downside-frequency information and is not the intended lower-partial-risk statistic.

Freeze the implementation instead as lower partial second moment around zero:

```text
x_i = min(r_i, 0)

downside_semivol_60
= sqrt(mean(x_i^2 over all 60 observations)) * sqrt(252)
```

Equivalently:

$$
\sigma^-_{60}=\sqrt{252\cdot\frac{1}{60}\sum_{i=1}^{60}\min(r_i,0)^2}
$$

This keeps both downside magnitude and downside frequency.

Do this before feature code is frozen.

---

## 6. PRE-ABLATION CONDITION F-A2 — missing-data contract must cover model input

The current spec says:

```text
train missing rows excluded from scaler fit
eval NaN -> train-fit mean
```

but it does not fully define what happens when a training observation itself contains a sporadic missing macro feature after warm-up.

The model observation contract must always be finite.

Freeze this rule:

```text
1. Fit each feature's imputation mean and scaler statistics from TRAIN ONLY.
2. Ignore NaN only when estimating those TRAIN statistics.
3. Before the model sees any TRAIN / VALIDATION / TEST observation:
      replace NaN with that feature's TRAIN mean.
4. Then normalize using TRAIN mean/std.
5. Therefore an imputed value maps to approximately normalized 0.
6. Never use Validation/Test statistics for imputation or scaling.
7. Never backward-fill or use future publication values.
```

This is simple, PIT-safe, and guarantees finite observations.

If a feature has no usable observations in a fold's TRAIN region, fail that feature/fold closed instead of fabricating a value.

---

## 7. Next authorized work

Authorize only:

```text
GATE_4_FEATURE_ABLATION_PREP
```

Scope:

```text
1. apply F-A1 downside-semivol formula correction
2. apply F-A2 train-only imputation contract
3. remove/rename misleading exact_test_mask benchmark count field
4. benchmark dividend settlement uses settle_date
5. implement F1/F2/F3 feature builders
6. implement strict PIT alignment tests
7. implement feature dimension assertions:
     F0 = 104
     F1 = 110
     F2 = 110
     F3 = 116
8. verify every observation finite after train-only imputation
9. verify train-only scaler/imputer isolation
10. produce a deterministic feature-construction smoke only
11. full pytest
12. submit GATE_4_FEATURE_ABLATION_PREP.md
13. STOP for review
```

Do not start the multi-fold feature ablation training yet.

---

## 8. Not authorized

```text
FEATURE_ABLATION_RUNS
GATE_4_10_SEED_FORMAL
OPTUNA
TEST_INFORMED_FEATURE_SELECTION
THEME_SLEEVE
QMT_LIVE
SOUTHBOUND_EXECUTION
```

Feature selection remains Validation-only once the actual ablation run is separately authorized.

---

## 9. Authorization record

```yaml
gate: 4
handoff_id: G4_EVAL_FIX_CORRECTIONS_001
packet: GATE_4_EVAL_FIX_CORRECTIONS
reviewed_code_commit: f2b7b4d4a7dcaadcc3174296521993b0366353c5

decision: APPROVED

passed:
  - B1_FOLD_LOCAL_BENCHMARK_RESET
  - B2_FIRST_DAY_TRANSITION_PARITY
  - B3_BENCHMARK_CA_ORDERING
  - EXACT_TEST_DATE_PARITY
  - NO_VALIDATION_GAP_EXPOSURE
  - FEATURE_PC1_CORRELATION_MATRIX
  - FEATURE_CORR_CHANGE_SIGN

pre_ablation_conditions:
  - F_A1_DOWNSIDE_SEMIVOL_LPM2
  - F_A2_TRAIN_ONLY_IMPUTATION_FOR_ALL_MODEL_OBSERVATIONS
  - CLEANUP_EXACT_TEST_MASK_REDUNDANT_BENCHMARK_COUNT
  - BENCHMARK_SETTLEMENT_USE_SETTLE_DATE

authorized_next:
  - GATE_4_FEATURE_ABLATION_PREP

forbidden_next:
  - FEATURE_ABLATION_RUNS
  - GATE_4_10_SEED_FORMAL
  - OPTUNA
  - TEST_INFORMED_FEATURE_SELECTION
  - THEME_SLEEVE
  - QMT_LIVE
  - SOUTHBOUND_EXECUTION
```

## END OF REVIEWER RESPONSE
