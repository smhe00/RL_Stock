# ChatGPT Reviewer Response — POST_L2 MaxDiv Live Capital Efficiency PREP CORRECTION_002

- handoff_id: `G4_POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_PREP_CORRECTION_002_001`
- reviewed packet commit: `c792e8d0cc8750a6f9e88796d4c624b167aba4b0`
- code_commit: `null` (PREP/docs contract only)
- decision: **MAXDIV_LIVE_CAPITAL_EFFICIENCY_PREP_ACCEPTED_RUN_AUTHORIZED**
- reviewer state: **REVIEW_COMPLETE**

## Decision

PREP_CORRECTION_002 resolves the remaining pre-run contract ambiguity. The M0-M3 capital-efficiency experiment is now sufficiently pre-registered to proceed to one frozen historical RUN. No cap search, expected-return optimization, execution-universe redesign, no-trade-band search, or RL work is authorized.

## Accepted frozen contract

1. `MaximumDiversification` core remains fixed at lookback `120`, shrinkage `0.5`, deterministic only, with no expected-return forecast in the optimizer.
2. Candidate caps remain unchanged and pre-registered:
   - M0 legacy control: no external operational cash; `CASH_LIKE<=25%`, `CN_DURATION<=25%`, defensive cap 50%.
   - M1: external operational cash 5%; strategic `CASH_LIKE<=5%`; `CN_DURATION<=20%`; total defensive cap 30%.
   - M2 principal challenger: external operational cash 5%; strategic `CASH_LIKE<=5%`; `CN_DURATION<=15%`; total defensive cap 25%.
   - M3: external operational cash 5%; strategic `CASH_LIKE=0`; `CN_DURATION<=15%`; total defensive cap 20%.
3. M1/M2/M3 retain the canonical 11-economic-slot optimizer vector; operational cash is a separate accounting sleeve. M3 preserves vector dimension with `CASH_LIKE cap=0`.
4. Total-NAV to 95% investable-sleeve constraint transforms are frozen before results.
5. M1-M3 joint projection objective is uniquely specified as the Euclidean convex projection `min 0.5*||w-raw||^2` subject to long-only, simplex, per-slot caps, growth-group cap and defensive-group cap, using named `scipy.optimize.minimize(method='SLSQP')`, fixed initialization/iterations/tolerances, and no post-result fallback solver.
6. M0 must remain on the exact legacy `RiskOverlayV0` path and must match accepted L1 post-risk targets across all `1011 x 11` weights with `max|diff| <= 1e-9` before challenger results are considered valid.
7. Tests are pre-specified to cover dual-group binding, independent/analytic minimum-distance correctness, true infeasibility, deterministic repeatability, cap transforms, forward-sanity actual-weight use, CE formulas and L1 parity.
8. MaxDD capital-efficiency diagnostic now correctly uses absolute drawdown magnitude: `(abs(MaxDD_candidate)-abs(MaxDD_M0))/(def_M0-def_candidate)*0.10`; signed MaxDD difference, if reported, is separate.
9. Accepted L1 reference binding remains implementation commit `f039d369d94295433132e17cf981b2eb6243c17a`, results SHA256 `917fe9663878990598a50ca13313beca7c4e367da2f7042234cb01fcfb6753a2`, raw SHA256 `e1b9b32b78f2adecc60134faec18720574536d8e0c04436ae91fdf5864719fe9`, with the same 2022-06-09..2026-08-06 decision window / 1011 decisions and T->T+1 research semantics.
10. Forward-return sanity remains audit-only and must use each candidate's actual latest post-risk total-NAV weights plus a dated defensive-yield snapshot; the user's 1.4% cash yield remains a labeled planning assumption, not historical data.
11. M2 remains the pre-designated principal challenger; the RUN must report all M0-M3 results, viability criteria and Pareto tradeoff without selecting new intermediate cap values.
12. The prior `03110.HK` execution-realism structural STOP remains a separate closed fact and is not repaired or treated as live-ready in this study. PPO/SAC/TD3 remain closed.

## RUN implementation guards

The following are hard acceptance checks for the authorized RUN; failure invalidates/blocks the RUN rather than permitting a solver or parameter change:

- SLSQP must require `result.success == True`; any non-success status, infeasible final constraints, or numerical failure is fail-closed and must be reported with candidate/date context.
- Do not implement the stated KKT/optimality check by recursively calling the same SLSQP projection and treating that as independent proof. Use a direct stationarity/complementarity residual if multipliers are available, or rely on the frozen independent analytic minimum-distance tests plus explicit feasibility/objective checks. No alternative solver may be introduced after observing results.
- Record Python / NumPy / SciPy versions in result provenance because the numerical solver is now part of the frozen implementation contract.
- M0 parity must be checked before interpreting M1-M3 economics. If M0 parity fails, STOP the RUN as invalid implementation.
- The historical RUN must preserve the same L1 causal window, research data path, corporate-action semantics and labeled `1x MainlandETFCostModel` simplification; do not silently move to the previously stopped instrument-execution mapping.
- Operational-cash accounting must follow the frozen rule consistently across M1-M3 and must not be used as an extra optimizer dimension.
- Criterion 6 must use the minimum matched CAGR degradation across all 5 calendar-year segments plus the 2 frozen stress/phase segments.
- Forward sanity must be computed after the historical candidate allocations are generated, using actual latest post-risk total-NAV weights; at-cap calculations, if present, remain labeled stress diagnostics only.

## Required RUN outputs

For each M0-M3 report the full pre-registered metric set, including cumulative return, calendar CAGR, active-day annualized return, volatility, Sharpe, Sortino, MaxDD, Calmar, worst calendar year, worst rolling 12m, all matched annual/stress subperiods, turnover/traded-notional proxy, mean/median/p95 defensive allocation, cap-hit rates, latest total-NAV target allocation, allocation time series, CE diagnostics, and 7%/8%/9% forward required-risk-return sanity calculations.

Also report the 8-item `HISTORICALLY_VIABLE_FOR_NEXT_PREP` table candidate-by-candidate and a Pareto view. Do not create a new winner-selection rule after seeing results.

## Authorized next

Only:

`POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_RUN`

This authorizes implementation/tests and one frozen M0-M3 historical concept RUN under the accepted PREP contract. Return a new unique `READY_FOR_REVIEW` handoff with exact implementation commit, tests, provenance and result artifacts.

## Forbidden next

- RESULT_INFORMED_CAP_SEARCH
- INTERMEDIATE_CAP_VALUES
- CAP_RETUNING
- EXPECTED_RETURN_OPTIMIZATION
- EXECUTION_UNIVERSE_REDESIGN
- INSTRUMENT_SUBSTITUTION
- NO_TRADE_BAND_SEARCH
- MINIMUM_TRADE_THRESHOLD_OPTIMIZATION
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
