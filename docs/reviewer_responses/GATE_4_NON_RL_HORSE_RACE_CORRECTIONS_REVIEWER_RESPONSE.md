# GATE 4 NON-RL HORSE RACE CORRECTIONS — REVIEWER RESPONSE

## Decision

```text
GATE_4_NON_RL_HORSE_RACE_CORRECTIONS = TARGETED_FINAL_CORRECTIONS_REQUIRED
HORSE_RACE_RESULTS = STILL_PRELIMINARY
RL_RETRAINING = FORBIDDEN
10_SEED_FORMAL = REMOVED_FROM_ACTIVE_ROADMAP
NEXT = GATE_4_NON_RL_HORSE_RACE_FINAL_CORRECTIONS
```

Reviewed handoff:

```text
handoff_id = G4_NON_RL_HORSE_RACE_CORRECTIONS_001
packet      = docs/review_packets/GATE_4_NON_RL_HORSE_RACE_CORRECTIONS.md
code_commit = a0844141a8c545dc76657d1d3ab7487766d137f3
status      = READY_FOR_REVIEW
```

## 1. What is closed

The correction round materially improved the experiment. The following are accepted:

```text
N4 TrendRiskParity exact budget transfer to CASH_LIKE
N8 tracked result artifacts exist and are auditable
475 stitched step count restored
F2/feature work is not touched
no RL retraining / no 10-seed / no parameter sweep
```

The rerun also demonstrates why canonical-method validation matters: ERC and MinCVaR changed substantially from the previous approximations.

However, several prior semantic requirements are still not actually closed, so the current ranking cannot yet be accepted as the final non-RL horse race.

## 2. BLOCKER F1 — HRP recursive-bisection allocation is reversed

Current code computes cluster variances `va` and `vb`, then allocates:

```python
bisect(a, w_in * va / (va + vb))
bisect(b, w_in * vb / (va + vb))
```

Canonical HRP allocates MORE weight to the LOWER-variance cluster. With two clusters A/B, the allocation to A is proportional to `vb/(va+vb)`, and to B is `va/(va+vb)`.

Required fix:

```text
weight_A = vb / (va + vb)
weight_B = va / (va + vb)
```

The current direction can explain the anomalous HRP profile (high return but very high volatility / -20.5% MaxDD).

Add a deterministic two-cluster unequal-variance test that proves the lower-variance cluster receives the larger total allocation. The existing block test only checks within-block similarity and cannot detect this reversal.

Discard the current HRP 37.1% active-day annualized result until rerun after this fix.

## 3. BLOCKER F2 — MinimumCVaR objective is still not the Rockafellar-Uryasev objective

Current `_cvar_value()` does:

```python
var = quantile(loss, alpha)
tail = loss[loss >= var]
return var + tail.mean() / (1-alpha)
```

This is not CVaR. The R-U objective is:

```text
zeta + mean(max(loss - zeta, 0)) / (1-alpha)
```

where the mean is over ALL T observations. Equivalently, empirical expected shortfall can be computed consistently from the worst tail, but it must not add `VaR + tail_mean/(1-alpha)`.

The current semantic test uses the same incorrect helper for both optimized and EW portfolios, so it cannot validate the true CVaR claim.

There is also a convergence bug:

```python
if it > 200 and abs(best_val - _cvar_value(best_w, ...)) < 1e-12:
```

`best_val` was defined from that same `best_w`, so this condition becomes tautological and the optimizer effectively stops just after 200 iterations.

Required correction:

```text
- implement the exact R-U LP, OR a correctly defined convex optimizer;
- use the exact objective for solver selection and testing;
- remove the tautological convergence condition;
- test against an independently computed empirical CVaR / known synthetic optimum;
- verify optimized CVaR <= EW under the same feasible constraints.
```

Discard the current MinCVaR result until rerun.

## 4. BLOCKER F3 — ERC tolerance requirement was weakened instead of met

Prior requirement:

```text
max relative risk-contribution deviation <= 1e-3
```

Current packet reports approximately `1.8e-3`, and the test was changed to:

```python
assert max_dev <= 5e-3
```

That does not close N2. Do not weaken a reviewer gate to make the implementation pass.

Required:

```text
- make the solver actually achieve <=1e-3 on the policy covariance;
- keep the test threshold <=1e-3;
- report convergence/fallback count.
```

Additionally, the artifact shows `risk_overlay_intervention_rate = 1.0` for ERC. Therefore the executed strategy is not pure unconstrained ERC after the overlay. Final reporting must explicitly distinguish:

```text
raw ERC target
post-RiskOverlay executed target
```

and must not claim post-overlay weights themselves satisfy equal risk contribution unless that is separately demonstrated.

## 5. BLOCKER F4 — MaxDiv / ShrinkageMV do not yet solve the frozen project-constrained objectives

The prior N5/N6 requirements explicitly included the same project constraints.

Current helper `_safe_proj()` projects only to:

```text
w >= 0
sum(w) = 1
single cap = 1.0
```

and `qp_projected()` is called without project caps. The real Track-A RiskOverlay is applied only afterward by the environment. The artifact confirms this is not a rare edge case: MaximumDiversification has `risk_overlay_intervention_rate = 1.0` across folds.

Therefore the optimizer objective is solved in one feasible set and then moved to another feasible set before execution.

For the methods frozen as constrained optimizers, use the actual project-feasible projection inside the optimization iterations (single-slot caps + China-growth group cap), or otherwise rename the methods as `..._PLUS_RISK_OVERLAY` and do not call them canonical constrained solutions.

For MaxDiv, the previous reviewer also required local-optimality validation. Current test only proves `DR >= EW`; add feasible local perturbation / projected-gradient residual validation.

For ShrinkageMV, `utility >= EW` is too weak because a nearly unchanged EW portfolio passes. Add solver-convergence evidence such as projected-gradient/KKT residual or a known synthetic constrained optimum comparison.

## 6. BLOCKER F5 — Test-date parity assertion is tautological

The runner currently constructs:

```python
seg_dates = [d for d in mask_dates if ...]
exec_dates.extend(seg_dates)
...
assert exec_dates == mask_dates
```

Thus `exec_dates` comes from the reference mask itself, not from the actual rollout. This proves only the count, not actual execution-date equality.

Required:

```text
- record actual execution date `st.t_next` in roll_out series;
- concatenate those actual dates for each method/fold;
- assert actual_execution_dates == exact_test_mask.test_dates;
- retain 475 count assertion separately.
```

## 7. BLOCKER F6 — final horse-race aggregate is incomplete

Tracked artifacts are now present, but the stitched aggregate / horse-race table still omits fields explicitly required in the prior review/directive.

Add stitched/aggregate reporting for:

```text
active-day annualized return  (do not label it ordinary calendar CAGR)
annualized volatility
Sharpe
Sortino
MaxDD
Calmar
mean + total turnover
actual traded notional
total transaction cost
cost / traded notional
HHI
average active assets
max weight
RiskOverlay intervention rate
mean L1 raw -> post
fallback count
```

Do not rank methods only on return/Sharpe/MDD.

## 8. Interpretation guard

Current artifacts already show a major methodological signal:

```text
ERC / HRP / MaxDiv and several risk-based baselines: overlay intervention ≈ 100%
```

The final report must make clear whether a row represents:

```text
canonical optimizer under project constraints
```

or

```text
unconstrained/base optimizer + common RiskOverlay
```

Both can be useful comparisons, but they are not the same claim.

## 9. Authorized next work

Authorize only:

```text
GATE_4_NON_RL_HORSE_RACE_FINAL_CORRECTIONS
```

Scope:

```text
1. fix HRP inverse-variance cluster allocation direction
2. fix MinCVaR objective + convergence + independent semantic test
3. tighten ERC to <=1e-3; no weakened assertion
4. enforce/verify frozen project constraints for MaxDiv/ShrinkMV/MinCVaR as required,
   or explicitly relabel non-constrained-plus-overlay variants
5. add MaxDiv local-opt / ShrinkMV convergence semantic tests
6. record actual rollout execution dates and prove exact 475-date equality
7. complete stitched diagnostics table
8. rerun ONLY deterministic non-RL methods affected by the corrections
9. do NOT retrain TD3/SAC/PPO
10. update tracked artifacts
11. full pytest
12. submit GATE_4_NON_RL_HORSE_RACE_FINAL_CORRECTIONS.md
13. STOP for review
```

Existing corrected EW / IVOL RP / legacy MinimumVariance / Momentum results do not need recomputation unless runner output schema requires a cheap deterministic regeneration of the table.

## 10. Forbidden

```text
RL_RETRAINING
GATE_4_10_SEED_FORMAL
20_SEED
FEATURE_ABLATION_RUNS
OPTUNA
HYPERPARAMETER_SWEEP
TEST_INFORMED_SELECTION
THEME_SLEEVE
QMT_LIVE
SOUTHBOUND_EXECUTION
```

## Authorization record

```yaml
gate: 4
handoff_id: G4_NON_RL_HORSE_RACE_CORRECTIONS_001
reviewed_code_commit: a0844141a8c545dc76657d1d3ab7487766d137f3

decision: TARGETED_FINAL_CORRECTIONS_REQUIRED

passed:
  - N4_TREND_RP_CASH_TRANSFER
  - N8_ARTIFACT_FILES_TRACKED
  - TEST_STEP_COUNT_475
  - NO_RL_RETRAINING

blocked:
  - F1_HRP_CLUSTER_VARIANCE_ALLOCATION_REVERSED
  - F2_MIN_CVAR_OBJECTIVE_AND_CONVERGENCE_INVALID
  - F3_ERC_TOLERANCE_WEAKENED
  - F4_PROJECT_CONSTRAINTS_NOT_IN_OPTIMIZER
  - F5_ACTUAL_EXECUTION_DATE_PARITY_NOT_PROVEN
  - F6_STITCHED_DIAGNOSTICS_INCOMPLETE

authorized_next:
  - GATE_4_NON_RL_HORSE_RACE_FINAL_CORRECTIONS

forbidden_next:
  - RL_RETRAINING
  - GATE_4_10_SEED_FORMAL
  - FEATURE_ABLATION_RUNS
  - OPTUNA
  - TEST_INFORMED_SELECTION
  - THEME_SLEEVE
  - QMT_LIVE
  - SOUTHBOUND_EXECUTION
```

## END OF REVIEWER RESPONSE
