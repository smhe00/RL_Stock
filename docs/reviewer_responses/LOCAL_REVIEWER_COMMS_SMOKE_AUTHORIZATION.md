# ChatGPT Reviewer Authorization — Local Communication Smoke Test

- trigger: explicit user request to verify the established GitHub file handoff
- reviewer handoff: `REVIEWER_INITIATED_LOCAL_COMMS_SMOKE_20260811_001`
- decision: **LOCAL_REVIEWER_COMMS_SMOKE_AUTHORIZED**
- scope: **PROTOCOL COMMUNICATION ONLY**

## Purpose

Verify the existing reviewer-to-Claude-to-reviewer GitHub communication path. This is not a research branch, experiment, backtest, strategy change, execution task, or trading prototype.

## Authorized next

Only:

`LOCAL_REVIEWER_COMMS_SMOKE_HANDOFF`

Claude should:

1. Fetch and consume the matching reviewer state and this response.
2. Create `docs/review_packets/LOCAL_REVIEWER_COMMS_SMOKE_20260811_001.md`.
3. Update only `docs/agent_state/CLAUDE_STATUS.yaml`.
4. Set the Claude handoff to:
   - `protocol_version: 3`
   - `actor: claude`
   - `handoff_id: LOCAL_REVIEWER_COMMS_SMOKE_20260811_001`
   - `state: READY_FOR_REVIEW`
   - `gate: LOCAL_PROTOCOL`
   - `phase: LOCAL_REVIEWER_COMMS_SMOKE`
   - `code_commit: null`
   - `packet: docs/review_packets/LOCAL_REVIEWER_COMMS_SMOKE_20260811_001.md`
5. Preserve the previous review in `last_consumed_review`, recording this reviewer-initiated authorization as the newly consumed review.
6. Commit and push only the two Claude-owned protocol files, then stop at the gate.

The packet should report only protocol-handshake evidence: the consumed reviewer handoff ID, the produced Claude handoff ID, ownership compliance, exact changed paths, commit SHA, and clean-worktree/push status.

## Forbidden

- Any financial backtest, experiment, data refresh, or result generation
- Any strategy, canonical artifact, accepted-result, execution, QMT, account, order, or market-data change
- Any trading prototype, paper trading, or live action
- Any new research branch or broader authorization
- Any change to MaxDiv 120/0.5 or M2 canonical status
- Any attempt to repair or bypass the unresolved 03110 execution-realism STOP
- PPO, SAC, TD3, RL retraining, or RL tuning
- Editing reviewer-owned files

## Frozen state

- MaxDiv lookback 120 and shrinkage 0.5 remain frozen.
- M2 remains the principal challenger with the accepted canonical metrics.
- Capital-efficiency research remains complete.
- The unresolved 03110 execution-realism STOP remains in force.
- PPO/SAC/TD3 remain closed.
- No research or execution step is authorized by this smoke test.
