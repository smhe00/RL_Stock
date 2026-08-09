# Reviewer Response — CORRECTED F0 RL EXECUTION HARNESS FINALIZATION

```yaml
handoff_id: CORRECTED_F0_RL_EXECUTION_HARNESS_FINALIZATION_001
reviewed_code_commit: 765ccacb8350e35efc25721f74f465e3be4a6f7d
reviewed_packet_commit: 361dbe535db2b5d647c143cc93bc06800f974956
reviewed_packet: docs/review_packets/CORRECTED_F0_RL_EXECUTION_HARNESS_FINALIZATION.md
decision: TARGETED_PUBLICATION_METRIC_BINDING_REQUIRED
reviewer_state: REVISIONS_REQUIRED
```

## Summary

F1-F6 are substantially closed. The final fail-closed mechanics are now much stronger: algorithm name/class mismatch is rejected, missing `n_eval_steps` fails, raw arrays/weight shapes are checked, metric seed keys and project algorithm completeness are enforced, Pareto requires finite frozen dimensions, and run-level config hashes are checked before publication.

One material publication-integrity gap remains before the 36-run corrected F0 execution can be authorized: the GO/NO-GO inputs and stop-violation count are still supplied independently from the validated 36-run raw result tree rather than being derived from it. Therefore the current `finalize_publish()` can validate one set of raw results and publish a contradictory externally supplied stitched summary.

## Passed

- F1 algo name/class mismatch rejection — PASS.
- F2 missing `n_eval_steps` fail-closed — PASS.
- F3 required raw series lengths and 11-wide weight rows — PASS.
- F4 exact metric seed keys and project algorithm completeness — PASS inside `evaluate_go_nogo()`.
- F5 finite-dimension requirement for MaxDiv Pareto reporting — PASS.
- F6 run-level config SHA consistency + invariant-before-evaluation ordering — PASS in core direction.
- No RL training — PASS.

## Blocking publication binding

### P1 — GO/NO-GO metrics are not derived from the validated raw run results

`finalize_publish()` currently accepts both:

```python
results
per_algo_stitched
```

as independent arguments. It validates `results`, then evaluates the unrelated caller-supplied `per_algo_stitched`.

The current passing F6 test demonstrates the problem directly: `_pass_results()` creates raw `net_returns = 0.0` for every test step, while the separately supplied stitched object claims roughly 27–30% annualized return and Sharpe 1.5–1.9; `finalize_publish()` still returns `published=True`.

That means a stale, corrupted, or incorrectly aggregated stitched summary can disagree with the audited raw artifact and still drive GO/NO-GO.

Required closeout:

1. implement one canonical aggregation function that derives, for every `(algorithm, seed)`, the ordered F1→F4 stitched `net_returns` directly from `results`;
2. recompute `active_day_annualized_return`, Sharpe, MaxDD, Calmar and all decision metrics from those raw series inside the publication path;
3. `finalize_publish()` must call that aggregator itself, rather than accept authoritative stitched decision metrics from the caller;
4. if a convenience caller-supplied summary remains, it may only be compared against the canonical recomputation and mismatch must fail closed;
5. add a test proving that zero raw returns cannot be published as a positive-return GO even if a contradictory external summary is supplied.

### P2 — Stop conditions are also caller-supplied rather than bound to each real run

`evaluate_go_nogo()` consumes `stop_violations` from the independent stitched object. The publication path does not derive this value from the actual run fields such as:

```text
save_load_deterministic_identical
nan_obs_or_reward
negative_cash_count
non-finite run/series values
```

Therefore a malformed caller can provide `stop_violations: 0` even if the actual run tree contains a stop violation.

Required closeout:

- derive stop status/count from the validated run records inside the canonical aggregation/publication path;
- missing stop-condition evidence must fail closed;
- any configured run with a hard stop must prevent that algorithm from GO;
- add synthetic tests where a raw run has NaN/negative-cash/save-load failure while the external summary says zero stops, and prove publication/evaluation does not treat it as GO.

### P3 — Synthetic publication proof should exercise the real canonical 475-date mask

The current synthetic publication path uses an arbitrary continuous business-day range. The validator logic is useful, but the final no-training proof should construct the actual folds and `exact_test_mask()` from repository data, then synthesize per-fold arrays against the real `[118,118,118,121]` ordered segments. This removes the final gap between the synthetic harness proof and the actual execution calendar.

This is a small verification item; it does not reopen the research protocol.

## Authorized next action

```yaml
authorized_next:
  - CORRECTED_F0_RL_EXECUTION_PUBLICATION_BINDING
```

This narrow closeout is limited to:

1. canonical raw-results → stitched-metrics aggregation;
2. raw-run-derived stop-condition aggregation;
3. binding GO/NO-GO exclusively to canonical recomputation;
4. real-mask synthetic publication-path proof;
5. full tests/dry-run, no RL training.

If this passes without a new material defect, the intended next gate is `CORRECTED_F0_RL_3SEED`.

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
CORRECTED_F0_RL_EXECUTION_HARNESS_FINALIZATION
= TARGETED_PUBLICATION_METRIC_BINDING_REQUIRED

NEXT
= CORRECTED_F0_RL_EXECUTION_PUBLICATION_BINDING
```
