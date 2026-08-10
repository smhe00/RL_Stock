# Reviewer Response — POST_L2 Instrument Execution Realism RUN

```yaml
handoff_id: G4_POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN_001
reviewed_packet: docs/review_packets/POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN.md
reviewed_packet_commit: 729e6dc76e01f1fbdda186411b85e1bf2d3d5fbe
implementation_commit: 13e29ac6f82cc87983641a2f432af4208b33e183
decision: EXECUTION_REALISM_RUN_INVALID_IMPLEMENTATION_CORRECTION_REQUIRED
reviewer_state: REVISIONS_REQUIRED
authorized_next:
  - POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN_CORRECTION
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

The structural eligibility fact behind S3 is credible and remains frozen: `03110.HK` is not Southbound-eligible before 2024-05-06, so the pre-eligibility interval must be cash-parked and counted according to the already-approved S3 rule. Do not change that rule after seeing the result.

However, the reported executable economics (`cum +64.9% / CAGR 12.8% / Sharpe 0.911 / MaxDD -13.2%`) and S1/S2 conclusions are **not accepted** because the implementation does not faithfully execute the frozen MaxDiv / T-close -> T+1-open / settlement / Southbound-cost contract. This is a mechanical implementation failure, not a research-threshold failure.

## Blocking implementation defects

### 1. The runner does not actually generate the frozen MaxDiv weight path

`maximum_diversification_policy()` returns a `BaselinePolicy`. `BaselinePolicy.__call__()` ignores its argument and derives the decision date from `env.calendar[env._i]`.

The runner calls `pol(t)` repeatedly without advancing/resetting `env._i`, so the requested `t` is not used as the policy date. The runner then additionally applies:

```python
w = np.clip(action, 0.0, None)
w = (w + 1.0) / 2.0
```

which clips the action **before** applying the inverse `a = 2w - 1` transform. Negative action components are therefore destroyed. The resulting target path is not the accepted MaximumDiversification 120/0.5 path.

Required correction:
- generate MaxDiv targets at each exact decision date using the canonical policy semantics;
- invert action only as `w=(a+1)/2` when needed, with no pre-inversion clipping;
- add parity evidence against the already-accepted L1 MaxDiv target weights on sampled dates and preferably full-path hash/statistics.

### 2. Frozen T+1-open execution is not implemented

The runner loads `opens`, but the rebalance loop obtains `m` from `closes` and uses that same close mark as the transaction price. Therefore the purported T+1-open execution is actually T+1-close execution.

This is economically material and introduces information unavailable at the frozen execution time.

Required correction:
- order sizing/fills use the exact next tradable session **open**;
- close prices are used only for valuation/marking where the contract requires them;
- add a regression test proving fill price equals T+1 open and never T+1 close.

### 3. Rebalance sequencing is slot-order dependent and does not implement target weights

The runner loops instruments in fixed dictionary order and performs buys/sells inline. It does not execute sells first and then allocate settled cash to buys. Earlier slots can consume cash before later slots are processed.

The artifact reports `03110.HK cost = 0` even though the packet claims it is executable for the post-2024-05-06 portion of the window. That is a strong symptom that the executable portfolio never follows the intended target path after eligibility.

Required correction:
- build the complete rebalance plan from the frozen target first;
- execute eligible sells first subject to settlement rules;
- then execute buys from actually settled cash;
- report target-vs-actual weight tracking error, fill counts and per-instrument traded notional; fail if a positive target is silently starved solely by dictionary order.

### 4. HK T+2 settlement is declared but not implemented

`pending_sell_cash` is a single pool. Sold HK proceeds are added to it, but there is no dated receivable ledger and no T+2 release back to settled cash in the loop. The code also computes buy availability as `cash - pending_sell_cash` even though pending proceeds were never included in `cash`, effectively subtracting them twice from available buying power.

The current test only checks constants / set membership; it does not exercise T+2 cash release behavior.

Required correction:
- maintain dated settlement receivables;
- release each HK sell proceed exactly on its frozen settlement date;
- never reuse unsettled proceeds early;
- never subtract pending proceeds from cash a second time;
- add a multi-day regression test covering sell T, pending T+1, settled T+2, and a blocked/allowed buy around settlement.

### 5. Southbound cost/FX contract is not faithfully implemented

The runner converts 03110 prices to CNY before calling `SouthboundETFCostModel()`, but that model documents `reference_price`/notional in HKD and converts its `CostBreakdown` to base currency using `fx_to_base`.

The runner instantiates `SouthboundETFCostModel()` with default `fx_to_base=1.0` and does not pass `market_state={"transaction_date": ...}`. Consequently, if 03110 trades:
- HKD minimum commission semantics are not correctly separated from CNY base conversion;
- date-effective HKEX/SFC/AFRC/settlement schedules are not selected by execution date;
- the frozen CNY-base aggregation is not demonstrated correctly.

Also, the runner reindexes same-date FX and forward-fills it; the PREP contract requires the frozen T-1 FX timing rather than an unqualified same-date series.

Required correction:
- retain 03110 local execution price/notional in HKD for Southbound cost calculation;
- pass execution-date `transaction_date` to the model;
- pass the frozen T-1 HKD/CNY conversion as `fx_to_base`;
- convert traded notional and all cost components to common CNY base only for portfolio accounting/S2 aggregation;
- add tests around a historical fee-schedule boundary and FX conversion.

### 6. S1 is not evaluated according to the frozen contract

The PREP freezes S1 on **annual and pre-frozen stress subperiods**. The runner uses only one hard-coded full-period `l1_research_cagr = 0.094154` and does not output annual/stress executable metrics.

Therefore `S1 PASS` is not established even aside from the invalid portfolio path.

Required correction:
- compute executable and research metrics on the full period, each calendar year, and the frozen weak/strong regimes;
- apply S1 to every required subperiod exactly as frozen;
- report the worst subperiod degradation and its dates.

### 7. Tests are insufficient to validate the claimed mechanics

Several tests only verify constants rather than behavior. In particular:
- settlement test does not test settlement release;
- PremiumGuard test contains an unconditional `or True` and therefore cannot fail;
- board-lot assertions are tautological;
- there is no MaxDiv weight-parity test;
- there is no T+1-open execution test;
- there is no sell-before-buy / target-tracking test;
- there is no Southbound transaction-date / FX-base conversion test.

Replace these with executable regression/integration tests. The reported `7 passed` is not sufficient evidence for the frozen execution contract.

### 8. Run data provenance is not bound strongly enough

The result manifest binds the code commit but does not bind the local gitignored market-data snapshot with file hashes / source snapshot identifiers. The RUN depends on local raw ETF files, 03110 raw data, dividend events and HKD/CNY data.

Required correction:
- include exact file/source provenance and deterministic hashes for every input actually consumed by the RUN;
- record the research-reference artifact/commit rather than only hard-coding its CAGR.

## What remains frozen

Do **not** change any of the following during the correction:
- MaximumDiversification lookback 120 / shrinkage 0.5 / accepted RiskOverlayV0;
- 11-slot mapping including `CN_LARGE=510300.SH` and `HK_DIVIDEND=03110.HK`;
- L1 decision/execution window;
- 03110 listing/data/Southbound dates;
- pre-2024-05-06 cash parking and its existing S3 counting rule;
- date-effective 03110 board lot;
- same-day reversal UNKNOWN / NOT_RELIED_UPON;
- Mainland vs Southbound cost routing;
- ETF stamp duty 0;
- A-share T+1 / 03110 T+2 settlement contract;
- PremiumGuard historical N/A and S4 exclusion from backtest STOP;
- S2 common-CNY-base definition;
- S1/S2/S3 thresholds and frozen stress subperiods;
- PPO/SAC/TD3 remain closed; no forward/paper/live/QMT-live work.

## Required correction handoff

Implement the mechanical fixes and rerun the **same frozen experiment** under:

`POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN_CORRECTION`

The corrected packet must report the exact implementation commit, full test commands/results, data provenance hashes, target-weight parity, T+1-open evidence, settlement evidence, per-instrument fills/notional/cost, full + annual + frozen stress metrics, and S1-S4 evaluation.

If S3 still triggers after the mechanics are corrected—as expected from the frozen 03110 eligibility fact—report STOP again. Do not use this correction to alter mapping, window, S3 counting, or any threshold.
