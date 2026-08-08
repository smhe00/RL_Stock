# Reviewer Response — GATE_4_FEATURE_ABLATION_RUNS

handoff_id: G4_FEATURE_ABLATION_RUNS_001

## Decision

```text
GATE_4_FEATURE_ABLATION_RUNS = REVISIONS_REQUIRED
CURRENT_F1_FACTOR_IMPORTANCE_ARTIFACT = EXPLORATORY_ONLY
NEXT = GATE_4_FEATURE_ABLATION_RUNS_CORRECTIONS
```

Reviewed:

- Packet: `docs/review_packets/GATE_4_FEATURE_ABLATION_RUNS.md`
- Code commit: `f0d471c81bae35bedc2a29a4172e31719f1550c2`
- Result artifact: `artifacts/gate4_feature_importance_results.json`
- Relevant code/tests: `factor_importance.py`, `gate4_feature_importance.py`, `test_feature_importance.py`

## What passes

- No RL retraining, 10-seed, Optuna, or hyperparameter sweep occurred.
- The 3 deterministic reference strategies use the corrected evaluation path and each expose 475 Test transitions.
- F1 feature construction reuses the frozen feature implementation rather than redefining formulas.
- The tracked result artifact is auditable and matches the packet's main numerical claims.
- Decision-date alignment is explicit and helper tests cover basic monotone/statistical semantics.
- `equity_vol_ratio_20_60` is clearly the strongest raw association in this exploratory Test-panel analysis; the artifact reports mean absolute risk Spearman about 0.179 across the three reference strategies and minimum Mann-Whitney p around 1e-5.

## Blocker A1 — this is Test-informed feature screening, not a valid frozen ablation completion

The frozen `FEATURE_ABLATION_SPEC.md` states that the F1/F2/F3 candidate sets are frozen independently of Test results and must not be changed because of Test performance.

The submitted runner uses all 475 Test transitions to:

- rank F1 features,
- identify one feature as the strongest,
- characterize the other five as weak,
- argue that F1 is redundant with F0,
- recommend maintaining F0 or only a very small selected extension for future RL input.

That makes the Test set part of feature-selection/model-design feedback. The packet labels these statements as "discovery", but the proposed downstream use is still Test-informed selection.

Therefore:

```text
- keep the current artifact only as exploratory/descriptive evidence;
- do NOT use it to add/drop/select F1 features or resize the future RL observation/network;
- do NOT claim that GATE_4_FEATURE_ABLATION_RUNS is complete from this artifact.
```

Because Test has now been inspected for these hypotheses, it cannot later be treated as pristine confirmatory evidence for the same feature-selection claims.

## Blocker A2 — the submitted work does not execute the frozen F0-vs-F1 ablation

The prior authorization was `GATE_4_FEATURE_ABLATION_RUNS` under the frozen feature-set contract. This packet instead performs a factor-outcome screening exercise on deterministic baseline returns. It does not compare a fixed downstream model/policy with F0 versus F1 observations under a preregistered training/evaluation protocol.

Given the explicit prohibition on RL retraining, do not start an RL ablation now. Instead, this gate must be corrected as a non-RL screening/diagnostic sub-gate and clearly separated from any future model ablation that would require separate authorization.

## Blocker A3 — significance claims assume iid observations despite overlapping rolling features / time-series dependence

`Mann-Whitney U` p-values are computed directly on daily low/high tercile outcomes. The F1 features use 20/60-day rolling windows and adjacent market returns/regimes are serially dependent and heteroskedastic. Treating the 475 daily observations as iid can materially overstate significance.

Required correction:

```text
- replace or supplement iid p-values with a time-series-aware uncertainty estimate:
  block bootstrap / stationary bootstrap / block permutation, with a predeclared block length;
- report confidence intervals for the low-vs-high risk gap and Spearman association;
- apply a multiple-testing correction across the preregistered F1 screening family (e.g. Holm or BH-FDR), or clearly mark unadjusted p-values as exploratory only.
```

The current `p < 0.001` language must not be presented as robust confirmatory significance until this is done.

## Blocker A4 — F0 residualization is full-Test-panel fitted, so it is not an out-of-sample incremental-information test

`ols_residual(f, f0p_aligned)` fits the F1-on-F0 regression using all 475 Test rows and then correlates those same-panel residuals with Test outcomes. This can describe linear redundancy in the observed Test panel, but it is not a fold-local/cross-fitted estimate of incremental predictive information.

Required correction for any model-design claim:

```text
- perform feature screening / F0 residualization only on TRAIN/VALIDATION data;
- fit residualization coefficients on TRAIN and apply them to VALIDATION, or use time-ordered cross-fitting;
- rank/select features using TRAIN/VALIDATION only;
- keep Test results quarantined as descriptive historical evidence and out of selection logic.
```

## Blocker A5 — ranking score is not a frozen statistical objective

`importance_score = mean(rho_ret) + mean(rho_risk)` mixes signed return association and signed absolute-return association. A negatively predictive risk feature can score poorly even if it is strongly informative, and the formula was not part of the frozen Feature Ablation spec.

Required correction:

- do not use this composite score for feature-selection claims;
- report preregistered metrics separately: return association, risk association, validation gap, uncertainty, and redundancy versus F0;
- if a composite ranking is desired later, freeze its definition before examining confirmatory data.

## Authorized next work

Authorize only:

```text
GATE_4_FEATURE_ABLATION_RUNS_CORRECTIONS
```

Scope:

1. Preserve the current 475-Test artifact as `EXPLORATORY_TEST_SCREENING_ONLY`; do not delete or rewrite history.
2. Build a Train/Validation-only factor-screening artifact using the same frozen F1 features and corrected PIT feature construction.
3. Use fold-local or time-ordered cross-fit residualization for F0 redundancy analysis.
4. Add time-series-aware uncertainty (block bootstrap/permutation) and multiple-testing adjustment.
5. Remove Test-informed feature-selection recommendations from the gate conclusion.
6. State explicitly that no canonical RL F0-vs-F1 model ablation has been executed because RL retraining remains forbidden.
7. Submit a corrected packet and stop for review.

## Explicitly forbidden

```text
RL_RETRAINING
GATE_4_10_SEED_FORMAL
OPTUNA
HYPERPARAMETER_SWEEP
TEST_INFORMED_FEATURE_SELECTION
FEATURE_DATA_READY_EXPANSION
F2/F3_REAL_MACRO_RUN
QMT_LIVE
SOUTHBOUND_EXECUTION
```

## Reviewer conclusion

The current artifact is useful exploratory research and the strongest raw signal (`equity_vol_ratio_20_60`) is worth retaining as a hypothesis. It is not valid evidence for pruning F1 or changing future RL observation design because the hypothesis ranking was obtained from the frozen Test panel and the reported iid significance does not account for time-series dependence. The next correction must restore Train/Validation-only selection discipline and quarantine Test from design decisions.
