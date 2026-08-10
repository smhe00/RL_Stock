# Reviewer Response — POST_L2 Instrument Execution Realism PREP

```yaml
handoff_id: G4_POST_L2_INSTRUMENT_EXECUTION_REALISM_PREP_001
reviewed_packet: docs/review_packets/POST_L2_INSTRUMENT_EXECUTION_REALISM_PREP.md
reviewed_packet_commit: aefd001e0478f59ab43a82ace3779b79fdc2cd53
parent_code_commit: 1ca71bb006cd4f82de1e10c3042bbd73395833e1
decision: EXECUTION_REALISM_PREP_SUBSTANTIALLY_CORRECT_CONTRACT_FIX_REQUIRED
reviewer_state: REVISIONS_REQUIRED
authorized_next:
  - POST_L2_INSTRUMENT_EXECUTION_REALISM_PREP_CORRECTION
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

The PREP is directionally correct: MaxDiv 120/0.5 remains frozen, the L1 1011-day real-instrument window is reused, execution is separated from research return, T-close -> next-session-open semantics are declared, lot/settlement/fail-closed concepts are included, and no RL or result-informed retuning is introduced. The commit is documentation/status only; no execution-realism run or new strategy result was produced.

However, the PREP cannot authorize a RUN yet because three contract elements are inconsistent with the already-audited repository state, and one STOP metric lacks a machine-evaluable denominator.

## Blocking correction 1 — HK_DIVIDEND mapping drift must be explicit and provenance-bound

The packet freezes:

```text
HK_DIVIDEND -> 513690.SH
```

but the audited Gate-1 preferred/frozen universe is:

```text
HK_DIVIDEND -> 03110.HK
```

Gate-1 corrections list `513690` only as an alternative instrument, while `03110.HK` has the audited listing date, Southbound eligibility date, lot metadata and data-source provenance.

Therefore the corrected PREP must choose exactly one path before RUN:

1. keep `03110.HK` as the instrument and explicitly model HKEX/Southbound execution constraints; or
2. deliberately substitute `513690.SH` for execution-realism and label this as an instrument substitution rather than reuse of the frozen mapping.

If option 2 is chosen, bind the replacement to explicit evidence: exact listing/real-history start, data file/source, raw open/close availability over the full 1011-day window, adjusted/research series mapping, lot size, exchange/T+0 rules, ADV/liquidity evidence and applicable fee model. The RUN must fail closed if any of those are not available. Do not silently change the instrument universe.

## Blocking correction 2 — fee contract contradicts the actual MainlandETFCostModel

The packet currently says:

```text
commission 万1~万3 + sell stamp duty 0.05%/0.1% + transfer fee
```

but the repository implementation currently has:

```text
broker_commission_rate = 0.00005   # 万0.5
stamp_duty_rate = 0.0              # ETF
exchange_fee_rate = 0.0
broker_commission_includes_exchange_fee = UNKNOWN_PENDING_BROKER_FEE_AUDIT
```

The PREP must not invent a different fee schedule under the label "existing MainlandETFCostModel (1x)". Freeze one exact executable cost contract before RUN.

Preferred correction:

```text
base case = repository MainlandETFCostModel as currently implemented
commission = 0.00005 unless account-verified evidence changes it before RUN
ETF stamp duty = 0 in the base case
exchange fee = 0 while inclusion remains UNKNOWN_PENDING_BROKER_FEE_AUDIT
spread/slippage must not be double-counted against the model's existing half_spread_bps/slippage_bps
```

If Claude proposes a new 5bp execution slippage overlay, state whether it replaces or adds to `half_spread_bps=1` and `slippage_bps=2`. The same friction must never be charged twice.

## Blocking correction 3 — PremiumGuard threshold semantics are not implemented

The PREP states that a premium threshold can trigger `US_BROAD` conversion to cash. Current `PremiumGuard` does not implement that behavior:

- if IOPV is unavailable/stale, it fail-closes buys;
- if IOPV is fresh, it returns `buy_allowed=True` regardless of `threshold_pct`;
- the source explicitly forbids using historical `close_to_official_nav_gap` P95 directly as a Live threshold.

Therefore the corrected PREP must freeze a research-valid rule that the RUN can actually execute.

Acceptable choices are:

1. **availability-only guard for this historical execution-realism track**: missing/stale historical IOPV-equivalent data blocks new buys, with no premium-magnitude threshold; or
2. add a separately reviewed historical FairNAV/IOPV proxy specification with exact formula, data source, timing and threshold before RUN.

Do not claim "premium > threshold -> cash" until the signal source and threshold logic exist and are tested. Historical `close_to_official_nav_gap` must not be reused as a disguised real-time premium threshold.

## Required clarification — S2 denominator/unit

The packet says:

```text
average daily fees > 5bp OR slippage cost > 10bp
```

Freeze the denominator and aggregation explicitly, for example:

```text
fee_bps_of_traded_notional = total_fee / total_traded_notional * 1e4
slippage_bps_of_traded_notional = total_slippage / total_traded_notional * 1e4
```

or an alternative NAV-based definition. The same definition must be used in the runner, artifact and STOP logic.

## Passed elements — keep frozen

- MaxDiv core only: lookback 120, shrinkage 0.5, accepted overlay;
- no Momentum blend, dense search or result-informed tuning;
- L1 real-instrument window remains decision 2022-06-09..2026-08-06 / execution 2022-06-10..2026-08-07 / 1011 intervals;
- no pre-launch backfill;
- T close -> next-session open execution intent;
- research-return and executable-net paths separated;
- lot rounding / cash residual accounting required;
- missing quote must fail closed rather than fabricate fills;
- NaN/non-finite observations must fail closed;
- annual + weak/strong subperiod reporting retained;
- PPO/SAC/TD3 remain closed;
- QMT live, paper/live and forward validation remain unauthorized.

## Required correction packet

Suggested handoff:

`G4_POST_L2_INSTRUMENT_EXECUTION_REALISM_PREP_CORRECTION_001`

The correction is PREP/specification only. Do not run the execution-realism experiment yet. Do not change MaxDiv parameters, L1 window, architecture conclusion, stress periods or research results.

The corrected packet must resolve:

1. `03110.HK` vs `513690.SH` mapping and full provenance;
2. exact fee/friction contract with no stamp-duty or spread/slippage inconsistency/double count;
3. PremiumGuard historical semantics and data source;
4. S2 denominator/unit;
5. corresponding tests/invariants to be implemented only after the corrected PREP is approved.

Once the corrected PREP is reviewed and accepted, one frozen `POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN` may be authorized.
