# GATE 4 FEATURE ABLATION PREP — REVIEWER RESPONSE

## Decision

```text
GATE_4_FEATURE_ABLATION_PREP = TARGETED_CORRECTIONS_REQUIRED
F1_INTERNAL_FEATURES = PASS
F_A1_DOWNSIDE_LPM2 = PASS
F_A2_TRAIN_ONLY_IMPUTATION_CORE = PASS
DIMENSION_CONTRACT = PASS
BENCHMARK_CLEANUP = PASS
F2_PIT_TIME_SEMANTICS = FAIL
FEATURE_SPEC_SYNC = FAIL
PREPROCESSING_PARITY = NEEDS_FIX
FEATURE_ABLATION_RUNS = NOT AUTHORIZED
GATE_4_10_SEED_FORMAL = NOT AUTHORIZED
NEXT = GATE_4_FEATURE_ABLATION_PREP_CORRECTIONS
```

Reviewed handoff:

```text
handoff_id = G4_FEATURE_ABLATION_PREP_001
packet      = docs/review_packets/GATE_4_FEATURE_ABLATION_PREP.md
code_commit = 7267cb797891685cb2d113cd16a1db66d6616d15
main merge  = 84152724e0b1bbee650184acfd8c812a801833eb
```

---

## 1. What passes

The following implementation work is materially correct and should be preserved:

```text
F1 corr_pc1_share_60 uses correlation matrix
F1 corr-change sign = corr20 - corr60
F-A1 downside semivol code = LPM2 around zero
F-A2 train-only imputation core logic
fail-closed when train feature has no usable observations
dimensions F0/F1/F2/F3 = 104/110/110/116
benchmark exact-mask cleanup
benchmark settlement switched to settle_date
138-test regression suite reported PASS
no unauthorized RL ablation training
```

The code-level F-A1 implementation is correct:

```text
sqrt(252 * mean(min(r,0)^2 over 60 observations))
```

and the preprocessor correctly uses TRAIN-only estimates for imputation and scaling.

---

# 2. BLOCKER P1 — F2 must compute on each source's native observation calendar before China alignment

Current implementation does:

```text
raw macro series
→ align/ffill to China trading calendar
→ rolling(252), pct_change(5), shift(20), zscore(60/20)
```

This violates the frozen rule:

```text
rolling window = last w AVAILABLE observations
```

and is especially wrong for VIX:

```text
5  = 5 completed US sessions
252 = 252 completed US sessions
```

not 5/252 China trading days.

China and US holiday calendars differ. Aligning first can duplicate stale VIX values on China-only trading days or skip US-only sessions, changing both the percentile and 5-session change.

### Required architecture

For every F2 source:

```text
native source observations
→ compute native-calendar derived feature
→ attach/retain availability timestamp
→ PIT as-of align DERIVED feature to China decision timestamp
```

Examples:

```text
VIX:
US session closes
→ compute 252-US-session percentile and 5-US-session change
→ align latest already-completed result to China EOD decision

USD/CNY:
source-native observations
→ 20-observation return
→ PIT align

CGB10Y:
source-native observations
→ 20-observation level change
→ PIT align

DR007:
source-native observations
→ 60-observation zscore
→ PIT align

A-share turnover:
source-native observations
→ 20-observation zscore
→ PIT align
```

Do not calculate rolling/shift windows on a forward-filled China-calendar copy.

---

# 3. BLOCKER P2 — VIX previous-completed-session semantics are not enforced

The frozen contract says:

```text
China EOD decision on date T
may only use the previous completed US session
```

Current `align_pit()` accepts any macro point indexed `<= T`.

If VIX input is indexed only by US session DATE, a value labelled date T could be selected for China T close even though the US T session has not occurred yet.

Therefore `date <= T` is insufficient for VIX.

### Required safe contract

Preferred:

```text
each macro observation carries available_at timestamp with timezone
China decision has decision_at timestamp
as-of join requires available_at <= decision_at
```

Minimum acceptable for date-only VIX:

```text
US session date < China decision calendar date
```

not `<=`.

Tests must include:

```text
same-calendar-date China close cannot see US same-date VIX close
US holiday / China open day
China holiday / US open day
weekend boundary
at least one DST-season date
```

The core rule is causality by availability time, not merely matching date labels.

---

# 4. BLOCKER P3 — VIX percentile formula does not match frozen spec

Frozen spec:

```text
pct = (rank - 1) / (252 - 1)
```

Current implementation:

```python
vix.rolling(252).rank(pct=True)
```

which uses `rank / N` semantics.

These are not identical.

Implement the frozen formula exactly, with an explicit tie convention. Recommended:

```text
rank = average rank among ties, 1-based
percentile = (rank - 1) / (N - 1)
```

and add a deterministic hand-computed unit test including ties.

---

# 5. BLOCKER P4 — FEATURE_ABLATION_SPEC.md is stale and contradicts code

The packet says F-A1/F-A2 were written into the frozen spec, but both `7267cb7` and current merged main still contain the older text:

```text
downside semivol = negative-subset standard deviation
train missing rows excluded / eval mean fill
```

while code now implements:

```text
LPM2 around zero
TRAIN-derived imputation for every model observation
```

This creates a source-of-truth split between code and frozen methodology.

Required:

```text
update docs/features/FEATURE_ABLATION_SPEC.md
```

to the already-approved F-A1/F-A2 definitions, plus the corrected native-calendar / availability-time F2 contract from this review.

The spec must be the canonical formula source before any ablation run.

---

# 6. PREPROCESSING PARITY P5 — do not silently change F0 normalization

Existing Gate-4 F0 scaler uses pandas:

```python
valid.std()
```

which is sample standard deviation (`ddof=1`).

New `FeaturePreprocessor` currently uses NumPy:

```python
valid.std()
```

which defaults to population standard deviation (`ddof=0`).

If the ablation runner switches the whole 93+ feature block to the new preprocessor, the original F0 observations change even before any new feature is added. That contaminates the ablation.

### Required

Use preprocessing semantics that preserve the current F0 baseline exactly.

Preferred:

```text
FeaturePreprocessor std uses ddof=1
```

for parity with legacy F0 scaling, with constant-feature protection retained.

Add:

```text
test_f0_preprocessor_matches_legacy_scaler
```

On a fully-finite F0 TRAIN region:

```text
legacy normalized F0
≈
FeaturePreprocessor normalized F0
```

within tight numerical tolerance.

The ablation must compare:

```text
same F0 transform + extra features
```

not a changed preprocessing pipeline plus extra features.

---

# 7. Required correction tests

At minimum add:

```text
test_vix_same_date_us_close_not_visible_to_china_close

test_vix_rolling_5_uses_five_us_sessions_not_five_china_days

test_vix_percentile_252_uses_native_us_sessions

test_vix_percentile_exact_rank_formula_with_ties

test_f2_native_calendar_then_asof_alignment

test_f2_holiday_calendar_mismatch_does_not_duplicate_window_observations

test_macro_available_at_timestamp_controls_visibility

test_f0_preprocessor_matches_legacy_scaler

test_feature_spec_contract_matches_implemented_fa1_fa2
```

The final test may be implemented as explicit formula/contract assertions rather than parsing prose, but code and spec must not disagree.

---

# 8. Real macro data remains a separate readiness gate

This packet deliberately used synthetic macro data. That is acceptable for prep.

After the above corrections pass, the next methodological step should be real-data readiness before RL ablation training:

```text
GATE_4_FEATURE_DATA_READY
```

It should freeze, for each source:

```text
provider/source
raw field
units
native calendar
release/availability timestamp semantics
timezone
missing-day policy
local snapshot/hash
coverage per fold
PIT audit
```

Do not run multi-fold RL ablation against synthetic macro data.

---

# 9. Required next packet

Generate:

```text
docs/review_packets/GATE_4_FEATURE_ABLATION_PREP_CORRECTIONS.md
```

Include:

```text
1. native-calendar-first F2 implementation
2. explicit availability-time PIT contract
3. VIX previous-completed-session proof
4. exact VIX percentile formula + tie convention
5. holiday/DST causality tests
6. FEATURE_ABLATION_SPEC synchronized with code
7. F0 legacy preprocessing parity
8. corrected deterministic feature smoke
9. full pytest
10. exact git commit SHA
```

No RL training is needed for this correction packet.

---

# 10. Authorization record

```yaml
gate: 4
handoff_id: G4_FEATURE_ABLATION_PREP_001
packet: GATE_4_FEATURE_ABLATION_PREP
reviewed_code_commit: 7267cb797891685cb2d113cd16a1db66d6616d15
reviewed_main_commit: 84152724e0b1bbee650184acfd8c812a801833eb

decision: TARGETED_CORRECTIONS_REQUIRED

passed:
  - F1_INTERNAL_FEATURE_FORMULAS
  - F_A1_LPM2_CODE
  - F_A2_TRAIN_ONLY_IMPUTATION_CORE
  - FEATURE_DIMENSIONS
  - BENCHMARK_MASK_CLEANUP
  - BENCHMARK_SETTLE_DATE

blocked:
  - F2_NATIVE_CALENDAR_WINDOW_SEMANTICS
  - VIX_PREVIOUS_COMPLETED_US_SESSION_CAUSALITY
  - VIX_PERCENTILE_EXACT_FORMULA
  - FEATURE_SPEC_CODE_SYNC
  - F0_PREPROCESSING_PARITY

authorized_next:
  - GATE_4_FEATURE_ABLATION_PREP_CORRECTIONS

forbidden_next:
  - FEATURE_ABLATION_RUNS
  - GATE_4_FEATURE_DATA_READY
  - GATE_4_10_SEED_FORMAL
  - OPTUNA
  - TEST_INFORMED_FEATURE_SELECTION
  - THEME_SLEEVE
  - QMT_LIVE
  - SOUTHBOUND_EXECUTION
```

## END OF REVIEWER RESPONSE
