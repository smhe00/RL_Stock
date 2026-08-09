# Reviewer Response — RL FORMAL PROTOCOL PREP CORRECTIONS

```yaml
handoff_id: RL_FORMAL_PROTOCOL_PREP_CORRECTIONS_001
reviewed_code_commit: 943f92c21a49d1c3e5284cef9dd0ffb7fe0bdb49
reviewed_packet_commit: fdaa1bbdae3ca4dabf711b446e779bc07acb94fb
reviewed_packet: docs/review_packets/RL_FORMAL_PROTOCOL_PREP_CORRECTIONS.md
decision: PROTOCOL_APPROVED_EXECUTION_HARNESS_NOT_YET_AUTHORIZED
reviewer_state: REVISIONS_REQUIRED
```

## Summary

The P1-P9 protocol corrections are substantially successful. The research semantics are now much cleaner: F0 is preserved as the pre-existing frozen baseline rather than selected from the descriptive F1 diagnostic; the 475-date panel is explicitly a research benchmark; the 3-seed run is separated from a conditional future robustness stage; EqualWeight and MaximumDiversification are both represented; checkpoint search is removed; per-algorithm GO/NO-GO is defined; and the stitched annualization metric is conceptually renamed.

However, the repository is not yet ready to authorize the 36-run corrected RL execution. The remaining gap is now **execution binding**, not research design. The new machine-readable config is declared canonical, but the actual RL runner still does not consume it, and the new hard-stop invariants are not yet executable fail-closed checks. There is also one remaining P9 naming inconsistency in the GO rule.

## Passed

- **P1 F0 rationale — PASS.** F0 is retained because it was already frozen; F1 remains a separate Gen-2 research set and is not eliminated by the descriptive diagnostic.
- **P2 stage hierarchy — PASS.** `CORRECTED_F0_RL_3SEED` is now a research-benchmark GO/NO-GO stage; conditional later robustness work remains unapproved rather than silently removed.
- **P3 research-benchmark labeling — PASS.** The 475-date mask is `RESEARCH_BENCHMARK_TEST`, with a future unseen forward holdout reserved for final confirmation.
- **P4 two-tier benchmark — PASS.** EqualWeight is the primary return hurdle and MaximumDiversification is the risk-adjusted frontier; Pareto interpretation is required.
- **P5 algorithm dimension — PASS in protocol semantics.** GO/NO-GO is defined per algorithm first and project-level second; Test-based winner selection is prohibited.
- **P6 checkpoint policy — PASS.** `final_training_endpoint_only` removes checkpoint-search degrees of freedom.
- **P7 machine-readable configuration — PASS as a specification artifact.** Seeds, train budget, architecture, devices, versions, and material PPO/SAC/TD3 defaults are frozen in `configs/rl_formal_protocol.yaml` and checked against SB3.
- **No RL training — PASS.** This handoff stayed inside the authorized prep/correction gate.

## Remaining blockers before any RL execution

### E1 — Canonical config is not consumed by the real execution path

`configs/rl_formal_protocol.yaml` says it is the canonical input for the execution runner, but `WalkForwardRunner.run_fold_rl()` still instantiates the algorithm from function arguments and implicit SB3 defaults, and `scripts/gate4_3seed_pilot.py` still owns the active seed/algo/train-pass selection.

The pilot also permits environment-variable overrides:

```text
GATE4_PILOT_SEEDS
GATE4_PILOT_PASSES
GATE4_PILOT_ALGOS
```

Therefore a future run could drift from the frozen config while still looking superficially compliant.

Required closeout:

1. create a dedicated corrected execution runner or refactor the existing runner so it loads `configs/rl_formal_protocol.yaml` directly;
2. pass the frozen algorithm kwargs explicitly to PPO/SAC/TD3 rather than relying on constructor defaults;
3. disable/fail on environment-variable overrides for the formal run;
4. record a config hash / frozen config snapshot in the result artifact;
5. add tests proving the runtime constructor receives the exact frozen values.

### E2 — Hard-stop invariants are currently declarations, not enforced runtime stops

The config now lists:

```text
execution_dates_equal_475_mask
n_eval_steps_equal_475
cost_reconciliation_pass
all_folds_present_no_duplicates
raw_series_complete
```

but the reviewed commit does not implement these as fail-closed checks in the actual RL execution path. The old pilot `check_stop_conditions()` only covers NaN/Inf, negative cash, save/load mismatch, and non-finite OOS return.

Required closeout: implement one runtime invariant validator that is called before final artifact publication and causes a non-zero/failure outcome when any invariant fails. Add targeted tests for both pass and fail cases.

### E3 — P9 naming is still inconsistent inside the GO rule

The protocol correctly defines stitched annualization as `active_day_annualized_return`, but §10 still says:

```text
median(seed CAGR) >= 0.2687
```

and the tests use a local `cagr` variable. Replace this with `median(seed active_day_annualized_return)` everywhere in the canonical protocol, config-driven evaluator, tests, and result schema. Do not expose a stitched `cagr` field that could be confused with calendar CAGR.

### E4 — Formal runner must compute project-level GO deterministically from artifacts

The current tests demonstrate the rule with toy arrays, but there is not yet a canonical evaluator function that consumes the three seed-level stitched results for each algorithm and emits:

```text
per_algorithm: GO / NO_GO + reasons
project_level: PROMISING / NO_GO
pareto_vs_maxdiv: dominated / non_dominated dimensions
```

Required closeout: implement and unit-test this evaluator before training. It must not perform Test-based winner ranking; it only applies the predeclared thresholds to each algorithm independently.

## Authorized next action

```yaml
authorized_next:
  - CORRECTED_F0_RL_EXECUTION_PREP
```

This is **execution-harness preparation only**. It may modify the runner/config plumbing/tests and add dry-run or constructor-spy verification, but it may not train PPO/SAC/TD3 or consume new Test results.

The gate exits only when:

```text
config -> runtime constructor binding is proven
formal env overrides are impossible/fail-closed
all hard-stop invariants are executable
active_day_annualized_return naming is consistent
GO/NO-GO evaluator is deterministic and config-driven
full tests pass
```

## Still forbidden

```yaml
forbidden_next:
  - RL_RETRAINING
  - CORRECTED_F0_RL_3SEED
  - GATE_4_10_SEED_FORMAL
  - OPTUNA
  - HYPERPARAMETER_SWEEP
  - TEST_INFORMED_ALGO_SELECTION
  - TEST_INFORMED_FEATURE_SELECTION
  - FEATURE_SET_CHANGE_FROM_CURRENT_TEST_RESULTS
  - FEATURE_DATA_READY_EXPANSION
  - F2_F3_REAL_MACRO_RUN
  - QMT_LIVE
  - SOUTHBOUND_EXECUTION
```

## Gate decision

```text
RL_FORMAL_PROTOCOL_PREP_CORRECTIONS
= PROTOCOL_APPROVED_EXECUTION_HARNESS_NOT_YET_AUTHORIZED

NEXT
= CORRECTED_F0_RL_EXECUTION_PREP
```
