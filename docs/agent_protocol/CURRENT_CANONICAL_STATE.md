# Current canonical state

Status date: 2026-08-11

```yaml
project: RL_Stock
research_status: RESEARCH_PHASE_COMPLETE

core:
  policy: MaxDiv
  lookback: 120
  covariance_shrinkage: 0.5

principal_challenger:
  name: M2
  scope: historical_concept_validation_only
  executable_or_live_ready: false
  cagr: 0.116441
  sharpe: 1.219346
  max_drawdown: -0.076651
  defensive_allocation: 0.25

execution_realism:
  instrument: 03110.HK
  state: STOP
  resolved: false

closed_models:
  - PPO
  - SAC
  - TD3

authorized_next: []
```

Interpretation rules:

- Capital-efficiency research is complete.
- M2 is the principal challenger, not a live or executable strategy.
- The `03110.HK` STOP is unresolved and remains separate from the accepted M2
  research result.
- There is no automatic authorization for another research or execution branch.
- This document summarizes canonical state; it does not replace or modify any
  accepted result artifact.

