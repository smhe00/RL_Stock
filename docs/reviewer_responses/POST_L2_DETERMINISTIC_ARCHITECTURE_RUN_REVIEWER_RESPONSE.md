# Reviewer Response — POST_L2 Deterministic Architecture RUN

```yaml
handoff_id: G4_POST_L2_DETERMINISTIC_ARCH_RUN_001
reviewed_packet: docs/review_packets/POST_L2_DETERMINISTIC_ARCHITECTURE_RUN.md
reviewed_result_commit: ea8798831a0df040c4296ff778c239913ae419fd
reviewed_code_commit: d31e3848c9c264e7ce01c2a2162ab0124f904dbd
decision: ARCH_RUN_RESULTS_SUBSTANTIVELY_ACCEPTED_R5_TEST_FIX_REQUIRED
reviewer_state: REVISIONS_REQUIRED
authorized_next:
  - POST_L2_DETERMINISTIC_ARCHITECTURE_RUN_CORRECTION
forbidden_next:
  - INSTRUMENT_EXECUTION_REALISM
  - FORWARD_PAPER_VALIDATION
  - RESULT_INFORMED_BLEND_WEIGHT_SEARCH
  - DYNAMIC_ALPHA
  - PPO
  - SAC
  - TD3
  - RL_RETRAINING
  - RL_HYPERPARAMETER_TUNING
  - RL_COMPARISON
  - QMT_LIVE
```

## Review conclusion

The frozen C0-C4 architecture run is substantively credible and the primary economic conclusion is accepted: under the pre-declared R1-R4 thresholds, none of the three static MaxDiv/Momentum blends qualifies as a useful architecture relative to the pure MaxDiv core. C0/C1 reconstruct exactly to the accepted gen3 parent metrics, all five candidates have zero post-overlay feasibility violations, the candidate set and parent parameters are unchanged, and no dense/dynamic alpha or RL path was introduced.

The accepted headline evidence is:

- C0 MaxDiv: Calendar CAGR 0.059496, Sharpe 1.02427, MaxDD -0.103874, Calmar 0.594678;
- C1 Momentum: Calendar CAGR about 8.39%, Sharpe about 0.571, MaxDD about -44.3%;
- C2 75/25: CAGR about 6.8%, Sharpe about 0.827, MaxDD about -18.5%, Calmar about 0.380, 1x cumulative cost delta about -4.8 percentage points;
- C3 50/50: CAGR about 7.3%, Sharpe about 0.678, MaxDD about -28.9%, cumulative cost delta about -8.8 percentage points;
- C4 25/75: CAGR about 7.9%, Sharpe about 0.614, MaxDD about -37.5%, cumulative cost delta about -12.7 percentage points.

C2-C4 all pass the return-improvement concept R1 but fail one or more of the frozen risk/cost gates R2-R4. In practice all three breach the MaxDD floor and cost tolerance; C2 narrowly clears Sharpe >=0.80 but misses Calmar >=0.40. Therefore the conclusion that the static blends do not meet the frozen definition of a useful architecture does not depend on R5.

## Passed review items

- unique READY_FOR_REVIEW handoff, not previously reviewed;
- exact implementation commit `d31e3848...` inspected;
- exact result/document commit `ea879883...` inspected;
- implementation only adds the architecture runner/tests; accepted parent strategy code and L2 panel implementation are not retuned in this run;
- frozen candidates remain exactly C0/C1/C2/C3/C4 = MaxDiv/Momentum alphas 1.0/0.0/0.75/0.50/0.25;
- MaxDiv 120/0.5 and Momentum 252/21 parent semantics are reused through the accepted L2 runner;
- same 11-slot, 2800-interval Track-C scenario path is reused;
- C0/C1 parity to accepted gen3 is reported as zero diff on Calendar CAGR, MaxDD, Sharpe and cumulative return;
- final weights are passed through the common `RiskOverlayV0`; post-overlay violations are zero for all candidates;
- R1 uses exact C0 relative CAGR +0.005;
- R2 uses exact C0 MaxDD minus 0.05;
- R3 is Sharpe >=0.80 and Calmar >=0.40;
- R4 uses net-minus-gross cumulative delta >= -0.03;
- turnover/cost is computed from the final executable weight path;
- result artifact is present on main and identifies implementation commit `d31e384`;
- no PPO/SAC/TD3, no result-informed alpha sweep, no dynamic alpha, no QMT live.

## Blocking correction 1 — R5 Pareto MaxDD direction is reversed in code

The current `dominates(a, b)` implementation defines:

```python
dims = [("cum_return", True), ("calendar_cagr", True), ("sharpe", True), ("max_drawdown", False)]
```

and for `higher_better == False` checks `av <= bv`. That treats a more negative MaxDD as better. For MaxDD, less negative / numerically larger is better. Therefore the Pareto comparison direction is incorrect.

Correct the implementation so that MaxDD is compared as a higher-is-better metric, e.g. conceptually:

```text
cum_return: higher better
calendar_cagr: higher better
sharpe: higher better
max_drawdown: higher better   # -0.10 is better than -0.20
```

or use positive drawdown magnitude and explicitly make lower magnitude better. Use one convention consistently.

For the current reported C2-C4 values, manual inspection shows that no parent actually dominates any blend even with the correct MaxDD direction: C0 has better Sharpe/MaxDD but lower cumulative return/CAGR, while C1 has higher cumulative return/CAGR than some blends but worse Sharpe and/or MaxDD. Thus this bug does **not** change the present economic conclusion, but the frozen R5 evaluator itself must be corrected before the architecture gate is closed.

## Blocking correction 2 — add an R5 regression test

`tests/test_arch_blend.py` covers candidate freezing, blend/overlay semantics, parent parity, R1-R4 evaluation, final-path cost and no-RL/no-dense constraints, but it does not test the Pareto direction or R5 output.

Add a synthetic regression test that proves, at minimum:

```text
A: same-or-better return/CAGR/Sharpe and MaxDD -10%
B: lower return/CAGR/Sharpe and MaxDD -20%
=> A dominates B
=> B does not dominate A
```

Also include a trade-off example where higher return but worse MaxDD/Sharpe is non-dominated, matching the intended C0-vs-blend geometry.

## Blocking correction 3 — provide test execution evidence

The handoff protocol requires completed tests/results before review. The repository contains the new test file, but the packet does not report a pytest command/count and there is no GitHub Actions run attached to `d31e384`.

The correction handoff must report actual execution evidence for:

```text
pytest tests/test_arch_blend.py -q
```

and preferably the full project suite used by the current Gate 4 branch. Also report:

```text
python scripts/gate4_arch_blend.py --check
```

Do not claim CI evidence unless a workflow actually exists/runs.

## Artifact/report correction

After fixing R5, deterministically rerun the same frozen C0-C4 architecture runner only as needed to regenerate the architecture artifacts and verify that:

- C0/C1 parity remains unchanged;
- C2-C4 R1-R4 verdicts remain unchanged;
- post-overlay violations remain zero;
- corrected R5 still reports the actual dominance relationships;
- no candidate, alpha, parent parameter, panel, timing, FX, cost convention, stress regime or threshold is changed.

The current primary conclusion is quarantined as substantively accepted but not yet gate-closed until this mechanical correction/test evidence is reviewed.

## Immediate next gate only

Authorized next is documentation/code/test correction only:

`POST_L2_DETERMINISTIC_ARCHITECTURE_RUN_CORRECTION`

Do not proceed to instrument-level execution realism, forward/paper validation, RL, live trading, or any new blend search yet.
