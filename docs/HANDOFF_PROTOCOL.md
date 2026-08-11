# Claude Code ↔ Local Codex Reviewer Handoff Protocol

Version: 3.0

## 1. Source of truth and transport

The established GitHub file protocol remains authoritative at gate handoffs.
The local migration changes reviewer latency and execution location, not the
ownership or STOP-GATE model.

```text
Claude Code = developer / experiment runner
Local Codex = reviewer / research gatekeeper
GitHub      = gate/checkpoint transport + audit history
```

Claude pushes only at a gate, blocker, test failure, or useful checkpoint. The
local watcher runs `git fetch origin main` every 60 seconds. It does not require
minute-by-minute progress commits, and it never starts Claude.

Chat history is not authoritative. The current `origin/main` protocol files and
the exact commits/artifacts they reference are authoritative.

## 2. Directory ownership

```text
docs/
├─ review_packets/                 # Claude writes
├─ reviewer_responses/             # Local Codex reviewer writes
├─ agent_state/
│  └─ CLAUDE_STATUS.yaml           # Claude writes only
├─ reviewer_state/
│  └─ CHATGPT_REVIEW.yaml          # Reviewer writes only; name retained
└─ HANDOFF_PROTOCOL.md             # change only deliberately
```

Ownership rule:

```text
Claude never edits CHATGPT_REVIEW.yaml or reviewer_responses/*
Reviewer never edits CLAUDE_STATUS.yaml or review_packets/*
```

The watcher invokes `codex exec` in a read-only sandbox. Codex returns a
schema-validated decision; the watcher alone writes the two reviewer-owned
outputs.

## 3. Claude status schema

`docs/agent_state/CLAUDE_STATUS.yaml`

```yaml
protocol_version: 3
actor: claude
handoff_id: G4_EVAL_FIX_001
state: READY_FOR_REVIEW

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

updated_at: 2026-08-11T01:30:00+08:00
```

Recognized Claude states:

```text
RUNNING
READY_FOR_REVIEW
BLOCKED
TEST_FAILED
WAITING_FOR_REVIEW
REVIEW_COMPLETE
```

Only `READY_FOR_REVIEW`, `BLOCKED`, and `TEST_FAILED` trigger a review.

## 4. Reviewer state schema

`docs/reviewer_state/CHATGPT_REVIEW.yaml` retains its path for compatibility.

```yaml
protocol_version: 3
actor: codex_reviewer
handoff_id: G4_EVAL_FIX_001
state: REVIEW_COMPLETE

reviewed_packet:
  path: docs/review_packets/GATE_4_EVAL_FIX.md
  commit: abc1234

reviewed_remote_head: abc1234
decision: APPROVED

response:
  path: docs/reviewer_responses/G4_EVAL_FIX_001_REVIEWER_RESPONSE.md

authorized_next: []
forbidden_next: []
```

Terminal reviewer states:

```text
REVIEW_COMPLETE
REVISIONS_REQUIRED
BLOCKED
```

## 5. Claude startup and resume

Every start or resume:

```text
1. git status --short
2. git fetch origin main
3. if worktree clean: git pull --ff-only
4. read docs/HANDOFF_PROTOCOL.md
5. read docs/agent_protocol/CURRENT_CANONICAL_STATE.md
6. read docs/agent_state/CLAUDE_STATUS.yaml
7. read docs/reviewer_state/CHATGPT_REVIEW.yaml
8. consume a response only when handoff_id matches
9. execute only explicitly authorized_next
```

Silence, elapsed time, passing tests, or a watcher event is not approval.

## 6. Claude to reviewer handoff

When a gate/sub-gate is complete or blocked:

```text
1. finish the allowed tests/results
2. create or update docs/review_packets/<PACKET>.md
3. update CLAUDE_STATUS.yaml
4. set a unique handoff_id
5. set state READY_FOR_REVIEW, BLOCKED, or TEST_FAILED
6. bind packet and code_commit to the exact evidence
7. commit all intended Claude-owned/developer changes
8. push main as the gate/checkpoint
9. verify remote commit SHA and clean worktree
10. STOP coding across the gate
```

For `BLOCKED` or `TEST_FAILED`, record failure reason, failed command/test, last
successful commit, working-tree state, and recommended recovery point. A packet
is recommended; `READY_FOR_REVIEW` requires one.

## 6a. Mandatory Claude handoff finalization — wake-up doorbell invariant

Every fresh handoff that requests Web ChatGPT review (`READY_FOR_REVIEW`,
`BLOCKED`, or `TEST_FAILED`) MUST end with a Claude-owned wake-up doorbell
`docs/web_bridge/<handoff_id>/claude_work_complete.json` published on
`origin/main`. The Web Fetch Bridge daemon is marker-only and research-state
agnostic: it never parses `CLAUDE_STATUS.yaml`, so a state transition without the
doorbell can never wake Web ChatGPT automatically. This invariant is MANDATORY;
a fresh Claude session must not omit it.

Finalization order (LAST is load-bearing):

```text
1. packet/status complete (docs/review_packets/<PACKET>.md + CLAUDE_STATUS.yaml)
2. commit/push packet/status; confirm origin/main HEAD
3. remote confirmation (local HEAD == origin/main; pull --ff-only if needed)
4. claude_work_complete.json doorbell for the exact handoff  <- MUST be LAST push
```

Use the deterministic helper rather than hand-creating the marker:

```text
.venv/Scripts/python.exe scripts/finalize_handoff.py \
    --handoff <HANDOFF_ID> --code-commit <SHA> [--expect-head <SHA>]
```

The helper requires an explicit handoff id and code commit, creates only the
Claude-owned doorbell, stamps a timezone-aware UTC timestamp, and fails closed on
duplicate/append-only violation or unexpected remote state. After it prints the
marker path, commit and push that single marker as the FINAL push of the gate.

Do NOT retrofit a doorbell to a handoff that has already been manually surfaced
and reviewed — that could trigger a duplicate browser fetch.

## 7. Local fetch monitor

The watcher performs one bounded scan every 60 seconds:

```text
1. git fetch origin main
2. read origin/main:docs/agent_state/CLAUDE_STATUS.yaml
3. ignore RUNNING / WAITING_FOR_REVIEW / REVIEW_COMPLETE
4. check READY_FOR_REVIEW / BLOCKED / TEST_FAILED
5. reject an already-seen handoff_id
6. verify the READY packet exists on origin/main
7. capture remote HEAD and status/packet/reviewer-state digests
8. invoke the read-only local Codex review entry
```

Fetch failure is logged as operational metadata and retried on the next minute.
The watcher never pulls a dirty worktree and never auto-resolves divergence.

## 8. Pre-write sync guard — HARD REQUIREMENT

The web reviewer guard remains in force. Before any reviewer write, the watcher
fetches again and verifies:

```text
origin/main HEAD unchanged
CLAUDE_STATUS digest unchanged
handoff_id and trigger state unchanged
packet digest unchanged
pre-existing reviewer-state digest unchanged
```

Then it fast-forwards a clean local `main` to the reviewed remote HEAD and writes
the reviewer response.

Before writing `CHATGPT_REVIEW.yaml`, it fetches and verifies the same remote
snapshot again.

If anything changes unexpectedly:

```text
STOP WRITE
do not overwrite Claude-owned files
do not force-push
do not auto-retry the same handoff_id
```

If the change occurs between the response and reviewer-state writes, the local
response may remain as an uncommitted audit artifact, but reviewer state is not
advanced.

## 9. Reviewer sequence

Local Codex:

```text
1. use the GitHub skill/connector to orient to smhe00/RL_Stock
2. read AGENTS.md and docs/agent_protocol/*
3. inspect origin/main CLAUDE_STATUS and matching packet
4. inspect exact commit/diff/source/tests/results
5. preserve canonical constraints and STOP gates
6. do not run a new financial backtest or experiment
7. return a schema-valid terminal review result
```

The watcher (numbering continues independently):

```text
7. apply the first pre-write sync guard
8. write reviewer_responses/<handoff_id>_REVIEWER_RESPONSE.md
9. apply the second pre-write sync guard
10. write CHATGPT_REVIEW.yaml
11. stage exactly those two reviewer-owned files
12. commit them as a gate checkpoint
13. fetch/check once more and push without force
```

If `publish_checkpoint = false`, steps 11–13 are manual. No automated review may
authorize a new research branch unless the user explicitly authorized that exact
branch; default `authorized_next` is empty.

## 10. Handoff identity and de-duplication

Every request/review pair has a unique `handoff_id`. A handoff is claimed before
Codex starts and is processed at most once automatically, including after watcher
restart.

`FAILED` and `STOP WRITE` do not loop. Normally Claude issues a new handoff ID
after changing the handoff. An operator may explicitly retry only after inspecting
the failure:

```text
scripts/start_local_reviewer.ps1 -RetryHandoff <ID> -Once
```

Never consume a reviewer response for a different handoff ID.

## 11. Git conflict and checkpoint rules

- Normal synchronization uses `git fetch` and `git pull --ff-only` or
  `git merge --ff-only origin/main` on a clean `main`.
- Never force-push, rebase automatically, discard work, or auto-resolve a
  divergence.
- Reviewer checkpoints contain only the response and reviewer-state files.
- A push rejection is a failure signal, not permission to retry more strongly.
- GitHub carries gate/checkpoint handoffs; it is not a high-frequency progress
  log.

## 12. Gate and research safety

- Passing tests does not authorize the next gate.
- Do not automatically relax research constraints or select a post-result branch.
- Do not start Claude, a trading prototype, a new financial backtest, paper/live
  trading, or QMT activity.
- Preserve MaxDiv `120/0.5`, M2 canonical state, the unresolved `03110.HK` STOP,
  closed PPO/SAC/TD3, and `authorized_next: []` unless the user explicitly changes
  them.

## 13. Logging

Logs are local, rotating, and ignored:

```text
runtime/local_reviewer/logs/local_reviewer.log
```

They contain only timestamps, operational event names, sanitized handoff IDs,
states, and exit/result codes. They must not contain prompts, packet contents,
model output, positions, account identifiers, orders, credentials, or
market/account data.

## END
