# Reviewer Response — POST_L2 Instrument Execution Realism PREP CONSISTENCY CLEANUP

```yaml
handoff_id: G4_POST_L2_INSTRUMENT_EXECUTION_REALISM_PREP_CONSISTENCY_CLEANUP_001
reviewed_packet: docs/review_packets/POST_L2_INSTRUMENT_EXECUTION_REALISM_PREP.md
reviewed_packet_commit: c780580c990fe5ed2a985af0752a2fb07ea77032
code_commit: 1ca71bb006cd4f82de1e10c3042bbd73395833e1
decision: EXECUTION_REALISM_PREP_CONSISTENCY_CLEANUP_ACCEPTED_FROZEN_RUN_AUTHORIZED
reviewer_state: REVIEW_COMPLETE
authorized_next:
  - POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN
forbidden_next:
  - FORWARD_PAPER_VALIDATION
  - PAPER
  - LIVE
  - RESULT_INFORMED_BLEND_WEIGHT_SEARCH
  - DENSE_ALPHA_SEARCH
  - DYNAMIC_ALPHA
  - PPO
  - SAC
  - TD3
  - RL_RETRAINING
  - RL_HYPERPARAMETER_TUNING
  - RL_COMPARISON
  - QMT_LIVE
```

## Review conclusion

The documentation-only consistency cleanup is accepted. The exact cleanup commit changes only `docs/agent_state/CLAUDE_STATUS.yaml` and `docs/review_packets/POST_L2_INSTRUMENT_EXECUTION_REALISM_PREP.md`; no runner, source, test implementation, data, or result artifact was changed or generated in this handoff.

The three requested cleanup items are resolved in the executable contract:

1. The stale duplicate legacy `frozen:` block has been removed and the Approval Record now contains one canonical frozen summary matching Sections 2b/4/6/8.
2. The Mainland cost-routing typo is corrected to `CN_LARGE = 510300.SH`, and the planned runner test explicitly requires the exact mapping assertion.
3. `S4` is now `NOT_APPLICABLE / NOT_EVALUATED` in `INSTRUMENT_BACKTEST` and excluded from historical STOP evaluation; the >5% realtime IOPV criterion is reserved for future PAPER/LIVE only.

The previously accepted Southbound contract remains frozen: 03110.HK listing/data/Southbound dates are distinct; pre-2024-05-06 is structurally non-executable and cash parked; board lot is date-effective 100→50 at 2026-07-24; same-day reversal remains UNKNOWN/NOT_RELIED_UPON; 03110 routes through `SouthboundETFCostModel` with ETF stamp duty 0 and date-effective fees; HK settlement is T+2 with no unsettled-cash reuse; historical PremiumGuard is not evaluable and must not fabricate IOPV; S2 costs and traded notionals aggregate in CNY base.

The frozen research core remains MaximumDiversification only with lookback 120, shrinkage 0.5 and accepted RiskOverlayV0. The nominal L1 window remains decision 2022-06-09..2026-08-06 and execution 2022-06-10..2026-08-07, with no pre-launch backfill and T-close → next tradable session open execution. No Momentum blend, dense/dynamic alpha search, result-informed retuning, PPO/SAC/TD3, forward/paper/live, or QMT live is authorized.

## Authorized RUN requirements

One frozen `POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN` is authorized. The runner must implement exactly the canonical PREP contract and must include the planned invariants/tests before reporting results. It must report the exact implementation commit, commands/tests executed, data/provenance bindings, net-vs-research metrics, annual and frozen stress subperiods, S1-S4 evaluation, fail-closed counts, and any STOP condition.

S3 remains intentionally frozen as specified, including structural ineligibility cash-parking events. If S3 triggers under the frozen 1011-day window, report it as a STOP result; do not change the instrument mapping, threshold, window, or counting rule after observing the result.

No later gate is authorized until the execution-realism RUN packet is reviewed.
