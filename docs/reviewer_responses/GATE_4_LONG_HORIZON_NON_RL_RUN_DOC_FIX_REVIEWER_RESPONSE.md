# Reviewer Response — L1 Documentation Fix / L2 Proxy PREP Authorization

```yaml
handoff_id: G4_LONG_HORIZON_NON_RL_RUN_DOC_FIX_001
reviewed_execution_commit: f039d369d94295433132e17cf981b2eb6243c17a
reviewed_doc_fix_commit: 36bbda6005c9af527193d2b611461fd4bb0fa1e8
reviewed_packet_head: 067ff6bd364bfa9ea51758b73fd6bb12733e546d
reviewed_packet: docs/review_packets/GATE_4_LONG_HORIZON_NON_RL_RUN.md
decision: DOC_FIX_ACCEPTED_L1_CLOSED_L2_PROXY_PREP_AUTHORIZED
reviewer_state: REVIEW_COMPLETE
authorized_next:
  - GATE_4_LONG_HORIZON_PROXY_PREP
forbidden_next:
  - GATE_4_LONG_HORIZON_PROXY_RUN
  - L2_PROXY_SCENARIO_EXECUTION
  - PPO
  - SAC
  - TD3
  - RL_RETRAINING
  - RL_HYPERPARAMETER_TUNING
  - RL_COMPARISON
  - QMT_LIVE
```

## Review conclusion

The required documentation correction is accepted. The corrected text now matches the frozen L1 artifact: MaximumDiversification has the highest weak-phase Sharpe (~0.86), while Momentum_12_1 is also positive (~+3.0% cumulative, Sharpe ~0.31). The previous uniqueness claim has been removed.

The change audit from the reviewer revision commit to current main shows only `docs/agent_state/CLAUDE_STATUS.yaml` and `docs/review_packets/GATE_4_LONG_HORIZON_NON_RL_RUN.md` changed. No L1 artifacts, implementation code, tests, parameters, or numeric results were changed or rerun.

Therefore L1 is formally closed with the accepted core result:

- MaximumDiversification: active-day annualized return ~9.8%, Sharpe ~1.655, MaxDD ~-4.0%, Calmar ~2.44 over 1011 real-instrument execution days.
- EqualWeight: Sharpe ~0.815, MaxDD ~-14.0%.
- Momentum_12_1: Sharpe ~1.004, MaxDD ~-17.0%.
- HS300 research-adjusted reference: Sharpe ~0.384, MaxDD ~-26.9%.

This supports proceeding to a longer scenario/proxy robustness study. It does not constitute a production/live authorization.

## Authorized next: L2 Proxy Scenario PREP only

The next task is to prepare, not execute, a substantially longer deterministic allocation study designed to span multiple bull/bear cycles. This is Track C Scenario Proxy Research from `GATE_4_DATA_HORIZON_PLAN.md` and must be labeled explicitly as retrospective scenario/method research, **not strict PIT OOS**.

### Research target

Aim for a common evaluation history that reaches back to approximately 2015 and continues through 2026-08-07, subject to proxy data quality. The purpose is to cover substantially more regimes than L1, including the 2015 equity boom/crash, 2018 bear/trade-war period, COVID-era shock/rebound, 2021-2023 China equity weakness, and the more recent period.

If a 2015 start is not technically supportable for all slots even under scenario proxies, PREP must report the limiting proxy and propose the earliest common start. Do not silently shorten the window.

### Method set remains frozen

Use the same six comparison rows unless PREP identifies a strictly technical reason otherwise:

1. HS300 / CN_LARGE reference proxy
2. EqualWeight
3. MaximumDiversification
4. MinimumVariance
5. RiskParity_IVOL
6. Momentum_12_1

Canonical parameters remain frozen from L1:

- MaxDiv: lookback 120, shrinkage 0.5
- MinVar: lookback 120, shrinkage 0.5
- RiskParity_IVOL: lookback 60
- Momentum_12_1: lookback 252, skip 21

No tuning, method additions, or result-informed parameter changes are authorized.

### Proxy/data authorization

Public-market data acquisition is authorized for PREP. Claude may research and fetch index/proxy histories needed to build a long scenario series. For every slot/proxy candidate, PREP must record at minimum:

- slot name and current real ETF instrument;
- proposed long-history proxy/index/series;
- economic exposure represented;
- provider/source;
- data-series start/end;
- index base date and launch date where known;
- whether history before launch is retrospective/backfilled;
- price-return vs total-return treatment;
- currency and FX treatment;
- dividend/reinvestment treatment;
- obvious methodology discontinuities or substitutions;
- mapping confidence / known basis risk versus the current ETF slot.

Backfilled/pre-launch index history is allowed in L2 because this is Track C, but it must be explicitly flagged. It must never be relabeled as real-instrument or strict point-in-time history.

### Required PREP design

Before any L2 run, freeze and return for review:

1. exact slot-to-proxy mapping for all 11 economic slots;
2. exact raw-data coverage and required warm-up period;
3. proposed first/last evaluation dates and expected day count;
4. synchronization/calendar rules across China, Hong Kong, US, gold, bond, and cash-like series;
5. return construction, FX handling, missing-day handling, and no-lookahead rules;
6. how transaction costs will be treated in a proxy scenario. If realistic proxy trading costs are not defensible, prefer a clearly labeled research-return comparison plus a separately stated sensitivity rather than pretending proxy/index data are directly executable ETFs;
7. exact six-method set and canonical parameters above;
8. annual metrics plus pre-frozen regime/sub-period reporting. PREP should propose regime boundaries before seeing strategy results; calendar/event-defined periods are acceptable for this diagnostic study;
9. full-period metrics: cumulative return/CAGR, annualized vol, Sharpe, Sortino, MaxDD, Calmar, worst calendar year, worst rolling 12m, turnover where meaningful, and concentration;
10. tests/invariants for causal lookbacks, date alignment, proxy provenance completeness, and explicit `SCENARIO_NOT_STRICT_PIT_OOS` labeling;
11. explicit confirmation that PPO/SAC/TD3 remain absent.

### Important interpretation requirement

The L2 question is not whether MaxDiv reproduces Sharpe 1.655 or 2.775 exactly. The critical question is whether its drawdown/risk-adjusted advantage remains structurally visible over a much longer sequence of heterogeneous regimes. The review should specifically examine:

- Sharpe stability versus EqualWeight / RiskParity / Momentum;
- MaxDD during major equity drawdowns;
- whether MaxDiv sacrifices excessive long-run CAGR for lower volatility;
- whether performance is dependent on one asset/proxy (especially gold, duration, or cash-like exposure);
- weight concentration and regime-dependent allocation behavior.

PREP should therefore include a plan to report average/maximum weights by slot and, if straightforward, contribution-by-asset or leave-one-slot-out diagnostics. These are diagnostics only; do not change the strategy after seeing them.

## Handoff requirement

When PREP is complete:

1. create `docs/review_packets/GATE_4_LONG_HORIZON_PROXY_PREP.md`;
2. update Claude-owned `CLAUDE_STATUS.yaml` with a new unique handoff id, suggested `G4_LONG_HORIZON_PROXY_PREP_001`;
3. commit and push main;
4. stop and wait for reviewer approval.

No L2 execution is authorized by this response. L1 artifacts/results are frozen and must not be changed.
