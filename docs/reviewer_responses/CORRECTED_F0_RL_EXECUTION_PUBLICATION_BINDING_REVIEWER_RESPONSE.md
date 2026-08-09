# Reviewer Response — CORRECTED F0 RL EXECUTION PUBLICATION BINDING

```yaml
handoff_id: CORRECTED_F0_RL_EXECUTION_PUBLICATION_BINDING_001
reviewed_code_commit: 6e183be8851da6a3ab745290c532892603f8b242
reviewed_packet_commit: b8c07e50fb41e9129dccfef9c0d54f6c6f71fb85
reviewed_packet: docs/review_packets/CORRECTED_F0_RL_EXECUTION_PUBLICATION_BINDING.md
decision: TARGETED_CANONICAL_SCHEMA_BRIDGE_REQUIRED
reviewer_state: REVISIONS_REQUIRED
```

## Summary

P1-P3 are materially improved: raw F1→F4 net returns are now recomputed into canonical seed-level metrics, stop evidence is derived from run records, and the synthetic proof uses the real repository Test mask. The previous independent-summary publication-integrity gap is therefore largely closed.

One blocking implementation mismatch remains before the 36-run corrected F0 execution can be authorized: `aggregate_raw_results()` and `evaluate_go_nogo()` use incompatible canonical schemas. As written, the newly recomputed seed metrics are not actually consumed by the GO/NO-GO evaluator.

## Passed

- **P1 raw-results aggregation — PASS at seed-metric computation level.** Ordered F1→F4 `net_returns` are used to recompute active-day annualized return, Sharpe, MaxDD and Calmar per `(algorithm, seed)`.
- **P2 run-derived stop evidence — PASS at seed aggregation level.** `save_load_deterministic_identical`, `nan_obs_or_reward`, `negative_cash_count` and non-finite raw returns are inspected, with missing evidence fail-closed.
- **P3 real canonical mask — PASS.** Synthetic publication now builds the repository folds and uses `exact_test_mask()` rather than an arbitrary business-day range.
- **Caller summary is no longer authoritative — PASS in direction.** Contradictory supplied diagnostics can fail closed.
- **No RL training — PASS.** This handoff stayed inside the authorized publication-binding closeout.

## Blocking issue

### S1 — Canonical aggregation schema is incompatible with the GO/NO-GO evaluator

`aggregate_raw_results()` currently returns:

```text
canonical[algo][seed] = {
    active_day_annualized_return,
    sharpe,
    max_drawdown,
    calmar,
    stop_violations,
    ...
}
```

but `evaluate_go_nogo()` still expects the older algorithm-centric shape:

```text
per_algo_stitched[algo] = {
    seed_keys: [...],
    active_day_annualized_return: {seed: value},
    sharpe: {seed: value},
    max_drawdown: {seed: value},
    calmar_median: value,
    stop_violations: value,
}
```

Consequences in the reviewed commit:

1. `evaluate_go_nogo()` sees empty return/Sharpe/MaxDD maps for every algorithm;
2. each algorithm becomes `INCOMPLETE/NO_GO` regardless of the actual recomputed seed performance;
3. seed-level `stop_violations` are also not read by the evaluator because it looks for an algorithm-level field;
4. Pareto reporting sees no `calmar_median` and becomes unavailable;
5. a genuinely strong 36-run result could therefore be falsely rejected.

The current tests do not expose this because they mostly use zero-return synthetic raw data, where `NO_GO` is expected anyway. The stop-violation test also passes for the wrong reason: the algorithm is already NO_GO from schema incompleteness, so it does not prove that a raw stop flips an otherwise-GO algorithm to NO_GO.

## Required closeout

Use **one canonical schema end-to-end**. Either refactor `evaluate_go_nogo()` to consume the seed-centric output directly, or pivot the raw aggregation into the evaluator's frozen contract. A clean compatible output would be, for example:

```text
canonical[algo] = {
    seed_keys: exact cfg.seeds,
    active_day_annualized_return: {seed: canonical_value},
    sharpe: {seed: canonical_value},
    max_drawdown: {seed: canonical_value},
    calmar_median: median(canonical seed calmars),
    stop_violations: sum(canonical seed stop violations),
    per_seed: {...}  # optional audit detail
}
```

Then add integration tests that exercise the entire publication chain, not just individual functions:

1. construct raw fold returns with finite variance, non-zero drawdown, and metrics that clear the frozen EqualWeight hurdle for one algorithm;
2. `raw results -> validate -> aggregate -> evaluate -> finalize_publish` must produce that algorithm `GO` and project `PROMISING`;
3. flip one actual run to `save_load_deterministic_identical=False` (or another frozen stop condition) while keeping the same returns; the same algorithm must become `NO_GO` because of the raw-derived stop;
4. verify the canonical seed metrics seen by `evaluate_go_nogo()` numerically equal the metrics recomputed from raw F1→F4 series;
5. keep the real 475-date mask synthetic proof.

Do not add or change research thresholds, algorithms, seeds, features, training budget, or Test-based selection logic in this closeout.

## Authorized next action

```yaml
authorized_next:
  - CORRECTED_F0_RL_EXECUTION_PUBLICATION_SCHEMA_CLOSEOUT
```

This is a narrow no-training correction gate limited to the canonical aggregation/evaluator schema bridge and the positive/stop-flip end-to-end synthetic tests above.

If this closeout passes without a new material execution defect, the intended next gate is `CORRECTED_F0_RL_3SEED`; that training gate is **not authorized by this response**.

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
CORRECTED_F0_RL_EXECUTION_PUBLICATION_BINDING
= TARGETED_CANONICAL_SCHEMA_BRIDGE_REQUIRED

NEXT
= CORRECTED_F0_RL_EXECUTION_PUBLICATION_SCHEMA_CLOSEOUT
```
