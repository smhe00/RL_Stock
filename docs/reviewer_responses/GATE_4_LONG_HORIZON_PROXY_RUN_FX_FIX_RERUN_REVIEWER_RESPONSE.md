# Reviewer Response — Gate 4 Long-Horizon Proxy RUN FX FIX RERUN

```yaml
handoff_id: G4_LONG_HORIZON_PROXY_RUN_FX_FIX_RERUN_001
reviewed_implementation_commit: 7781800d4ce996a216aa1e08f1346504c2628b66
reviewed_result_commit: 97fc857e863a06e14035d996d0dc146d5ba576d0
reviewed_packet: docs/review_packets/GATE_4_LONG_HORIZON_PROXY_RUN.md
decision: L2_PROXY_SCENARIO_ACCEPTED_GATE4_LONG_HORIZON_CLOSED
reviewer_state: REVIEW_COMPLETE
authorized_next:
  - POST_L2_DETERMINISTIC_ARCHITECTURE_PREP
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

The FX-corrected final rerun is accepted. Gate 4 long-horizon deterministic proxy research is now closed.

The previously identified implementation issues have been resolved without changing the frozen experimental design:

1. signal and realized-return panels are separated;
2. lagged non-A-share information is used only for decision signals;
3. realized returns use the raw economic T->T+1 interval;
4. common `RiskOverlayV0` constraints are applied to all five executable deterministic methods;
5. CN_DURATION uses the frozen unit-safe return-space construction;
6. CASH_LIKE remains carry-only / near-zero-duration;
7. HK_TECH and HK_DIVIDEND are now converted into CNY economic levels with the repository's existing `load_fx_hkd_cny()` series before signal lagging;
8. the frozen 2800-interval window is preserved;
9. cost sensitivity, STAR calibration and raw reproducibility artifacts are populated;
10. PPO/SAC/TD3 remain absent.

No further L2 rerun is authorized or required.

## Accepted final L2 result

Label: `LONG_HORIZON_PROXY_SCENARIO_DIAGNOSTIC` / `SCENARIO_NOT_STRICT_PIT_OOS`.

Window:

- decision start: 2015-01-28;
- first research-return interval: 2015-01-28 -> 2015-01-29;
- last decision: 2026-08-06;
- last interval end: 2026-08-07;
- intervals: 2800.

Final primary no-cost scenario results:

| Method | Cum Return | Calendar CAGR | Active-day Ann. | Sharpe | MaxDD | Calmar |
|---|---:|---:|---:|---:|---:|---:|
| EqualWeight | +72.0% | +4.8% | +5.0% | 0.427 | -30.4% | 0.165 |
| MaximumDiversification | +94.6% | +6.0% | +6.2% | 1.024 | -10.4% | 0.595 |
| MinimumVariance | +65.0% | +4.4% | +4.6% | 0.459 | -25.4% | 0.182 |
| RiskParity_IVOL | +65.7% | +4.5% | +4.7% | 0.479 | -24.5% | 0.190 |
| Momentum_12_1 | +153.1% | +8.4% | +8.7% | 0.571 | -44.3% | 0.197 |
| HS300_ref | +33.2% | +2.5% | +2.6% | 0.228 | -46.7% | — |

Interpretation:

- MaximumDiversification is the strongest risk-adjusted deterministic allocator in the accepted L2 scenario. Its Sharpe remains above 1 with MaxDD around -10%, while the competing executable risk-based methods remain below 0.5 Sharpe and have materially deeper drawdowns.
- Momentum remains economically important despite its lower Sharpe. Its accepted L2 calendar CAGR is approximately 8.4% and its active-day annualized return approximately 8.7%, materially above MaxDiv, but this comes with roughly -44% MaxDD and much higher turnover/cost drag.
- These are different portfolio roles rather than a simple winner/loser relationship: MaxDiv is a credible risk-control/core-allocation candidate; Momentum is a credible long-horizon return-engine candidate.
- The accepted L2 evidence is sufficient to justify a subsequent deterministic architecture PREP, but not result-informed parameter tuning.

## Regime robustness accepted

MaximumDiversification retained materially lower drawdown through the pre-frozen stress periods:

- 2015 crash: MaxDD about -7.2%;
- 2018 bear/trade-war: about -4.8%;
- COVID shock: about -7.8%;
- 2021-2023 China-weak phase: about -10.4%, with cumulative return approximately +0.6%.

This is the main structural evidence supporting MaxDiv as a core allocator. The L1 real-instrument result remains frozen historical context and is not a GO threshold.

## Cost sensitivity accepted

The separate 1x project-cost sensitivity remains descriptive/non-executable because the long-horizon proxy panel is not itself an executable ETF history.

Notable accepted estimates:

- MaxDiv: cumulative-return impact about -1.3 percentage points; active-day annualized return about 6.18% gross vs 6.12% net approximation.
- Momentum: cumulative-return impact about -16.3 percentage points; active-day annualized return about 8.72% gross vs 8.08% net approximation.

This reinforces the distinction between low-turnover MaxDiv and higher-turnover Momentum.

## STAR proxy basis-risk warning

The post-2020 calibration remains an important limitation:

- `000986` versus 科创50 correlation: approximately 0.1475 over the reported overlap.

Therefore the STAR slot in Track C is a broad technology scenario proxy, not a close historical reconstruction of 科创50. This does not invalidate the full cross-asset L2 experiment, but any conclusion specifically attributed to the STAR sleeve must be treated cautiously.

No proxy replacement is authorized after seeing this result.

## Non-blocking documentation correction

The packet text describes the BOC quote direction once as `HKD 每 100 CNY`. The repository loader actually reads `中行折算价 / 100` via `load_fx_hkd_cny()`, consistent with a CNY-per-HKD conversion factor used elsewhere in the project (e.g. approximately 0.8-0.9 CNY per HKD).

Correct the wording in the next Claude-owned documentation update to state the quote direction unambiguously as equivalent CNY per 100 HKD (then `/100` -> CNY per HKD). This is documentation-only and does not require another rerun.

## Authorized next phase

`POST_L2_DETERMINISTIC_ARCHITECTURE_PREP` is authorized as a PREP-only phase.

Purpose:

- design, before seeing any new architecture results, a controlled study of how the accepted MaxDiv core and Momentum return engine could coexist;
- explicitly separate objectives such as terminal wealth, drawdown control, Sharpe/Calmar, turnover and implementation complexity;
- freeze candidate architecture(s), allocation rules and evaluation thresholds before any combined-strategy run;
- include a path toward instrument-level execution realism and forward/paper validation.

Do not optimize blend weights by searching the accepted L2 history. Any candidate mix ratios or dynamic-overlay rules must be proposed and frozen in PREP before a result run.

## Still not authorized

- PPO/SAC/TD3 or any RL reopening;
- RL tuning/comparison;
- QMT live trading;
- strategy changes inferred from the quarantined gen1/gen2 outputs;
- proxy substitutions based on observed L2 results.

Gate 4 long-horizon proxy research is closed with the FX-corrected gen3 result as the accepted L2 record.
