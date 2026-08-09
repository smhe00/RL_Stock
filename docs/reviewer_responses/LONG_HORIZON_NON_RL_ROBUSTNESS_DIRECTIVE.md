# Long-Horizon Non-RL Robustness Directive

```yaml
source_handoff_id: GATE_4_RL_NO_GO_CLOSEOUT_001
source_code_commit: c18234a1153f9f03c38537fe717c26a025e94200
decision: LONG_HORIZON_NON_RL_PREP_AUTHORIZED
reviewer_state: REVIEW_COMPLETE
authorized_next:
  - GATE_4_LONG_HORIZON_NON_RL_PREP
forbidden_next:
  - PPO
  - SAC
  - TD3
  - RL_RETRAINING
  - RL_HYPERPARAMETER_TUNING
  - RL_COMPARISON
  - QMT_LIVE
```

## 1. Objective

The current PPO/SAC/TD3 branch remains closed. The next research objective is to test whether the strong deterministic results observed on the 475-day benchmark survive a materially longer market window and multiple market regimes.

The primary hypothesis under test is not "can Sharpe 2.77 be reproduced exactly", but whether the structural ranking and risk-control advantage of EqualWeight / MaximumDiversification survives a longer history.

## 2. Two-stage plan

### L1 — Real-Instrument Long-Horizon Diagnostic

Use the actual 11 core ETF instruments only. Target the longest common causally usable period allowed by real launch dates and required lookback/warm-up, expected to be approximately 2022-05/06 through 2026-08-07 (~4.2 years / ~1000+ decision days).

This study is explicitly labeled:

`REAL_INSTRUMENT_LONG_HORIZON_DIAGNOSTIC`

It is a robustness diagnostic, not a pristine new OOS claim, because the historical data have already been observed during research.

Methods in scope:

1. CN_LARGE / 510300 research-adjusted HS300 reference
2. EqualWeight
3. MaximumDiversification
4. MinimumVariance
5. RiskParity_IVOL
6. Momentum_12_1

Do not add methods after seeing results.

Required metrics for each strategy:

- cumulative return
- active-day annualized return and, where meaningful, calendar CAGR
- annualized volatility
- Sharpe
- Sortino
- maximum drawdown
- Calmar
- worst calendar-year return / worst 12-month rolling return if implementation is straightforward
- turnover
- transaction cost / traded notional
- average active assets / concentration diagnostics already available in the project

Also produce sub-period or calendar-year breakdowns sufficient to show whether performance is concentrated in one regime.

Execution semantics must remain causal and consistent with the corrected path:

`T information / close decision -> T+1 execution`

No future data may enter rolling covariance, volatility, momentum, adjustment, or execution calculations.

### L2 — Long-History Proxy Scenario

Do NOT execute L2 yet.

After L1 is completed and reviewed, prepare a separate proposal for approximately 2015-2026 proxy-based scenario research. L2 is intended to span substantially more bull/bear regimes and will be explicitly labeled scenario/method research rather than strict real-instrument OOS.

## 3. Data authorization

Additional public-market data acquisition is authorized when needed for L1 preparation, subject to all of the following:

- real ETF launch dates remain hard boundaries for L1;
- no pre-launch synthetic or backfilled ETF history may be presented as real-instrument data;
- missing/invalid rows inside the real live period may be re-fetched or repaired from auditable public/approved data sources;
- preserve provider/source, fetch date, raw-vs-adjusted distinction, corporate-action handling, and any transformations;
- do not silently replace current data with a different economic series;
- any material source mismatch or unresolved adjustment issue is a review blocker, not an invitation to improvise.

Proxy/index backfill before ETF launch belongs only to L2 and requires a separate reviewed plan.

## 4. L1 PREP deliverable — no result-informed tuning

The currently authorized step is PREP. Before running the long-horizon horse race, Claude must produce a review packet that freezes:

- exact common start/end dates after warm-up;
- exact instruments and data coverage;
- any additional data fetches/repairs and provenance;
- exact six-method set above;
- rebalance rules / lookbacks as inherited from current canonical implementations;
- cost model and accounting semantics;
- metric definitions;
- sub-period reporting scheme;
- new script/artifact paths;
- tests/invariants preventing lookahead and accidental use of the old 475-day stitched mask;
- explicit statement that PPO/SAC/TD3 are absent from all code paths and output tables for this study.

No hyperparameter or lookback optimization is authorized. Existing canonical deterministic policy parameters should be reused unless a change is strictly required to make the long-horizon evaluator function; any such change must be declared in PREP and reviewed before execution.

## 5. Review target

For MaximumDiversification, the key robustness questions are:

- Does long-window Sharpe remain materially above HS300 and competitive deterministic baselines?
- Does MaxDD remain substantially below HS300 / EqualWeight?
- Is the advantage present across more than one sub-period, rather than generated almost entirely by 2024-2026?
- How much of the current Sharpe 2.77 / MaxDD -3.4% collapses when the early 2022-2023 weak equity regime is included?

No fixed GO threshold is imposed at PREP. Thresholds, if any, must be frozen before the L1 run rather than invented after results are seen.

## 6. Handoff requirement

When PREP is complete:

1. create `docs/review_packets/GATE_4_LONG_HORIZON_NON_RL_PREP.md`;
2. update Claude-owned `CLAUDE_STATUS.yaml` with a new unique handoff id, suggested `G4_LONG_HORIZON_NON_RL_PREP_001`;
3. commit and push main;
4. stop and wait for reviewer approval before executing the long-horizon run.

This directive supersedes only the previous `authorized_next: []` for follow-on deterministic research. It does not reopen the closed RL branch.
