# GATE 4 FEATURE ABLATION PREP CORRECTIONS — REVIEWER RESPONSE

## Decision

```text
GATE_4_FEATURE_ABLATION_PREP_CORRECTIONS = PASS
F2_NATIVE_CALENDAR_WINDOW_SEMANTICS       = PASS
VIX_PREVIOUS_COMPLETED_SESSION            = PASS_FOR_DATE_ONLY_CONTRACT
VIX_PERCENTILE_FORMULA                    = PASS
FEATURE_SPEC_CODE_SYNC                    = PASS
F0_PREPROCESSING_PARITY                   = PASS

10_SEED_FORMAL                            = REMOVED_FROM_ACTIVE_ROADMAP
RL_RETRAINING                             = FORBIDDEN
FEATURE_ABLATION_RUNS                     = DEFERRED
NEXT                                      = GATE_4_NON_RL_HORSE_RACE
```

Reviewed handoff:

```text
handoff_id = G4_FEATURE_ABLATION_PREP_CORRECTIONS_001
packet      = docs/review_packets/GATE_4_FEATURE_ABLATION_PREP_CORRECTIONS.md
code_commit = a273b63a9e8752a077bef1b446aacf6dcc1dc9cd
status      = READY_FOR_REVIEW
```

## 1. Overall conclusion

The five requested corrections P1-P5 are materially closed.

The implementation now computes F2 rolling/shift statistics on each source's native observation calendar before China-calendar PIT alignment, which fixes the prior US-session/China-trading-day semantic error.

The VIX path now uses strict previous-session alignment for date-only inputs, excluding same-calendar-date US close from a China EOD decision. The exact percentile formula is implemented as `(rank-1)/(N-1)` with average-rank ties. FEATURE_ABLATION_SPEC is synchronized with F-A1/F-A2/native-first/PIT contracts, and FeaturePreprocessor now uses `ddof=1` to preserve legacy F0 normalization semantics.

Reported regression suite:

```text
146 tests passed
no RL training
no ablation run
```

Therefore:

```text
GATE_4_FEATURE_ABLATION_PREP_CORRECTIONS = PASS
```

## 2. P1 — native-calendar-first F2: PASS

Reviewed implementation follows:

```text
native source observations
→ native rolling/shift calculation
→ derived native series
→ as-of alignment to China decisions
```

VIX uses native 5/252 US-session windows before alignment. USD/CNY, CGB10Y, DR007 and turnover likewise compute their 20/60-observation windows before China as-of alignment.

This closes the prior bug in which ffill to the China calendar could duplicate observations across market-holiday mismatches.

## 3. P2 — VIX causality: PASS for current date-only contract

The current production path for date-only VIX uses:

```text
source session date < China decision date
```

for `strict_prev_session`, so same-calendar-date US close is not visible at China EOD.

Tests cover same-date exclusion and market-holiday mismatch.

### Carry-forward before real F2 macro data is used in an experiment

The spec describes a preferred timezone-aware `available_at <= decision_at` contract. The current implementation does not yet expose a full timezone-aware China `decision_at` interface; the test uses naive datetime ordering as a conservative proxy.

This does **not** block the current Gate or the non-RL horse race because the horse race does not require F2 macro features.

Before any real F2 feature-ablation run, require:

```text
explicit timezone-aware available_at
explicit China decision_at
comparison in one normalized timezone
no tz-naive/tz-aware mixing
```

This is a FEATURE_DATA_READY carry-forward, not a current blocker.

## 4. P3 — VIX percentile: PASS

The implementation now uses:

```text
percentile = (rank - 1) / (N - 1)
N = 252
rank = 1-based average rank for ties
```

and calculates it on the VIX native US-session calendar before China alignment.

## 5. P4 — spec/code synchronization: PASS

`FEATURE_ABLATION_SPEC.md` now records the approved contracts:

```text
F-A1 downside semivol = zero-target LPM2
F-A2 train-only imputation for all model observations
F2 native-calendar-first
VIX strict previous completed session
VIX percentile = (rank-1)/(N-1)
FeaturePreprocessor ddof=1
```

This restores the spec as the canonical formula source.

## 6. P5 — F0 preprocessing parity: PASS

FeaturePreprocessor now uses sample standard deviation:

```text
ddof = 1
```

matching the legacy pandas F0 scaler behavior. The reported parity test verifies the new preprocessor does not silently change the original 93 exogenous F0 dimensions during ablation.

## 7. Roadmap override from user decision

The user explicitly decided that 10-seed expansion has poor exploration-stage cost/benefit and should be removed for now.

Therefore the next phase is **not** feature-ablation training and is **not** 10-seed RL.

The next authorized work is:

```text
GATE_4_NON_RL_HORSE_RACE
```

Use the previously published roadmap directive:

```text
docs/reviewer_responses/ROADMAP_NON_RL_BASELINE_COMPARISON_DIRECTIVE.md
```

Key rules:

```text
DO NOT retrain TD3/SAC/PPO
DO NOT run 10-seed
DO NOT run feature-ablation training yet
run deterministic/classical non-RL comparison on corrected evaluation path
reuse existing RL 3-seed outputs only as HISTORICAL_RL_PILOT_REFERENCE
```

## 8. Authorized next work

```text
GATE_4_NON_RL_HORSE_RACE
```

Required Tier-A methods are defined in the roadmap directive and include existing corrected-path deterministic baselines plus ERC, HRP, Maximum Diversification, Trend Risk Parity, Minimum CVaR 95%, and Shrinkage Mean-Variance.

All new non-RL methods must use the same Track-A universe, RiskOverlay, corporate-action accounting, t-close → t+1-open execution semantics, 1x transaction costs, fold-local Test resets and exact stitched Test mask.

## 9. Not authorized

```text
RL_RETRAINING
GATE_4_10_SEED_FORMAL
FEATURE_ABLATION_RUNS
OPTUNA
TEST_INFORMED_FEATURE_SELECTION
THEME_SLEEVE
QMT_LIVE
SOUTHBOUND_EXECUTION
```

## 10. Authorization record

```yaml
gate: 4
handoff_id: G4_FEATURE_ABLATION_PREP_CORRECTIONS_001
packet: GATE_4_FEATURE_ABLATION_PREP_CORRECTIONS
reviewed_code_commit: a273b63a9e8752a077bef1b446aacf6dcc1dc9cd

decision: APPROVED

passed:
  - P1_F2_NATIVE_CALENDAR_FIRST
  - P2_VIX_DATE_ONLY_PREVIOUS_COMPLETED_SESSION
  - P3_VIX_PERCENTILE_EXACT_FORMULA
  - P4_FEATURE_SPEC_CODE_SYNC
  - P5_F0_PREPROCESSING_PARITY

carry_forward_before_real_F2_ablation:
  - TIMEZONE_AWARE_AVAILABLE_AT_AND_DECISION_AT

authorized_next:
  - GATE_4_NON_RL_HORSE_RACE

forbidden_next:
  - RL_RETRAINING
  - GATE_4_10_SEED_FORMAL
  - FEATURE_ABLATION_RUNS
  - OPTUNA
  - TEST_INFORMED_FEATURE_SELECTION
  - THEME_SLEEVE
  - QMT_LIVE
  - SOUTHBOUND_EXECUTION
```

## END OF REVIEWER RESPONSE
