# ChatGPT Reviewer Response — POST_L2 MaxDiv Live Capital Efficiency PREP CORRECTION_001

- handoff_id: `G4_POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_PREP_CORRECTION_001`
- reviewed packet commit: `d5baae7b01c2c5268955712dd1e857a502d35da1`
- code_commit: `null` (PREP/docs contract only)
- decision: **MAXDIV_LIVE_CAPITAL_EFFICIENCY_PREP_CORRECTION_001_NEARLY_ACCEPTED_FINAL_PROJECTION_SPEC_CLEANUP_REQUIRED**
- reviewer state: **REVISIONS_REQUIRED**

## Decision

CORRECTION_001 resolves the prior substantive PREP ambiguities and is close to RUN-ready. No M0-M3 backtest/run is authorized yet because two remaining contract ambiguities can change reported candidate weights/diagnostics and therefore must be frozen before results are observed.

## Accepted corrections

1. M1/M2/M3 now retain the canonical 11 economic-slot optimizer vector; the external 5% operational-cash sleeve is a separate accounting sleeve, and M3 keeps the same dimension with `CASH_LIKE cap = 0`.
2. Total-NAV to 95% investable-sleeve cap transforms are explicit and numerically correct for M1-M3.
3. The constraint set is correctly stated as the joint intersection of long-only, simplex, per-slot, growth-group and defensive-group caps, with simultaneous final assertions and fail-closed semantics.
4. Forward-return sanity now uses each future RUN candidate's actual latest post-risk total-NAV allocation; at-cap calculations are diagnostic-only.
5. Accepted L1 reference binding now records implementation commit `f039d369d94295433132e17cf981b2eb6243c17a` plus explicit results/raw SHA256 values; M0 parity target is the accepted `1011 x 11` post-risk target path.
6. The historical comparison engine is frozen to the accepted L1 T->T+1 causal semantics, CA semantics and labeled 1x MainlandETFCostModel research simplification.
7. Operational cash accounting, CE formulas/zero-denominator behavior, and viability criterion 6 across the 5 calendar-year + 2 frozen stress segments are now explicitly specified.
8. M0-M3 caps remain pre-registered, M2 remains the principal challenger, no expected-return model enters the optimizer, the stopped 03110 execution mapping is not repaired, and PPO/SAC/TD3 remain closed.

## Final required cleanup before RUN

### 1. Freeze one exact joint projection algorithm

The packet currently permits `active-set / multiplier iteration`, `Dykstra`, or ordinary `alternating projection`. These are not interchangeable contracts. In particular, ordinary alternating projections can converge to a feasible point without being the Euclidean projection solving:

`min ||w - raw||_2  subject to C1-C5`.

Before RUN, freeze exactly one deterministic algorithm and its convergence/tolerance/failure rules. Recommended contract:

- solve the convex quadratic projection `min 0.5*||w-raw||^2` over C1-C5 with one explicitly named deterministic method;
- fixed tolerances and maximum iterations;
- no fallback to a different projection method after observing failures/results;
- fail closed if convergence/KKT/feasibility checks fail;
- preserve the legacy `RiskOverlayV0` path exactly for M0 rather than routing M0 through a numerically different solver.

Tests must include:

- M0 exact/all-1011-day parity to accepted L1 target weights within a pre-frozen tolerance;
- a synthetic case where growth and defensive constraints both bind;
- an independent reference/analytic assertion that the returned point is the intended minimum-distance projection, not merely feasible;
- a true-infeasible case that raises `InfeasibleConstraints`;
- deterministic repeatability.

### 2. Fix MaxDD-per-10ppt sign convention

The current text gives:

`(MaxDD_candidate - MaxDD_M0)/(def_M0-def_candidate)*0.10`

while saying the diagnostic is the increase in **absolute drawdown magnitude**. Those are inconsistent when MaxDD values are negative. Freeze the intended diagnostic as:

`delta_MaxDD_magnitude_per_10ppt = (abs(MaxDD_candidate) - abs(MaxDD_M0)) / (def_M0 - def_candidate) * 0.10`

with the already frozen zero-denominator rule returning `NaN`.

The signed `MaxDD_candidate - MaxDD_M0` may be reported separately if desired, but must not be mislabeled as magnitude increase.

## Authorized next

Only:

`POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_PREP_CORRECTION_002`

This is a narrow PREP/docs-contract cleanup only. After it is reviewed and accepted, the next gate may be the frozen M0-M3 capital-efficiency RUN.

## Forbidden next

- CAPITAL_EFFICIENCY_RUN
- NEW_BACKTEST
- RESULT_INFORMED_CAP_SEARCH
- INTERMEDIATE_CAP_VALUES
- EXPECTED_RETURN_OPTIMIZATION
- EXECUTION_UNIVERSE_REDESIGN
- INSTRUMENT_SUBSTITUTION
- NO_TRADE_BAND_SEARCH
- EXECUTION_TIME_OPTIMIZATION
- FORWARD_PAPER_VALIDATION
- PAPER
- LIVE
- QMT_LIVE
- DENSE_ALPHA_SEARCH
- DYNAMIC_ALPHA
- PPO
- SAC
- TD3
- RL_RETRAINING
- RL_HYPERPARAMETER_TUNING
- RL_COMPARISON

PPO/SAC/TD3 remain closed unless the user explicitly reopens them.
