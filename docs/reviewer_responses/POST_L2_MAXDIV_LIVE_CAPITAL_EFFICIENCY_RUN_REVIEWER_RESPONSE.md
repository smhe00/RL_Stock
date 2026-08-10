# ChatGPT Reviewer Response — POST_L2 MaxDiv Live Capital Efficiency RUN

- handoff_id: `G4_POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_RUN_001`
- implementation/code commit: `675f1eea5ea63397ae2d6e312eab282c17c7968e`
- result/packet commit: `8bda08aba97ba0b43821fa672599dd331585709a`
- packet: `docs/review_packets/POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_RUN.md`
- decision: **MAXDIV_LIVE_CAPITAL_EFFICIENCY_RUN_PROVISIONAL_ECONOMICS_PROMISING_MECHANICAL_CORRECTION_REQUIRED**
- reviewer state: **REVISIONS_REQUIRED**

## Decision

The pre-registered capital-efficiency hypothesis is economically promising, and the primary historical candidate metrics are directionally strong: M1/M2 materially raise CAGR while keeping MaxDD below the frozen 12% limit, M2 remains the pre-designated principal challenger, and M3 correctly fails the frozen Sharpe >= 1.20 screen. M0 all-1011x11 target parity is exactly zero and the core full-period M0 metrics match accepted L1.

However, this RUN cannot yet be accepted as canonical. Several implementation/artifact/reporting defects violate the frozen PREP contract or make required outputs internally inconsistent. These are mechanical corrections only. They do **not** authorize cap changes, parameter retuning, a new candidate, expected-return optimization, or any result-informed search.

The current economics are therefore **provisional, not rejected**. Correct the mechanics and rerun the exact same M0-M3 experiment once.

## What passed / appears scientifically useful

1. MaxDiv core remains frozen at lookback 120 / shrinkage 0.5; no expected-return optimizer, momentum blend, dense/dynamic alpha, or RL path is introduced.
2. Candidate caps remain exactly the pre-registered M0/M1/M2/M3 values; M2 remains principal by design.
3. M0 target-path parity passes exactly: `max|diff| = 0.0 <= 1e-9` over `1011 x 11` weights.
4. Full-period primary economics are promising and should be preserved as provisional reference values pending the mechanical rerun:
   - M0: CAGR 9.415%, Sharpe 1.655, MaxDD -4.017%.
   - M1: CAGR 11.263%, Sharpe 1.282, MaxDD -6.811%.
   - M2 principal: CAGR 11.644%, Sharpe 1.219, MaxDD -7.665%.
   - M3: CAGR 12.148%, Sharpe 1.179, MaxDD -8.461%; fails pre-registered Sharpe >=1.20.
5. The capital-efficiency tradeoff is qualitatively coherent: reducing defensive allocation raises CAGR while increasing drawdown magnitude and reducing Sharpe.
6. SLSQP `result.success` is checked fail-closed, final simultaneous feasibility checks exist, deterministic/analytic projection tests exist, and Python/NumPy/SciPy versions are recorded.
7. The old `03110.HK` execution-realism STOP is not silently repaired or treated as live-ready.

## Required mechanical corrections

### 1. Restore the frozen SLSQP initialization

The accepted PREP froze the M1-M3 joint Euclidean projection with **bounded-simplex waterfill initialization**. The implementation instead calls SLSQP with `x0=v.copy()`.

Fix `RiskOverlayCE.apply()` so the SLSQP initial point is the pre-frozen bounded-simplex waterfill point under the per-slot caps, not the raw vector. Keep the same objective, method, caps, group constraints, `max_iter=200`, `ftol=1e-12`, feasibility tolerance, and no-fallback rule.

Because the objective is convex and the current runs converged, this correction may leave weights unchanged, but the run must still be regenerated from the contract-compliant implementation commit.

### 2. Fix forward sanity: sleeve weights are currently passed as total-NAV weights

`_forward_sanity()` is documented to accept actual latest **total-NAV** weights. In `main()`, it is called with `c["sleeve_w"][-1]` for every candidate. For M1-M3 this overstates strategic CASH_LIKE/CN_DURATION by `1/0.95`.

The artifact exposes the error directly:
- M1 reports `defensive_w=0.313158` despite the frozen total defensive cap being 0.30.
- M2 reports `defensive_w=0.260526` despite the frozen cap being 0.25.
- M3 reports `defensive_w=0.207895` despite the frozen cap being 0.20.

Call forward sanity with the actual latest total-NAV slot weights (`0.95 * sleeve_w` for M1-M3, or the already constructed `total_w`). Add an end-to-end test that the forward-sanity defensive weight equals `op_cash + latest_total_nav[CASH_LIKE] + latest_total_nav[CN_DURATION]` from the actual candidate run/artifact, not merely a synthetic unit test.

Using the same 1.4% cash planning assumption and 1.7114% duration snapshot, rough corrected 8% target checks should be approximately:
- M0: 14.44% required risk-sleeve return (unchanged)
- M1: 10.74%
- M2: 10.14%
- M3: 9.59%

These are reviewer sanity anchors only; the corrected artifact is canonical after rerun.

### 3. Fix raw artifact weight semantics

`gate4_maxdiv_capital_efficiency_raw.json` currently writes:

`"total_weights": {name: c["sleeve_w"].tolist() ...}`

For M1-M3 these are **sleeve-normalized weights summing to 1.0**, not total-NAV slot weights summing to 0.95. This is dangerous for the later execution study.

Write two explicit fields:
- `sleeve_weights`: optimizer/sleeve weights, sum = 1.0;
- `total_nav_slot_weights`: slot weights after multiplying by sleeve fraction, sum = 0.95 for M1-M3 and 1.0 for M0.

Keep `op_cash` separately explicit so total NAV reconstructs to 1.0. Do not label sleeve weights as total weights.

### 4. Make turnover / traded notional / cost reporting consistent with total NAV

M1-M3 total portfolio returns are correctly formed as `0.95 * env_ret + 0.05 * cash_ret`, but reported `mean_turnover`, `traded_notional`, and `total_cost` are copied from the full-sized sleeve simulation without the 0.95 total-NAV scaling.

Under the frozen rule that operational cash contributes zero turnover, report both if useful, but distinguish them:
- sleeve-normalized turnover/notional/cost;
- total-NAV-normalized turnover/notional/cost = sleeve value * 0.95 for M1-M3.

The pre-registered criterion 7 should use the consistently defined **total-NAV turnover proxy**. This correction is expected to be conservative and should not turn a current pass into a fail, but it must be explicit and test-covered.

### 5. Remove the tautological viability criterion-8 flag

The runner sets:

`c["parity_ok"] = (name == "M0") or True`

which is always `True`. Consequently candidate criterion 8 (`tests / provenance / parity`) is not actually derived from run validity.

Replace this with explicit run-level validity evidence. At minimum bind criterion 8 to:
- M0 reference parity PASS;
- all required behavioral tests PASS / `--check` PASS recorded for the exact implementation commit;
- required provenance bindings present and matching the frozen L1 hashes;
- no candidate SLSQP/feasibility failure during the run.

Do not encode an unconditional `True` in the scientific screening logic.

### 6. Use the frozen matched **calendar CAGR** semantics for criterion 6

Criterion 6 is defined as minimum matched CAGR degradation across the 5 calendar-year segments plus 2 frozen stress segments. The current implementation recomputes `_cagr_of()` using `252/n` active-day annualization rather than using each segment's already computed `calendar_cagr`.

Use the exact matched `subperiods[...]["calendar_cagr"]` values for candidate minus M0. Recompute all 7 segment degradations and the minimum. Current margins are sufficiently far from -5ppt that the viability classification is likely unchanged, but the canonical numbers must use the frozen semantic.

### 7. Fix `worst_calendar_year_return`

`_compute_metrics()` constructs an equity curve and then computes each yearly return as `last_equity / first_equity - 1`, which drops the first return observation of each year.

This already breaks claimed M0 metric parity: the accepted L1 worst-year return is about `-0.003933`, while the new artifact reports `-0.006839` even though the same M0 return path is being used.

Compute each calendar-year return by compounding **all returns in that calendar year**, e.g. `prod(1+r)-1`. Add a direct M0 assertion against the accepted L1 worst-calendar-year return and ensure all required full metrics are actually parity-consistent, not just CAGR/Sharpe/MaxDD.

### 8. Regenerate the packet annual/stress table from the canonical result artifact

The packet's Section 7 annual/stress table is not consistent with `gate4_maxdiv_capital_efficiency_results.json`. Example: the packet reports M1 2022 as about `+1.1%`, while the result artifact reports M1 2022 calendar CAGR about `-2.75%`; the packet also materially understates several later-year challenger returns.

Do not hand-copy or use a second formula path. Generate/report the table directly from the corrected canonical result artifact using the frozen calendar-CAGR definition. The packet and artifact must agree exactly up to display rounding.

### 9. Tighten forward-yield provenance presentation

The result contains the SHA256 of `data/qmt/proxy/CN_DURATION_CN10Y_yield.csv`, but the file is not present in the GitHub repository, so the reviewer cannot inspect its dated row/source from GitHub.

For the corrected run, embed in the result manifest the exact snapshot metadata used by forward sanity: observation date, value, source label/method, local path, and SHA256. This is audit-only and must not change the historical optimizer or candidate selection.

### 10. Do not claim a production KKT check unless one exists

The code/docstring/status say `KKT + feasibility fail-closed`, while production `RiskOverlayCE.apply()` currently performs solver-success + final feasibility checks but no direct KKT residual. The accepted reviewer contract allowed independent analytic minimum-distance tests as the optimality proof path.

Either implement a non-circular direct optimality/KKT residual, or change the run documentation to state accurately that optimality is guarded by the frozen independent analytic/reference projection tests plus production solver-success/feasibility checks. Do not claim a check that is not executed.

## Required correction rerun

Authorized correction must:

1. change only the mechanical items above;
2. preserve M0-M3 caps exactly;
3. preserve MaxDiv 120/0.5, same 1011-day window, same data path and L1 causal/cost/CA semantics;
4. preserve M2 as principal challenger;
5. rerun all M0-M3 once after tests pass;
6. return exact code commit, exact result/packet commit, test count, corrected artifacts and provenance;
7. report whether any of the primary economics or viability classifications changed from the provisional RUN.

If corrected M0 parity fails, any SLSQP candidate fails, or the corrected outputs materially change the scientific conclusion, stop and return for review; do not tune/fallback.

## Authorized next

Only:

`POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_RUN_CORRECTION`

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

The prior 03110 execution-realism STOP remains closed and unchanged. PPO/SAC/TD3 remain closed unless the user explicitly reopens them.
