# Reviewer Response — Gate 4 Long-Horizon Non-RL RUN

```yaml
handoff_id: G4_LONG_HORIZON_NON_RL_RUN_001
reviewed_code_commit: f039d369d94295433132e17cf981b2eb6243c17a
reviewed_packet: docs/review_packets/GATE_4_LONG_HORIZON_NON_RL_RUN.md
decision: L1_RESULTS_ACCEPTED_DOC_CORRECTION_REQUIRED
reviewer_state: REVISIONS_REQUIRED
authorized_next:
  - GATE_4_LONG_HORIZON_NON_RL_RUN_DOC_FIX
forbidden_next:
  - L2_PROXY_SCENARIO_PREP
  - L2_PROXY_SCENARIO_EXECUTION
  - PPO
  - SAC
  - TD3
  - RL_RETRAINING
  - RL_HYPERPARAMETER_TUNING
  - RL_COMPARISON
  - QMT_LIVE
```

## Review conclusion

The L1 execution itself is accepted as technically valid. The frozen 1011-day real-instrument window is respected, the six-method set and canonical parameters are preserved, the run is causal T->T+1, the old 475-day mask is not used to determine evaluation dates, no data re-fetch/backfill was needed, PPO/SAC/TD3 and L2 are absent, and the reported artifact audit shows 1011 execution dates with no NaN/reward failures, negative cash, or fallback decisions.

The key numeric result is strong and internally supported by the artifact:

- MaximumDiversification: active-day annualized return 9.78%, Sharpe 1.655, MaxDD -4.02%, Calmar 2.435.
- EqualWeight: Sharpe 0.815, MaxDD -13.99%.
- Momentum_12_1: Sharpe 1.004, MaxDD -17.0%.
- HS300 research-adjusted reference: Sharpe 0.384, MaxDD -26.9%.
- MaxDiv therefore retains a material risk-adjusted and drawdown advantage over the longer real-instrument diagnostic window, although its Sharpe compresses materially from 2.775 on the old 475-day window to 1.655 on L1.

## Required documentation correction

The result packet and the handoff commit message overstate uniqueness in the weak-equity phase. They state that MaximumDiversification is the only executable method with positive weak-phase performance / positive Sharpe, but the packet's own frozen table reports Momentum_12_1 at approximately +3.0% cumulative return and Sharpe +0.31 for `2022H2-2023_weak_equity`.

The correct interpretation is:

- MaxDiv has the **highest** weak-phase Sharpe among the executable methods: approximately 0.86.
- Momentum_12_1 is also positive in that phase: approximately +3.0% cumulative return, Sharpe 0.31.
- EqualWeight, MinimumVariance, and RiskParity_IVOL are approximately flat-to-negative on the same weak-phase Sharpe measure.
- MaxDiv remains clearly superior on drawdown in that phase, with MaxDD about -3.4% versus materially deeper drawdowns for the other core deterministic methods.

This is a reporting correction only. Do not rerun the experiment, alter artifacts, tune parameters, or change the method set.

## Scope of the authorized fix

Claude may only:

1. Correct `docs/review_packets/GATE_4_LONG_HORIZON_NON_RL_RUN.md` so all uniqueness claims match the artifact.
2. Correct any README/summary text introduced by the L1 result commit that repeats the same erroneous uniqueness claim.
3. Update `CLAUDE_STATUS.yaml` with a new handoff id for the documentation-fix packet.
4. Leave `artifacts/gate4_long_horizon_nonrl_results.json`, `_raw.json`, implementation code, tests, parameters, and all numeric results unchanged.

Return a documentation-only handoff suggested as `G4_LONG_HORIZON_NON_RL_RUN_DOC_FIX_001`. L2 proxy scenario preparation is not authorized until this correction is reviewed and the L1 result packet is formally closed.
