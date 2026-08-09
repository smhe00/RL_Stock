# Reviewer Response — Gate 4 Long-Horizon Proxy RUN FIX RERUN

```yaml
handoff_id: G4_LONG_HORIZON_PROXY_RUN_FIX_RERUN_001
reviewed_implementation_commit: aff4b341a4bed8f104b276947eff5232a984c037
reviewed_result_commit: 0c8b9b4500fe73488c9bce442e583a9d53337f77
reviewed_packet: docs/review_packets/GATE_4_LONG_HORIZON_PROXY_RUN.md
decision: FIX_RERUN_SUBSTANTIALLY_CORRECT_FX_CONVERSION_MISSING_FINAL_RERUN_REQUIRED
reviewer_state: REVISIONS_REQUIRED
authorized_next:
  - GATE_4_LONG_HORIZON_PROXY_RUN_FX_FIX_RERUN
forbidden_next:
  - ACCEPT_L2_RESULTS
  - STRATEGY_SELECTION_FROM_L2
  - PPO
  - SAC
  - TD3
  - RL_RETRAINING
  - RL_HYPERPARAMETER_TUNING
  - RL_COMPARISON
  - QMT_LIVE
```

## Review conclusion

The two blockers from the prior review are correctly fixed:

1. `signal_panel` and realized `return_levels` are now separated, so lagged non-A-share information is used for signals while realized returns are assigned from the raw T->T+1 economic interval.
2. `RiskOverlayV0` is now applied uniformly to all five executable deterministic methods. The corrected run reports zero post-overlay feasibility violations and removes the prior pathological 92-100% CASH_LIKE concentrations.

The corrected result is therefore materially more credible than the quarantined original run. Under this implementation, MaxDiv reports Sharpe ~1.012 and MaxDD ~-11.2%, remaining the strongest risk-adjusted executable deterministic method in the current scenario table.

However, the result still cannot be accepted as final L2 because one previously frozen data contract was never implemented: HKD->CNY conversion for the Hong Kong proxy slots.

## BLOCKER — frozen HKD/CNY conversion is absent from the implemented panel

The approved PREP explicitly froze the Hong Kong currency rule:

```text
FX: HKD->CNY uses hkd_cny_boc, daily ffill.
Decision T uses T-1 FX under the same conservative availability rule as HK inputs.
```

The current implementation does not load or apply `hkd_cny_boc` anywhere in `long_horizon_proxy_panel.py` or `gate4_long_horizon_proxy_fetch.py`.

`HK_TECH` and `HK_DIVIDEND` are therefore currently represented by raw HSI/HSCEI index-point levels only. Their signal history and realized returns omit HKD/CNY currency movement, even though the frozen experiment is a CNY-based cross-asset allocation panel.

This matters because FX changes affect:

- the realized CNY return of both Hong Kong slots;
- their rolling volatility and covariance versus mainland, gold, bond and US_BROAD exposures;
- risk-based target weights, especially MaxDiv / MinVar / RiskParity;
- long-horizon Sharpe, drawdown and regime attribution.

The omission is therefore material enough to require one final implementation-correctness rerun.

## Required correction

Implement the already-frozen currency convention without changing any other experiment dimension.

For both `HK_TECH` and `HK_DIVIDEND`:

```text
raw_hk_level_cny(t) = raw_hk_index_level_hkd(t) * hkd_cny(t)
```

where `hkd_cny(t)` must use the repository's existing `hkd_cny_boc` series with the frozen alignment/ffill convention.

Then preserve the signal/return separation already fixed:

```text
return_level_cny(T) = raw HK CNY-converted economic level at T
signal_level_cny(T) = return_level_cny(T-1)
realized return assigned to decision T = return_level_cny(T+1) / return_level_cny(T) - 1
```

If the stored FX quote is expressed in the inverse direction, normalize explicitly and document the transformation. Do not infer silently from column names.

## Required regression tests

Add tests that fail closed unless all are true:

1. HK return levels actually change when the FX series is perturbed while the HK index series is held fixed.
2. For a synthetic constant-HK-index case, HK CNY return equals the corresponding HKD/CNY FX return.
3. Decision T HK signal uses only T-1 CNY-converted level under the frozen timing rule.
4. Decision T realized return remains the CNY-converted T->T+1 interval.
5. The full 2800-interval parity remains exact after FX integration.
6. All five methods still satisfy the common RiskOverlay constraints with zero post-overlay violations.

## Accepted elements that must remain frozen

Do not change any of the following during this final correction:

- `SCENARIO_NOT_STRICT_PIT_OOS` / `LONG_HORIZON_PROXY_SCENARIO_DIAGNOSTIC` labeling;
- 11-slot proxy mapping;
- STAR = 000986 scenario proxy;
- CASH_LIKE carry-only construction;
- CN_DURATION D_eff=7.5 unit-safe formula;
- primary price-return convention;
- window 2015-01-28 through 2026-08-07 with exactly 2800 intervals;
- six comparison rows and canonical parameters;
- annual/regime boundaries;
- common `RiskOverlayV0` feasible set;
- signal-vs-realized-return panel separation;
- no PPO/SAC/TD3;
- L1 frozen results.

No proxy substitution, parameter change, method change, data-source substitution, regime change, or result-informed strategy adjustment is authorized.

## Result interpretation status

The current corrected numbers — MaxDiv Sharpe ~1.012 / MaxDD ~-11.2%, Momentum CAGR ~8.2% with MaxDD ~-44.3%, and the corrected MinVar/RP results — should be preserved as **quarantined corrected-run-v1 output**, not used as the final L2 conclusion.

The post-2020 `000986` vs 科创50 correlation of ~0.1475 is also an important basis-risk warning. It does not trigger a proxy change in this rerun because the proxy was frozen ex ante; it must remain prominently disclosed in the final interpretation.

## Required handoff

Suggested handoff:

`G4_LONG_HORIZON_PROXY_RUN_FX_FIX_RERUN_001`

Required sequence:

1. integrate the frozen HKD/CNY conversion into the two HK CNY economic return levels;
2. preserve T-1 signal lag and T->T+1 realized-return separation;
3. add FX-specific regression tests;
4. run the full test suite and `scripts/gate4_long_horizon_proxy.py --check`;
5. fail closed unless the window is exactly 2800 intervals and post-overlay violations are zero;
6. perform one final rerun with no other experimental changes;
7. update the result packet, cost sensitivity and raw artifact from that final rerun;
8. preserve both earlier result generations as quarantined history.

L2 remains open until this FX-corrected rerun is reviewed and explicitly accepted.