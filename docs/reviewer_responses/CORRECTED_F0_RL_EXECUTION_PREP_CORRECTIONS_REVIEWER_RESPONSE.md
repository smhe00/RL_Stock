# Reviewer Response — CORRECTED F0 RL EXECUTION PREP CORRECTIONS

```yaml
handoff_id: CORRECTED_F0_RL_EXECUTION_PREP_CORRECTIONS_001
reviewed_code_commit: b17fe19d77d25b691a5c41556d52bd6446db0c0f
reviewed_packet_commit: 832c70c40cd3051a87cac9a5ec609e8d56a60cf8
reviewed_packet: docs/review_packets/CORRECTED_F0_RL_EXECUTION_PREP_CORRECTIONS.md
decision: TARGETED_HARNESS_FINALIZATION_REQUIRED
reviewer_state: REVISIONS_REQUIRED
```

## Summary

H1-H7 are materially improved and the execution-prep work is now close to release quality. The major earlier defects are fixed: the dry-run shares the runtime constructor path, run-level config SHA is a real digest, fold-level lengths are no longer incorrectly required to be 475, stitched execution dates are checked in order, cost evidence is no longer silently skipped, configured run identities are checked, incomplete seed sets are recognized, and the MaxDiv comparison now uses true Pareto directionality rather than one-dimension underperformance.

I am not authorizing the 36-run corrected F0 execution yet because a few fail-closed holes remain. These are narrow implementation issues, not a reopening of the frozen research protocol.

## Passed

- **H1 shared constructor path — PASS in core direction.** `_construct_model()` is used by both `run_fold_rl_config()` and the dry-run spy.
- **H2 true config digest — PASS at run level.** `run_fold_rl_config()` now records the real 64-hex SHA-256 digest.
- **H3 fold/stitched mask logic — PASS in core direction.** Fold lengths are `[118,118,118,121]` and F1→F4 ordered stitched dates are compared with the ordered 475-date mask.
- **H4 cost evidence — PASS in core direction.** Missing `costs`/`total_cost` evidence fails and `sum(costs)==total_cost` is checked; rollout itself still fail-closes on fees-delta reconciliation.
- **H5 exact algorithm×seed identity — PASS in core direction.** The validator derives expected algorithms/seeds from the canonical config.
- **H6 incomplete seed status — PASS in core direction.** An incomplete declared seed set cannot GO.
- **H7 Pareto semantics — PASS in core direction.** Mixed better/worse dimensions are no longer automatically labeled dominated.
- **No RL training — PASS.** This handoff stayed within the authorized prep-only gate.

## Remaining finalization blockers

### F1 — Algorithm name/class mismatch is still not rejected

The previous review explicitly required the formal path to reject an `algo_name` / `algo_cls` mismatch. `_construct_model()` currently takes both independently and does not verify them.

A mapping mistake could therefore instantiate, for example, TD3 while applying the PPO config under `algo_name="PPO"`.

Required:

```text
algo_cls identity/name must match the canonical algorithm key
mismatch -> FormalConfigError before construction/training
```

Add a targeted mismatch test.

### F2 — Missing `n_eval_steps` is not fail-closed

The validator currently checks:

```python
if n_eval is not None and n_eval != fold_len:
```

Therefore a result with no `n_eval_steps` evidence can pass this invariant.

Required:

```text
missing n_eval_steps -> invariant failure
present n_eval_steps -> must equal the fold-specific expected length
```

### F3 — `raw_series_complete` still does not enforce compatible lengths for all required arrays

The current validator checks `net_returns` and `cash` lengths, but only checks existence of `actual_weights`; it also does not enforce `costs` length or the other recorded weight series lengths.

For every fold, require exact fold-length compatibility for at least:

```text
execution_dates
net_returns
costs
cash
actual_weights
raw_weights
post_risk_weights
```

For weight arrays, also require each row to have the frozen action dimension (11). Missing or malformed evidence must fail closed.

### F4 — GO/NO-GO can still GO with a missing metric seed

`evaluate_go_nogo()` checks `seed_keys`, but then consumes the values of the three metric dictionaries without requiring each metric dictionary to have the exact configured seed keys.

Thus this malformed payload can still look complete:

```text
seed_keys = [42, 2026, 7]
return/sharpe/max_drawdown maps contain only two seeds
```

If those two observations clear the thresholds, the current code can produce GO.

Required:

- each decision-metric map must have key set exactly equal to `cfg["seeds"]`;
- each configured seed must have one finite return, Sharpe and MaxDD;
- missing/extra metric keys -> `NO_GO / INCOMPLETE`;
- project-level status must not become `PROMISING` from an incomplete algorithm payload.

Also require the top-level algorithm set to match the configured algorithm set before a complete project-level decision is emitted; otherwise mark project status incomplete rather than treating missing algorithms as if they were intentionally absent.

### F5 — Pareto output needs full finite frontier evidence

The current code computes dominance over `finite_dims`. If Calmar is missing/NaN, it can still label an algorithm `dominated` or `not_dominated` using only the remaining dimensions.

For a report explicitly called Pareto vs MaxDiv, require all frozen Pareto dimensions to be finite. If any required RL/frontier dimension is unavailable, emit an `UNAVAILABLE/INCOMPLETE` Pareto status rather than a dominance claim.

### F6 — Artifact-level config provenance is not yet bound

Run-level SHA is fixed, but there is still no formal artifact-publication path proving:

```text
top-level artifact config_sha256 == every run config_sha256 == current frozen config digest
```

Before execution is authorized, the execution harness should have a deterministic aggregation/publication function (or equivalent dry-run synthetic path) that:

1. stores one top-level config SHA/snapshot;
2. verifies every run carries the same SHA;
3. runs `validate_runtime_invariants()` before writing final tracked artifacts;
4. runs `evaluate_go_nogo()` only after invariant validation;
5. fails without publishing a final artifact on any mismatch.

This can be verified with synthetic no-training results; no real Test result consumption is needed.

## Authorized next action

```yaml
authorized_next:
  - CORRECTED_F0_RL_EXECUTION_HARNESS_FINALIZATION
```

This is the final prep/closeout gate. It is limited to F1-F6 above, tests, and synthetic/dry-run publication-path verification. It must not train PPO/SAC/TD3.

If this finalization passes without new material defects, the intended next gate is `CORRECTED_F0_RL_3SEED`, but that execution is **not authorized by this response**.

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
CORRECTED_F0_RL_EXECUTION_PREP_CORRECTIONS
= TARGETED_HARNESS_FINALIZATION_REQUIRED

NEXT
= CORRECTED_F0_RL_EXECUTION_HARNESS_FINALIZATION
```
