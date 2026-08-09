# Reviewer Response — GATE 4 FEATURE ABLATION RUNS CORRECTIONS

```yaml
handoff_id: G4_FEATURE_ABLATION_RUNS_CORRECTIONS_001
reviewed_code_commit: 520d13ad1252d7ef73b57ec6175b349bd06b6510
reviewed_packet: docs/review_packets/GATE_4_FEATURE_ABLATION_RUNS_CORRECTIONS.md
decision: TARGETED_STATISTICAL_FINALIZATION_REQUIRED
reviewer_state: REVISIONS_REQUIRED
```

## Summary

The correction materially improves the previous Test-informed screening: no RL retraining was performed, the composite importance score was removed, a train→validation residualization path was added, and time-series-aware resampling helpers/tests were introduced.

However, the packet is not yet statistically final. The remaining issues are narrow and do **not** justify expanding scope into RL retraining, 10-seed, Optuna, F2/F3 macro acquisition, or further feature selection.

## Passed / accepted

- **A2 scope discipline — PASS.** This is correctly treated as a non-RL diagnostic; no canonical RL F0-vs-F1 model ablation was executed.
- **A5 composite score removal — PASS.** The ad-hoc signed `rho_ret + rho_risk` ranking is no longer used.
- **No RL retraining / no 10-seed / no sweep — PASS.** Current forbidden work was respected.
- **Train-fit → validation-apply mechanics — PARTIAL PASS.** The residualization implementation itself fits on train and applies on validation; the remaining issue is the interpretation/scope of the F0 predictor set.
- **Time-series uncertainty direction — PARTIAL PASS.** Moving-block bootstrap infrastructure exists, but the reported inferential quantities are not yet valid enough for a final statistical claim.

## Blocking finalization items

### B1 — The claimed `475 Test quarantine` is not globally true

`_fold_screen_days()` uses each fold's `train ∪ validation` and excludes only that fold's **own** Test. In an expanding walk-forward, later folds' train windows contain earlier folds' Test dates. The unit test explicitly confirms that the union of screening dates overlaps the union of Test dates.

Therefore the packet must not state that the original 475-day Test panel is "completely isolated" or that the new analysis is independent of the already-observed Test panel.

Required fix — choose one and state it explicitly:

1. **Preferred:** construct `global_test_union = union(all frozen fold Test decision dates)` and exclude those dates from every screening / fit dataset used in this diagnostic; or
2. relabel the analysis as a **sequential walk-forward development diagnostic** where prior realized Test periods can enter later training, and remove any claim that it independently invalidates or confirms the original 475-Test result.

Because the stated purpose of this correction was to remove Test-informed inference, option 1 is preferred.

### B2 — `median per-fold Mann–Whitney p -> Holm/BH` is not a valid multiple-testing procedure

The script computes four ordinary Mann–Whitney p-values per feature, takes their median, then applies Holm/BH across the six median p-values. A median of p-values is not itself a calibrated p-value under the null, so Holm/BH on that quantity does not provide family-wise/FDR control.

Required fix:

- produce **one valid dependence-aware inferential p-value per feature** from a predeclared aggregate statistic, then apply Holm or BH across the six features; or
- if a valid p-value is not implemented, remove the Holm/BH significance claims entirely and keep the result descriptive only.

A segment-aware block permutation / circular-shift null on a validation-only or globally-Test-excluded panel is acceptable. Do not use iid Mann–Whitney p-values as the final confirmatory evidence.

### B3 — The reported "bootstrap 95% CI" is not an aggregate 95% CI

The script computes a bootstrap CI separately in each fold, then takes the **median of the lower endpoints and median of the upper endpoints**. That interval has no established 95% coverage for the cross-fold aggregate statistic and must not be labeled a 95% CI.

Required fix:

- either report the four fold CIs as four fold CIs with no synthetic aggregate confidence level; or
- bootstrap the predeclared cross-fold aggregate statistic directly using a segment-aware resampling scheme and report that actual aggregate CI.

Also correct the comment `BLOCK_LEN = 20  # = longest rolling window`: F1 contains 60-day rolling features. If block length 20 is retained, justify it independently and show sensitivity to a materially longer dependence block (for example 20/40/60 or an automatic block-length rule).

### B4 — `p_bs` is not a valid null p-value

`block_bootstrap_ci()` samples from the empirical distribution centered near the observed statistic and then computes:

```python
2 * min(P(bootstrap_stat >= observed_stat), P(bootstrap_stat <= observed_stat))
```

This is not a test of the null `stat = 0`; for a well-behaved bootstrap distribution centered on the observed statistic it will tend toward approximately 1 even when the observed statistic is far from zero.

Required fix:

- remove `p_bs` from inference/artifacts, or
- implement a proper null-centered bootstrap/permutation test.

The percentile CI itself can remain as a descriptive uncertainty interval subject to B3.

### B5 — The residualization conclusion overstates what was removed

`_f0_predictor_frame()` contains only 10 predictors: 5 global F0 descriptors plus 5 CN_LARGE asset features. It is **not** the full F0 observation contract (104 dimensions, including all per-asset features and portfolio weights).

Therefore statements such as "F1 does not provide information beyond F0" are not supported by this diagnostic.

Required fix — either:

- relabel the predictor set as `reduced_F0_market_proxy` and conclude only that there is no robust positive monotonic residual association after removing this reduced linear proxy; or
- construct and justify a fuller policy-independent F0 predictor set. Portfolio weights cannot be silently treated as removed in a no-policy diagnostic.

Even after residualization, zero Spearman correlation does not prove absence of nonlinear incremental predictive information. Keep the conclusion correspondingly narrow.

## Reviewer interpretation of the current findings

The present numbers are consistent with the hypothesis that the six F1 features do **not** show a strong, stable monotonic relationship with next-day market absolute return in the development data. That is useful negative evidence.

They are **not yet sufficient** to claim:

- formal absence of F1 predictive value;
- a valid multiple-testing-controlled null result;
- independent refutation of the previously observed 475-Test `equity_vol_ratio_20_60` association; or
- absence of incremental information beyond the complete F0 observation state.

No F1 feature should be added/removed because of these results; the frozen F1 candidate set remains unchanged.

## Authorized next action

```yaml
authorized_next:
  - GATE_4_FEATURE_ABLATION_RUNS_STAT_FINALIZATION
```

This sub-gate is limited to:

1. resolve B1 Test-set semantics;
2. replace/remove invalid median-p multiple testing;
3. make bootstrap aggregation statistically honest and add block-length sensitivity;
4. remove/fix `p_bs`;
5. narrow the residualization label/conclusion to the actual reduced F0 proxy;
6. regenerate the tracked artifact and packet;
7. run tests and stop for review.

## Still forbidden

```yaml
forbidden_next:
  - RL_RETRAINING
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
GATE_4_FEATURE_ABLATION_RUNS_CORRECTIONS
= TARGETED_STATISTICAL_FINALIZATION_REQUIRED

NEXT
= GATE_4_FEATURE_ABLATION_RUNS_STAT_FINALIZATION
```
