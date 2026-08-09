# Reviewer Response — GATE 4 FEATURE ABLATION DIAGNOSTIC CLOSEOUT

```yaml
handoff_id: G4_FEATURE_ABLATION_DIAGNOSTIC_CLOSEOUT_001
reviewed_code_commit: cad0d4bd1c3b1b070f7b9a7aa65b7de64f130a03
reviewed_packet_commit: c78a2151bf2f85ffa94e577d2eb7261f56e22304
reviewed_packet: docs/review_packets/GATE_4_FEATURE_ABLATION_DIAGNOSTIC_CLOSEOUT.md
decision: APPROVED
reviewer_state: REVIEW_COMPLETE
```

## Summary

The requested diagnostic closeout is complete. The packet follows the reviewer-preferred path: retire confirmatory resampling inference rather than adding more methodological degrees of freedom, preserve the exact Test-transition quarantine, and retain only clearly descriptive development-data evidence.

This closes the feature-diagnostic sub-gate. It does **not** establish that F1 has no predictive value, and it does **not** authorize changing the frozen F1 candidate set or the RL observation/network because of these results.

## Review checks

- **D1 confirmatory inference retired — PASS.** The closeout no longer uses segment block-permutation p-values, Holm/BH, or the degenerate 60-day primary null as confirmatory evidence.
- **D2 bootstrap CI evidence removed — PASS.** The closeout script does not use the compact-array moving-block bootstrap path that could cross quarantined Test gaps.
- **D3 conclusion narrowed — PASS.** The final conclusion is explicitly descriptive negative evidence only.
- **Test-transition quarantine — PASS.** The canonical 475 Test execution dates are mapped to preceding decision dates; the script asserts no retained `t -> t+1` outcome lands on a frozen Test execution date and excludes every fold `val_end` boundary decision.
- **Per-segment reporting — PASS.** The admissible data are reported as contiguous segments `[359, 60, 60, 60]`; no cross-gap inferential resampling is used in the closeout.
- **Reduced-F0 interpretation — PASS.** Residualization remains labeled `reduced_F0_market_proxy (10 predictors; NOT full 104-dim F0)` and is treated descriptively.
- **Frozen feature set / scope discipline — PASS.** No F1 feature was added or removed; no RL retraining, 10-seed, Optuna, F2/F3 expansion, or architecture change was performed.
- **Tests/results — PASS for gate evidence.** The packet reports 200 tests passing, and the exact commit adds explicit tests documenting single-block permutation degeneracy while retaining the transition-invariant checks.

## Accepted research interpretation

The supported conclusion is limited to:

> On the transition-quarantined development data, none of the six frozen F1 features shows a large, stable monotonic association with next-day market absolute return; the previously observed Test vol-ratio association does not reproduce with the same sign.

This is useful descriptive negative evidence. It is **not** a formal proof of no predictive information and must not be used as a feature-elimination rule.

A minor non-blocking note: the artifact retains `mann_whitney_p_exploratory_only`. That is acceptable because it is explicitly marked exploratory, but it must not be consumed by the next gate for feature selection, network changes, or claims of statistical significance.

## Authorized next action

```yaml
authorized_next:
  - RL_FORMAL_PROTOCOL_PREP
```

`RL_FORMAL_PROTOCOL_PREP` is a **protocol-freeze/preparation gate only**. It may define and freeze the corrected F0 RL experiment contract, including algorithms, train budget, seed policy, validation-only model-selection rule, exact Test mask, benchmark hurdle, metrics, GO/NO-GO criteria, artifacts, and stop conditions.

It may **not** train or retrain RL models.

## Still forbidden

```yaml
forbidden_next:
  - RL_RETRAINING
  - CORRECTED_F0_RL_3SEED
  - GATE_4_10_SEED_FORMAL
  - OPTUNA
  - HYPERPARAMETER_SWEEP
  - TEST_INFORMED_FEATURE_SELECTION
  - FEATURE_SET_CHANGE_FROM_CURRENT_TEST_RESULTS
  - FEATURE_DATA_READY_EXPANSION
  - F2_F3_REAL_MACRO_RUN
  - QMT_LIVE
  - SOUTHBOUND_EXECUTION
```

## Gate decision

```text
GATE_4_FEATURE_ABLATION_DIAGNOSTIC_CLOSEOUT
= APPROVED

NEXT
= RL_FORMAL_PROTOCOL_PREP
```
