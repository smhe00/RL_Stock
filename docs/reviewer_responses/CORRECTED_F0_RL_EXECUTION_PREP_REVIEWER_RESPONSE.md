# Reviewer Response — CORRECTED F0 RL EXECUTION PREP

```yaml
handoff_id: CORRECTED_F0_RL_EXECUTION_PREP_001
reviewed_code_commit: 338693c2d065a168599ae651152d60d06cb8da26
reviewed_packet_commit: d76ccedd4e84a05421581e8b8f5ef5c78678051f
reviewed_packet: docs/review_packets/CORRECTED_F0_RL_EXECUTION_PREP.md
decision: TARGETED_EXECUTION_HARNESS_CORRECTIONS_REQUIRED
reviewer_state: REVISIONS_REQUIRED
```

## Summary

The execution-prep direction is correct and several protocol gaps are now materially improved: the canonical YAML exists, algorithm kwargs are explicitly represented, forbidden pilot overrides have a fail-closed helper, the GO/NO-GO evaluator is separated per algorithm, and stitched return naming has moved to `active_day_annualized_return`. No RL training was performed.

However, the current harness is **not safe to authorize the 36-run corrected F0 execution**. The remaining defects are implementation-level and would either reject valid real runs, silently skip required invariants, or mislabel deterministic-frontier comparisons. These must be corrected and tested against the real fold/result schema before `CORRECTED_F0_RL_3SEED` can be authorized.

## Passed / accepted

- **No RL training — PASS.** The gate remained prep/dry-run only.
- **Canonical machine-readable config exists — PASS as specification.** `configs/rl_formal_protocol.yaml` contains seeds, devices, train budget, network and explicit algorithm kwargs.
- **Forbidden pilot override helper — PASS in direction.** `GATE4_PILOT_SEEDS/PASSES/ALGOS` are rejected by `check_no_forbidden_overrides()`.
- **E3 naming direction — PASS.** The protocol and evaluator use `active_day_annualized_return` rather than stitched calendar-CAGR terminology.
- **E4 per-algorithm evaluator skeleton — PASS in direction.** Thresholds are applied per algorithm and no Test-based winner ranking is emitted.

## Blocking corrections

### H1 — The dry-run spy does not exercise the real config-driven execution function

`gate4_rl_formal_runner.py --dry-run` manually reconstructs each SB3 constructor call. The corresponding unit test also directly constructs PPO. Neither path calls `run_fold_rl_config()`.

Therefore the current spy proves only that a manually duplicated constructor expression can match the YAML; it does **not** prove that the future formal execution path actually consumes the canonical config correctly.

Required correction:

- exercise `run_fold_rl_config()` itself with a fake/minimal runner and spy algorithm class, or refactor constructor creation into one shared function used by both real execution and dry-run;
- assert the exact config algorithm kwargs, `net_arch`, device, seed and train budget reach that shared runtime path;
- reject an `algo_name`/class mismatch and seeds not present in the canonical config.

### H2 — `config_sha256` is currently written incorrectly by the real fold harness

`load_protocol_config()` correctly computes the SHA-256 digest, but `run_fold_rl_config()` returns:

```python
"config_sha256": cfg["_config_path"]
```

That is the config **path**, not the digest. A future result could therefore claim config provenance without actually recording the frozen content hash.

Required correction: pass the loaded config envelope/digest into the execution path and record the actual 64-hex SHA-256 in every run and top-level artifact; verify all run hashes equal the artifact-level hash.

### H3 — The runtime execution-mask invariant is implemented at the wrong level and will reject every valid real run

The real walk-forward contract has fold Test lengths:

```text
F1 = 118
F2 = 118
F3 = 118
F4 = 121
stitched total = 475
```

But `validate_runtime_invariants()` iterates **each fold** and requires:

```python
set(fold.execution_dates) == full_475_mask
fold.n_eval_steps == 475
```

A valid fold will therefore fail by construction. The passing test hides this by fabricating 475 dates for every fold.

Required correction:

1. validate each fold against its own expected `test_start..test_end` execution-date segment and expected step count;
2. concatenate F1→F4 execution dates in order and require exact equality with the canonical ordered 475-date mask;
3. require stitched `n_eval_steps == 475` only at the stitched `(algo, seed)` level;
4. add a test using the actual expected fold lengths `[118,118,118,121]` rather than synthetic 475-per-fold data.

Do not compare masks as unordered sets when exact ordering/duplication matters.

### H4 — `cost_reconciliation_pass` is silently skipped

The real rollout `series` contains `costs`, but it does not contain `fees`. The validator currently checks reconciliation only under:

```python
if "costs" in series and "fees" in series:
    ...
```

so the required formal invariant is never evaluated on the actual rollout schema.

The rollout function already performs an internal `sum(costs) == fees_delta` assertion, which is useful, but the formal publication validator must still have auditable fail-closed evidence rather than silently skipping a declared invariant.

Required correction — one acceptable design:

- export an explicit per-fold `cost_reconciliation_pass=true` plus the relevant totals from rollout; or
- validate `sum(series.costs) == test.total_cost` and require the rollout-level fees reconciliation assertion/evidence to be present.

If required evidence is absent, the validator must fail closed.

### H5 — `raw_series_complete` and exact run identity are not actually enforced

The config declares `raw_series_complete`, but the validator does not check completeness/length parity of the required raw arrays. It also counts 36 dictionary entries without proving the exact configured algorithm/seed/fold Cartesian product.

Required correction:

- derive expected algorithms and seeds from the canonical config;
- require exactly `algorithms × seeds × {F1,F2,F3,F4}`, no missing or extra identities;
- for every fold require at least `execution_dates`, `net_returns`, `costs`, `cash`, and required weight series to have the expected compatible lengths;
- explicitly reject missing raw series/evidence rather than treating absent optional keys as pass.

### H6 — GO/NO-GO seed completeness is not fail-closed

`evaluate_go_nogo()` trusts caller-provided `n_seeds` and hardcodes `n_pass_sharpe < 2`. It does not require the exact configured seed keys. A two-seed payload could potentially satisfy the current logic if both pass.

Required correction:

- require exact seed set equality with `cfg["seeds"]` for each algorithm;
- require all decision metrics finite for all configured seeds;
- derive the `2/3` threshold from the frozen rule/config, not from a caller-supplied `n_seeds` value;
- incomplete seed results should be `NO_GO / INCOMPLETE`, never GO.

### H7 — `pareto_vs_maxdiv = dominated` is not Pareto dominance

The current evaluator labels an RL algorithm `dominated` whenever it is worse than MaxDiv on **any one** of Sharpe / MaxDD / Calmar. True Pareto domination requires the comparator to be at least as good on all included objectives and strictly better on at least one.

Required correction — choose one:

- implement true dominance semantics with correct objective directions and finite-value requirements; or
- rename the output to `underperforms_maxdiv_dimensions` and stop calling it Pareto domination.

A strategy that is better on Sharpe but worse on MaxDD is not Pareto-dominated merely because one dimension is worse.

## Reviewer interpretation

This is now a narrow harness-quality issue, not a research-design reopening. The frozen protocol remains acceptable. The next correction should avoid adding new research degrees of freedom and should focus only on proving that the **actual** execution function, artifact validator and deterministic evaluator implement that protocol exactly.

## Authorized next action

```yaml
authorized_next:
  - CORRECTED_F0_RL_EXECUTION_PREP_CORRECTIONS
```

This sub-gate is limited to:

1. bind dry-run/tests to the same constructor/runtime path used by `run_fold_rl_config()`;
2. fix real config-hash propagation;
3. fix fold-level vs stitched 475-date invariants using ordered masks and real fold lengths;
4. make cost reconciliation and raw-series completeness auditable fail-closed checks;
5. enforce exact config algorithm/seed/fold identities and complete seed sets;
6. fix/rename MaxDiv dominance semantics;
7. run the full test suite plus no-training dry-run/check and stop for review.

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
CORRECTED_F0_RL_EXECUTION_PREP
= TARGETED_EXECUTION_HARNESS_CORRECTIONS_REQUIRED

NEXT
= CORRECTED_F0_RL_EXECUTION_PREP_CORRECTIONS
```
