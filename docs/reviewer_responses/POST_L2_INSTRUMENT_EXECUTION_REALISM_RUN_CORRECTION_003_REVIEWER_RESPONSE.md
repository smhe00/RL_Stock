# ChatGPT Reviewer Response — POST_L2 Instrument Execution Realism RUN CORRECTION_003

- handoff_id: `G4_POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN_CORRECTION_003`
- reviewed packet commit: `7dfabcd8b1e87a462cfa6482b43d7101e00a82f5`
- reviewed implementation commit: `aabe0ca30aa9522ad34c682e49155d6cd6c18c4b`
- decision: **EXECUTION_REALISM_RUN_CORRECTION_003_ACCEPTED_STOP_CONFIRMED**
- reviewer state: **BLOCKED**

## Decision

CORRECTION_003 is accepted as a sufficiently faithful execution-realism result for the frozen experiment. The experiment itself does **not** pass: frozen S3 remains a hard STOP, so no forward/paper/live gate is authorized.

Accepted executable result:

- cumulative return: `+47.21%`
- calendar CAGR: `+9.74%`
- Sharpe: `1.738`
- MaxDD: `-4.24%`
- S1: PASS; worst matched annual/stress degradation `-0.70pct` (well inside `-5pct` threshold)
- S2: PASS; fee `4.457bp`, spread+slippage `3.000bp` of traded notional
- S3: FAIL; `478/1011 = 47.28%` distinct fail-closed days
- S4: N/A in historical backtest
- STOP: TRUE

## Why CORRECTION_003 is accepted

1. `03110.HK` now has an actual executable path. Raw HKD open/close data are retained, CNY sizing/accounting marks use frozen T-1 HKD/CNY, and Southbound cost calculation receives local HKD price, transaction date and T-1 `fx_to_base`. The eligible-period Southbound path is exercised: 217 attempted orders, 217 fills, about CNY 735.8k traded notional.
2. MaxDiv target weights are bound to the accepted L1 raw artifact and match the accepted post-risk path across all `1011 x 11` observations with zero reported max absolute difference.
3. S1 is now matched segment-by-segment against the accepted L1 research artifact rather than reusing full-period CAGR. Calendar-year and frozen stress-period day counts match the L1 artifact.
4. S3 now uses the frozen distinct-day union: 461 structural-ineligibility days union 18 no-quote days, with one overlap, yielding 478 distinct fail-closed days.
5. Corporate actions are applied before open sizing/execution in the canonical settle -> unit conversion -> accrual sequence using pre-open holdings.
6. HK sell receivables use the 03110 tradable-session calendar for T+2 rather than calendar days or the SH execution index.
7. Provenance now hashes the actually consumed local price/FX/corporate-action inputs and binds both accepted L1 results/raw artifacts by SHA256. Tests include deterministic behavioral assertions for the corrected failure modes; 21 tests passed.
8. PPO/SAC/TD3 remain absent and no result-informed mapping/window/threshold change was introduced.

## STOP interpretation

The failure is structural, not a profitability or transaction-cost failure. S1 and S2 pass, and the executable net path remains close to the accepted L1 research MaxDiv path. The blocker is that the frozen experiment maps `HK_DIVIDEND` to `03110.HK` over a 2022-06 to 2026-08 evaluation window even though Southbound eligibility starts only on `2024-05-06`. The frozen counting rule therefore records 461 structural pre-eligibility decision days before considering ordinary missing-quote days. This alone is far above the 1% S3 threshold.

This review does **not** authorize changing the mapping, eligibility date, denominator, evaluation window or S3 threshold after seeing the result. Any alternative universe/window treatment is a new research design and requires a fresh PREP review.

## Authorized next

Only:

`POST_L2_INSTRUMENT_EXECUTION_REALISM_STOP_CLOSEOUT`

The closeout is documentation/decision synthesis only. It should freeze this result as a valid STOP, separate (a) economic performance findings from (b) structural eligibility failure, and enumerate possible future research branches without executing or selecting them. No new backtest/run is authorized under the closeout.

## Forbidden next

- FORWARD_PAPER_VALIDATION
- PAPER
- LIVE
- QMT_LIVE
- RESULT_INFORMED_INSTRUMENT_SUBSTITUTION
- RESULT_INFORMED_WINDOW_CHANGE
- RESULT_INFORMED_STOP_THRESHOLD_CHANGE
- DENSE_ALPHA_SEARCH
- DYNAMIC_ALPHA
- PPO
- SAC
- TD3
- RL_RETRAINING
- RL_HYPERPARAMETER_TUNING
- RL_COMPARISON

PPO/SAC/TD3 remain closed unless the user explicitly reopens them.
