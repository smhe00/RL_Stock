# Reviewer Response — POST_L2 Deterministic Architecture PREP

```yaml
handoff_id: G4_POST_L2_DETERMINISTIC_ARCH_PREP_001
reviewed_packet: docs/review_packets/POST_L2_DETERMINISTIC_ARCHITECTURE_PREP.md
reviewed_packet_commit: 0710c54adbd1ad23dc923d1dfb0d2d5a1c0d4f8d
parent_code_commit: 7781800d4ce996a216aa1e08f1346504c2628b66
decision: ARCH_PREP_SUBSTANTIALLY_CORRECT_SEMANTIC_FIX_REQUIRED
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

The submitted PREP is substantively aligned with the prior reviewer requirements and is suitable as the basis for a frozen MaxDiv + Momentum architecture study after three blocking semantic corrections.

The candidate set is finite and ex-ante: pure MaxDiv and pure Momentum controls plus three static blends (75/25, 50/50, 25/75). There is no dense alpha sweep and no dynamic rule. Parent parameters remain frozen: MaxDiv lookback 120 / shrinkage 0.5 and Momentum lookback 252 / skip 21. The accepted 11-slot panel, `RiskOverlayV0`, stress periods and no-RL/no-live constraints remain fixed.

No combined result has been run, so these corrections can still be made cleanly before the architecture experiment.

## Blocking correction 1 — HK FX timing must preserve signal/return separation

Section 4 currently states:

```text
CNY return-level treatment: HK_TECH/HK_DIVIDEND = HKD × hkd_cny（T-1 FX）
```

That is not the accepted L2 return-level contract and is internally inconsistent with the next line saying the return panel is unlagged.

Freeze the architecture timing exactly as:

```text
return_level_hk_cny(t) = raw_hk_index_hkd(t) * hkd_cny(t)
signal_hk_cny(T) = return_level_hk_cny(T-1)
realized_return_for_decision_T
  = return_level_hk_cny(T+1) / return_level_hk_cny(T) - 1
```

Therefore:

- decision-T HK signal uses the converted T-1 level, containing T-1 HK and T-1 FX;
- the return level itself is an unlagged same-date CNY economic level;
- realized research return remains converted CNY T->T+1;
- do not insert a T-1 FX lag directly into the raw return-level construction.

This is the exact signal/return separation accepted in the FX-corrected L2 gen3 and must not drift in the architecture RUN.

## Blocking correction 2 — R4 cost inequality is reversed

The PREP currently states:

```text
R4: 1x 成本后 cum Δ 相对无成本 <= -3.0pct
```

If `cum_delta = net cumulative return - gross cumulative return`, transaction-cost drag is normally zero or negative. The intended rule is “cost drag no worse than 3 percentage points”. Therefore freeze one explicit convention, preferably:

```text
cost_cum_delta = net_cum_return - gross_cum_return
R4 passes iff cost_cum_delta >= -3.0 percentage points
```

Equivalent positive-drag form:

```text
cost_drag = gross_cum_return - net_cum_return
R4 passes iff cost_drag <= 3.0 percentage points
```

Use one convention consistently in the packet, runner, artifact and pass/fail logic.

## Blocking correction 3 — R1/R2 must bind to exact C0 values, not rounded display values

The PREP correctly intends R1/R2 to be relative to pure MaxDiv C0, but then illustrates them from rounded `6.0%` CAGR and `-10.4%` MaxDD.

The accepted gen3 artifact contains exact C0 metrics:

```text
MaxDiv calendar_cagr = 0.059496
MaxDiv max_drawdown  = -0.103874
```

Freeze the machine-evaluable rules as:

```text
R1: candidate_calendar_cagr - C0_calendar_cagr >= 0.005
R2: candidate_max_drawdown >= C0_max_drawdown - 0.05
```

with C0 bound to the exact accepted gen3 control path/metrics. Equivalent exact thresholds from the current accepted artifact are:

```text
R1 threshold = 0.064496   # 6.4496%
R2 threshold = -0.153874  # -15.3874%
```

The relative-form rule is preferred. Rounded headline values may be displayed in reports but must not drive pass/fail logic.

## Clarify C0/C1 control handling

The correction must also state how pure-parent controls enter the architecture RUN. Use one of these two valid approaches:

1. reuse the exact accepted gen3 executable parent weight/return paths; or
2. deterministically reconstruct C0/C1 with the unchanged accepted implementations and assert metric parity to the accepted gen3 artifact before evaluating C2-C4.

Do not silently create a new parent baseline with different timing, fallback, FX or overlay semantics.

## Passed PREP elements — keep frozen

- parent strategies immutable and canonical;
- candidate set frozen to C0-C4 only;
- pure parents retained as controls;
- no dense or efficient-frontier weight search;
- no dynamic rule in this track;
- static blend semantics explicitly frozen;
- final `RiskOverlayV0` application specified;
- turnover/cost computed from the final executable path;
- no lookahead and accepted fallback semantics retained;
- full evaluation metric set frozen;
- accepted stress regimes reused;
- R1/R2/R3/R5/R6 intent is suitable subject to exact-value binding above;
- instrument-level realism -> forward/paper -> small-capital path preserved;
- PPO/SAC/TD3 and QMT live remain closed.

## Candidate set remains frozen

Do not change the candidate set during this correction:

```text
C0 = 100% MaxDiv
C1 = 100% Momentum
C2 = 75% MaxDiv + 25% Momentum
C3 = 50% MaxDiv + 50% Momentum
C4 = 25% MaxDiv + 75% Momentum
```

No 60/40, 70/30, 80/20, volatility targeting, regime switch, dynamic alpha or efficient-frontier scan is authorized in this track.

## Required correction packet

Suggested handoff:

`G4_POST_L2_DETERMINISTIC_ARCH_PREP_CORRECTION_001`

The correction is documentation/specification only. Do not run any combined strategy yet and do not change:

- C0-C4 candidate weights;
- MaxDiv or Momentum parameters;
- panel, dates, slots, data or stress regimes;
- R1 threshold magnitude (+0.5 percentage points);
- R2 threshold magnitude (+5.0 percentage points MaxDD degradation);
- R3 thresholds (Sharpe >= 0.80 and Calmar >= 0.40);
- R5/R6 semantics.

Only fix the HK signal/return FX wording, R4 sign convention, exact C0 binding for R1/R2, and C0/C1 control handling. Once the corrected PREP is reviewed and accepted, a single frozen architecture RUN over C0-C4 may be authorized.

L2 remains closed and accepted. PPO/SAC/TD3 and QMT live remain forbidden.