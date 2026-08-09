# Reviewer Response — CORRECTED F0 RL 3-SEED

```yaml
handoff_id: CORRECTED_F0_RL_3SEED_001
reviewed_code_commit: de621a6ab080da871829d7c009184fad47b3fbaa
reviewed_packet_commit: 991cf7c8b8b5f60d4655f3d7a74fdc425b676e58
reviewed_packet: docs/review_packets/CORRECTED_F0_RL_3SEED.md
decision: FORMAL_NO_GO_ACCEPTED_RL_ROBUSTNESS_NOT_AUTHORIZED
reviewer_state: REVIEW_COMPLETE
```

## Summary

The corrected F0 3-seed formal execution is accepted as a valid Gate-4 result. The execution completed the full configured 36-run matrix through the frozen config-driven path, with no reported stop-condition or runtime-invariant violations, and publication passed through `finalize_publish()`. The resulting project-level `NO_GO` is therefore treated as a strategy-performance conclusion under the frozen protocol rather than an execution failure.

No algorithm clears the frozen EqualWeight hurdle. PPO is close on return but still fails the precommitted Sharpe, drawdown, and seed-consistency conditions; SAC and TD3 fail by wider margins. All three are also Pareto-dominated by the frozen MaximumDiversification risk-adjusted reference in Sharpe / MaxDD / Calmar.

Accordingly, the conditional 10-seed robustness stage is not authorized. This result must not be used to justify Test-informed tuning, algorithm selection, feature changes, Optuna/sweeps, or live deployment.

## Review findings

- **Execution completeness — PASS.** 36/36 configured PPO/SAC/TD3 × seeds 42/2026/7 × folds F1-F4 are represented.
- **Formal runtime path — PASS.** The execution runner calls `run_fold_rl_config()` using the canonical config and shared constructor rather than the legacy pilot constructor path.
- **Frozen configuration — PASS.** F0 dim 104, train_passes 20, net [256,256], configured seeds/algorithms and final-endpoint policy are preserved.
- **Publication/invariant path — PASS.** Results are aggregated and finalized through `finalize_publish()` before tracked result/raw artifacts are written.
- **Stop conditions — PASS.** Reported stop flags are empty for PPO/SAC/TD3; canonical stitched records show zero stop violations.
- **PPO — NO_GO accepted.** Median active-day annualized return ≈ 27.36% clears the 26.87% return hurdle, but median Sharpe ≈ 1.617 is below 1.64, median MaxDD ≈ -9.10% is worse than -8.81%, and only 1/3 seeds clears the Sharpe hurdle rather than the required 2/3.
- **SAC — NO_GO accepted.** Median return ≈ 24.90% and median Sharpe ≈ 1.527 are below the frozen hurdle; 0/3 seeds clears Sharpe.
- **TD3 — NO_GO accepted.** Median return ≈ 18.98%, Sharpe ≈ 1.210 and MaxDD ≈ -12.33% are materially below the hurdle; 0/3 seeds clears Sharpe.
- **Project-level decision — NO_GO accepted.** No algorithm has per-algorithm GO, so project-level `NO_GO` follows the frozen evaluator contract.
- **MaxDiv frontier — accepted.** PPO/SAC/TD3 are all reported Pareto-dominated on the frozen Sharpe / MaxDD / Calmar dimensions.
- **No Test-informed winner selection — PASS.** PPO may be described as the closest RL result, but this does not authorize selecting or advancing PPO based on Test.

## Interpretation boundary

This result supports the narrow conclusion:

```text
Under the frozen F0 / 3-seed / 20-pass corrected protocol,
PPO, SAC and TD3 do not provide sufficient incremental value over the EqualWeight hurdle,
and none justifies conditional formal robustness.
```

It does **not** prove that all RL architectures or all feature sets are permanently unprofitable. However, because `RESEARCH_BENCHMARK_TEST` has already been consumed repeatedly and the protocol explicitly forbids Test-informed iteration, this result cannot be used to redesign the RL model/feature set and rerun on the same Test as confirmatory evidence.

## Authorized next action

```yaml
authorized_next:
  - GATE_4_RL_NO_GO_CLOSEOUT
```

`GATE_4_RL_NO_GO_CLOSEOUT` is documentation/decision closeout only. It may:

1. record the accepted formal NO_GO result and archive the exact artifacts/config hash;
2. summarize the economic comparison against EqualWeight and MaximumDiversification;
3. update the research roadmap so the current F0 PPO/SAC/TD3 branch is marked closed for formal robustness;
4. identify future research hypotheses only as **new pre-registered experiments requiring a new untouched forward period or separately authorized data regime**;
5. preserve deterministic strategies as the current benchmark/fallback path without starting any new optimization or live execution.

No new RL training, feature change, tuning, or market deployment is authorized by this closeout.

## Still forbidden

```yaml
forbidden_next:
  - GATE_4_10_SEED_FORMAL
  - CONDITIONAL_FORMAL_ROBUSTNESS_EXECUTION
  - RL_RETRAINING_ON_RESEARCH_BENCHMARK_TEST
  - PPO_ONLY_ADVANCEMENT_FROM_TEST
  - SAC_ONLY_ADVANCEMENT_FROM_TEST
  - TD3_ONLY_ADVANCEMENT_FROM_TEST
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
CORRECTED_F0_RL_3SEED
= FORMAL_NO_GO_ACCEPTED_RL_ROBUSTNESS_NOT_AUTHORIZED

NEXT
= GATE_4_RL_NO_GO_CLOSEOUT
```
