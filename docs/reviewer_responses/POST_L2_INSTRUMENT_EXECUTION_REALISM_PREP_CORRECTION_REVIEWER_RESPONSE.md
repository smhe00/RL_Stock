# Reviewer Response — POST_L2 Instrument Execution Realism PREP Correction

```yaml
handoff_id: G4_POST_L2_INSTRUMENT_EXECUTION_REALISM_PREP_CORRECTION_001
reviewed_packet: docs/review_packets/POST_L2_INSTRUMENT_EXECUTION_REALISM_PREP.md
reviewed_packet_commit: 2396fda84fb580ad9e270526af7f851e4e361268
parent_code_commit: 1ca71bb006cd4f82de1e10c3042bbd73395833e1
decision: EXECUTION_REALISM_PREP_CORRECTION_PARTIAL_PASS_SOUTHBOUND_CONTRACT_FIX_REQUIRED
reviewer_state: REVISIONS_REQUIRED
authorized_next:
  - POST_L2_INSTRUMENT_EXECUTION_REALISM_PREP_FINAL_CORRECTION
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

The correction resolves several items from the prior review: `HK_DIVIDEND` is no longer silently substituted with `513690.SH`; the Mainland fee contract now matches `MainlandETFCostModel`; the extra 5 bp slippage overlay was removed; the unsupported premium-magnitude threshold was removed; and S2 is expressed in bps of traded notional. No execution-realism run was performed, MaxDiv 120/0.5 remains frozen, and PPO/SAC/TD3 remain closed.

However, the corrected PREP is still **not RUN-ready**. Once `03110.HK` is selected as the executable `HK_DIVIDEND` instrument, the packet must respect the already-frozen Gate-1 Southbound metadata and the existing `SouthboundETFCostModel`. The current PREP contradicts those sources in several material execution semantics.

## Blocking correction 1 — separate listing date, data-start date, and Southbound eligibility date

The corrected packet currently presents `03110.HK` as Southbound-executable across the full L1 decision window `2022-06-09..2026-08-06`. Gate-1 corrections freeze three distinct concepts:

```text
listing_date = 2013-06-17
southbound_eligible_from = 2024-05-06
current_southbound_eligible = true
```

The packet separately cites a local raw file starting `2021-01-11`. That is a **dataset availability date**, not the listing date or the Southbound eligibility date.

Therefore the final PREP must explicitly freeze all three dates and must not treat `2022-06-09..2024-05-03` as executable Southbound history for `03110.HK`.

Choose one reviewed execution rule before RUN:

1. keep `03110.HK` and apply an eligibility mask: before `2024-05-06`, `HK_DIVIDEND` is not Southbound-buyable and its target weight is parked in broker cash / the explicitly frozen parking asset; or
2. propose an explicit date-effective substitute instrument for the pre-eligibility period, with full provenance and a new reviewer check.

If option 1 is used, specify whether structural Southbound ineligibility counts toward S3 fail-closed frequency. Do not leave this ambiguous because almost two years of the 1011-day window are affected.

## Blocking correction 2 — 03110 lot size must be date-effective

The packet freezes `HK lot = 100` for the whole period. Gate-1 corrections instead freeze:

```text
board_lot_size = 50
board_lot_effective_date = 2026-07-24
original board lot = 100 before 2026-07-24
broker metadata/order support = UNKNOWN_PENDING_GATE6
```

The execution-realism runner must therefore use a date-effective lot schedule:

```text
t < 2026-07-24  -> lot = 100
 t >= 2026-07-24 -> lot = 50
```

and test the transition. Historical simulation of the official board lot is allowed; it must not be represented as proof that the connected broker supports the lot or Southbound order path.

## Blocking correction 3 — do not claim verified T+0 / same-day reversal for 03110

The packet states that HK supports T+0 and that `03110.HK` can be bought at T+1 open and sold again on T+1. Repository decision D-015 explicitly carries forward:

```text
same_day_reversal = UNKNOWN_PENDING_RULE_VERIFICATION
```

until HKEX/Southbound rule and broker capability verification.

This experiment does not need same-day reversal: the strategy is frozen to T-close decision -> next-session-open execution. Therefore set the contract to `same_day_reversal = UNKNOWN / NOT_RELied_UPON` and add an invariant that the historical runner never depends on same-session reversal.

## Blocking correction 4 — 03110 must use the Southbound cost path, not MainlandETFCostModel

For Mainland-listed ETFs, the corrected base case now correctly matches `MainlandETFCostModel`:

```text
commission = 0.00005
ETF stamp duty = 0
exchange fee = 0 while inclusion is UNKNOWN_PENDING_BROKER_FEE_AUDIT
half-spread = 1 bp
slippage = 2 bp
```

But `03110.HK` is a Southbound HKEX instrument. The repository already contains `SouthboundETFCostModel` with date-effective historical schedules and base-currency conversion. The final PREP must route `03110.HK` through that model rather than use the Mainland model as its base case.

The packet's text saying HK ETF stamp duty is `0.1%` is inconsistent with both D-017 and `SouthboundETFCostModel`, which freeze ETF stamp duty at `0` for this path. Remove that claim.

Freeze the execution cost routing explicitly:

```text
Mainland-listed instruments -> MainlandETFCostModel
03110.HK                    -> SouthboundETFCostModel
```

For Southbound, retain the model's date-effective HKEX trading fee / SFC levy / AFRC levy / settlement-fee schedules. Its broker commission scenario (`0.0003`, min HKD 5) is explicitly NOT ACCOUNT-VERIFIED and must remain labeled as such. A sensitivity may be added, but it cannot replace the base routing after results are seen.

## Blocking correction 5 — HK settlement cannot be called T+1-conservative

The packet itself notes HK `T+2` settlement but then freezes a unified `T+1` settlement and calls it conservative. Earlier cash availability is not conservative.

Freeze one unambiguous accounting rule. Preferred:

```text
03110.HK settlement cash/stock availability follows the Southbound/HK settlement lag used by the historical simulator;
unsettled sale proceeds cannot finance purchases before that lag expires.
```

If a simplification is retained, it must be explicitly labeled as an approximation and must not create earlier cash availability than the real settlement rule. Add a ledger invariant preventing reuse of unsettled cash.

## Blocking correction 6 — historical PremiumGuard availability must have a data-mode contract

The correction correctly removed the unsupported premium-magnitude threshold. But Gate-1/D-011 records that historical realtime IOPV is not available. Current `PremiumGuard` blocks buys whenever IOPV is missing/stale.

Therefore the final PREP must freeze one of these semantics before RUN:

1. `INSTRUMENT_BACKTEST`: PremiumGuard realtime IOPV protection is `NOT_EVALUABLE_HISTORICALLY`, excluded from historical PnL and reported as N/A; PAPER/LIVE remain fail-closed; or
2. deliberately run an availability-fail-closed diagnostic in which missing historical IOPV blocks buys, explicitly acknowledging that this may block essentially all protected-instrument buys and trigger STOP; or
3. separately specify and review a historical FairNAV/IOPV-equivalent proxy with exact data provenance/timing before using it.

Do not silently fabricate IOPV, and do not use `close_to_official_nav_gap` as a substitute realtime signal.

## Required clarification — S2 must aggregate in one base currency

The corrected denominator is directionally right, but the portfolio now contains CNY and HKD instruments. The runner must not sum raw HKD notional with CNY notional.

Freeze:

```text
total_traded_notional_base_cny = sum(abs(qty * execution_price_local) * fx_to_base_at_execution)
fee_bps_of_traded_notional = total_fee_base_cny / total_traded_notional_base_cny * 1e4
slippage_bps_of_traded_notional = total_slippage_base_cny / total_traded_notional_base_cny * 1e4
```

or an equivalent single-base-currency definition. Use the same FX convention in cost model, denominator, artifact and STOP logic.

## Passed elements — keep frozen

- MaxDiv only, lookback 120, shrinkage 0.5, accepted `RiskOverlayV0`;
- no Momentum blend, dense alpha search, dynamic alpha or result-informed tuning;
- L1 nominal decision/execution dates remain `2022-06-09..2026-08-06` / `2022-06-10..2026-08-07`, subject to explicit instrument eligibility masks;
- no pre-launch backfill;
- research-return and executable-net paths remain separated;
- T-close -> next-session-open intent remains frozen;
- missing/invalid execution quotes fail closed rather than invent fills;
- Mainland fee contract and spread/slippage no-double-count correction is accepted for Mainland instruments;
- premium-magnitude threshold removal is accepted;
- S2 bps-of-traded-notional concept is accepted, pending single-base-currency aggregation;
- annual + frozen weak/strong subperiod reporting remains required;
- no run has been performed;
- PPO/SAC/TD3 remain closed;
- forward/paper/live/QMT live remain unauthorized.

## Required final correction packet

Suggested handoff:

`G4_POST_L2_INSTRUMENT_EXECUTION_REALISM_PREP_CORRECTION_002`

The correction remains PREP/specification only. Do **not** run execution realism yet.

Before requesting RUN authorization, freeze and test-plan:

1. exact `03110.HK` listing / local-data-start / Southbound-eligibility dates and pre-eligibility behavior;
2. date-effective board lot `100 -> 50` on `2026-07-24`;
3. same-day reversal `UNKNOWN/NOT_RELied_UPON`;
4. per-instrument cost routing with `SouthboundETFCostModel` for `03110.HK`, ETF stamp duty 0, and date-effective HK fees;
5. settlement/cash-availability semantics with no unsettled-cash reuse;
6. historical PremiumGuard data-mode semantics;
7. S2 cost/notional aggregation in CNY base currency;
8. corresponding invariants/tests, while preserving MaxDiv parameters and all previously frozen research results.

Only after this final PREP correction is reviewed may one frozen `POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN` be considered for authorization.
