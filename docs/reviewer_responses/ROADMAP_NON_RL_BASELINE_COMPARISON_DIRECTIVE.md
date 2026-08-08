# ROADMAP DIRECTIVE — NON-RL PORTFOLIO HORSE RACE

Date: 2026-08-09
Authority: user roadmap decision + ChatGPT reviewer research

## Decision

```text
GATE_4_10_SEED_FORMAL = DEFERRED / REMOVED_FROM_ACTIVE_ROADMAP
DO_NOT_RETRAIN_TD3_SAC_PPO
NEXT_AFTER_CURRENT_PREP_CORRECTIONS = GATE_4_NON_RL_HORSE_RACE
```

The project is still in exploration. Expanding RL from 3 seeds to 10 seeds has low marginal information value relative to compute cost, because the 3-seed pilot already showed low seed dispersion. Do not schedule 10-seed work unless the user explicitly re-authorizes it later.

## Current work ordering

1. Finish only the already-authorized `GATE_4_FEATURE_ABLATION_PREP_CORRECTIONS` (PIT/native-calendar/spec/preprocessing-parity correctness).
2. STOP and submit that correction packet.
3. After reviewer confirms the corrections, prioritize `GATE_4_NON_RL_HORSE_RACE` before any feature-ablation training.
4. Feature-ablation training is deferred behind the non-RL comparison.
5. 10-seed formal is not an automatic later step.

## Existing algorithms / results

Existing deterministic baseline implementations already include:

```text
EqualWeight
RiskParity (inverse volatility)
MinimumVariance
Momentum (12-1 relative momentum)
```

Existing RL training already completed:

```text
TD3 / SAC / PPO
3 seeds = 42 / 2026 / 7
4 folds
```

Do NOT retrain TD3/SAC/PPO for the horse race.

Existing RL pilot numbers may be carried into the comparison as `HISTORICAL_RL_PILOT_REFERENCE` with the explicit caveat that they were generated before the later evaluation-semantics corrections. They are not to be silently relabeled as corrected formal OOS evidence.

## Non-RL algorithms to compare

### Tier A — required

1. `EqualWeight` — existing control; rerun is allowed because deterministic and cheap, using the corrected evaluation path.
2. `RiskParity_IVOL` — existing inverse-volatility implementation; corrected-path rerun allowed.
3. `MinimumVariance` — existing shrinkage GMV; corrected-path rerun allowed.
4. `Momentum_12_1` — existing relative momentum; corrected-path rerun allowed.
5. `EqualRiskContribution_ERC` — true equal marginal risk contribution; distinct from inverse-vol risk parity when correlations differ.
6. `HierarchicalRiskParity_HRP` — correlation-distance clustering + quasi-diagonalization + recursive bisection; no expected-return estimation.
7. `MaximumDiversification` — maximize diversification ratio `(w' sigma) / sqrt(w' Sigma w)` under long-only / project constraints.
8. `TrendRiskParity` — absolute trend filter + inverse-vol allocation; assets failing the trend filter allocate to `CASH_LIKE` rather than forcing risk exposure.
9. `MinimumCVaR_95` — long-only 95% expected-shortfall minimization, to add a tail-risk objective distinct from variance.
10. `ShrinkageMeanVariance` — expected-return-aware classical optimizer using explicitly frozen shrinkage assumptions; included as a stress benchmark for estimation error, not presumed superior.

### Tier B — optional only if Tier A implementation is clean

```text
HERC (Hierarchical Equal Risk Contribution)
Exponentiated-Gradient online portfolio selection
OLMAR
```

Do not create a parameter sweep. These methods introduce linkage/learning-rate/reversion hyperparameters and can easily become a multiple-testing exercise.

## Frozen design principles

```text
same Track-A 11 Asset Slots
long-only
no leverage
same RiskOverlay / slot caps
same t close -> t+1 open execution
same raw-price fill / total-return feature dual-price contract
same 1x transaction-cost model
same corporate-action accounting
same corrected fold-local Test reset semantics
same stitched exact Test mask
no Test-informed tuning
```

All dynamic non-RL algorithms must use only information available at decision time `t`.

## Parameter policy

Use one preregistered parameterization per algorithm. No grid search on Test.

Recommended starting contracts:

```text
ERC: covariance lookback 120D; shrinkage covariance; long-only
HRP: returns lookback 120D; correlation distance sqrt((1-rho)/2); canonical single-linkage unless implementation dependency requires a documented alternative
MaximumDiversification: 120D shrinkage covariance; long-only
TrendRiskParity: inverse-vol 60D; absolute trend = positive 252/21 (12-1) return; non-trending risky weight -> CASH_LIKE
MinimumCVaR_95: 120D historical returns; alpha=0.95; long-only; same caps
ShrinkageMeanVariance: 252D expected-return window; expected returns shrunk toward cross-sectional mean; covariance shrunk; long-only; same caps
```

If a required lookback is unavailable at a decision date, use the same fail-safe convention defined before the run (normally EW or CASH_LIKE), and report fallback count.

## Comparison protocol

Run only the non-RL algorithms. Do not retrain or rerun RL training.

For every non-RL algorithm output:

```text
per-fold net return
stitched cumulative net return
stitched active-day annualized return
annualized volatility
Sharpe
Sortino
MaxDD
Calmar
mean / total turnover
actual traded notional
transaction cost
cost / traded notional
HHI
average active assets
max single weight
RiskOverlay intervention rate
fallback count
```

Produce a final horse-race table containing:

```text
A. corrected-path non-RL algorithms
B. existing RL 3-seed median/mean/min/max as historical reference only
```

Do not declare a universal winner from one short OOS sample. Rank separately on:

```text
return
risk-adjusted return
drawdown
tail risk
turnover/cost
stability across folds
```

## Research rationale

- 1/N remains an important benchmark because expected-return/covariance estimation error can erase the theoretical benefit of optimization (DeMiguel, Garlappi, Uppal).
- ERC equalizes component risk contributions and differs materially from simple inverse-volatility weights when correlations are non-uniform (Maillard, Roncalli, Teiletche).
- HRP was proposed specifically to address instability, concentration and covariance-inversion problems of quadratic optimizers (Lopez de Prado).
- Maximum Diversification optimizes the diversification ratio and provides a correlation-aware risk-based benchmark (Choueifaty, Coignard).
- Trend-following overlays combined with risk-based allocation have empirical support in multi-asset allocation and provide a distinct tactical mechanism from relative momentum (Clare et al.; Antonacci).
- CVaR/Expected-Shortfall optimization adds an explicit downside-tail objective; it should be judged primarily on downside control rather than raw CAGR.
- Shrinkage covariance is preferred to raw sample covariance for optimizers because covariance estimation error materially destabilizes portfolio weights (Ledoit-Wolf).

## Output packet

After implementation/run, submit:

```text
docs/review_packets/GATE_4_NON_RL_HORSE_RACE.md
runs/gate4_non_rl_horse_race_results.json
runs/gate4_non_rl_horse_race_raw.json
```

and STOP for review.

## Explicitly not authorized

```text
RL retraining
10-seed formal
20-seed
Optuna / hyperparameter sweeps
Test-informed algorithm parameter selection
theme sleeve
QMT live
Southbound execution
```
