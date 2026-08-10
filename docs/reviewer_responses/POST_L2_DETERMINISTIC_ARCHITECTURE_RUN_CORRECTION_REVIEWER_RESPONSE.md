# POST_L2 DETERMINISTIC ARCHITECTURE RUN CORRECTION — Reviewer Response

handoff_id: `G4_POST_L2_DETERMINISTIC_ARCH_RUN_CORRECTION_001`

reviewed_packet: `docs/review_packets/POST_L2_DETERMINISTIC_ARCHITECTURE_RUN.md`

packet_main_commit: `08c4775a8e6e3ca31e60fd111aebf6aea99d28f9`

code_commit: `1ca71bb006cd4f82de1e10c3042bbd73395833e1`

decision: `ARCH_RUN_CORRECTION_ACCEPTED_ARCHITECTURE_GATE_CLOSED_EXECUTION_REALISM_PREP_AUTHORIZED`

state: `REVIEW_COMPLETE`

## Reviewer checks

1. **Exact correction diff**
   - Relative to the immediately preceding reviewer-state commit `1311fe3250a08cf3f94783473633104fd1ff3115`, implementation commit `1ca71bb006cd4f82de1e10c3042bbd73395833e1` changes only:
     - `scripts/gate4_arch_blend.py`
     - `tests/test_arch_blend.py`
   - No candidate weights, parent parameters, panel construction, timing, FX, cost convention, stress-regime definition, thresholds, or upstream data/provenance code changed in the correction commit.

2. **R5 Pareto MaxDD direction fixed**
   - `dominates()` now treats all four dimensions `cum_return`, `calendar_cagr`, `sharpe`, `max_drawdown` as higher-is-better.
   - This correctly encodes `-0.10 > -0.20` for MaxDD.
   - Tolerance remains symmetric at `1e-9`; a candidate dominates only when all dimensions are non-worse and at least one is strictly better.

3. **Regression coverage added**
   - Synthetic dominance case verifies that a candidate with higher return/CAGR/Sharpe and better MaxDD dominates the inferior candidate, and not vice versa.
   - Synthetic trade-off case verifies that higher return but worse Sharpe/MaxDD is non-dominated relative to a lower-return, better-risk candidate.
   - Existing candidate-set, overlay, parent-parity, R1-R4, cost-path, and no-RL/no-dense-search tests remain present.

4. **Execution evidence**
   - Packet reports `pytest tests/test_arch_blend.py -q` -> `8 passed`.
   - Packet reports `python scripts/gate4_arch_blend.py --check` -> `PASSED`.
   - The reviewer independently inspected the relevant test/source logic; no remaining mechanical R5 defect was found.

5. **Artifact binding and rerun evidence**
   - `artifacts/gate4_arch_blend_results.json` manifest records `commit: 1ca71bb` and a post-fix run timestamp.
   - Frozen candidate set remains exactly C0-C4.
   - C0/C1 parity to gen3 remains zero-diff on the frozen parity metrics.
   - Post-overlay violations remain zero for all candidates.
   - C2-C4 retain `R5_not_pareto_dominated=true` and `pareto_dominated_by=[]` after the corrected comparator.

6. **Primary result unchanged**
   - C2-C4 still fail one or more of frozen R2-R4 despite CAGR improvement.
   - Therefore the previously accepted economic conclusion is unchanged: the static MaxDiv/Momentum blends do not satisfy the frozen useful-architecture definition; pure MaxDiv remains the risk-adjusted core under this experiment.
   - No result-informed blend retuning is authorized.

7. **Data provenance / causality unchanged**
   - The correction commit does not alter `long_horizon_proxy_panel.py` or `gate4_long_horizon_proxy.py`.
   - The reviewed Track-C proxy contract remains: SH decision calendar, separated signal and return levels, T-to-T+1 research-return realization, lagged decision signals for HK/US/GOLD as frozen, CNY HK economic return levels, and `SCENARIO_NOT_STRICT_PIT_OOS` labeling.
   - This acceptance does not upgrade the study to strict PIT OOS or executable/live evidence.

8. **RL closure preserved**
   - PPO/SAC/TD3 remain absent/forbidden for this research direction.
   - Dense/dynamic alpha search remains forbidden.
   - QMT live remains forbidden.

## Gate decision

The requested mechanical correction is accepted and the `POST_L2_DETERMINISTIC_ARCHITECTURE` experiment is closed.

### authorized_next

- `POST_L2_INSTRUMENT_EXECUTION_REALISM_PREP`

This authorization is **PREP only**. It may specify and freeze the instrument-level execution-realism experiment, including real tradable instrument mapping, listing-date availability, tradability/calendar handling, decision/execution timestamps, costs/fees/slippage assumptions, lot/T+1/T+0 constraints, premium/quote fail-closed semantics, metrics, subperiods, and STOP criteria. It must not run the experiment until a separate reviewer authorization.

### forbidden_next

- `POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN`
- `FORWARD_PAPER_VALIDATION`
- `PAPER`
- `LIVE`
- `RESULT_INFORMED_BLEND_WEIGHT_SEARCH`
- `DENSE_ALPHA_SEARCH`
- `DYNAMIC_ALPHA`
- `PPO`
- `SAC`
- `TD3`
- `RL_RETRAINING`
- `RL_HYPERPARAMETER_TUNING`
- `RL_COMPARISON`
- `QMT_LIVE`

## Required PREP emphasis for the next handoff

The next PREP must keep MaxDiv as the frozen strategy core and must distinguish research-return performance from executable instrument-level performance. It should explicitly freeze real-instrument availability/listing dates, slot-to-instrument mapping, execution calendar alignment, next-session execution semantics, fee/slippage/lot/settlement assumptions, missing/stale quote fail-closed behavior, and the exact criteria that would STOP progression to forward/paper validation.
