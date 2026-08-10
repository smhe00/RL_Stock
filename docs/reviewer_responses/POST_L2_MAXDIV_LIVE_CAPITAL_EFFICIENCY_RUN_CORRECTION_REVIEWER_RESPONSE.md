# ChatGPT Reviewer Response — POST_L2 MaxDiv Live Capital Efficiency RUN CORRECTION

- handoff_id: `G4_POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_RUN_CORRECTION_001`
- reviewed packet commit: `7a4474b04b2a719215a91dc6a90531f8e8f0b463`
- implementation commit: `487fd0042f424a2061070c3da357f136420fcc2f`
- decision: **MAXDIV_LIVE_CAPITAL_EFFICIENCY_RUN_CORRECTION_ACCEPTED_DOC_CONSISTENCY_CLEANUP_REQUIRED**
- reviewer state: **REVISIONS_REQUIRED**

## Decision

The mechanical RUN correction is substantively accepted. The corrected implementation resolves the prior result-affecting issues without changing the frozen M0-M3 candidates, MaxDiv 120/0.5 core, window, solver, or selection thresholds. The corrected rerun preserves the provisional economics, so the capital-efficiency conclusion is now scientifically usable as a historical concept result.

No further rerun is required. A narrow documentation/comment consistency cleanup is required before this research line is closed because the review packet and one source docstring still contain stale/non-canonical text.

## Accepted corrected result

Canonical corrected artifact economics:

- M0 legacy: cumulative `+45.42%`, calendar CAGR `9.4154%`, Sharpe `1.654531`, MaxDD `-4.0172%`, mean defensive allocation `50%`.
- M1: cumulative `+55.92%`, calendar CAGR `11.2629%`, Sharpe `1.282467`, MaxDD `-6.8107%`, mean defensive allocation `30%`; historically viable.
- **M2 principal challenger**: cumulative `+58.15%`, calendar CAGR `11.6441%`, Sharpe `1.219346`, MaxDD `-7.6651%`, mean defensive allocation `25%`; all 8 pre-registered viability criteria pass.
- M3: cumulative `+61.14%`, calendar CAGR `12.1481%`, Sharpe `1.178854`, MaxDD `-8.4609%`, mean defensive allocation `20%`; fails the frozen Sharpe >= 1.20 screen and is not eligible for the next execution study.

The corrected forward sanity now uses actual total-NAV weights. Under the frozen cash-yield assumption `1.4%` and CN10Y snapshot `1.7114%` dated `2026-08-07`, M2 requires approximately `10.1377%` annual risk-sleeve return for an `8%` total-portfolio target, versus `14.4443%` for M0.

## Accepted mechanical fixes

1. SLSQP initialization is now the frozen bounded-simplex waterfill, not raw weights.
2. Forward sanity uses actual total-NAV slot weights and passes end-to-end candidate checks.
3. Raw artifact now separates `sleeve_weights` from `total_nav_slot_weights`, with operational cash explicit.
4. Turnover/notional/cost now distinguish sleeve-normalized and total-NAV-normalized quantities; criterion 7 uses total-NAV turnover.
5. The tautological `parity_ok or True` path is removed; criterion 8 now binds runtime validity, while test/provenance evidence is separately present in the handoff.
6. Criterion 6 now uses matched subperiod calendar CAGR.
7. Worst-calendar-year return compounds all returns in the year; M0 matches accepted L1 `-0.003933`.
8. Forward duration-yield snapshot now binds observation date/value/source/path/SHA256.
9. M0 all-`1011 x 11` target parity remains exact (`max|diff| = 0`).
10. Fifteen behavioral tests are reported passed and the projection tests include analytic minimum-distance checks, infeasibility, determinism, and actual-candidate forward-sanity validation.

## Required narrow cleanup — NO RERUN

Only documentation/comment consistency changes are authorized:

1. In the packet full-period table, replace stale Sortino values with the canonical artifact values:
   - M1 `1.752721` (not `1.682`)
   - M2 `1.675018` (not `1.584`)
   - M3 `1.624766` (not `1.517`).
2. Normalize criterion-6 worst-degradation summaries to the corrected artifact values everywhere in the packet/approval record:
   - M1 `-0.020451` = about `-2.05 ppt`
   - M2 `-0.025159` = about `-2.52 ppt`
   - M3 `-0.029931` = about `-2.99 ppt`.
   Remove stale values such as `-2.51/-2.53/-2.61` or `-2.06/-2.53/-3.01` where they purport to be canonical.
3. Rename the `2026 H1` row to `2026 YTD through 2026-08-07` (or simply `2026` segment). The evaluated segment extends beyond H1.
4. Clarify the full-period table turnover column. Prefer canonical total-NAV mean turnover values because criterion 7 is defined on that basis: M0 `0.011407`, M1 `0.012455`, M2 `0.012929`, M3 `0.013006`. If sleeve turnover is retained, label it explicitly and show total-NAV turnover separately.
5. In `src/china_etf/risk/risk_overlay.py`, remove the stale docstring claim that production `KKT` failure is checked. The implementation correctly uses `result.success`, final feasibility checks, and independent analytic projection tests; there is no production KKT residual. This is comment-only cleanup; do not change solver behavior.
6. Preserve the corrected result artifacts and all economic outputs unchanged. No new backtest/rerun, no candidate/cap/window/threshold/solver change, and no result-informed tuning.

## Authorized next

Only:

`POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_RUN_DOC_CLEANUP`

This is documentation/source-comment consistency cleanup only. It must not regenerate or alter the canonical result artifacts.

## Forbidden next

- CAPITAL_EFFICIENCY_RERUN
- NEW_BACKTEST
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

The prior `03110.HK` execution-realism structural STOP remains separate and closed. M2 is accepted here only as a historical capital-efficiency principal challenger; it is not yet an executable/live-ready strategy.
