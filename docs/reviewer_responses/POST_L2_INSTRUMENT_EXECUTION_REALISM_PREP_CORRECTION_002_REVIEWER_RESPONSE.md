# Reviewer Response — POST_L2 Instrument Execution Realism PREP CORRECTION_002

```yaml
handoff_id: G4_POST_L2_INSTRUMENT_EXECUTION_REALISM_PREP_CORRECTION_002
reviewed_packet: docs/review_packets/POST_L2_INSTRUMENT_EXECUTION_REALISM_PREP.md
reviewed_packet_commit: f6664f380965b2123b77442ac7ec61a3fc1106c7
code_commit: 1ca71bb006cd4f82de1e10c3042bbd73395833e1
decision: EXECUTION_REALISM_PREP_FINAL_CONTRACT_SUBSTANTIVELY_ACCEPTED_STALE_FREEZE_BLOCK_MUST_BE_REMOVED
reviewer_state: REVISIONS_REQUIRED
authorized_next:
  - POST_L2_INSTRUMENT_EXECUTION_REALISM_PREP_CONSISTENCY_CLEANUP
forbidden_next:
  - POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN
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

The substantive CORRECTION_002 Southbound fixes are accepted. The packet now correctly separates 03110.HK listing/data/Southbound dates, models pre-2024-05-06 structural ineligibility, freezes the 100→50 lot transition at 2026-07-24, keeps same-day reversal UNKNOWN/NOT_RELIED_UPON, routes 03110 through SouthboundETFCostModel with ETF stamp duty 0 and date-effective HK fees, models T+2 settlement with no unsettled-cash reuse, marks historical PremiumGuard NOT_EVALUABLE_HISTORICALLY, and defines S2 in common CNY base.

However, the packet still contains stale contradictory freeze records in its Approval Record. Because this packet is intended to be the executable source-of-truth for the upcoming runner, those contradictions are blocking even though the corrected main sections are substantively right.

## Blocking consistency cleanup

### 1. Remove stale duplicated `frozen:` block

At the end of the packet, a second legacy `frozen:` block still states obsolete semantics including:

```text
execution: ... T+1 settlement
costs: MainlandETFCostModel 1x + 5bp slippage + lot rounding + T+1 settlement; PremiumGuard US_BROAD
fail_closed: ... premium->cash
stop_criteria: ... S4 premium>5% days
```

These directly contradict the accepted CORRECTION_002 contract:

```text
03110.HK settlement = T+2 with no unsettled-cash reuse
no extra 5bp slippage overlay
PremiumGuard in INSTRUMENT_BACKTEST = NOT_EVALUABLE_HISTORICALLY / N/A
no premium-magnitude threshold or premium->cash behavior
S4 historical IOPV metric = N/A in backtest mode
```

Delete the stale legacy block or replace it with one single canonical frozen summary matching Sections 2b/4/6/8. There must be exactly one unambiguous freeze record for runner implementation.

### 2. Correct the Mainland instrument typo

Section 4 cost routing currently lists:

```text
Mainland-listed (513300/512100/...)
```

The CN_LARGE frozen instrument is `510300.SH`, not `513300`. Correct the typo and add a mapping assertion in the planned test so the runner cannot silently route a nonexistent/wrong code.

### 3. Normalize S4 wording

Section 6 already says PremiumGuard is `NOT_EVALUABLE_HISTORICALLY`, but S4 still says:

```text
IOPV fail-closed buy trigger rate >5% ... backtest mode expected N/A
```

For this historical INSTRUMENT_BACKTEST run, freeze S4 explicitly as `NOT_APPLICABLE / NOT_EVALUATED` and exclude it from STOP evaluation. Preserve the >5% criterion only for a future PAPER/LIVE gate where realtime IOPV exists. This avoids a runner ambiguity between `N/A` and `STOP`.

## Accepted elements to preserve

- MaximumDiversification only, lookback 120 / shrinkage 0.5 / accepted RiskOverlayV0;
- no Momentum blend, dense/dynamic alpha search or result-informed retuning;
- nominal L1 window remains decision 2022-06-09..2026-08-06 / execution 2022-06-10..2026-08-07;
- 03110 listing_date=2013-06-17, local_data_start=2021-01-11, southbound_eligible_from=2024-05-06;
- pre-Southbound interval cash parking and S3 counting;
- 03110 lot 100 before 2026-07-24, 50 from 2026-07-24;
- same_day_reversal UNKNOWN/NOT_RELIED_UPON;
- Mainland instruments use MainlandETFCostModel; 03110 uses SouthboundETFCostModel;
- ETF stamp duty 0; no extra slippage overlay;
- 03110 T+2 settlement, no unsettled-cash reuse;
- historical PremiumGuard N/A, no fabricated IOPV, no close_to_official_nav_gap threshold;
- S2 costs and traded notionals converted to CNY base before aggregation;
- no pre-launch backfill;
- T-close → next tradable session open execution;
- research-return and executable-net paths remain separate;
- PPO/SAC/TD3 remain closed; QMT live/forward/paper/live remain unauthorized.

## Next action

This should be a documentation-only consistency cleanup. Do not implement or run `gate4_instrument_execution_realism.py` yet. Once the stale freeze block, `510300` typo and S4 N/A semantics are corrected and reviewed, one frozen `POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN` may be considered for authorization.
