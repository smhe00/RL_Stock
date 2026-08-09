# Reviewer Response — RL FORMAL PROTOCOL PREP

```yaml
handoff_id: RL_FORMAL_PROTOCOL_PREP_001
reviewed_code_commit: 707bbe34d157e66275edfac0e9f35c24ce687a02
reviewed_packet_commit: 90558aaef0b0a900572ed98f6079b420a05d06ef
reviewed_packet: docs/review_packets/RL_FORMAL_PROTOCOL_PREP.md
decision: TARGETED_PROTOCOL_CORRECTIONS_REQUIRED
reviewer_state: REVISIONS_REQUIRED
```

## Summary

The prep gate is directionally strong: it freezes F0, the corrected walk-forward/evaluation path, 475-date execution-mask parity, fixed train budget, three algorithms, seed IDs, tracked artifacts, and explicit stop conditions without launching RL training.

However, the current document is not yet a sufficiently unambiguous formal experiment contract. Several choices either conflict with already-frozen repository contracts or leave material research degrees of freedom unresolved. These must be fixed **before any corrected F0 RL training is authorized**.

## Passed / accepted

- **Prep-only scope — PASS.** No RL retraining, corrected 3-seed execution, Optuna, sweep, F2/F3, or feature-set change was performed.
- **Corrected evaluation semantics — PASS in direction.** E1/E2/E3, fold-local reset, costs, corporate actions, t-close→t+1-open, and exact 475 execution-date mask are correctly referenced.
- **Train budget skeleton — PASS.** `TRAIN_PASSES=20` and fold-local `train_decision_steps` are frozen.
- **Seed identities — PASS as a pilot seed set.** `{42, 2026, 7}` is deterministic and auditable.
- **Artifact intent — PASS.** Results/raw series are intended to be tracked rather than relying on prose-only summaries.
- **No formal significance claim from 3 seeds — PASS.** The protocol correctly avoids claiming statistical significance from three seeds.

## Blocking protocol corrections

### P1 — F0 is correct, but the stated reason improperly consumes the descriptive feature diagnostic

The approved feature closeout explicitly said the F1 diagnostic is **descriptive negative evidence only** and must not be used to delete F1 features or change the RL observation/network.

The new protocol repeatedly says, in effect:

```text
observation = F0 because feature-ablation found no F1 gain
```

That is too strong and creates exactly the model-selection interpretation the closeout prohibited.

At the same time, the older frozen `FEATURE_ABLATION_SPEC.md` already states that the formal baseline uses F0 and does not mix F1/F2/F3 into that formal run. Therefore F0 can remain frozen, but the rationale must be corrected:

```text
F0 is preserved because it is the pre-existing frozen formal baseline contract.
F1 remains a separate Gen-2 research candidate set; the descriptive diagnostic does not prove F1 has no value and is not used to select F0.
```

### P2 — The protocol silently removes the previously frozen conditional 10-seed stage

`FEATURE_ABLATION_SPEC.md` still says:

```text
10-seed formal 使用 F0（当前特征集）冻结
```

The new protocol instead says:

```text
10-seed = REMOVED_FROM_ACTIVE_ROADMAP / REMOVED
```

This is a conflict between frozen canonical documents. The current prep authorization allowed defining seed policy for the **next corrected RL experiment**, but it did not silently deprecate an earlier frozen formal stage.

Required correction:

- treat the next `{42, 2026, 7}` run as **CORRECTED_F0_RL_3SEED / research-benchmark GO-NO-GO**, not the final formal statistical stage;
- keep any 10-seed stage **conditional and not authorized**, rather than deleting it now; or explicitly deprecate the old frozen spec through a separately justified reviewer-approved protocol change.

Preferred roadmap wording:

```text
3-seed corrected benchmark -> GO/NO-GO -> conditional formal robustness stage
```

No 10-seed execution is authorized by this review.

### P3 — The 475-date Test panel is a research benchmark, not a pristine final holdout

The same historical 475-date panel has already been observed through prior RL pilot references, deterministic horse-race results, and feature diagnostics. Therefore this protocol must not present the corrected 3-seed run as an untouched confirmatory holdout experiment.

Required correction:

- label the 475-date mask as `RESEARCH_BENCHMARK_TEST` (or equivalent);
- define GO as evidence that RL is worth further validation, not proof of final generalization;
- reserve a future `FINAL_FORWARD_HOLDOUT` / genuinely unseen forward period for final confirmation.

This is a labeling/interpretation correction; the exact 475-date mask itself remains useful and should stay frozen.

### P4 — EqualWeight alone is not the full non-RL hurdle

The finalized horse race shows two materially different benchmark anchors:

```text
EqualWeight:
  active-ann 26.9%, Sharpe 1.64, MaxDD -8.8%, Calmar 3.05

MaximumDiversification:
  active-ann 18.3%, Sharpe 2.77, MaxDD -3.4%, Calmar 5.38
```

EqualWeight is a strong return hurdle, but MaximumDiversification is the clearly stronger risk-adjusted frontier. A protocol intended to decide whether RL has incremental economic value should not ignore that frontier.

Required correction: freeze a two-tier benchmark interpretation, for example:

```text
PRIMARY RETURN HURDLE = EqualWeight
RISK-ADJUSTED FRONTIER REFERENCE = MaximumDiversification
```

The exact GO rule may remain based on the EqualWeight hurdle if clearly labeled `PROMISING_GO`, but the protocol must also report whether RL is Pareto-dominated by the deterministic frontier on Sharpe / MaxDD / Calmar. It must not claim overall RL superiority merely for clearing EqualWeight.

Also either use the documented EqualWeight MaxDD hurdle in GO/guardrail logic or remove it from the frozen hurdle tuple; currently it is frozen but ignored by §10.

### P5 — GO/NO-GO is ambiguous across PPO / SAC / TD3

The protocol defines `median(seed Sharpe)` and `median(seed CAGR)` but does not specify the algorithm dimension. With three algorithms, this is materially ambiguous.

Required correction:

- define GO/NO-GO **per algorithm** first;
- define the project-level interpretation separately;
- explicitly prohibit Test-based algorithm winner selection;
- freeze what happens after the 3-seed gate if one/two/all algorithms pass.

If a later stage advances only one algorithm, the selection rule must be validation-only and frozen **before Test is consumed**. Otherwise all predeclared algorithms must continue under the same rule.

### P6 — “Validation-only model selection” is underspecified

The protocol says:

```text
若执行多 checkpoint：按 VAL 指标选
```

but does not freeze:

- whether checkpoint selection exists at all;
- checkpoint cadence;
- the primary validation metric;
- tie-break rule;
- whether selection is per fold / per seed / per algorithm.

This leaves a large post-hoc degree of freedom.

Preferred correction for this gate: use **final training endpoint only, no checkpoint search**. If checkpointing is required, freeze the exact schedule and validation objective/tie-break now.

### P7 — Effective algorithm hyperparameters are not fully frozen

`WalkForwardRunner.run_fold_rl()` instantiates SB3 algorithms with only `policy_kwargs`, seed, device, and defaults for the remaining algorithm-specific parameters. Although `stable-baselines3==2.8.0` is pinned in `requirements-gate3.txt`, a formal contract should record the **effective constructor configuration**, not rely on implicit defaults.

Required correction: freeze and test the effective hyperparameters for PPO/SAC/TD3, including all material defaults such as learning rate, gamma, batch size, rollout/buffer settings, tau, train frequency/gradient steps, PPO epochs/GAE/clip parameters, TD3 policy delay/target noise, etc., plus SB3/Torch/Gym versions and device policy.

Prefer one machine-readable protocol config consumed by the execution runner and tests rather than prose + source-string assertions.

### P8 — Correctness invariants must be hard stop conditions, not only descriptive contract text

The current stop list covers NaN/Inf, negative cash, save/load mismatch, and non-finite OOS return. The corrected evaluator also depends on invariants that are equally fundamental.

Add hard-stop conditions for at least:

```text
execution_dates != exact 475-date mask
n_eval_steps != 475
cost reconciliation failure
missing/duplicate fold result or raw series
```

The formal runner should fail closed on these conditions rather than merely report them.

### P9 — Metric naming must distinguish stitched active-day annualization from calendar CAGR

The deterministic artifact calls the hurdle `active_day_annualized_return`, while the pilot `stitched_metrics()` computes

```text
(1 + cumulative_return) ** (252 / 475) - 1
```

and labels it `cagr` even though validation gaps are omitted from the stitched series.

Freeze one unambiguous name such as:

```text
active_day_annualized_return
```

and use the same definition on RL and non-RL sides. Do not mix this with calendar-time CAGR in tables or GO criteria.

## Test-review note

The added tests are useful contract smoke checks, but they are currently too shallow to close the formal protocol. In particular, the GO/NO-GO tests do not encode the full rule (CAGR + stops + algorithm dimension), and several configuration tests inspect source strings/default signatures rather than a canonical machine-readable experiment config.

The packet reports `210 passed`; no contrary failure evidence was found in the reviewed commit. This review is therefore a **protocol-definition revision**, not a test-failure disposition.

## Authorized next action

```yaml
authorized_next:
  - RL_FORMAL_PROTOCOL_PREP_CORRECTIONS
```

This sub-gate is limited to protocol/config/test corrections only:

1. fix F0 rationale without consuming the descriptive F1 diagnostic;
2. reconcile 3-seed vs conditional 10-seed/future robustness stage;
3. relabel 475 dates as research benchmark and reserve final forward holdout;
4. add the deterministic risk-adjusted frontier reference;
5. make per-algorithm and project-level GO/NO-GO unambiguous;
6. freeze checkpoint/validation selection policy;
7. freeze effective SB3 hyperparameters/software/device in machine-readable form;
8. add evaluator-invariant stop conditions and consistent active-day metric naming;
9. update tests/check script; stop for review.

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
RL_FORMAL_PROTOCOL_PREP
= TARGETED_PROTOCOL_CORRECTIONS_REQUIRED

NEXT
= RL_FORMAL_PROTOCOL_PREP_CORRECTIONS
```
