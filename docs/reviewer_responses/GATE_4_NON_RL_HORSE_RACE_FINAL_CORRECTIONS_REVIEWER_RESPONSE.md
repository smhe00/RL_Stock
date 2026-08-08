# GATE 4 NON-RL HORSE RACE — FINAL CORRECTIONS — REVIEWER RESPONSE

## Decision

```text
GATE_4_NON_RL_HORSE_RACE_FINAL_CORRECTIONS = TARGETED_FINALIZATION_REQUIRED
HORSE_RACE_RESULTS = NOT YET FINAL
NEXT = GATE_4_NON_RL_HORSE_RACE_FINALIZATION
```

Reviewed handoff:

```text
handoff_id = G4_NON_RL_HORSE_RACE_FINAL_CORRECTIONS_001
packet      = docs/review_packets/GATE_4_NON_RL_HORSE_RACE_FINAL_CORRECTIONS.md
packet_commit = 59ea96240a165a5e2cb9f73455f790a2ff070aff
code_commit = 4ace12fb3ff3633dfa961a8eb69c8c6ae4629b71
```

## Passed

The following prior blockers are materially closed:

```text
F1_HRP_CLUSTER_VARIANCE_DIRECTION = PASS
F2_MIN_CVAR_RU_OBJECTIVE_AND_NONTAUTOLOGICAL_CONVERGENCE = PASS
F3_ERC_RAW_SOLVER_TOLERANCE_1E3 = PASS
F5_ACTUAL_EXECUTION_DATE_PARITY = PASS
```

Evidence checked:

- HRP recursive bisection now assigns A = vb/(va+vb), B = va/(va+vb), so the lower-variance cluster receives more weight; an unequal-variance cluster semantic test was added.
- `_cvar_value` now implements the Rockafellar-Uryasev empirical objective using `VaR + E[(L-VaR)+]/(1-alpha)` and the previous tautological convergence test was removed. An independent worst-tail ES test checks optimized ES <= EW.
- ERC uses an analytic Jacobian and the raw unconstrained ERC solver is again checked against the <=1e-3 contribution-deviation target.
- `roll_out` now records actual `st.t_next` execution dates, and the horse-race runner compares these real dates directly against the frozen 475-date Test mask.
- 162 tests are reported passing; no RL retraining / 10-seed / feature-ablation run was performed.

## Remaining blocker F4A — ERC / HRP labeling overstates constrained optimization

The packet states that project constraints are "in the optimizer" for ERC and HRP, but the reviewed source does not do that:

```text
ERC:
  _erc_solve(sigma)              # solve unconstrained ERC
  -> _proj_constrained(w)        # project afterward

HRP:
  canonical HRP recursive bisection
  -> _proj_constrained(weights)  # project afterward
```

This is acceptable as an execution construction, but it is not a constrained ERC solver or constrained HRP objective. `overlay=0` only proves that the pre-RiskOverlay projection already satisfies the execution caps; it does not prove the canonical objective was solved over the constrained feasible set.

Required finalization:

```text
Either:
A. relabel these methods explicitly, e.g.
   ERC_ProjectProjected
   HRP_ProjectProjected
   and report raw-objective diagnostics before project projection;

or

B. implement a genuinely constrained formulation and provide objective/KKT evidence.
```

Do not silently call a post-projected canonical solution a constrained optimum.

For MaxDiv / MinCVaR / ShrinkageMV, iterative projection into the project feasible set is present and may retain the constrained label, subject to the diagnostics cleanup below.

## Remaining blocker F4B — projection semantics must be described accurately

`waterfill_proj` is a deterministic feasibility projection built from single-slot waterfill plus ChinaGrowth rescaling/redistribution. It is not demonstrated to be the exact Euclidean projection onto the intersection of all constraints.

This is acceptable for this gate if the report calls it the frozen **project feasibility projection contract**, rather than claiming generic exact Euclidean projection. No new optimizer is required solely for this wording issue.

## Remaining blocker F6 — stitched diagnostics are still incomplete / approximate

The prior reviewer requirement explicitly included:

```text
actual traded notional
cost / traded notional
raw -> post RiskOverlay L1
total turnover from actual rollout totals
```

Those fields already exist in `roll_out`:

```text
actual_traded_notional
total_cost_over_traded_notional
risk_overlay_mean_l1_raw_to_post
total_turnover / total_turnover_l1
```

but `METRICS` does not carry them into `per_fold`, and the stitched output omits them.

Also, current stitched calculations use approximations:

```text
total_turnover = sum(mean_turnover * n_eval_steps)
total_cost     = mean(per_fold total_cost) * 4
```

The second happens to equal the sum only because there are four folds; the first is not the exact rollout total because turnover has one fewer transition than evaluation steps within each reset segment.

Required finalization:

```text
1. add to METRICS:
   total_turnover / total_turnover_l1
   actual_traded_notional
   total_cost_over_traded_notional
   risk_overlay_mean_l1_raw_to_post

2. stitched totals must use exact sums of per-fold totals:
   total_turnover = sum(per_fold total_turnover)
   total_cost = sum(per_fold total_cost)
   actual_traded_notional = sum(per_fold actual_traded_notional)
   cost_over_traded_notional = total_cost / actual_traded_notional

3. stitched weighted means should be weighted by the appropriate step count, not a simple mean of fold means where fold lengths differ.

4. include fallback_count explicitly in both stitched and horse_race_table; if genuinely zero, document how it was counted rather than hard-coding an unexplained constant.
```

## Packet/result consistency cleanup

The packet summary table reports `EqualWeight overlay = 1.00`, while the tracked artifact/source diff shows EqualWeight overlay intervention is 0.0. Regenerate the packet table from the final tracked artifact rather than manually copying values.

## Result interpretation retained

The corrected results already show the earlier false HRP outperformance disappearing after the allocation-direction fix. The current risk/return ordering is useful as provisional evidence, but final ranking should wait until the above labeling and exact diagnostic aggregation are fixed.

No RL rerun is needed. Existing TD3/SAC/PPO values remain historical pre-correction references only.

## Authorized next work

Authorize only:

```text
GATE_4_NON_RL_HORSE_RACE_FINALIZATION
```

Scope:

```text
1. correct ERC/HRP method labels or implement genuinely constrained variants
2. describe project projection semantics accurately
3. carry exact rollout turnover/traded-notional/cost/L1 fields into per-fold + stitched outputs
4. aggregate totals exactly and means with proper weighting
5. make fallback count auditable
6. regenerate tracked result artifacts + packet table
7. run only deterministic non-RL tests/results needed for this cleanup
8. submit a new READY_FOR_REVIEW packet and STOP
```

Explicitly forbidden:

```text
RL_RETRAINING
GATE_4_10_SEED_FORMAL
FEATURE_ABLATION_RUNS
FEATURE_DATA_READY_EXPANSION
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
handoff_id: G4_NON_RL_HORSE_RACE_FINAL_CORRECTIONS_001
decision: TARGETED_FINALIZATION_REQUIRED

passed:
  - F1_HRP_CLUSTER_VARIANCE_DIRECTION
  - F2_MIN_CVAR_RU_OBJECTIVE
  - F3_ERC_RAW_TOLERANCE_1E3
  - F5_ACTUAL_EXECUTION_DATE_PARITY

blocked:
  - F4_ERC_HRP_CONSTRAINED_LABELING
  - F6_EXACT_STITCHED_DIAGNOSTICS
  - PACKET_ARTIFACT_CONSISTENCY

authorized_next:
  - GATE_4_NON_RL_HORSE_RACE_FINALIZATION

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
