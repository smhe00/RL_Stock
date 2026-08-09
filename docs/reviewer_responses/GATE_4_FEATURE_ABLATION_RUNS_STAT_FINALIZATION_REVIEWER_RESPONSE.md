# Reviewer Response — GATE 4 FEATURE ABLATION RUNS STAT FINALIZATION

```yaml
handoff_id: G4_FEATURE_ABLATION_RUNS_STAT_FINALIZATION_001
reviewed_code_commit: 6dd8b344564ca0cca1559c3ecf45840ee16d47f6
reviewed_packet_commit: d93891e8a68c107cf045b32931e59d0de79d3c10
reviewed_packet: docs/review_packets/GATE_4_FEATURE_ABLATION_RUNS_STAT_FINALIZATION.md
decision: TARGETED_TRANSITION_AND_RESAMPLING_CORRECTIONS_REQUIRED
reviewer_state: REVISIONS_REQUIRED
```

## Summary

B4 and B5 are materially closed: `p_bs` has been removed from the descriptive bootstrap helper, and the residualization is now correctly labeled as a `reduced_F0_market_proxy` rather than the full 104-dimensional F0 observation state. The attempt to globally quarantine the frozen Test panel and replace median-p inference is also directionally correct.

However, the current packet still does **not** establish a genuinely Test-transition-free or fully dependence-aware confirmatory diagnostic. The remaining issues are narrow but substantive. No RL retraining, 10-seed, Optuna, F2/F3 expansion, or feature-set change is authorized.

## Passed / accepted

- **B4 bootstrap null-p removal — PASS.** `block_bootstrap_ci()` is now descriptive only and no longer emits `p_bs`.
- **B5 reduced-F0 labeling — PASS.** The implementation and packet explicitly state that the 10 predictors are a reduced market proxy, not the full F0 contract, and the conclusion is narrowed accordingly.
- **No synthetic aggregate CI claim — PARTIAL PASS.** Fold-specific intervals are retained rather than presenting median endpoints as an aggregate 95% CI.
- **No RL retraining / no 10-seed / no sweep / frozen F1 candidates unchanged — PASS.** Scope discipline was respected.

## Blocking corrections

### C1 — Global Test exclusion is shifted by one transition at every fold boundary

The frozen Test metric is an **execution-date** transition series. `WalkForwardRunner._rollout_segment()` explicitly defines:

```text
Test: decision at val_end close -> first execution at test_start open -> first metric date test_start
```

Therefore, for a Test execution date `e`, the feature/outcome decision date used by this diagnostic is the immediately preceding research-calendar date `d`, because the diagnostic outcome is `t -> t+1`.

The current script instead builds:

```python
global_test.update(adj.index[(adj.index >= f.test_start) & (adj.index <= f.test_end)])
screen = decision_days - global_test
```

This removes the **execution dates themselves**, not their corresponding decision dates. Consequently, each fold's `val_end` remains in `screen`, and its `mfwd[val_end]` is exactly the forward return into `test_start` — the first frozen Test transition. Conversely, each `test_end` is removed even though it is a terminal mark/non-decision date.

With four folds, the current 540-day panel can therefore still contain up to four frozen Test transitions.

Required fix:

1. construct the exact frozen 475 Test **execution-date** mask using the same canonical path used by evaluation;
2. map those 475 execution dates to their immediately preceding `adj.index` decision dates (the existing `decision_dates()` helper is suitable if fed the exact execution mask);
3. exclude that mapped decision-date union from every screening, bootstrap/permutation, and residualization fit/apply dataset;
4. add an assertion/test that no `t -> t+1` outcome in the diagnostic has `t+1` in the frozen Test execution mask.

The invariant should be transition-based, not same-date based.

### C2 — The current `block_permutation_p` is not actually a block permutation

`block_permutation_p()` calls `_moving_block_indices()`, which samples overlapping block starts **with replacement** and concatenates those sampled blocks. That is a moving-block bootstrap/resample of `y`, not a permutation of the observed blocks.

The packet currently describes the result as a `block-shuffle permutation` and then calls the resulting p-values valid dependence-aware p-values. That claim is too strong for the implementation as written.

Required fix — use one clearly specified null mechanism, for example:

- a segment-aware circular-shift/random-lag test that preserves each series' within-segment dependence while breaking contemporaneous alignment; or
- a genuine contiguous-block permutation without replacement within each admissible segment; or
- another justified dependence-aware null resampler, but label it accurately and document the null hypothesis.

For a symmetric zero-centered statistic such as Spearman, prefer an empirical two-sided Monte-Carlo p-value of the form

```text
p = (1 + count(|T_null| >= |T_obs|)) / (B + 1)
```

or justify an alternative. In all cases clamp p to `[0,1]`; the current doubled-tail implementation can in principle exceed 1 near the null center.

### C3 — Resampling is not segment-aware after removing Test blocks

After Test dates are removed, `screen` is converted to a compact sorted array. `_moving_block_indices()` then treats adjacent array positions as consecutive observations even when the original calendar contains a removed Test interval between them.

Thus a bootstrap/permutation block can cross an excluded Test gap and splice together observations that were not temporally adjacent in the source process. The same issue can occur in the fold-specific panels after subtracting `global_test`.

This does not satisfy the previously requested **segment-aware** dependence treatment.

Required fix:

- identify contiguous admissible development/validation segments using the original `adj.index` adjacency;
- resample/shift/permutate only within those segments;
- never let a block cross a quarantined Test interval or another removed gap;
- record segment boundaries/counts in the artifact and add a unit test for no cross-gap block construction.

### C4 — The four fold CIs are not independent

The packet calls the vol-ratio intervals "4 个独立 CI". The walk-forward training/development panels are expanding and nested, so these intervals are fold-specific but **not independent**.

Required fix:

- relabel them as four fold-specific/nested-panel descriptive CIs;
- do not use independence language or combine them as if they were independent studies.

The block-length endpoint table may remain as a descriptive sensitivity summary, provided it is not labeled an aggregate CI.

### C5 — Dependence sensitivity should cover the inferential p-value, not only the descriptive CI

The final p-value currently uses only `block_len=20`, while the F1 set contains 60-session rolling features. The packet does CI sensitivity at 20/40/60, but the family-wise inference itself is still tied to the 20-block null resampler.

Required fix:

- either freeze a justified primary dependence scale (60 is the conservative obvious candidate here) before rerunning and use that for confirmatory p-values; or
- report the valid null-test p-values over 20/40/60 and base the confirmatory statement on a predeclared conservative rule.

Do not choose the block length post hoc based on which p-value is most favorable.

## Reviewer interpretation of the current numbers

The current artifact remains useful as descriptive evidence: on the intended development data, none of the six F1 features shows a large stable monotonic relationship with next-day market absolute return, and the previously observed Test `equity_vol_ratio_20_60` association does not visibly reproduce with the same sign.

But because C1 leaves boundary Test transitions in the panel and C2/C3 do not yet implement the stated segment-aware permutation null, the reported Holm/BH values cannot yet be treated as the final confirmatory multiple-testing result.

The frozen F1 candidate set remains unchanged. These diagnostics must not drive feature addition/removal or RL architecture changes.

## Authorized next action

```yaml
authorized_next:
  - GATE_4_FEATURE_ABLATION_RUNS_STAT_FINALIZATION_CORRECTIONS
```

This sub-gate is limited to:

1. map the exact 475 Test execution mask to Test transition decision dates and prove zero overlap;
2. implement an accurately named, segment-aware dependence null test;
3. prevent resampling across quarantined gaps;
4. remove the false independence wording for fold CIs;
5. make inferential dependence-scale handling predeclared and robust;
6. regenerate the tracked artifact and packet, run tests, and stop for review.

## Still forbidden

```yaml
forbidden_next:
  - RL_FORMAL_PROTOCOL_PREP
  - RL_RETRAINING
  - CORRECTED_F0_RL_3SEED
  - GATE_4_10_SEED_FORMAL
  - OPTUNA
  - HYPERPARAMETER_SWEEP
  - TEST_INFORMED_FEATURE_SELECTION
  - FEATURE_DATA_READY_EXPANSION
  - F2_F3_REAL_MACRO_RUN
  - FEATURE_SET_CHANGE_FROM_CURRENT_TEST_RESULTS
  - QMT_LIVE
  - SOUTHBOUND_EXECUTION
```

## Gate decision

```text
GATE_4_FEATURE_ABLATION_RUNS_STAT_FINALIZATION
= TARGETED_TRANSITION_AND_RESAMPLING_CORRECTIONS_REQUIRED

NEXT
= GATE_4_FEATURE_ABLATION_RUNS_STAT_FINALIZATION_CORRECTIONS
```
