# GATE 4 3-SEED PILOT — REVIEWER RESPONSE

## Decision

```text
GATE_4_3_SEED_PILOT = PASS_AS_MECHANICS
GATE_4_3_SEED_PILOT_PERFORMANCE = PRELIMINARY_NOT_FORMAL
GATE_4_10_SEED_FORMAL = NOT AUTHORIZED
NEXT = GATE_4_EVAL_FIX
```

Reviewed state:

```text
reviewed repo commit = 24562834b5e0d2d65c773fcfd5b16517314ce622
results commit       = 8081d01bdbef742186d56f5fa44ad6e4e17b0c6b
runner implementation= 78eb29796a39ac6239f652afcc441307686ab2b9
```

## 1. What passed

The pilot succeeded as a mechanics / robustness exercise:

```text
36/36 RL trainings completed
0 NaN/Inf
0 negative cash
0 failed run
0 retry
save/load deterministic
TD3/SAC/PPO all runnable
seed dispersion reasonably low
corporate-action path stable enough for pilot
```

Therefore:

```text
PILOT MECHANICS = PASS
```

The reported stitched OOS results are useful diagnostics, but are not yet formal evidence because evaluation-path issues were found during source review.

## 2. Preliminary results retained for diagnosis

Reported stitched Test OOS medians:

```text
TD3  CAGR ~24.9%, Sharpe ~1.49
SAC  CAGR ~25.5%, Sharpe ~1.57
PPO  CAGR ~27.5%, Sharpe ~1.61
```

Momentum baseline reported CAGR ~30.4%, which reinforces the requirement to keep strong deterministic baselines in the formal comparison.

No algorithm winner declaration is authorized.

---

# BLOCKER E1 — segment portfolio state is produced by retroactive replay

Current `WalkForwardRunner._rollout_segment()` builds an environment containing all historical data up to the segment end and calls `roll_out(..., eval_start=start)`.

`roll_out()` resets the environment at the historical warm-up start and executes the final trained policy through historical Train/Validation periods before it begins recording Test metrics.

So Test starts with a portfolio state created by:

```text
final trained policy
→ replay old Train history
→ replay old Validation history
→ arrive at Test boundary with synthetic portfolio state
→ record Test
```

This is not the strict walk-forward deployment semantics we want.

## Required E1 contract

Keep complete PIT feature history for 252D features, but reset portfolio/accounting state at each evaluation boundary.

### Validation

```text
feature history: retained
accounting reset: train_end close
initial portfolio: cash, zero positions
decision: train_end close
first execution: val_start open
first evaluated transition: val_start
```

### Test

```text
feature history: retained
accounting reset: val_end close
initial portfolio: cash, zero positions
decision: val_end close
first execution: test_start open
first evaluated transition: test_start
```

Do not solve this by truncating feature history.

Required tests at minimum:

```text
test_validation_accounting_resets_at_train_end
test_test_accounting_resets_at_val_end
test_test_start_position_does_not_depend_on_retroactive_train_replay
test_test_first_fill_occurs_at_test_start_open
test_feature_history_preserved_after_accounting_reset
test_corporate_actions_before_segment_reset_do_not_create_receivables_after_reset
```

Manifest should expose:

```text
segment_predecision_date
segment_first_execution_date
segment_first_metric_date
initial_cash
initial_positions
```

---

# BLOCKER E2 — Test cost includes pre-Test accumulated fees

In `roll_out()`:

```python
prev_fees = 0.0
```

but `PortfolioAccounting.fees_paid` is cumulative, and `prev_fees` is only advanced after `st.t >= eval_start`.

Therefore the first recorded Test `step_cost` includes fees accumulated before Test.

This explains the implausible reported combination:

```text
PPO mean turnover ~0.054
PPO F3 cost / initial ~2.38%
```

while the current Mainland V1 one-way cost assumption is only about:

```text
0.5 bp commission
+1.0 bp half spread
+2.0 bp slippage
≈3.5 bp
```

## Required E2 fix

If E1 gives each segment independent accounting, fee accumulation should naturally restart from zero at the segment boundary.

Otherwise initialize:

```text
prev_fees = fees_at_segment_start
```

and assert:

```text
sum(test_step_cost)
== fees_at_test_end - fees_at_test_start
```

Add per strategy/fold:

```text
mean_turnover_l1
total_turnover_l1
estimated_one_way_traded_fraction = total_turnover_l1 / 2
actual_traded_notional
actual_traded_notional / initial_equity
total_cost
total_cost / actual_traded_notional
cost_over_initial_equity
```

Required tests:

```text
test_segment_cost_excludes_presegment_fees
test_total_cost_reconciles_to_fee_delta
test_cost_turnover_order_of_magnitude_consistent
```

---

# BLOCKER E3 — RiskOverlay diagnostics are mathematically inconsistent

Packet reports approximately:

```text
TD3 F1 intervention_rate = 43.6%
mean L1(raw→post)        = ~1e-16
```

but code defines intervention as:

```python
l1 = abs(raw - post).sum()
overlay_intervened += int(l1 > 1e-6)
```

If 43.6% of steps have L1 > 1e-6, the mean L1 cannot be ~1e-16.

Required diagnostics:

```text
raw_single_core_violation_rate
raw_china_growth_violation_rate
overlay_intervention_rate
mean_l1_raw_to_post
post_single_core_at_cap_rate
post_china_growth_at_cap_rate
post_constraint_violation_rate
```

Add reconciliation assertions so an impossible report cannot be emitted.

---

# Benchmark / stitched-mask requirement

The stitched OOS series is non-contiguous because Validation gaps exist between Test folds.

Therefore 510300 benchmark must use the exact same Test-date mask.

Formal output must include:

```text
strategy_stitched_steps
benchmark_stitched_steps
exact_test_date_count
first_test_date
last_test_date
excluded_validation_dates
```

and assert equal step counts.

Prefer wording:

```text
stitched OOS active-day annualized return
```

rather than implying a continuous calendar hold from first to last date.

Also add an executable baseline:

```text
CN_LARGE_BUY_HOLD
```

using raw execution prices + corporate-action accounting + 1x costs + exact same Test mask.

Keep separate labels:

```text
510300_RESEARCH_TR_REFERENCE
510300_EXECUTABLE_NET_BUY_HOLD
```

---

# OOS fallback pay dates

Current inventory:

```text
total cash events              = 24
official pay-date events       = 2
conservative fallback events   = 22
fallback events inside Test    = 7
```

Before 10-seed formal, either:

1. resolve official payment dates for the 7 OOS fallback events; or
2. run settlement-delay sensitivity (+3T/+5T/+7T) on baselines plus one representative RL seed and show immaterial impact.

No need to resolve all non-OOS fallback events if they cannot affect formal OOS evidence.

---

# Baseline metric parity

Formal baselines must report the same metric family as RL:

```text
CAGR
annualized vol
Sharpe
Sortino
MaxDD
Calmar
turnover
actual traded notional
cost
HHI
active assets
```

Before final Gate-4 comparison, add:

```text
Mean-Variance
Trend + RiskParity
```

or explicitly RFC-remove them.

---

# Feature-ablation preparation

Do not start 10-seed formal yet.

Freeze feature candidates now, before using Test results to influence feature selection.

## F0 — current

```text
ObsDim = 104
```

## F1 — Risk / Correlation

```text
corr_pc1_share_60
equity_bond_corr_change_20_60
equity_gold_corr_change_20_60
cn_us_corr_60
equity_vol_ratio_20_60
equity_downside_semivol_60
```

## F2 — Macro / Forward Risk

```text
vix_prev_close_percentile_252
vix_prev_close_change_5
usd_cny_return_20
cgb10y_yield_change_20
dr007_zscore_60
a_share_turnover_zscore_20
```

All external features must be strict PIT. China EOD decisions may use only the previous completed US session VIX.

## F3 — Combined

```text
F1 + F2
```

Keep ObsDim approximately <=120. Do not add a large TA bundle (RSI/MACD/KDJ/CCI/ADX/many MAs) because current R5/R20/R60/R120 + vol20/60 + drawdown60/250 already encode substantial price-path information.

Feature ablation runs are NOT yet authorized. Only spec/preparation is authorized until E1/E2/E3 are fixed.

---

# Required next packet

Create:

```text
docs/review_packets/GATE_4_EVAL_FIX.md
```

Include:

```text
1. E1 segment accounting-reset implementation
2. Validation/Test predecision/first-fill/first-metric timeline
3. E2 cost reconciliation
4. corrected turnover/cost diagnostics
5. E3 RiskOverlay reconciliation
6. exact stitched Test-mask proof
7. executable 510300 buy-and-hold baseline smoke
8. OOS fallback pay-date official-date or sensitivity plan
9. frozen F0/F1/F2/F3 feature spec
10. full pytest
11. corrected seed42 mechanics/regression smoke only
12. old-vs-new metric delta, diagnostic only
13. exact git commit
```

Do not rerun all 36 pilot jobs yet.

---

# Authorization record

```yaml
gate: 4
handoff_id: G4_3SEED_001
packet: GATE_4_3_SEED_PILOT

decision:
  pilot_mechanics: PASS
  pilot_performance: PRELIMINARY
  ten_seed_formal: NOT_AUTHORIZED

next_authorized:
  - GATE_4_EVAL_FIX

feature_work:
  ablation_spec_prep: authorized
  ablation_run: not_yet_authorized

forbidden:
  - GATE_4_10_SEED_FORMAL
  - OPTUNA
  - TEST_INFORMED_FEATURE_SELECTION
  - THEME_SLEEVE
  - QMT_LIVE
  - SOUTHBOUND_EXECUTION
```

## Claude next instruction

```text
1. Pull latest main.
2. Read docs/HANDOFF_PROTOCOL.md.
3. Create/maintain docs/agent_state/CLAUDE_STATUS.yaml.
4. Do NOT start 10-seed formal.
5. Implement E1/E2/E3 fixes.
6. Add exact Test-mask and executable 510300 checks.
7. Resolve/sensitivity-bound 7 OOS fallback pay dates.
8. Freeze F0/F1/F2/F3 spec; do not run feature ablation yet.
9. Run full tests.
10. Run corrected seed42 mechanics/regression smoke only.
11. Generate docs/review_packets/GATE_4_EVAL_FIX.md.
12. Set handoff_id=G4_EVAL_FIX_001 and state=READY_FOR_REVIEW.
13. Commit + push.
14. STOP and run scripts/wait_for_reviewer.py G4_EVAL_FIX_001.
```

## END OF REVIEWER RESPONSE
