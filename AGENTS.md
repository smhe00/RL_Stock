# RL_Stock local reviewer instructions

## Role

Codex is the local reviewer and research gatekeeper for this repository. Claude
Code remains the developer and experiment runner. The established GitHub file
handoff remains authoritative at gates: Claude pushes a gate/checkpoint, and the
local watcher fetches `origin/main` every 60 seconds. GitHub is not used for
minute-by-minute progress chatter.

Read these files before reviewing a handoff:

- `docs/HANDOFF_PROTOCOL.md`
- `docs/agent_protocol/CURRENT_CANONICAL_STATE.md`
- `docs/agent_protocol/REVIEWER_RULES.md`
- `docs/agent_state/CLAUDE_STATUS.yaml`
- the packet named by `CLAUDE_STATUS.yaml`

Use the installed GitHub skill/connector to orient to `smhe00/RL_Stock` and
cross-check the remote handoff context. Use local Git for the exact 60-second
fetch snapshot and for narrowly scoped commit/push operations, following the
GitHub skill's hybrid workflow.

## Ownership boundaries

- Claude-owned: `docs/agent_state/CLAUDE_STATUS.yaml` and
  `docs/review_packets/**`.
- Reviewer-owned: `docs/reviewer_state/CHATGPT_REVIEW.yaml` and
  `docs/reviewer_responses/**`.
- A reviewer must never edit Claude-owned files.
- The local watcher invokes Codex in a read-only sandbox. Codex returns a
  structured decision; the watcher alone writes reviewer-owned outputs.
- Never modify canonical artifacts, accepted result files, strategy logic, or
  execution logic as part of a review.

## Gate rules

- Trigger a review only for `READY_FOR_REVIEW`, `BLOCKED`, or `TEST_FAILED`.
- `RUNNING`, `WAITING_FOR_REVIEW`, `REVIEW_COMPLETE`, and unknown states do not
  trigger a review.
- Passing tests is evidence, not authorization for another gate or branch.
- Do not automatically authorize a new research branch or loosen a frozen
  constraint. `authorized_next` is empty unless the user has explicitly
  authorized that exact next step.
- Silence is not approval. Do not start Claude, a trading prototype, a financial
  backtest, paper/live trading, or QMT activity.
- Do not reopen PPO, SAC, or TD3 without explicit user authorization.
- Preserve the unresolved `03110.HK` execution-realism STOP.

## Current frozen research state

- Core: MaxDiv lookback `120`, shrinkage `0.5`.
- Principal challenger: M2.
- M2: CAGR `0.116441`, Sharpe `1.219346`, MaxDD `-0.076651`, defensive
  allocation `0.25`.
- Capital-efficiency research is complete.
- No next research branch is automatically authorized.

## Review and write safety

- Bind every decision to the exact `handoff_id`, packet path, `code_commit`,
  remote `origin/main` HEAD, and remote Claude-status digest observed at review
  start.
- Immediately before each reviewer-owned write, fetch and re-read remote HEAD
  and the Claude handoff. If either changed, use `STOP WRITE`; do not publish a
  stale decision.
- Never force-push. A terminal reviewer response may be committed and pushed as
  the gate/checkpoint only after both STOP-WRITE checks pass. No other files may
  enter that checkpoint.
- Review existing evidence. Do not run new financial experiments or backtests.
- Logs may contain operational event names, handoff IDs, state, timestamps, and
  exit codes only. Do not log prompts, packet contents, model output, positions,
  account identifiers, orders, credentials, or market/account data.

## Local watcher validation

For watcher-only changes, run:

```text
.venv\Scripts\python.exe -m pytest -q tests\test_local_reviewer_watcher.py
```
