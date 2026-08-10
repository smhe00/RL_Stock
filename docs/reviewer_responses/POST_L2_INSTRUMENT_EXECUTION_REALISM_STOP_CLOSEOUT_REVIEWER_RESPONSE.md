# ChatGPT Reviewer Response — POST_L2 Instrument Execution Realism STOP CLOSEOUT

- handoff_id: `G4_POST_L2_INSTRUMENT_EXECUTION_REALISM_STOP_CLOSEOUT_001`
- reviewed packet commit: `8166ffd927d5d1afc4ebcd86e67372c613c52975`
- referenced accepted implementation commit: `aabe0ca30aa9522ad34c682e49155d6cd6c18c4b`
- decision: **STOP_CLOSEOUT_SUBSTANTIVELY_ACCEPTED_DOC_CONSISTENCY_CLEANUP_REQUIRED**
- reviewer state: **REVISIONS_REQUIRED**

## Decision

The closeout is substantively correct in direction and scope. It preserves the accepted CORRECTION_003 STOP, separates economic findings from the structural Southbound-eligibility failure, does not run a new backtest, does not select a post-result branch, and keeps forward/paper/live/QMT live and PPO/SAC/TD3 closed.

However, the closeout cannot yet be treated as the canonical archival record because several numbers/text blocks do not exactly match the already accepted CORRECTION_003 reviewer record. Only a documentation consistency cleanup is authorized; no code or experiment change is permitted.

## Accepted closeout content

- Accepted execution-realism result remains: cumulative return `+47.21%`, calendar CAGR `+9.74%`, Sharpe `1.738`, MaxDD `-4.24%`.
- S2 remains PASS: fee `4.457bp`, spread+slippage `3.000bp`.
- S3 remains FAIL: `478/1011 = 47.28%` distinct fail-closed days, from `461` structural pre-eligibility days union `18` no-quote days with `1` overlap.
- `03110.HK` Southbound eligibility remains frozen at `2024-05-06`; the STOP is structural, not a profitability or modeled-cost failure.
- 03110 eligible-period execution was genuinely exercised in the accepted run: `217` attempted orders, `217` fills, about `CNY 735.8k` traded notional.
- Future branches may be listed only as unselected ideas requiring a fresh PREP; none is authorized or preferred by this closeout.

## Required documentation cleanup

1. **Correct the S1 worst matched-subperiod degradation.** The accepted CORRECTION_003 reviewer record freezes S1 worst degradation at about `-0.70pct` (`-0.006967` in reviewer state), not `-0.84pct`. Replace the closeout's `year_2026 -0.84%` statements and any derived net/research pair unless they are reproduced exactly from the accepted artifact.
2. **Remove stale test/provenance counts.** The accepted CORRECTION_003 review records `21 tests passed` and provenance that binds the actually consumed inputs plus both accepted L1 results/raw artifacts by SHA256. The closeout still contains stale `10 tests`, `13 files`, and conflicting `19 files` text. Use one canonical count/description or avoid a numeric count and refer to the accepted provenance manifest.
3. **Bind the closeout record to the exact accepted artifacts/commits.** Preserve accepted implementation commit `aabe0ca30aa9522ad34c682e49155d6cd6c18c4b`, accepted result/packet commit `7dfabcd8b1e87a462cfa6482b43d7101e00a82f5`, and this closeout packet commit `8166ffd927d5d1afc4ebcd86e67372c613c52975` distinctly. Do not label the implementation commit as the closeout commit.
4. **Normalize future-branch wording.** Branch A may mention `513690.SH` only as an example requiring a fresh PREP. Do not assert that it necessarily makes the entire frozen 2022-06..2026-08 window tradable unless that launch/eligibility fact is separately verified in the new PREP. Likewise, all A-E branches remain unselected.
5. **Keep STOP semantics unchanged.** No mapping substitution, eligibility-date reinterpretation, window change, denominator change, S1/S2/S3 threshold change, or rerun is allowed in this cleanup.

## Authorized next

Only:

`POST_L2_INSTRUMENT_EXECUTION_REALISM_STOP_CLOSEOUT_DOC_CLEANUP`

This is documentation-only. It must make the closeout exactly consistent with the already accepted CORRECTION_003 reviewer state/response and then return for review.

## Forbidden next

- any new backtest or execution-realism rerun
- FORWARD_PAPER_VALIDATION
- PAPER
- LIVE
- QMT_LIVE
- RESULT_INFORMED_INSTRUMENT_SUBSTITUTION
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

PPO/SAC/TD3 remain closed unless the user explicitly reopens them.
