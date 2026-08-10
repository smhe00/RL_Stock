# ChatGPT Reviewer Authorization — Fresh MaxDiv Live Capital Efficiency PREP

- trigger: explicit user selection after the prior POST_L2 instrument execution-realism experiment was formally closed
- new research direction: deterministic long-horizon, live-oriented MaxDiv capital efficiency
- decision: **USER_SELECTED_FRESH_MAXDIV_LIVE_CAPITAL_EFFICIENCY_PREP_AUTHORIZED**
- scope: **PREP ONLY — no backtest/run/result generation yet**

## Research question

The accepted MaxDiv core is robust, but the latest target can place ~50% of NAV in `CASH_LIKE + CN_DURATION`, which is undesirable when current cash/bond forward yields are low. Test whether simple ex-ante capital-budget constraints can improve capital efficiency while preserving most of MaxDiv's robustness.

This is a new pre-registered study. It is NOT a modification/rerun of the closed execution-realism STOP experiment.

## Frozen strategy core

Do not retune the MaxDiv estimator:

- MaximumDiversification only
- lookback = 120
- shrinkage = 0.5
- same project-constrained / RiskOverlayV0 semantics as accepted L1
- deterministic only
- no Momentum blend
- no dense alpha / dynamic alpha
- no expected-return forecast inside the optimizer
- PPO/SAC/TD3 remain closed

The PREP must explicitly bind the exact accepted L1 reference artifacts/commits used for parity/reference.

## Research/execution separation

The previous execution-realism experiment is closed with a structural S3 STOP caused mainly by `HK_DIVIDEND -> 03110.HK` pre-eligibility. Do NOT silently fix or substitute that mapping here.

For this capital-efficiency concept study:

1. use the accepted L1 11 economic-slot research path as the primary historical reference;
2. do not claim that the stopped 11-instrument execution mapping is live-ready;
3. do not select a replacement ETF/universe in this PREP;
4. any executable-universe redesign must be a later separate fresh PREP after this concept is reviewed.

## Freeze four candidates before any RUN

All caps below are expressed as fractions of TOTAL NAV. Apart from the stated defensive-cap changes, preserve the existing per-risk-asset 25% cap and all other accepted MaxDiv semantics. PREP must show the exact constraint transformation used when the optimizer acts only on the investable sleeve.

### M0 — legacy control

- no external operational-cash sleeve
- current 11-slot MaxDiv
- `CASH_LIKE <= 25%`
- `CN_DURATION <= 25%`
- therefore defensive capital can reach 50%

M0 must reproduce the accepted L1 MaxDiv target path/metrics within deterministic tolerance before comparing challengers.

### M1 — light capital-efficiency constraint

- operational cash = fixed 5% of total NAV, held outside the optimizer
- strategic `CASH_LIKE <= 5%` of total NAV
- `CN_DURATION <= 20%` of total NAV
- `operational_cash + CASH_LIKE + CN_DURATION <= 30%` of total NAV
- remaining 95% investable sleeve stays MaxDiv 120/0.5 subject to the transformed total-NAV constraints

### M2 — principal challenger (pre-designated)

- operational cash = fixed 5% of total NAV, held outside the optimizer
- strategic `CASH_LIKE <= 5%` of total NAV
- `CN_DURATION <= 15%` of total NAV
- `operational_cash + CASH_LIKE + CN_DURATION <= 25%` of total NAV
- remaining 95% investable sleeve stays MaxDiv 120/0.5

M2 is the principal challenger by design, not because of any observed result. Do not retune these values after seeing results.

### M3 — aggressive capital-efficiency constraint

- operational cash = fixed 5% of total NAV
- strategic `CASH_LIKE = 0%`
- `CN_DURATION <= 15%` of total NAV
- `operational_cash + CASH_LIKE + CN_DURATION <= 20%` of total NAV
- remaining 95% investable sleeve stays MaxDiv 120/0.5

## Operational cash accounting

PREP must specify one deterministic historical accounting rule for the fixed operational-cash sleeve. Preferred default for historical comparability: use the already accepted `CASH_LIKE` research return series as the historical return proxy for the external operational-cash sleeve, while keeping the sleeve outside MaxDiv optimization.

For forward-looking sanity checks, keep the historical return proxy separate from the current cash-yield assumption. The current `1.4%` cash yield is a user-supplied planning assumption and must be labeled as such, not retroactively used to rewrite historical returns.

## No expected-return model in optimization

Do NOT introduce Black-Litterman, mean-variance expected returns, earnings-yield forecasts, tactical views, momentum forecasts, or discretionary expected-return inputs in this phase.

Forward-return work is audit-only, not an optimizer input.

## Required forward-return sanity audit

The PREP must freeze a transparent audit that answers whether a candidate can plausibly reach 7%, 8%, and 9% portfolio returns under today's low defensive yields.

At RUN time, freeze a dated assumption snapshot with source/provenance for:

- operational/strategic cash yield (user planning assumption currently 1.4%, clearly labeled)
- current CN_DURATION yield/YTM proxy from a documented source/snapshot

Do not invent equity expected returns. Instead calculate the required annual return of the residual risk-asset sleeve to reach each portfolio target:

`required_risk_return(T) = (T - defensive_carry_contribution) / risk_asset_weight`

Report this for T = 7%, 8%, 9% for M0-M3. This is a sanity diagnostic only.

## Historical evaluation plan to freeze in PREP

Primary evaluation must use the accepted L1 deterministic long-horizon window and exact causal semantics. No new data repair/backfill or result-informed window changes.

At minimum report for every M0-M3:

- cumulative return
- calendar CAGR
- active-day annualized return
- annualized volatility
- Sharpe
- Sortino
- MaxDD
- Calmar
- worst calendar year
- worst rolling 12m return
- calendar-year subperiod metrics
- accepted frozen stress/phase subperiod metrics
- turnover / traded-notional proxy consistent with the research path
- mean / median / p95 `operational_cash + CASH_LIKE + CN_DURATION`
- cap-hit rate for CASH_LIKE, CN_DURATION and aggregate defensive cap
- latest target allocation
- allocation time series suitable for later execution study

Add capital-efficiency diagnostics:

- `CE_current_hurdle = (historical_CAGR - current_cash_hurdle) / abs(MaxDD)` using the same frozen current cash hurdle for all candidates; label this as a cross-candidate diagnostic, not a stationary historical Sharpe replacement
- CAGR gained/lost per 10ppt reduction in average defensive allocation versus M0
- MaxDD increase per 10ppt reduction in average defensive allocation versus M0

## Pre-registered viability criteria

These are screening criteria for later execution study, not permission to select/tune a winner after results.

A constrained candidate is `HISTORICALLY_VIABLE_FOR_NEXT_PREP` only if ALL hold:

1. calendar CAGR >= 7.0%
2. Sharpe >= 1.20
3. MaxDD >= -12.0%
4. Calmar >= 0.70
5. CAGR is not worse than M0 by more than 0.5 percentage point
6. worst calendar-year or frozen-stress CAGR degradation versus M0 is not worse than -5 percentage points
7. turnover <= 1.5x M0
8. deterministic tests/provenance/parity all pass

M2 remains the principal challenger regardless of whether M1 or M3 looks better. The RUN must report all candidates and the Pareto tradeoff; no post-result cap search or intermediate cap values are allowed.

## Explicitly deferred dimensions

Do NOT combine these into the first capital-efficiency experiment:

- no-trade bands (1%/2%)
- minimum-trade threshold optimization
- 09:35/TWAP/passive execution policy
- alternative HK_DIVIDEND instrument mapping
- new universe construction
- dynamic defensive cap
- current-yield-aware tactical switching

These may be separate later gates only after the M0-M3 historical concept is reviewed.

## PREP deliverables

Claude should prepare a review packet only, with no experimental result generation, containing:

1. exact M0-M3 mathematical/implementation contract;
2. exact total-NAV vs investable-sleeve constraint transformation;
3. accepted L1 artifact/commit bindings and deterministic provenance plan;
4. operational-cash historical accounting rule;
5. forward-sanity assumption/source schema and formulas;
6. metrics, subperiods, viability thresholds and STOP/FAIL semantics;
7. planned source files/scripts/tests and behavioral regression tests;
8. explicit no-RL/no-alpha/no-retune statement;
9. explicit statement that current stopped execution-universe mapping is NOT being silently repaired or treated as live-ready.

Set a new unique Claude handoff_id, recommended:

`G4_POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_PREP_001`

and stop at `READY_FOR_REVIEW`.

## Authorized next

Only:

`POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_PREP`

## Forbidden until PREP review

- CAPITAL_EFFICIENCY_RUN
- NEW_BACKTEST
- EXECUTION_UNIVERSE_REDESIGN
- INSTRUMENT_SUBSTITUTION
- FORWARD_PAPER_VALIDATION
- PAPER
- LIVE
- QMT_LIVE
- RESULT_INFORMED_CAP_SEARCH
- RESULT_INFORMED_WINDOW_CHANGE
- EXPECTED_RETURN_OPTIMIZATION
- DENSE_ALPHA_SEARCH
- DYNAMIC_ALPHA
- PPO
- SAC
- TD3
- RL_RETRAINING
- RL_HYPERPARAMETER_TUNING
- RL_COMPARISON

PPO/SAC/TD3 remain closed unless the user explicitly reopens them.
