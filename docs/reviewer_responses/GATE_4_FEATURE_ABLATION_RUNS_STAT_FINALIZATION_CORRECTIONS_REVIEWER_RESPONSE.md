# Reviewer Response — GATE 4 FEATURE ABLATION RUNS STAT FINALIZATION CORRECTIONS

```yaml
handoff_id: G4_FEATURE_ABLATION_RUNS_STAT_FINALIZATION_CORRECTIONS_001
reviewed_code_commit: 4cc590f0e729ea1581445c5c82bf1fd4d219110b
reviewed_packet_commit: b1f94520dce22c1bcccab7c0f2cb8f117a4af6b8
reviewed_packet: docs/review_packets/GATE_4_FEATURE_ABLATION_RUNS_STAT_FINALIZATION_CORRECTIONS.md
decision: TARGETED_RESAMPLING_CLOSEOUT_REQUIRED
reviewer_state: REVISIONS_REQUIRED
```

## Summary

C1 is now correctly fixed at the **transition** level: the canonical 475 Test execution dates are mapped to their preceding decision dates, and the code asserts that no diagnostic `t -> t+1` outcome lands on a frozen Test execution date. C4 wording is also corrected, and the reduced-F0 interpretation remains appropriately narrow.

However, the remaining resampling implementation is still not sufficient for the packet's claimed dependence-aware confirmatory inference. The issues are now narrow. Because this factor screen is diagnostic only and must not drive feature selection, the preferred closeout is to simplify the statistical claims rather than keep expanding the methodology.

## Passed / accepted

- **C1 Test-transition quarantine — PASS.** `exact_test_mask()` supplies the canonical 475 execution dates; `decision_dates()` maps them to 475 decision dates; the diagnostic excludes those dates and asserts `t+1` never belongs to the frozen execution mask. `val_end` is explicitly checked as excluded.
- **C4 nested-panel wording — PASS.** The fold CIs are no longer called independent.
- **C5 primary dependence scale — PASS in design intent.** `block_len=60` is predeclared as the conservative primary scale and 20/40 are reported only as sensitivity.
- **B4/B5 remain closed.** No bootstrap null p-value is emitted, and the residualization is correctly labeled `reduced_F0_market_proxy` rather than full F0.
- **Scope discipline — PASS.** No RL retraining, 10-seed, Optuna, F2/F3 expansion, or feature-set change was performed.

## Remaining blockers

### D1 — The primary 60-day block permutation is degenerate on three of the four admissible segments

The transition-quarantined panel has four contiguous segments with sizes:

```text
[359, 60, 60, 60]
```

`_shuffle_segment_blocks(values, block_len=60)` partitions each 60-day segment into exactly **one block**. Shuffling one block is the identity operation. Therefore, under the primary `block_len=60` null, the three 60-day segments — 180 of the 539 observations — remain perfectly aligned with their observed `x-y` pairing in every permutation.

Only the 359-day segment is meaningfully randomized. The resulting `p(60)` therefore cannot be described as a full-panel segment-aware permutation test of no contemporaneous association.

Required closeout — choose one:

1. **Preferred:** remove formal confirmatory `p/Holm/BH` claims from this diagnostic and keep the transition-quarantined results explicitly descriptive only; or
2. implement a null mechanism that actually breaks alignment within every admissible segment, such as a clearly specified segment-wise circular-shift/random-lag test, with tests demonstrating non-identity randomization for 60-day segments.

Do not switch to a smaller block length merely because it yields a more convenient p-value.

### D2 — The descriptive fold bootstrap still crosses quarantined Test gaps

The permutation path uses `contiguous_segments()`, but the fold-specific CI path still builds compacted date arrays after subtracting `excluded` and then calls `block_bootstrap_ci()` on those compact arrays.

For later expanding folds, those compact arrays contain multiple original-calendar segments separated by quarantined Test intervals. `_moving_block_indices()` can therefore sample a block across an artificial adjacency created by removing the Test gap.

This is the same cross-gap problem C3 was meant to eliminate; it remains in the bootstrap path.

Required closeout — choose one:

- make the bootstrap segment-aware as well and prove blocks never cross excluded gaps; or
- **preferred for this diagnostic:** remove the bootstrap CI evidence from the closeout packet and retain only clearly descriptive point estimates / per-segment summaries.

There is no need to build a more elaborate inferential framework if these diagnostics will not be used for feature selection.

### D3 — Packet conclusion should remain narrower than "no F1 feature significant" unless D1 is fixed

Until the primary null resampler is valid over all admissible segments, statements such as:

```text
no F1 feature significant under conservative dependence-aware multiple testing
```

are too strong.

The evidence already supports the useful, narrower statement:

> On the transition-quarantined development data, none of the six frozen F1 features shows a large, stable monotonic association with next-day market absolute return; the previously observed Test vol-ratio association does not reproduce with the same sign.

That is sufficient for this diagnostic gate. It does **not** authorize deleting F1 features or changing the RL observation/network.

## Reviewer interpretation

The important research conclusion is already stable: the F1 screen provides **negative/descriptive evidence**, not a reason to spend more research degrees of freedom selecting features. The frozen F1 set should remain unchanged, and the historical 475-day Test association should remain labeled exploratory.

The remaining work should therefore be a statistical **closeout**, not another broad analysis round.

## Authorized next action

```yaml
authorized_next:
  - GATE_4_FEATURE_ABLATION_DIAGNOSTIC_CLOSEOUT
```

This sub-gate is limited to:

1. resolve D1 by either retiring confirmatory p/Holm/BH claims (preferred) or implementing a genuinely non-degenerate per-segment null mechanism;
2. resolve D2 by making bootstrap segment-aware or removing bootstrap CI evidence from the closeout;
3. narrow final wording to descriptive negative evidence unless formal inference is genuinely fixed;
4. preserve the frozen F1 candidate set unchanged;
5. regenerate the tracked artifact/packet, run tests, and stop for review.

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
GATE_4_FEATURE_ABLATION_RUNS_STAT_FINALIZATION_CORRECTIONS
= TARGETED_RESAMPLING_CLOSEOUT_REQUIRED

NEXT
= GATE_4_FEATURE_ABLATION_DIAGNOSTIC_CLOSEOUT
```
