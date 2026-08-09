# Reviewer Response — Gate 4 Long-Horizon Proxy RUN

```yaml
handoff_id: G4_LONG_HORIZON_PROXY_RUN_001
reviewed_implementation_commit: 00d7f64c1a0a632a6a0c0232a194ad8a42877228
reviewed_result_commit: 538e6881472e8ae2ef7d061db7328e52ab249481
reviewed_packet: docs/review_packets/GATE_4_LONG_HORIZON_PROXY_RUN.md
decision: L2_RUN_RESULTS_QUARANTINED_IMPLEMENTATION_FIX_RERUN_REQUIRED
reviewer_state: REVISIONS_REQUIRED
authorized_next:
  - GATE_4_LONG_HORIZON_PROXY_RUN_FIX_RERUN
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

The L2 run completed the intended 2800-interval window and produced an internally coherent result artifact, but the reported strategy results are **not accepted** because the implementation violates two frozen execution contracts in ways that can materially alter strategy ranking, drawdown, and Sharpe.

The current numerical results — including MaxDiv Sharpe 1.183 / MaxDD -11.4% — must be treated as **quarantined diagnostic output only**. They may not be used as the final L2 robustness conclusion until the implementation is corrected and the same frozen experiment is rerun.

This is an implementation-correctness rerun, not authorization to tune methods, proxies, parameters, dates, regimes, or data after observing results.

## BLOCKER 1 — signal panel and realized-return panel are incorrectly conflated

The frozen contract is:

- decision date T uses A-share/rates information through T;
- HK/US/GOLD/FX signals are conservatively lagged to information available by T (T-1 source levels under the frozen convention);
- the target weight selected at T is assigned to the **subsequent T -> T+1 research-return interval**.

However, `build_panel()` shifts HK/US/GOLD price levels by one day and returns that lagged level panel. The runner then computes:

```python
ret_panel = panel.pct_change()
```

and uses `ret_panel` both for signal history and realized portfolio returns.

For a lagged slot:

```text
signal_panel(T)   = raw_price(T-1)
signal_panel(T+1) = raw_price(T)
ret_panel(T+1)    = raw_price(T) / raw_price(T-1) - 1
```

Therefore the return assigned to a weight chosen on decision date T is the source-market T-1 -> T return, not the frozen T -> T+1 return. Much of that return occurred before the T decision cutoff. This is a material timing/return-alignment error.

### Required correction

Separate the data structures explicitly:

1. `signal_panel`: decision-available levels used only for rolling covariance/volatility/momentum; lag HK/US/GOLD according to the frozen information rule.
2. `return_panel`: economic proxy levels/returns used for realized interval returns; do **not** inherit the signal lag. For decision T, the assigned return must correspond to the frozen raw T -> T+1 interval.

A-share/rates may share the same underlying level construction where timing permits, but signal availability and realized-return alignment must remain conceptually and programmatically separate.

### Required tests

Add a synthetic timing test that proves for a lagged slot:

- T weights are functions only of source data available through T-1;
- changing source price at T or T+1 cannot change the already-computed T weight;
- the realized return assigned to T weight is source `price(T+1)/price(T)-1`, not `price(T)/price(T-1)-1`.

`--check` must fail closed if signal and realized-return panels for a lagged slot are accidentally identical after the lag transformation.

## BLOCKER 2 — project RiskOverlay constraints are not applied uniformly to the horse race

The canonical baseline module explicitly states that deterministic baselines run through the standard environment path:

```text
target weight -> ActionTransform -> RiskOverlay -> execution
```

and `RiskOverlayV0` enforces the project constraints:

- long-only;
- sum = 1;
- single-core max = 25%;
- CHINEXT + STAR group max = 50%.

The L2 runner bypasses the environment and computes target weights directly in `ProxyPolicy`. After that it only clips to non-negative and normalizes to sum one. It does **not** apply `RiskOverlayV0` to every method.

This is directly visible in the reported results:

- MinimumVariance max single weight = 100.0%;
- RiskParity_IVOL max single weight = 97.2%;
- Momentum_12_1 max single weight = 84.1%;
- MaxDiv alone stays at 25% because its optimizer internally uses the project-constrained projection.

Therefore the comparison is not under a common feasible set. The packet's interpretation that MinVar/RP's pathological Sharpe is merely a mathematical consequence of the frozen CASH_LIKE proxy is incomplete: the near-zero-volatility proxy creates the attraction, but the **missing common RiskOverlay is what permits 92-100% concentration**, contrary to the standard project execution path.

### Required correction

After each method produces its normalized target vector and before assigning the interval return, apply the exact project overlay or an exact-equivalent projection:

```text
RiskOverlayV0(slots).apply(target_weights)
```

for **all five executable deterministic methods**, including EqualWeight, MaxDiv, MinVar, RiskParity, and Momentum.

MaxDiv should remain effectively unchanged if already feasible; the overlay must nevertheless be common and testable across all methods.

### Required tests

For every method across the full run:

- `sum(weights) == 1` within tolerance;
- each slot weight <= 0.25 + tolerance;
- CHINEXT + STAR <= 0.50 + tolerance;
- no negative weights;
- at least one synthetic case where unconstrained MinVar/RP/Momentum would exceed 25% and the overlay demonstrably projects it back into the project feasible set.

The rerun packet must report pre-overlay and post-overlay maximum violation counts (expected post-overlay violations = 0).

## RESULT-PACKET COMPLETENESS FIXES REQUIRED IN THE SAME RERUN

These are secondary to the two blocking implementation errors, but the rerun must also close them:

### 1. 1x cost sensitivity must contain numbers

The result artifact currently creates `cost_sensitivity` with only a descriptive note; no strategy-level numeric sensitivity is computed. The frozen PREP and run authorization required a separate 1x project-cost sensitivity.

Compute and report, for each deterministic strategy, at minimum:

- cumulative-return delta vs no-cost main table;
- annualized/CAGR delta;
- total estimated cost / initial capital or equivalent normalized cost;
- turnover basis used.

Keep it explicitly labeled non-executable / approximate.

### 2. STAR calibration must actually be computed

The result artifact currently records only a note that `000986 vs 科创50 post-2020` is to be reported. The run authorization required the overlapping-period calibration.

Compute and report the fixed post-2020 correlation (and date range / sample count). Do not change the STAR proxy after seeing it.

### 3. Raw artifact must be either populated or removed from claims

`artifacts/gate4_long_horizon_proxy_raw.json` currently contains only:

```json
{"methods": {}}
```

while the packet presents it as part of the result artifact set. Either populate it with the intended reproducibility payload (e.g. per-interval strategy returns/weights or the already-defined raw content contract), or stop claiming it as a substantive raw artifact. Do not silently leave an empty placeholder.

## Frozen items that must NOT change during rerun

The following remain frozen exactly as approved:

- label: `LONG_HORIZON_PROXY_SCENARIO_DIAGNOSTIC` / `SCENARIO_NOT_STRICT_PIT_OOS`;
- 11-slot proxy mapping;
- STAR = `000986` scenario proxy;
- CASH_LIKE carry-only construction;
- CN_DURATION unit-safe D_eff=7.5 formula;
- HKD/CNY conservative lag rule;
- primary price-return convention;
- decision window 2015-01-28 through 2026-08-06, ending 2026-08-07, expected 2800 intervals;
- six comparison rows;
- canonical parameters 120/0.5, 120/0.5, 60, 252/21;
- pre-frozen annual and event-defined regime boundaries;
- no PPO/SAC/TD3;
- L1 remains frozen.

No data-source substitution, proxy substitution, parameter adjustment, method addition/removal, regime change, or result-informed patch is authorized.

## Required rerun handoff

Suggested handoff:

`G4_LONG_HORIZON_PROXY_RUN_FIX_RERUN_001`

Required sequence:

1. Correct signal-vs-return panel separation.
2. Apply common `RiskOverlayV0` constraints to every executable deterministic method.
3. Add the timing and overlay regression tests above.
4. Run the full test suite and `scripts/gate4_long_horizon_proxy.py --check`.
5. Fail closed if the derived window is not exactly 2800 intervals.
6. Execute one corrected L2 rerun under the frozen contract.
7. Replace/update the L2 result packet with corrected results, numeric cost sensitivity, STAR calibration, and valid raw/reproducibility artifact handling.
8. Preserve the original 538e688/00d7f64 results as quarantined historical output; do not use them for strategy conclusions.
9. Stop at `READY_FOR_REVIEW`.

Until that corrected handoff is reviewed, L2 is **not closed**, no MaxDiv GO/NO-GO conclusion is authorized from the 1.183/-11.4% run, and no live-trading or RL next step is authorized.