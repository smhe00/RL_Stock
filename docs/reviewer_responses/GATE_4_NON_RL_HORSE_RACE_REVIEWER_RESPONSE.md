# GATE 4 NON-RL HORSE RACE — REVIEWER RESPONSE

## Decision

```text
GATE_4_NON_RL_HORSE_RACE = TARGETED_CORRECTIONS_REQUIRED
HORSE_RACE_RESULTS = NOT ACCEPTED AS ALGORITHM COMPARISON YET
RL_RETRAINING = FORBIDDEN
10_SEED_FORMAL = REMOVED_FROM_ACTIVE_ROADMAP
NEXT = GATE_4_NON_RL_HORSE_RACE_CORRECTIONS
```

Reviewed handoff:

```text
handoff_id = G4_NON_RL_HORSE_RACE_001
packet      = docs/review_packets/GATE_4_NON_RL_HORSE_RACE.md
code_commit = 6ded3acacb17b629e00acf8af96c42ebed46e2cb
status      = READY_FOR_REVIEW
```

## 1. Overall conclusion

The corrected-path deterministic runner is useful, but the current table cannot be treated as a valid horse race because several newly named portfolio methods are only loose approximations of the frozen algorithms, and at least one implementation is directionally wrong.

Existing corrected-path controls (EW / inverse-vol RP / legacy MinimumVariance / Momentum) may be retained. The six newly added methods must be corrected before their ranking is interpreted.

## 2. BLOCKER N1 — `MinimumCVaR_95` is not a minimum-CVaR optimizer

Current `_cvar95_lp()` does not solve the Rockafellar-Uryasev CVaR program.

Two concrete errors:

```text
1. alpha=0.95 is used as np.quantile(..., 0.95), then samples <= that quantile are selected.
   That selects roughly 95% of observations, not the worst 5% loss tail.

2. avg tail return is converted to:
      score = max(-avg, 0)
      w = score / sum(score)
   This gives MORE weight to assets with larger negative tail losses, which is opposite to
   a minimum-tail-risk allocation.
```

Therefore the reported `MinCVaR_95` CAGR / Sharpe / MaxDD must be discarded.

Required correction:

```text
Implement the actual long-only historical-CVaR optimization:
  minimize zeta + 1/((1-alpha)T) * sum(u_t)
  subject to
    u_t >= -r_t^T w - zeta
    u_t >= 0
    sum(w) = 1
    w >= 0
    same project caps / projection contract
```

Using a deterministic LP solver is acceptable. If an exact constrained solver cannot be used, do not call the method `MinimumCVaR_95`; however, the frozen Tier-A contract requires the real method, so exact implementation is preferred.

Add a semantic test on constructed returns where the optimized portfolio has CVaR no worse than EW and where the known low-tail-risk asset receives higher allocation.

## 3. BLOCKER N2 — ERC solver is not sufficiently validated

Current ERC update is:

```text
w_new ∝ 1 / (Sigma w)
```

This fixed-point iteration is not, by itself, a robust proof of equal-risk-contribution convergence and can oscillate or settle inaccurately.

The test is also too weak:

```text
std(normalized risk contributions) < 0.15
```

and it evaluates contributions using the raw covariance while the policy uses a 0.5-shrunk covariance.

Required correction:

```text
- use a robust ERC solver (cyclical coordinate descent / Newton / constrained optimization),
- evaluate risk contributions with the SAME shrunk covariance used by the policy,
- assert active-asset normalized risk contributions are equal to tight numerical tolerance
  (target max relative deviation <= 1e-3; tighter if solver permits),
- report convergence/fallback count.
```

Until this is done, the reported ERC CAGR 35.6% is not accepted as evidence for ERC.

## 4. BLOCKER N3 — HRP implementation is not canonical HRP

The current implementation performs single-linkage until only two clusters remain, then recursively splits the arbitrary member order of each final cluster and allocates by sums of inverse volatility.

That omits the key canonical HRP steps:

```text
1. full hierarchical clustering / dendrogram
2. quasi-diagonalization (seriation) from the linkage tree
3. recursive bisection using cluster variance, not simply sum(inv_vol)
```

Therefore the current method is a cluster-aware inverse-vol heuristic, not canonical HRP as frozen in the roadmap.

Required correction:

```text
- retain the full linkage structure,
- derive the quasi-diagonal asset order,
- perform recursive bisection with cluster-variance allocation,
- add a block-correlation synthetic test whose cluster order/allocation is known.
```

Do not interpret the current 1.86 Sharpe as HRP evidence.

## 5. BLOCKER N4 — TrendRiskParity does not transfer non-trending risk budget to CASH_LIKE

The frozen contract says risky assets failing the trend filter allocate their risk budget to `CASH_LIKE`.

Current code zeros non-trending risky assets and then renormalizes surviving weights. It only adds the cash asset's own inverse-vol contribution again when cash itself has non-positive trend. It does not transfer the removed risky-asset budget to cash.

Required correction:

```text
1. build the base inverse-vol portfolio across the eligible universe;
2. normalize base weights;
3. identify non-trending risky assets;
4. move the SUM of their base weights to CASH_LIKE;
5. keep trending risky-asset base weights unchanged before the common execution transform;
6. test exact budget conservation on a deterministic synthetic example.
```

## 6. BLOCKER N5 — Maximum Diversification is only an unconstrained solution clipped afterward

Current implementation computes:

```text
w ~ Sigma^-1 sigma
```

then clips negative weights and projects to the simplex.

That is not generally the solution of the long-only constrained maximum-diversification problem after active constraints bind.

Required correction:

```text
solve the actual long-only constrained diversification-ratio objective,
with sum(w)=1 and the same project caps/long-only contract.
```

Add a semantic test that the resulting diversification ratio is at least as high as EW and is locally optimal versus feasible perturbations on a synthetic covariance matrix.

If an approximation is deliberately retained, rename it `MaximumDiversification_Approx` and exclude it from claims about canonical Maximum Diversification; however, Tier A currently requires the canonical method.

## 7. BLOCKER N6 — `ShrinkageMeanVariance` objective is underspecified

Current implementation uses:

```text
w ~ Sigma^-1 mu_shrunk
```

followed by clipping/projection. After normalization this is closer to a long-only clipped tangency-style heuristic than a clearly specified constrained mean-variance utility problem.

Before rerun, freeze and implement one explicit objective, for example:

```text
maximize mu^T w - lambda/2 * w^T Sigma w
subject to sum(w)=1, w>=0, project caps
```

with one preregistered `lambda`, or explicitly rename the method to the objective actually solved. No Test-based tuning.

## 8. BLOCKER N7 — exact Test-mask parity is not demonstrated

The packet reports:

```text
474 execution days
```

while the previously frozen executable Test mask / benchmark parity contract was 475 Test dates.

The runner code includes the first test-start transition, so this discrepancy must be explained rather than accepted silently.

Required correction:

```text
For each of the 10 methods, assert:
  stitched execution dates == exact_test_mask(folds).test_dates
  n_eval_steps == exact_test_date_count

Also independently compare against the corrected executable benchmark count.
```

If the correct count is 474 because the fold/calendar definition changed, document the exact changed date and why; otherwise restore 475 parity.

## 9. BLOCKER N8 — required result artifacts are not in the reviewed commit

The packet states that these outputs exist:

```text
runs/gate4_non_rl_horse_race_results.json
runs/gate4_non_rl_horse_race_raw.json
```

but they are not present in the reviewed GitHub tree. The script writes them locally, but the reviewer cannot independently inspect the claimed per-fold metrics, turnover/cost, or raw series.

Required correction:

```text
- commit the result artifacts (force-add if `/runs` is ignored), OR
- place reviewer-auditable immutable result JSON under a tracked results/artifacts path,
- ensure the packet links to the exact tracked files and commit.
```

The final report must expose the requested fields, not only say they exist:

```text
per-fold return
stitched return/CAGR/vol/Sharpe/Sortino/MaxDD/Calmar
mean + total turnover
actual traded notional
total transaction cost
cost/traded notional
HHI
active assets
max weight
RiskOverlay intervention
fallback count
```

## 10. Test quality requirements

The present tests mostly check legal weights / finiteness. Add algorithm-semantic tests before rerunning:

```text
ERC: tight equal risk contributions using policy covariance
HRP: known clustered covariance -> known hierarchy/seriation behavior
MaxDiv: objective improvement / feasible local optimality
TrendRP: exact non-trend budget moved to cash
MinCVaR: optimized historical CVaR <= EW on constructed tail sample
ShrinkageMV: objective value >= EW for frozen utility on constructed sample
Test mask: exact execution-date equality for every method
```

## 11. What may be retained

The corrected evaluation path itself, corporate-action accounting, cost model, and the four pre-existing deterministic baselines do not need to be discarded solely because these six new algorithms need correction.

Do not rerun TD3/SAC/PPO. Their existing values remain historical references only.

## 12. Authorized next work

Authorize only:

```text
GATE_4_NON_RL_HORSE_RACE_CORRECTIONS
```

Scope:

```text
1. fix N1-N6 algorithm definitions/solvers
2. add semantic tests
3. prove exact Test-mask parity (N7)
4. commit auditable result artifacts (N8)
5. rerun ONLY deterministic non-RL methods
6. regenerate the horse-race table
7. keep existing RL values as historical references; no RL training
8. submit GATE_4_NON_RL_HORSE_RACE_CORRECTIONS.md
9. STOP for review
```

## 13. Explicitly not authorized

```text
RL_RETRAINING
GATE_4_10_SEED_FORMAL
FEATURE_ABLATION_RUNS
FEATURE_DATA_READY_EXPANSION
OPTUNA
HYPERPARAMETER_SWEEP
TEST_INFORMED_SELECTION
THEME_SLEEVE
QMT_LIVE
SOUTHBOUND_EXECUTION
```

## Authorization record

```yaml
gate: 4
handoff_id: G4_NON_RL_HORSE_RACE_001
reviewed_code_commit: 6ded3acacb17b629e00acf8af96c42ebed46e2cb

decision: TARGETED_CORRECTIONS_REQUIRED

blocked:
  - N1_MIN_CVAR_IMPLEMENTATION_INVALID
  - N2_ERC_SOLVER_VALIDATION
  - N3_HRP_NOT_CANONICAL
  - N4_TREND_RP_CASH_TRANSFER
  - N5_MAXDIV_CONSTRAINED_OBJECTIVE
  - N6_SHRINKAGE_MV_OBJECTIVE
  - N7_EXACT_TEST_MASK_PARITY
  - N8_RESULT_ARTIFACTS_NOT_TRACKED

authorized_next:
  - GATE_4_NON_RL_HORSE_RACE_CORRECTIONS

forbidden_next:
  - RL_RETRAINING
  - GATE_4_10_SEED_FORMAL
  - FEATURE_ABLATION_RUNS
  - OPTUNA
  - TEST_INFORMED_SELECTION
  - THEME_SLEEVE
  - QMT_LIVE
  - SOUTHBOUND_EXECUTION
```

## END OF REVIEWER RESPONSE
