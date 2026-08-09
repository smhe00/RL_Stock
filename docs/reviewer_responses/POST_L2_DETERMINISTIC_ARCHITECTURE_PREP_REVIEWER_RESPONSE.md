# Reviewer Response — POST_L2 Deterministic Architecture PREP

```yaml
handoff_id: G4_POST_L2_DETERMINISTIC_ARCH_PREP_001
reviewed_packet: docs/review_packets/POST_L2_DETERMINISTIC_ARCHITECTURE_PREP.md
reviewed_packet_commit: 0710c54adbd1ad23dc923d1dfb0d2d5a1c0d4f8d
parent_code_commit: 7781800d4ce996a216aa1e08f1346504c2628b66
decision: ARCH_PREP_SUBSTANTIALLY_CORRECT_THRESHOLD_SEMANTICS_FIX_REQUIRED
reviewer_state: REVISIONS_REQUIRED
authorized_next:
  - POST_L2_DETERMINISTIC_ARCHITECTURE_PREP_CORRECTION
forbidden_next:
  - POST_L2_DETERMINISTIC_ARCHITECTURE_RUN
  - RESULT_INFORMED_BLEND_WEIGHT_SEARCH
  - PPO
  - SAC
  - TD3
  - RL_RETRAINING
  - RL_HYPERPARAMETER_TUNING
  - RL_COMPARISON
  - QMT_LIVE
```

## Review conclusion

The submitted PREP is substantively aligned with the prior reviewer requirements and is suitable as the basis for a frozen MaxDiv + Momentum architecture study after one small but blocking correction to the success criteria.

The candidate set is finite and ex-ante: pure MaxDiv and pure Momentum controls plus three static blends (75/25, 50/50, 25/75). There is no dense alpha sweep and no dynamic rule. Parent parameters remain frozen: MaxDiv lookback 120 / shrinkage 0.5 and Momentum lookback 252 / skip 21. The accepted 11-slot panel, timing, HK CNY conversion, T-1 non-A signal treatment, T->T+1 realized-return semantics, RiskOverlayV0, stress periods and no-RL/no-live constraints are all preserved.

The canonical parent source was rechecked at commit `7781800`: Momentum still uses the frozen 252/21 positive-score rule with equal-weight fallback, while MaxDiv still uses the frozen 120-day covariance window, 0.5 shrinkage and project-constrained diversification-ratio optimization. No parameter drift was found.

## Blocking correction 1 — R4 cost inequality is reversed

The PREP currently states:

```text
R4: 1x 成本后 cum Δ 相对无成本 <= -3.0pct
```

Under the packet's own convention, `cum Δ = net cumulative return - gross cumulative return`, so transaction-cost drag is normally zero or negative. The intended rule is clearly "cost drag no worse than 3 percentage points". Therefore the correct acceptance condition must be:

```text
R4: cum_delta_1x >= -3.0 percentage points
```

or equivalently:

```text
abs(cost drag) <= 3.0 percentage points
```

The current `<= -3.0pct` would perversely require at least 3 percentage points of cost damage and would reject low-turnover candidates such as MaxDiv-like blends. This must be corrected before any RUN so that the acceptance rule remains genuinely ex-ante.

## Blocking correction 2 — compare R1/R2 to exact C0 values, not rounded display values

The packet defines the intended relative thresholds correctly, but then illustrates them using rounded accepted values (`6.0%` CAGR and `-10.4%` MaxDD). The RUN must evaluate the rules from the exact same-run C0 control values, not from those rounded display numbers.

Freeze the machine-evaluable form as:

```text
R1: candidate_calendar_cagr - C0_calendar_cagr >= 0.005
R2: candidate_maxdd >= C0_maxdd - 0.05
```

This does not change the thresholds. It only prevents a boundary candidate from being classified differently because the report rounded C0 to one decimal place.

The report may still show the approximate human-readable examples, but the decision logic must use exact values.

## Passed PREP elements

- parent strategies immutable and canonical;
- candidate set frozen to C0-C4 only;
- pure parents retained as controls;
- no dense or efficient-frontier weight search;
- static blend semantics explicitly frozen;
- final RiskOverlayV0 application specified;
- turnover/cost computed from the final executable path;
- accepted L2 timing and information cutoffs preserved;
- HK CNY/FX treatment preserved;
- no lookahead and fallback semantics restated;
- full evaluation metric set frozen;
- accepted stress regimes reused;
- R1/R2/R3/R5/R6 intent is suitable;
- instrument-level realism -> forward/paper -> small-capital path preserved;
- PPO/SAC/TD3 and QMT live remain closed.

## Required correction packet

Suggested handoff:

`G4_POST_L2_DETERMINISTIC_ARCH_PREP_CORRECTION_001`

The correction must be documentation/specification only. Do not run any combined strategy yet and do not change:

- C0-C4 candidate weights;
- MaxDiv or Momentum parameters;
- panel, dates, slots, data, FX, timing or stress regimes;
- R1 threshold magnitude (+0.5 percentage points);
- R2 threshold magnitude (+5.0 percentage points MaxDD degradation);
- R3 thresholds (Sharpe >= 0.80 and Calmar >= 0.40);
- R5/R6 semantics.

Only correct R4's inequality and bind R1/R2 to exact C0 values. Once the corrected PREP is reviewed, a single frozen architecture RUN may be authorized.
