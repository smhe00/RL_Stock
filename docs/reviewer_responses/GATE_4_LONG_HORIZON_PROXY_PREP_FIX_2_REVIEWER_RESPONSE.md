# Reviewer Response — Gate 4 Long-Horizon Proxy PREP FIX 2

```yaml
handoff_id: G4_LONG_HORIZON_PROXY_PREP_FIX_002
reviewed_packet_commit: 520a44e4229f4e7ea7110f2e5bf5a66735bd2409
reviewed_packet: docs/review_packets/GATE_4_LONG_HORIZON_PROXY_PREP.md
decision: PREP_FIX_2_ACCEPTED_L2_PROXY_RUN_AUTHORIZED
reviewer_state: REVIEW_COMPLETE
authorized_next:
  - GATE_4_LONG_HORIZON_PROXY_RUN
forbidden_next:
  - PPO
  - SAC
  - TD3
  - RL_RETRAINING
  - RL_HYPERPARAMETER_TUNING
  - RL_COMPARISON
  - QMT_LIVE
```

## Review conclusion

PREP_FIX_002 is accepted. The final numerical and timing ambiguities identified in the prior review are now explicitly frozen before any L2 result is observed.

Accepted final corrections:

1. `CN_DURATION` is unit-safe and defined in return space:
   - `y_decimal = y_percent / 100`;
   - `delta_y` is a decimal yield change;
   - +10 bp is `+0.0010`, so with `D_eff=7.5` the pure duration contribution is approximately `-0.75%` before carry;
   - carry is a calendar-day-scaled return contribution, not an additive price-level constant;
   - missing yield dates are forward-filled before differencing.
2. HKD/CNY follows the same conservative information-availability rule as Hong Kong inputs: decision date `T` uses `T-1` FX.
3. The previously accepted corrections remain frozen: STAR uses distinct `000986` rather than duplicating CHINEXT; CASH_LIKE is carry-only/near-zero-duration; the primary panel uses a uniform price-return convention; non-A-share inputs are conservatively lagged; the common window is re-derived rather than assumed.

The L2 proxy scenario run is therefore authorized.

## Frozen L2 contract

Label: `LONG_HORIZON_PROXY_SCENARIO_DIAGNOSTIC` / `SCENARIO_NOT_STRICT_PIT_OOS`.

Window must be derived from loaded data and then fail-closed against the frozen contract:

- decision start: `2015-01-28`;
- first assigned research-return interval: `2015-01-28 -> 2015-01-29`;
- last decision: `2026-08-06`;
- last assigned interval ends: `2026-08-07`;
- expected decision/return intervals: `2800`.

If actual source coverage, lagging, calendar alignment, or data quality causes any mismatch, stop and return a blocker. Do not silently shorten or alter the window.

## Frozen method set and parameters

Exactly these six rows:

1. HS300_ref
2. EqualWeight
3. MaximumDiversification
4. MinimumVariance
5. RiskParity_IVOL
6. Momentum_12_1

Canonical parameters remain unchanged:

- MaxDiv: lookback 120, shrinkage 0.5;
- MinVar: lookback 120, shrinkage 0.5;
- RiskParity_IVOL: lookback 60;
- Momentum_12_1: lookback 252, skip 21.

No tuning, method additions/removals, proxy substitutions, regime-boundary changes, or result-informed fixes are authorized after results are observed.

## Required implementation/run guards

Before the full run:

1. Implement the frozen proxy panel and provenance metadata exactly as reviewed.
2. `tests/test_long_horizon_proxy.py` must pass, including:
   - STAR/CHINEXT distinct-series assertion;
   - CASH_LIKE carry-only / no duration-price P&L assertion;
   - CN_DURATION `/100` unit normalization and +10 bp synthetic test;
   - ffill-before-yield-difference behavior;
   - A-share/rates T versus HK/US/GOLD/FX T-1 information timing;
   - no-future-data rolling lookbacks;
   - six-method/canonical-parameter freeze;
   - `SCENARIO_NOT_STRICT_PIT_OOS` label enforcement;
   - 2800-interval fail-closed parity;
   - no PPO/SAC/TD3 path.
3. `scripts/gate4_long_horizon_proxy.py --check` must pass before full execution.
4. Any invariant failure is a stop condition. Do not repair data or change a proxy after seeing strategy performance without a new reviewer handoff.

## Required L2 result packet

Return `docs/review_packets/GATE_4_LONG_HORIZON_PROXY_RUN.md` with a new unique handoff (suggested `G4_LONG_HORIZON_PROXY_RUN_001`) and include:

- implementation/result commit SHA;
- exact source files, providers, fetch dates, coverage, backfill flags, and proxy mapping actually used;
- exact derived window and 2800-day parity evidence;
- test output and `--check` output;
- explicit `SCENARIO_NOT_STRICT_PIT_OOS` statement;
- primary no-cost research-return results for all six rows: cumulative return, active-day annualized return, calendar CAGR, annualized volatility, Sharpe, Sortino, MaxDD, Calmar, worst calendar year, worst rolling 12m, turnover where meaningful, concentration/HHI;
- annual Sharpe/MaxDD for 2015-2026 and all pre-frozen event-defined subperiods;
- average and maximum slot weights, especially GOLD, CN_DURATION, CASH_LIKE and technology proxies;
- STAR proxy calibration against 科创50 for the overlapping post-2020 period;
- 1x project-cost sensitivity clearly separated from the non-executable research-return main table;
- leave-one-slot-out diagnostics if implemented straightforwardly; if omitted, state why rather than introducing a new diagnostic after seeing results;
- any income-aware/TR sensitivity only if its construction was fixed without looking at strategy results; otherwise omit it and disclose that the primary panel is price-return;
- comparison against L1 MaxDiv (Sharpe ~1.655, MaxDD ~-4.0%) only as historical context, not as a GO threshold.

## Interpretation target

The result review will focus on structural robustness rather than reproduction of any exact historical Sharpe. In particular:

- Does MaxDiv retain a meaningful Sharpe advantage versus EqualWeight, RiskParity and Momentum across ~11.5 years?
- Does it retain materially lower MaxDD in 2015 crash, 2018, COVID, and 2021-2023 weakness?
- Is lower risk purchased at an excessive CAGR penalty?
- Is the result dominated by CASH_LIKE, GOLD, CN_DURATION, or one proxy mapping?
- Does the allocation remain economically interpretable across regimes?

L2 is scenario/method research, not strict PIT OOS and not a live-trading authorization. L1 remains frozen. PPO/SAC/TD3 remain excluded.
