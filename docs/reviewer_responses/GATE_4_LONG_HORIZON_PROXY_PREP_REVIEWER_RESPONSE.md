# Reviewer Response — Gate 4 Long-Horizon Proxy PREP

```yaml
handoff_id: G4_LONG_HORIZON_PROXY_PREP_001
reviewed_packet_commit: 41ce4dd36ac1264a28755b2f46cd4c97d895e5df
reviewed_packet: docs/review_packets/GATE_4_LONG_HORIZON_PROXY_PREP.md
decision: PREP_REVISIONS_REQUIRED_L2_RUN_NOT_AUTHORIZED
reviewer_state: REVISIONS_REQUIRED
authorized_next:
  - GATE_4_LONG_HORIZON_PROXY_PREP_FIX
forbidden_next:
  - GATE_4_LONG_HORIZON_PROXY_RUN
  - L2_PROXY_SCENARIO_EXECUTION
  - PPO
  - SAC
  - TD3
  - RL_RETRAINING
  - RL_HYPERPARAMETER_TUNING
  - RL_COMPARISON
  - QMT_LIVE
```

## Review conclusion

The PREP has the right high-level direction and achieves the intended historical breadth: approximately 2015-2026, explicit `SCENARIO_NOT_STRICT_PIT_OOS` labeling, the same six deterministic methods and canonical parameters, pre-frozen regime reporting, provenance fields, and no L2 execution. The proposed 2015-01-28 through 2026-08-07 span would cover the major bull/bear regimes that L1 cannot cover.

However, the current proxy contract contains several design choices that can materially change the relative ranking of EqualWeight, MaximumDiversification, RiskParity, MinimumVariance, and Momentum. L2 execution is therefore not authorized yet.

## Required PREP revisions

### 1. Do not duplicate CHINEXT as the STAR proxy for 2015-2019

The current contract maps both `CHINEXT` and `STAR` to the same `399006.SZ` ChiNext series before 2020. This is not merely basis risk: it duplicates one economic return stream as two separate portfolio slots for almost five years.

That would mechanically double-count the same growth factor in EqualWeight, distort covariance/risk-budget methods, and can alter MaximumDiversification weights simply because one risk exposure appears twice in the universe.

Required resolution, in priority order:

1. Probe QMT/approved public sources for a distinct pre-2020 China technology/innovation/growth proxy with defensible STAR-like exposure and freeze it with provenance; or
2. if no defensible distinct proxy exists, return an explicit alternative design for review (for example a later common start, or another clearly distinct scenario proxy).

Do **not** run L2 with two slots sharing the exact same multi-year return series. Any proposed substitute must remain fixed before seeing strategy results.

### 2. CASH_LIKE must be genuinely cash-like

The current `CASH_LIKE` construction uses a 2-year Treasury yield with approximately 1.8-year duration price P&L plus carry. That behaves as a short-duration bond, not as cash/money-market exposure, especially during rising-rate regimes.

Because MaxDiv and other risk allocators may concentrate in the lowest-volatility slot, this proxy can materially affect the headline drawdown result.

Required resolution:

- Main `CASH_LIKE` proxy should be carry-dominated with near-zero duration exposure: SHIBOR/repo/short-rate/very-short sovereign carry or an equivalent auditable series.
- If SHIBOR only begins in 2015-05, either define a pre-frozen bridge for the first months, find an earlier short-rate source, or move the common start and re-derive the window.
- A 2-year-duration version may remain only as a labeled sensitivity, not the primary CASH_LIKE series.

`CN_DURATION` may continue to use a 10Y yield-derived duration proxy if the exact duration/carry formula is frozen and tested.

### 3. Freeze a consistent equity return convention before the run

The current panel mixes price-return equity indices (`000300`, `000852`, `000015`, ChiNext/STAR, HSI/HSCEI) with total-return-adjusted real ETF history for `US_BROAD` and `GOLD`. Gold has no dividend issue, but the equity mismatch is material, especially for the `CN_DIVIDEND` slot.

Before L2 execution, PREP must choose and freeze one defensible convention. Preferred order:

1. Probe for total-return / net-total-return index variants or other auditable total-return proxy series; or
2. if full TR coverage cannot be obtained, define a deliberately uniform price-return research panel for equity slots and clearly separate any income-aware sensitivity; or
3. propose another fixed, auditable dividend/reinvestment augmentation method before results are seen.

Do not leave dividend augmentation as an optional post-result sensitivity. The main panel's return basis must be fixed ex ante and the basis must be documented per slot.

### 4. Clarify market-time availability and next-period return timing

The current text says unified Shanghai calendar, same-date HSI/HSCEI data, `T close decision -> T+1 execution`, and close-to-close proxy returns. These statements are not yet a single unambiguous causal timeline.

In particular, Hong Kong closes after Shanghai, so same-calendar-day HK close cannot be treated as information available at a Shanghai 15:00 decision timestamp. Also, a close-to-close return from T to T+1 contains return before a T+1-open execution.

Freeze one explicit causal convention, for example:

- information cutoff after all relevant Asian market closes on date T, with weights effective only on the next allowed return interval; or
- lag HK/FX inputs so all features are known by the chosen Shanghai decision cutoff; and
- if only close-to-close proxy returns are used, shift target weights so they apply only to a return interval that begins after the signal is observable, rather than claiming T+1-open execution without open data.

The runner/tests must enforce this alignment. If the corrected timing changes the first/last usable date or count, re-derive and re-freeze the window; do not preserve `2801` by assumption.

## Accepted elements that should remain frozen

- Track C / `SCENARIO_NOT_STRICT_PIT_OOS` labeling.
- Same six rows: HS300_ref, EqualWeight, MaximumDiversification, MinimumVariance, RiskParity_IVOL, Momentum_12_1.
- Canonical parameters: MaxDiv 120/0.5, MinVar 120/0.5, RiskParity 60, Momentum 252/21.
- No result-informed tuning or method additions.
- Annual plus pre-frozen event-defined sub-period reporting.
- Main research-return table separated from any cost sensitivity.
- Weight/concentration diagnostics and leave-one-slot-out diagnostics if practical.
- PPO/SAC/TD3 remain excluded.
- L1 artifacts/results remain frozen.

## Required handoff

Return a documentation/PREP revision only, suggested handoff:

`G4_LONG_HORIZON_PROXY_PREP_FIX_001`

Update `docs/review_packets/GATE_4_LONG_HORIZON_PROXY_PREP.md` with:

1. corrected STAR pre-2020 mapping without exact duplicate CHINEXT history;
2. corrected primary CASH_LIKE proxy;
3. frozen return-basis convention for every slot;
4. exact causal information/execution/return timeline;
5. re-derived window and expected day count if any of the above changes it;
6. updated provenance and tests/invariants.

Do not execute the L2 horse race until this revised PREP is reviewed and explicitly approved.
