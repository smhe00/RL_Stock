# Reviewer Response — Gate 4 Long-Horizon Proxy PREP FIX

```yaml
handoff_id: G4_LONG_HORIZON_PROXY_PREP_FIX_001
reviewed_packet_commit: 89c549f868e1dbcaa4b197473c3b5dacba80121e
reviewed_packet: docs/review_packets/GATE_4_LONG_HORIZON_PROXY_PREP.md
decision: PREP_FIX_SUBSTANTIALLY_ACCEPTED_BOND_FORMULA_FIX_REQUIRED
reviewer_state: REVISIONS_REQUIRED
authorized_next:
  - GATE_4_LONG_HORIZON_PROXY_PREP_FIX_2
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

The four previously required design corrections are substantively accepted:

1. `STAR` no longer duplicates `CHINEXT`; the proposed `000986` technology proxy is a distinct continuous series and the prior exact double-counting problem is removed.
2. Primary `CASH_LIKE` is now carry-only / near-zero-duration, with SHIBOR O/N as the main series and a short pre-SHIBOR carry-only bridge; the 2Y duration-price version is demoted to sensitivity.
3. The main panel now uses a pre-frozen uniform price-return convention, with income-aware/TR treatment separated as sensitivity rather than mixed into the main cross-asset panel.
4. The cross-market information timeline is now materially clearer: Shanghai-close decision time, A-share/rates at T, non-A-share inputs conservatively lagged, and weights applied to the subsequent T->T+1 close-to-close research-return interval. The usable window is re-derived to 2800 decision intervals rather than preserving the previous count by assumption.

These changes address the material ranking distortions identified in the prior review. However, one numerical contract remains ambiguous enough to block the L2 run.

## Required final PREP correction — CN_DURATION unit-safe return formula

The packet currently states the 10Y duration proxy approximately as:

`P_t = P_{t-1} × exp(-D_eff × Δy_t) + carry`, with `D_eff = 7.5`.

This is not sufficiently specified for a frozen experiment because the source yield series is commonly represented in percentage units. If, for example, a change from 2.50 to 2.60 is interpreted as `Δy=0.10` instead of decimal `0.0010`, the duration shock is amplified by 100x. Also, adding a dimensionless carry return directly to a price level is dimensionally ambiguous.

Before L2 execution, freeze the primary CN_DURATION construction explicitly in return space with units. A suitable contract is:

```text
y_t_decimal = y_t_percent / 100
Δy_t = y_t_decimal - y_{t-1}_decimal
carry_t = y_{t-1}_decimal × Δcalendar_days / 365
log_return_t = -D_eff × Δy_t + carry_t
proxy_price_t = proxy_price_{t-1} × exp(log_return_t)
D_eff = 7.5
```

Equivalent first-order/simple-return notation is acceptable if mathematically explicit and tested, but the chosen formula must be frozen before results are observed.

Required invariants/tests:

- assert the raw yield unit and the `/100` normalization explicitly;
- synthetic test: a +10 bp yield move means `Δy = +0.0010`, not `+0.10`;
- with `D_eff=7.5`, the pure duration component for +10 bp should be approximately -0.75% before carry;
- carry must be a return contribution scaled by elapsed calendar days, not an additive price-level constant;
- no future yield enters the T decision or the T->T+1 assigned return;
- document how missing yield dates are forward-filled before computing `Δy`, so a multi-day gap is not accidentally treated as multiple independent shocks.

## Minor timing clarification to freeze in the same revision

For HKD/CNY conversion, use a value that is available under the same conservative timing rule as the Hong Kong proxy. If publication time is not proven available by the Shanghai T decision cutoff, lag the FX input consistently with the HK series. The test should enforce the chosen lag. This is a clarification of the accepted causal design, not a request to redesign the window unless the derived availability changes it.

## Accepted elements remain frozen

- `SCENARIO_NOT_STRICT_PIT_OOS` / Track C labeling.
- Window target remains approximately 2015-01-28 through 2026-08-07, subject only to fail-closed re-derivation after the final formula/timing clarification.
- Same six deterministic rows and canonical parameters.
- STAR=`000986` scenario proxy, no exact duplicate CHINEXT history.
- CASH_LIKE carry-only primary proxy.
- Uniform price-return main panel plus separately labeled income-aware sensitivity.
- Pre-frozen annual/event-regime reporting.
- Weight/concentration and leave-one-slot-out diagnostics if practical.
- No result-informed tuning or method additions.
- PPO/SAC/TD3 excluded; L1 remains frozen.

## Required handoff

Return a documentation/PREP-only revision, suggested handoff:

`G4_LONG_HORIZON_PROXY_PREP_FIX_002`

Update `docs/review_packets/GATE_4_LONG_HORIZON_PROXY_PREP.md` with the explicit unit-safe CN_DURATION formula, its tests/invariants, and the FX timing clarification. Do not execute L2 until this revision is reviewed and explicitly approved.
