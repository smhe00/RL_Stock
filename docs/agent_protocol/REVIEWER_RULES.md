# Local Codex reviewer rules

## Trigger contract

The watcher may trigger one local Codex review only when the top-level Claude
state is one of:

```text
READY_FOR_REVIEW
BLOCKED
TEST_FAILED
```

`RUNNING`, `WAITING_FOR_REVIEW`, `REVIEW_COMPLETE`, and unknown states do not
trigger. A handoff ID is processed at most once automatically, including across
watcher restarts. A stopped or failed handoff requires a new handoff ID or an
explicit operator retry.

For `READY_FOR_REVIEW`, the packet named by `packet` must exist under
`docs/review_packets/`. `BLOCKED` and `TEST_FAILED` may be reviewed from the
status file when no packet is available.

## Evidence and decision contract

The reviewer must:

1. Use the GitHub skill/connector to orient to `smhe00/RL_Stock`, then read the
   current canonical-state document, handoff protocol, Claude status,
   referenced packet, exact commit/diff, and existing evidence.
2. Keep research results, execution-realism findings, and live authority
   separate.
3. Report one terminal reviewer state: `REVIEW_COMPLETE`,
   `REVISIONS_REQUIRED`, or `BLOCKED`.
4. Bind the response to the exact handoff, packet, code commit, and local HEAD.
5. Leave `authorized_next` empty unless the user explicitly authorized that
   exact next step. An automated review may not open a new research branch.
6. Preserve all frozen parameters and STOP gates unless the user explicitly
   changes them.

The reviewer must not run a new financial backtest or experiment, start Claude,
modify strategy/execution code, create a trading prototype, contact QMT, or
perform paper/live actions.

## Ownership contract

Claude writes only:

```text
docs/agent_state/CLAUDE_STATUS.yaml
docs/review_packets/**
```

The reviewer writes only:

```text
docs/reviewer_responses/**
docs/reviewer_state/CHATGPT_REVIEW.yaml
```

The Codex subprocess itself runs read-only. The watcher validates its structured
result and performs the two reviewer-owned writes atomically.

## STOP WRITE contract

After `git fetch origin main`, the watcher records:

- remote `origin/main` HEAD;
- the complete remote Claude-status digest;
- the remote referenced-packet digest or its absence;
- the pre-existing remote reviewer-state digest.

Immediately before writing the response, all four values must still match.
After writing the response, they are checked again before updating
`CHATGPT_REVIEW.yaml`.

If any value changes:

```text
STOP WRITE
do not overwrite Claude-owned files
do not update CHATGPT_REVIEW.yaml
do not automatically retry the same handoff
```

If the change happens before the first reviewer write, nothing is published. If
it happens between the two reviewer writes, the response file may remain as an
uncommitted audit artifact, but the machine-readable reviewer state is not
advanced.

## Git contract

The watcher fetches `origin/main` every 60 seconds. It may fast-forward a clean
local `main` and commit/push the two reviewer-owned outputs as the terminal gate
checkpoint. It never force-pushes, rebases, auto-merges divergent history, or
includes Claude-owned/source/result files in a reviewer checkpoint.

This is the GitHub skill's hybrid model: connector-first for remote repository
and handoff context; local `git` for continuous fetch and the exact
reviewer-owned checkpoint because those operations are not covered reliably by
the connector.

## Logging contract

Operational logs may contain only event name, timestamp, sanitized handoff ID,
Claude state, and exit/result code. Prompts, packet text, reviewer output,
positions, account identifiers, orders, credentials, and market/account data
must never be logged.
