# Reviewer Response — Gate 4 Long-Horizon Non-RL PREP

```yaml
handoff_id: G4_LONG_HORIZON_NON_RL_PREP_001
reviewed_code_commit: 8cd365904ec2b51eeece6615b54a9fda33f149ff
reviewed_packet: docs/review_packets/GATE_4_LONG_HORIZON_NON_RL_PREP.md
decision: PREP_APPROVED_L1_RUN_AUTHORIZED
reviewer_state: REVIEW_COMPLETE
authorized_next:
  - GATE_4_LONG_HORIZON_NON_RL_RUN
forbidden_next:
  - PPO
  - SAC
  - TD3
  - RL_RETRAINING
  - RL_HYPERPARAMETER_TUNING
  - RL_COMPARISON
  - L2_PROXY_SCENARIO_EXECUTION
  - QMT_LIVE
```

## Review conclusion

The PREP packet is approved. It correctly freezes the L1 objective, the six-method set, canonical parameters, causal T->T+1 execution semantics, long-window reporting, and explicit exclusion of PPO/SAC/TD3. The study remains a robustness diagnostic rather than pristine OOS.

The next gate may implement the planned runner/tests and execute the single L1 long-horizon horse race, subject to the hard guards below.

## Hard guards for L1 execution

1. **Window/date parity is fail-closed.** The runner must derive the usable decision window from the actual loaded data and then assert exact parity with the frozen contract: start `2022-06-10`, end `2026-08-07`, `1011` decision/execution dates under the chosen single-segment semantics. If the derived window differs for any reason, stop and return a blocker/revision packet; do not silently shift the date range or day count.

2. **No old 475-day test mask.** The L1 code path must not import/use `exact_test_mask` or `RESEARCH_BENCHMARK_TEST` to determine the evaluation dates. The 475-day benchmark may appear only as a historical comparison in the final report.

3. **Method set is immutable.** Execute exactly: `HS300_ref`, `EqualWeight`, `MaximumDiversification`, `MinimumVariance`, `RiskParity_IVOL`, `Momentum_12_1`. No post-result additions/removals and no lookback/shrinkage tuning.

4. **Canonical deterministic parameters must match current source.** In particular: MaxDiv `lookback=120, shrinkage=0.5`; MinVar `lookback=120, shrinkage=0.5`; RiskParity `lookback=60`; Momentum `lookback=252, skip=21`.

5. **Causal data only.** At decision date T, covariance/volatility/momentum and all portfolio inputs may use only information dated <=T. Existing corrected accounting/company-action ordering remains unchanged.

6. **Cost-model labeling.** The executable deterministic strategies should reuse the current project execution path and its current `MainlandETFCostModel` exactly for comparability with Gate 4. Because the 11-slot universe includes non-mainland economic exposures, the final report must label this as the current project 1x cost-model simplification, not as a claim of fully realistic cross-market/Southbound fee modeling.

7. **HS300 is a research-adjusted reference, not an executable net strategy.** Report it in a clearly separate reference column/section. Do not directly present its return minus strategy net return as if both had identical transaction-cost/accounting semantics. Sharpe/MaxDD comparison is acceptable when the distinction is explicit.

8. **Sub-period reporting is descriptive.** Calendar-year breakdown is required. The frozen `2022H2-2023` vs `2024-2026` split may also be shown, but label it as a pre-frozen descriptive phase split rather than an objectively identified market-regime classifier.

9. **No data fabrication/backfill in L1.** Re-fetch/repair within actual live periods is allowed only with provenance. Any material source mismatch, adjustment mismatch, or pre-launch requirement is a blocker.

10. **Tests/check before full run.** `tests/test_long_horizon_nonrl.py` plus the runner `--check` contract validation must pass before the full L1 execution. A failed invariant is a stop condition, not something to bypass.

## Required result packet

After execution, return `docs/review_packets/GATE_4_LONG_HORIZON_NON_RL_RUN.md` with:

- exact implementation/result commit;
- exact window and date count evidence;
- data provenance/repairs, if any;
- test results and `--check` output;
- full-period table: cumulative return, active-day annualized return, calendar CAGR where defined, vol, Sharpe, Sortino, MaxDD, Calmar, worst year, worst rolling 12m, turnover, cost/traded, concentration;
- annual/sub-period Sharpe and MaxDD;
- direct comparison of the new long-window metrics with the old 475-day metrics, especially MaxDiv Sharpe `2.77` and MaxDD `-3.4%`;
- no GO threshold invented after observing results;
- explicit confirmation that PPO/SAC/TD3 and L2 proxy research were not executed.

## Interpretation target

The primary question is whether MaximumDiversification retains a **material risk-adjusted and drawdown advantage** after the early weak-equity period is included. Exact reproduction of the 475-day Sharpe 2.77 is not required. The reviewer will focus on the magnitude of Sharpe compression, MaxDD expansion, stability across calendar sub-periods, and whether the advantage remains economically meaningful relative to EqualWeight and HS300.
