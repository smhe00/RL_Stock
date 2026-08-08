# Claude Code ↔ ChatGPT Reviewer Handoff Protocol

Version: 2.0

## 1. Source of truth

GitHub repository `smhe00/RL_Stock` is the shared state and message bus.

```text
Claude Code = Developer / experiment runner
ChatGPT     = Reviewer / research gatekeeper
GitHub      = shared state + handoff channel
```

Chat history is not authoritative. Repository state is authoritative.

## 2. Directory ownership

```text
docs/
├─ review_packets/                 # Claude writes
├─ reviewer_responses/             # ChatGPT writes
├─ agent_state/
│  └─ CLAUDE_STATUS.yaml           # Claude writes only
├─ reviewer_state/
│  └─ CHATGPT_REVIEW.yaml          # ChatGPT writes only
└─ HANDOFF_PROTOCOL.md             # protocol; change only deliberately

scripts/
└─ wait_for_reviewer.py            # local Claude polling helper
```

Ownership rule:

```text
Claude never edits CHATGPT_REVIEW.yaml or reviewer_responses/*
ChatGPT never edits CLAUDE_STATUS.yaml or review_packets/*
```

This prevents push conflicts and stale handoff overwrites.

## 3. Claude status schema

`docs/agent_state/CLAUDE_STATUS.yaml`

```yaml
protocol_version: 2
actor: claude
handoff_id: G4_EVAL_FIX_001
state: RUNNING

gate: 4
phase: GATE_4_EVAL_FIX
code_commit: abc1234
packet: docs/review_packets/GATE_4_EVAL_FIX.md

progress:
  current_task: segment_accounting_reset

last_consumed_review:
  handoff_id: G4_3SEED_001
  decision: PILOT_MECHANICS_PASS_FORMAL_NOT_AUTHORIZED
  response: docs/reviewer_responses/GATE_4_3_SEED_PILOT_REVIEWER_RESPONSE.md

updated_at: 2026-08-09T01:30:00+08:00
```

Allowed Claude states:

```text
RUNNING
READY_FOR_REVIEW
BLOCKED
TEST_FAILED
WAITING_FOR_REVIEW
```

## 4. ChatGPT reviewer state schema

`docs/reviewer_state/CHATGPT_REVIEW.yaml`

```yaml
protocol_version: 2
actor: chatgpt_reviewer
handoff_id: G4_EVAL_FIX_001
state: REVIEW_COMPLETE

reviewed_packet:
  path: docs/review_packets/GATE_4_EVAL_FIX.md
  commit: abc1234

decision: APPROVED
response:
  path: docs/reviewer_responses/GATE_4_EVAL_FIX_REVIEWER_RESPONSE.md

authorized_next:
  - GATE_4_FEATURE_ABLATION

forbidden_next:
  - GATE_4_10_SEED_FORMAL
```

Reviewer states:

```text
REVIEW_COMPLETE
REVISIONS_REQUIRED
BLOCKED
```

## 5. Claude startup / resume sequence

Every start or resume:

```text
1. git status --short
2. git fetch origin main
3. if worktree clean: git pull --ff-only
4. read docs/HANDOFF_PROTOCOL.md
5. read docs/agent_state/CLAUDE_STATUS.yaml
6. read docs/reviewer_state/CHATGPT_REVIEW.yaml
7. if reviewer handoff_id matches the pending handoff, read the referenced reviewer response
8. execute only explicitly authorized_next
```

Silence is not approval.

## 6. Claude → ChatGPT handoff

When a gate/sub-gate is complete:

```text
1. finish tests / results
2. create or update docs/review_packets/<PACKET>.md
3. update CLAUDE_STATUS.yaml
4. set unique handoff_id
5. set state = READY_FOR_REVIEW
6. commit all intended developer changes
7. push main
8. verify remote commit SHA
9. ensure working tree clean
10. STOP coding across the gate
11. run scripts/wait_for_reviewer.py <handoff_id>
```

The packet must record the exact implementation/result commit being reviewed.

## 7. ChatGPT review sequence

Triggered by either:

```text
user says “检查进展”
```

or hourly watchdog.

ChatGPT:

```text
1. reads CLAUDE_STATUS.yaml
2. checks READY_FOR_REVIEW / BLOCKED / TEST_FAILED
3. reads the packet
4. inspects exact commit/diff/source/tests/results
5. writes docs/reviewer_responses/<PACKET>_REVIEWER_RESPONSE.md
6. writes/updates docs/reviewer_state/CHATGPT_REVIEW.yaml
7. pushes to main
8. notifies user only when there is a meaningful decision/blocker
```

ChatGPT must not edit Claude-owned files.

## 8. Claude waits for reviewer by fetch, not pull

While waiting, use `git fetch`, not repeated `git pull`.

Recommended poll interval: 60–120 seconds.

When the expected `handoff_id` appears in `origin/main:docs/reviewer_state/CHATGPT_REVIEW.yaml` with a terminal reviewer state:

```text
REVIEW_COMPLETE
REVISIONS_REQUIRED
BLOCKED
```

then:

```text
1. verify worktree clean
2. git pull --ff-only
3. read CHATGPT_REVIEW.yaml
4. read referenced reviewer response
5. update CLAUDE_STATUS.yaml to RUNNING if work is authorized
6. execute only authorized_next
```

## 9. Handoff identity

Every request/review pair has a unique ID, for example:

```text
G4_3SEED_001
G4_EVAL_FIX_001
G4_FEATURE_ABLATION_001
G4_10SEED_001
```

Never consume a reviewer response for a different handoff ID.

## 10. Failure protocol

If a stop condition or test failure occurs, Claude writes:

```yaml
state: BLOCKED
```

or:

```yaml
state: TEST_FAILED
```

and records:

```text
failure reason
failed command/test
last successful commit
working-tree state
recommended recovery point
```

Then push and stop.

## 11. Git conflict rules

Before pulling:

```text
git status --short
```

If dirty with unrelated work, do not auto-merge or discard.

Normal synchronization must use:

```text
git pull --ff-only
```

Never force-push `main`.

## 12. Long-running runs

While `RUNNING`, Claude may push status at natural milestones, but should not create noisy minute-by-minute commits.

Useful milestones:

```text
seed batch complete
major test suite complete
blocking failure
READY_FOR_REVIEW
```

ChatGPT may read progress while Claude is running, but should avoid repository writes unless issuing an explicit reviewer response to a completed handoff.

## 13. Gate rule

Passing tests does not authorize the next gate.

Only `authorized_next` in the matching `CHATGPT_REVIEW.yaml` / reviewer response authorizes cross-gate work.

## 14. Legacy status

`docs/CODEX_AGENT_STATUS.md` may remain as historical context, but the machine-readable primary status is now:

```text
docs/agent_state/CLAUDE_STATUS.yaml
```

## END
