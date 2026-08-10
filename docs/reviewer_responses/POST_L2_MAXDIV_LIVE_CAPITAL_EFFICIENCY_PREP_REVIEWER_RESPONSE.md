# ChatGPT Reviewer Response — POST_L2 MaxDiv Live Capital Efficiency PREP

- handoff_id: `G4_POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_PREP_001`
- reviewed packet commit: `a50f7b70c9d764884da6425e68697cd4dcce3898`
- code_commit: `null` (PREP only; no run/backtest/source implementation yet)
- decision: **MAXDIV_LIVE_CAPITAL_EFFICIENCY_PREP_CONTRACT_CLEANUP_REQUIRED**
- reviewer state: **REVISIONS_REQUIRED**

## Decision

The research direction and most of the pre-registration are accepted in substance, but the PREP is not yet precise enough to authorize the M0-M3 RUN. No backtest/run is authorized yet.

The frozen high-level design remains unchanged:

- M0 legacy control;
- M1 total defensive cap 30%;
- M2 principal challenger total defensive cap 25%;
- M3 total defensive cap 20%;
- M1-M3 fixed 5% operational cash outside the optimizer;
- MaxDiv lookback 120 / shrinkage 0.5 unchanged;
- no expected-return model in the optimizer;
- no cap search after results;
- no execution-universe redesign in this experiment;
- PPO/SAC/TD3 remain closed.

## Required PREP corrections before RUN authorization

### 1. Fix the investable-sleeve slot-count contradiction

Section 5 says the M1-M3 optimizer outputs weights over `仅 10 个投资槽位`, but M1 and M2 explicitly retain strategic `CASH_LIKE <= 5%` inside the optimizer. These statements cannot both be true.

Freeze one canonical representation:

- keep the original **11 economic-slot optimizer vector** for M1-M3;
- the external 5% operational-cash sleeve is a separate accounting sleeve and does **not** replace the strategic `CASH_LIKE` economic slot;
- M3 may keep the same 11-slot vector with `CASH_LIKE cap = 0`, rather than changing vector dimension.

This preserves cross-candidate parity, slot ordering and deterministic tests.

### 2. Replace sequential group scaling with a joint-feasible deterministic projection contract

The proposed implementation says bounded-simplex waterfill followed by defensive-group scaling “like the existing growth group”. With two disjoint group caps (`CHINEXT+STAR` and `CASH_LIKE+CN_DURATION`), sequential scaling plus redistribution can re-inflate the other group and either violate a cap or falsely report infeasibility even when a feasible solution exists.

Before RUN, freeze an algorithm that projects onto the **joint intersection** of:

- long-only simplex;
- per-slot caps;
- growth-group cap;
- defensive-group cap.

It must be deterministic, fail closed only when the joint constraint set is genuinely infeasible, and have final simultaneous assertions for all constraints. Behavioral tests must include a synthetic case where both group caps bind simultaneously, a genuinely infeasible case, and exact M0 parity with current `RiskOverlayV0`.

Do not change the numerical M0-M3 caps while fixing the projection method.

### 3. Make the forward-return sanity audit use actual candidate allocation, not cap values

Section 8 says defensive carry is computed “按候选冻结配置权重”, which is ambiguous and can be read as using the cap values. Caps are limits, not realized portfolio weights.

Freeze the primary sanity calculation to use each candidate's **latest post-risk TOTAL-NAV target weights produced by the RUN**:

`defensive_w = op_cash + strategic CASH_LIKE + CN_DURATION`

`risk_asset_w = 1 - defensive_w`

and calculate required residual risk-asset return for 7% / 8% / 9% using those actual latest weights and the dated cash/duration-yield snapshot.

A separate “at-cap” stress diagnostic is allowed if clearly labeled, but it must not replace the actual-allocation calculation or become a selection criterion.

### 4. Bind the accepted L1 reference exactly now; remove placeholders

The PREP claims L1 artifact/commit binding but still contains a placeholder for the accepted L1 implementation commit and does not show the exact artifact hashes.

The corrected PREP must explicitly bind:

- `artifacts/gate4_long_horizon_nonrl_results.json` SHA256;
- `artifacts/gate4_long_horizon_nonrl_raw.json` SHA256;
- accepted L1 implementation commit `f039d369d94295433132e17cf981b2eb6243c17a`;
- any distinct accepted result/packet commit if applicable, clearly labeled rather than conflated.

M0 parity must compare the full 1011 x 11 accepted post-risk target path and accepted metrics against those exact references.

### 5. Freeze the historical return/cost/causal accounting and capital-efficiency formulas exactly

The RUN must preserve the accepted L1 historical comparison engine, not silently switch to a no-cost direct-return calculation. State explicitly that M0-M3 use the same L1 `T decision -> T+1 execution/return` causal convention, corporate-action semantics and the same labeled `1x MainlandETFCostModel` research simplification used by the accepted L1 benchmark, so M0 metric parity is meaningful.

For the 5% operational-cash sleeve, state explicitly:

- target operational cash is 5% of TOTAL NAV at each decision/rebalance;
- T target earns the accepted `CASH_LIKE` T->T+1 research return proxy;
- it is included in total-NAV returns and allocation statistics but excluded from MaxDiv covariance/optimization;
- define how it enters the research turnover/traded-notional proxy, and label any simplification consistently across M1-M3.

Also freeze exact formulas/units for:

- CAGR gained/lost per 10ppt reduction in average defensive allocation vs M0;
- MaxDD increase per 10ppt reduction in average defensive allocation vs M0;
- criterion 6 as the minimum matched CAGR degradation across **all five calendar-year segments plus both frozen stress segments**, requiring `min(candidate_CAGR_segment - M0_CAGR_segment) >= -0.05`.

Handle zero/near-zero defensive-allocation reduction explicitly rather than dividing by zero.

## Passed / preserved

- new study is correctly separated from the closed 03110 execution-realism STOP;
- PREP only, no backtest/result generation occurred;
- M0/M1/M2/M3 numerical caps are pre-registered;
- M2 is correctly pre-designated as principal challenger;
- MaxDiv 120/0.5 remains frozen;
- current 1.4% cash yield is correctly labeled as a planning assumption rather than historical rewrite;
- forward-return work remains audit-only;
- no expected-return optimizer, Momentum blend, dense/dynamic alpha or RL is introduced;
- no replacement HK_DIVIDEND instrument/universe is selected;
- no forward/paper/live/QMT-live step is authorized.

## Authorized next

Only:

`POST_L2_MAXDIV_LIVE_CAPITAL_EFFICIENCY_PREP_CORRECTION`

This is a **documentation/contract correction only**. Do not implement or run M0-M3 yet.

## Forbidden next

- CAPITAL_EFFICIENCY_RUN
- NEW_BACKTEST
- RESULT_INFORMED_CAP_SEARCH
- INTERMEDIATE_CAP_VALUES
- EXPECTED_RETURN_OPTIMIZATION
- EXECUTION_UNIVERSE_REDESIGN
- INSTRUMENT_SUBSTITUTION
- NO_TRADE_BAND_SEARCH
- EXECUTION_TIME_OPTIMIZATION
- FORWARD_PAPER_VALIDATION
- PAPER
- LIVE
- QMT_LIVE
- DENSE_ALPHA_SEARCH
- DYNAMIC_ALPHA
- PPO
- SAC
- TD3
- RL_RETRAINING
- RL_HYPERPARAMETER_TUNING
- RL_COMPARISON

PPO/SAC/TD3 remain closed unless the user explicitly reopens them.
