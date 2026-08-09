# Reviewer Response — Post-L2 Deterministic Architecture PREP ACK

```yaml
handoff_id: G4_L2_CLOSED_POST_L2_ARCH_PREP_001
reviewed_head: f7385be5496eaba420582910e6493c2d5d0c91eb
reviewed_packet: docs/review_packets/GATE_4_LONG_HORIZON_PROXY_RUN.md
decision: POST_L2_ARCH_PREP_ACK_ONLY_ACTUAL_PREP_PACKET_REQUIRED
reviewer_state: REVISIONS_REQUIRED
authorized_next:
  - POST_L2_DETERMINISTIC_ARCHITECTURE_PREP
forbidden_next:
  - POST_L2_DETERMINISTIC_ARCHITECTURE_RUN
  - RESULT_INFORMED_BLEND_WEIGHT_SEARCH
  - PPO
  - SAC
  - TD3
  - RL_RETRAINING
  - RL_HYPERPARAMETER_TUNING
  - RL_COMPARISON
  - QMT_LIVE
```

## Review conclusion

This handoff correctly acknowledges the accepted FX-corrected L2 result, applies the non-blocking BOC quote-direction wording correction, and transitions the declared phase to `POST_L2_DETERMINISTIC_ARCHITECTURE_PREP`.

However, it is **not yet an architecture PREP submission**. The handoff still points to the old `GATE_4_LONG_HORIZON_PROXY_RUN.md` packet, and no new MaxDiv+Momentum architecture specification is present. Therefore no combined-strategy run is authorized yet.

The next handoff must submit a dedicated PREP packet before any architecture result is computed.

## Required PREP packet

Suggested path:

`docs/review_packets/POST_L2_DETERMINISTIC_ARCHITECTURE_PREP.md`

Suggested handoff:

`G4_POST_L2_DETERMINISTIC_ARCH_PREP_001`

The packet must freeze the following **before seeing any combined-strategy result**.

### 1. Parent strategies are immutable

Use the accepted canonical parents without retuning:

- MaximumDiversification: lookback 120, shrinkage 0.5, project-constrained implementation already accepted;
- Momentum_12_1: lookback 252, skip 21, positive-score weighting, accepted fallback semantics;
- same 11 slots, same signal timing, same CNY/FX treatment, same `RiskOverlayV0`, same 2800-interval Track-C scenario panel;
- no proxy replacement and no parameter search.

### 2. Exact candidate architecture set

Freeze a **small, finite, rationale-driven** candidate set. Do not create a dense blend-weight sweep.

The PREP must state exact sleeve weights for every candidate, e.g. a limited set of static MaxDiv/Momentum blends. Pure MaxDiv and pure Momentum must remain controls.

If any dynamic architecture is proposed, its formula, inputs, thresholds, update cadence and caps must be completely specified ex ante. A dynamic rule may not use future combined-run results to choose its thresholds.

### 3. Exact blending semantics

The packet must state the order of operations unambiguously. Recommended canonical structure:

```text
w_maxdiv(T) = accepted executable MaxDiv target at T
w_mom(T)    = accepted executable Momentum target at T

w_blend_raw(T) = alpha * w_maxdiv(T) + (1-alpha) * w_mom(T)

w_final(T) = RiskOverlayV0(w_blend_raw(T))
```

If a different order is proposed, explain why and freeze it before the run.

Turnover and cost must be computed on the final executable weight path, not by averaging the standalone reported turnovers.

### 4. Rebalance and timing contract

Freeze:

- decision cadence;
- information cutoff;
- T-1 treatment for non-A-share signals;
- CNY return-level treatment for HK sleeves;
- T->T+1 realized-return assignment;
- no lookahead;
- missing-data/fallback handling.

Prefer reusing the already accepted L2 timing path without alteration.

### 5. Evaluation table

Every candidate and both parent controls must report at minimum:

- cumulative return;
- Calendar CAGR;
- active-day annualized return;
- annualized volatility;
- Sharpe;
- Sortino;
- MaxDD;
- Calmar;
- worst calendar year;
- worst rolling 12m return;
- turnover;
- 1x approximate cost sensitivity;
- average and maximum slot weights;
- HHI/concentration;
- post-overlay feasibility violations.

Use the same pre-frozen stress regimes as accepted L2.

### 6. Ex-ante success criteria

Before running, define what constitutes a useful architecture.

The PREP must explicitly freeze decision criteria that reflect the intended trade-off between MaxDiv and Momentum, including at least:

- required improvement in long-horizon return versus pure MaxDiv;
- maximum acceptable degradation in drawdown versus pure MaxDiv;
- minimum acceptable Sharpe and/or Calmar;
- cost/turnover tolerance;
- whether terminal-wealth improvement is allowed to justify a lower Sharpe;
- how a candidate is treated if it is Pareto-dominated by one of the parents.

Do not invent or alter these thresholds after seeing combined results.

### 7. No winner-picking by dense search

Forbidden during the next RUN:

- scanning many alpha values and selecting the historical optimum;
- optimizing blend weights on the accepted 2015-2026 history;
- changing MaxDiv/Momentum parameters;
- introducing a new signal because a candidate underperforms;
- changing stress periods, costs, data, slots or proxies after observing results.

A small set of pre-declared candidates is acceptable; a retrospective efficient-frontier search is not.

### 8. Next-stage path must be documented

The PREP should state that even a successful architecture result does **not** authorize live trading. The expected sequence remains:

```text
architecture PREP
-> one frozen architecture RUN
-> instrument-level execution realism
-> forward/paper validation
-> only then consider small-capital deployment
```

## Accepted context that must not be reopened

The following are already closed/accepted and should be treated as fixed inputs:

- FX-corrected L2 gen3 accepted;
- MaxDiv accepted L2: ~6.0% Calendar CAGR, Sharpe 1.024, MaxDD ~-10.4%;
- Momentum accepted L2: ~8.4% Calendar CAGR, Sharpe 0.571, MaxDD ~-44.3%;
- MaxDiv role: risk-control/core allocator;
- Momentum role: long-horizon return engine;
- STAR Track-C basis-risk warning remains disclosed;
- L1 remains frozen;
- PPO/SAC/TD3 and QMT live remain forbidden.

## Required next action

Create the dedicated architecture PREP packet and update Claude status to point to that packet. Do **not** run combined MaxDiv+Momentum results yet.
