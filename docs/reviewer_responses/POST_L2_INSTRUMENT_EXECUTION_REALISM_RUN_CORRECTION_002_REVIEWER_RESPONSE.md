# ChatGPT Reviewer Response — POST_L2 Instrument Execution Realism RUN CORRECTION_002

- handoff_id: `G4_POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN_CORRECTION_002`
- reviewed packet commit: `3dacdcdd418ab754f17c5eb10b5d007ecbe16445`
- reviewed implementation commit: `16b8dd794bd21bc53b15f7fcb1abc047cfe42824`
- decision: **EXECUTION_REALISM_RUN_CORRECTION_002_INVALID_CORRECTION_003_REQUIRED**
- reviewer state: **REVISIONS_REQUIRED**

## What is accepted

The correction materially improves the prior implementation: MaxDiv date/action inversion remains fixed; the main loop now separates open sizing/fills from close valuation; post-fill NAV includes cash, positions and receivables; T+2 uses a session-index ledger rather than calendar `+2d`; raw 03110 HKD prices are loaded; T-1 FX and date-effective Southbound cost hooks are present; frozen mapping/window/parameters and the 461 structural pre-eligibility days are unchanged; PPO/SAC/TD3 and QMT live remain excluded.

## Blocking findings

### 1. 03110 executable price path is still absent from the actual rebalance marks

`load_all()` calls `load_execution_prices()`. The project loader still maps `HK_DIVIDEND` to research wrapper `513690.SH`, so `opens/closes` are keyed by `513690.SH`, not `03110.HK`. CORRECTION_002 separately loads `opens_hkd/closes_hkd`, but never creates `opens["03110.HK"]` / `closes["03110.HK"]` or otherwise supplies an executable CNY mark before the main loop reads `open_marks.get("03110.HK")`.

The artifact itself confirms the failure: `no_quote_hold = 550`, exactly the 550 post-eligibility decision days, while `03110.HK` notional/cost remain zero. Therefore the packet explanation that the 0 fills are caused by low MaxDiv target weight / board-lot infeasibility is not established. The runner is instead treating 03110 as missing-quote throughout the eligible period.

Required correction: preserve raw 03110 HKD open/close as the execution source; for each execution session convert to CNY using the frozen T-1 HKD/CNY only for sizing/accounting, while passing raw HKD price plus `fx_to_base=T-1 FX` to `SouthboundETFCostModel`. Add behavioral assertions proving finite 03110 marks after `2024-05-06`, attempted-order counts, feasible-lot counts and fills/notional.

### 2. S1 per-subperiod comparison is not implemented; the reported 2022 S1 FAIL is invalid

`_s1_subperiods()` loads the accepted L1 artifact but does not use its subperiod returns. It assigns the same full-period research CAGR `0.094154` to every calendar year and both stress periods. Consequently `year_2022 net 4.3% vs research 9.4% = -5.08pct` is not a valid frozen S1 comparison.

The accepted L1 result artifact already contains MaximumDiversification calendar-year and phase returns. CORRECTION_003 must bind the exact accepted L1 reference artifact/commit and compute research CAGR for each identical date segment from the accepted raw return path or from the accepted segment cumulative return + exact day count. S1 is `FAIL` only if any matched segment has `net CAGR - research CAGR < -5pct`.

### 3. S3 accounting is internally inconsistent with the frozen definition

The frozen contract defines S3 over fail-closed events including structural ineligibility and missing quotes. The artifact reports `structural_ineligible_cash_parking=461` and `no_quote_hold=550`, but `S3_fail_closed_pct` is calculated only from the 461 structural days. This does not alter the fact that S3 is already a STOP, but the reported 45.6% is not the full fail-closed rate of the current run. After fixing 03110 marks, missing-quote events must be recomputed and S3 must use the frozen event/day definition without post-result changes.

### 4. Corporate-action timing remains wrong for executable entitlement

The runner applies ex-date dividend accrual and unit conversion after T+1 open trading. The existing canonical environment applies corporate actions before order planning/execution on `t_next`, with dividend entitlement based on the pre-open position. The current ordering can give newly bought ex-date shares a dividend and can size trades from pre-conversion quantities. Reuse the canonical corporate-action sequence or reproduce it exactly, with behavioral tests for ex-date pre-open holdings, unit conversion, accrual and settle-date cash.

### 5. T+2 calendar must be the applicable settlement/tradable-session calendar

Using `exec index + 2` is better than calendar `+2d`, but the index is the SH decision/execution calendar. For `03110.HK`, demonstrate that this is a valid frozen Southbound/HK settlement-session approximation across HK/Mainland holiday mismatches, or use an explicit applicable session calendar. Do not release a Southbound receivable on a date that is not a valid settlement session for that instrument.

### 6. Provenance/reference binding remains incomplete

The artifact hashes local raw/FX/CA files, but the accepted L1 research-reference artifact is only recorded by path; its SHA256 and exact source/result commit are not bound in the manifest. The packet also contains stale counts/text (`13`/`19`, `10`/`12` tests) in different sections. CORRECTION_003 must emit one canonical provenance manifest containing every actually consumed input plus the research-reference artifact hash and commit.

### 7. Tests still fail to catch the defects above

Several tests remain source-string/structure assertions rather than execution-behavior regressions. In particular, no test asserts that 03110 has finite executable marks after eligibility, so all 550 eligible days can be `no_quote` while the suite passes. MaxDiv parity still checks constraints/average allocation rather than exact sampled target weights against the accepted L1 target path. Add behavioral tests that execute isolated ledger/rebalance helpers or the deterministic runner path and compare exact expected fills/NAV/settlement/CA/S1 reference segments.

## Result validity

The structural fact `03110.HK southbound_eligible_from = 2024-05-06` and the frozen 461 pre-eligibility days remain valid. The frozen S3 threshold therefore remains a STOP condition unless the original counting contract itself is separately reviewed; this review does **not** authorize any mapping/window/threshold change.

However, the reported executable economics `cum +48.1% / CAGR 9.9% / Sharpe 1.801 / MaxDD -3.9%`, S1 FAIL, and S2 execution interpretation are **not accepted for decision-making** because the eligible-period 03110 execution path is missing and S1 is compared against the wrong research subperiod benchmark.

## Authorized next

Only:

`POST_L2_INSTRUMENT_EXECUTION_REALISM_RUN_CORRECTION_003`

This is the same frozen experiment with mechanical/fidelity corrections only. No result-informed instrument substitution, window change, S1/S2/S3 threshold change, blend search, dense/dynamic alpha, forward/paper/live, PPO, SAC, TD3, RL retraining/comparison, or QMT live is authorized.
