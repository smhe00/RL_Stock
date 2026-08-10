# Reviewer Response — POST_L2 Instrument Execution Realism RUN CORRECTION_001

```yaml
handoff_id: G4_POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN_CORRECTION_001
reviewed_packet: docs/review_packets/POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN.md
reviewed_packet_commit: 3a469c68adb2495e1467805deafd612f649fd546
code_commit: be022a6ee8e34bed14b10a0936dcc7545108e9fe
decision: EXECUTION_REALISM_RUN_CORRECTION_STILL_INVALID_SECOND_MECHANICAL_CORRECTION_REQUIRED
reviewer_state: REVISIONS_REQUIRED
authorized_next:
  - POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN_CORRECTION_002
forbidden_next:
  - FORWARD_PAPER_VALIDATION
  - PAPER
  - LIVE
  - RESULT_INFORMED_MAPPING_CHANGE
  - RESULT_INFORMED_WINDOW_CHANGE
  - RESULT_INFORMED_STOP_THRESHOLD_CHANGE
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

The correction improves the MaxDiv date/action path and removes several defects from RUN_001, but the corrected executable economics are still not valid. The packet claims T+1-open execution, dated settlement, per-subperiod S1 comparison, behavioral regression coverage, and complete provenance, while the actual implementation does not yet satisfy those contracts.

The structural S3 fact remains valid and frozen: 03110.HK is Southbound-ineligible before 2024-05-06 and the frozen counting rule produces 461/1011 structural fail-closed days. A mechanically corrected rerun may therefore still STOP on S3. This is not permission to alter the mapping, window, S3 denominator or threshold.

The reported +48.3% cumulative / 9.9% Calendar CAGR / Sharpe 1.750 / MaxDD -3.9%, and the current S1/S2 PASS decisions, are not accepted for decision-making until the following mechanics are corrected.

## Blocking mechanical defects

### 1. T+1-open execution is still not implemented

In the main loop the runner constructs `marks` from `closes` at `t_next`, then uses those same `marks` for `target_qty`, sell notional and buy notional. `opens` are loaded but are not consumed by the rebalance/fill loop.

Required correction:

```text
pre-trade sizing/fills at execution date = exact T+1 open price
post-trade valuation = T+1 close price
```

A regression test must use deliberately different open/close synthetic prices and assert the exact fill price/notional. A source-string test that merely finds the word `opens` is insufficient.

### 2. Net NAV/return path is pre-trade close value, not post-fill net portfolio value

`total_val` is computed before the T+1 rebalance using close marks, then appended to `portfolio_values` after the trades without recomputing post-fill end-of-day NAV. Consequently the current daily return path does not correctly include same-day execution fees, changed holdings, and open-to-close PnL of the new portfolio.

Required sequence per execution date:

```text
release eligible settled receivables
value portfolio at T+1 open for sizing
apply structural eligibility / target
execute fills at T+1 open and deduct fees
value the resulting positions + settled cash + unsettled receivables at T+1 close
record this post-fill net close NAV
```

The artifact must bind returns to this net NAV series.

### 3. HK T+2 ledger uses calendar +2 days and receivables are omitted from NAV/tracking

The code uses:

```text
release_date = execution_date + pd.Timedelta(days=2)
```

and the test explicitly expects a 2025-01-02 sale to release on Saturday 2025-01-04. That is not a settlement-session T+2 ledger. Also, outstanding receivables are excluded from `total_val` and `actual_val`, even though they remain portfolio assets while unavailable for new purchases.

Required correction:

- define T+2 on the frozen settlement/trading-session calendar, not calendar days;
- include unsettled receivables in NAV and target-tracking value;
- exclude them only from available buying cash;
- add an executable weekend/holiday regression proving release on the correct settlement session and no pre-release reuse.

### 4. Frozen T-1 HKD/CNY execution timing is internally inconsistent

`load_prices()` converts 03110 raw HKD open/close to CNY using same-date FX. Later the Southbound path derives `m_hkd = m_cny / fx_t1`, where `fx_t1` is the frozen lagged FX. Therefore the recovered `m_hkd` is not the original local HKD price when same-date FX differs from T-1 FX.

Required correction:

- preserve 03110 raw HKD open/close as local execution series;
- use the frozen T-1 HKD/CNY only when converting local notional/marks/cost to base CNY;
- pass local HKD price + `transaction_date` + `fx_to_base=T-1 FX` to `SouthboundETFCostModel`;
- add a synthetic regression with intentionally different same-day and T-1 FX values.

### 5. Frozen corporate-action accounting is absent from the executable path

The PREP contract explicitly freezes existing corporate actions: unit conversion / dividend accrual at ex-date and dividend settlement at pay/settle date. The manual runner does not load or apply corporate actions to actual executable positions; it only uses research-adjusted series for signals.

Required correction:

Reuse the existing accounting/corporate-action implementation or implement equivalent tested mechanics for the execution ledger. Add at least one dividend and one unit-conversion regression on held positions. The net executable path must not silently lose dividends or ignore share conversion.

### 6. S1 is still not evaluated against research on each frozen subperiod

The artifact reports net annual/stress metrics, but the code computes:

```text
worst_degrad = full_period_research_cagr - full_period_net_cagr
```

using one hard-coded `0.094154`. No annual or stress-period research CAGR is loaded or compared. The PREP contract is explicit: S1 fails if executable net CAGR degrades by >5pct on **any** calendar-year / frozen stress subperiod.

Required correction:

- bind to the accepted L1 research artifact/commit (`artifacts/gate4_long_horizon_nonrl_results.json`, MaximumDiversification);
- compute matching research CAGR on every evaluated annual and stress segment with identical date boundaries;
- report each `net_cagr - research_cagr` and use the worst segment for S1.

Do not infer subperiod PASS from full-period similarity.

### 7. Tests are still mostly static/source-text checks rather than behavioral regressions

Examples:

- T+1-open test only checks that `opens`/`open` text exists;
- T+2 test checks string/dictionary presence and currently validates a Saturday calendar release;
- sell-before-buy checks source ordering;
- Southbound date/FX checks source substrings;
- MaxDiv parity checks constraints/average CASH_LIKE weight, not exact parity to the accepted L1 target-weight path.

Replace these with executable synthetic or artifact-parity tests. At minimum require:

```text
exact MaxDiv target-weight parity on sampled dates against accepted L1 path
open != close synthetic fill assertion
post-fill net NAV/fee assertion
T+2 settlement-session release + no early cash reuse
receivable included in NAV but not buying cash
Southbound local-HKD + transaction-date + lagged-FX cost assertion
corporate-action dividend/unit-conversion assertion
sell-before-buy cash feasibility / target-tracking assertion
```

### 8. Provenance record is incomplete and over-claims file count

The artifact contains 12 actual SHA256 file entries plus `_note`, while the packet claims 13 input files. More importantly, `load_research_adj()` consumes corporate-action event files but those event files are not hashed, and the exact accepted research-reference artifact/commit is not bound in the manifest.

Required correction:

- hash every raw/FX/corporate-action input actually consumed by the corrected run;
- record source path + SHA256 deterministically;
- bind the accepted L1 research reference artifact blob/commit used for S1;
- report exact count from the manifest rather than a hand-written number.

## Additional execution diagnostic required

The corrected artifact still reports `03110.HK notional = 0`. This may be a legitimate outcome of the frozen MaxDiv weights + lot constraints, but because the actual RUN therefore does not exercise the Southbound execution branch, report after 2024-05-06:

```text
mean / max HK_DIVIDEND target weight
number of dates with target notional >= one board lot
number of attempted 03110 orders
number of actual fills
```

Keep this diagnostic descriptive only; do not change the instrument or strategy because of it.

## Preserved / accepted items

- unique new handoff and authorized correction scope;
- MaxDiv 120/0.5 and the 11-slot mapping remain frozen;
- env-date advancement and removal of the pre-inversion action clip are directionally correct;
- 03110 listing/data/Southbound dates remain frozen;
- 03110 board-lot transition 100 -> 50 remains frozen;
- PremiumGuard historical mode remains N/A and S4 remains excluded;
- no result-informed mapping/window/threshold change was made;
- structural S3 = 461/1011 remains the frozen fact to be re-evaluated unchanged after mechanical correction;
- PPO/SAC/TD3 remain closed and QMT live remains forbidden.

## Authorized correction only

`POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN_CORRECTION_002`

This is a same-experiment mechanical correction and rerun. It is not a new architecture/search gate. Do not change MaxDiv parameters, the 11 instruments, the 1011-day window, S1-S4 definitions, stress-period boundaries, or S3 counting semantics. Do not advance to forward/paper/live after the rerun without a new reviewer decision.
