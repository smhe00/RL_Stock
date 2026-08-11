# WebGPT Wake Bridge Protocol V1

Protocol identifier: `web_fetch_bridge_v1`

## Purpose

Wake a dedicated Web ChatGPT reviewer conversation from a local project without coupling the bridge to that project's business/research state machine.

## Actors

- **Agent**: initially Claude Code; owns work-complete and review-consumed markers.
- **Bridge**: local marker watcher + Git transport + browser sender; owns only the fetch-sent marker.
- **Web ChatGPT**: reviewer; owns fetch-ack and review-published markers.
- **Git remote**: durable source of truth and audit bus.

## Marker root

Default:

```text
docs/web_bridge/<handoff_id>/
```

The root is configurable but must remain a safe subdirectory of the consumer repository.

## Markers and ownership

| Marker | Owner | Meaning |
|---|---|---|
| `claude_work_complete.json` | Agent | Work, packet/status, commit/push and remote confirmation are complete; request Web review. |
| `trigger_fetch_sent.json` | Bridge | Browser receipt was positively established for `fetch <handoff_id>`. |
| `chatgpt_fetch_ack.json` | Web ChatGPT | Matching automated fetch was received; written before substantive review. |
| `chatgpt_review_published.json` | Web ChatGPT | Review artifacts/state are durable; this is Web reviewer final marker. |
| `claude_review_ack.json` | Agent | Matching Web review was consumed. |

One complete review cycle is:

```text
claude_work_complete.json
  -> trigger_fetch_sent.json
  -> chatgpt_fetch_ack.json
  -> chatgpt_review_published.json
  -> claude_review_ack.json
```

All protocol markers are append-only and immutable.

## Minimum marker schema

```json
{
  "protocol": "web_fetch_bridge_v1",
  "handoff_id": "EXAMPLE_001_001",
  "event": "claude_work_complete.json",
  "timestamp": "2026-08-11T09:18:39+00:00"
}
```

Optional actor-specific fields are allowed, e.g. `code_commit`, `review_commit`, `decision`, provided no credentials or secrets are included.

Filename/existence is authoritative for protocol state. The `event` field may use the filename-style value or a recognized semantic alias for backward compatibility, but the normalized event **must match the marker filename**.

## Agent finalization invariant

Every fresh handoff that requests Web review must finish in this exact order:

```text
1. work + review packet/status complete
2. commit + push
3. confirm remote state
4. publish claude_work_complete.json as the LAST agent push
```

The standalone finalizer requires an explicit handoff ID and code commit, verifies the commit resolves to a real commit already contained in the configured remote branch, and refuses duplicate doorbells.

A handoff already manually surfaced and reviewed must not receive a late doorbell.

## Remote bridge state machine

For each handoff with `claude_work_complete.json` on the remote:

```text
chatgpt_review_published exists -> DONE
chatgpt_fetch_ack exists        -> WAIT_FOR_REVIEW / reconcile marker only if needed
trigger_fetch_sent exists       -> WAIT_FOR_FETCH_ACK
otherwise                       -> candidate for one browser attempt
```

The decision is marker-only. The bridge must not infer readiness from project status files.

## Crash-safe local attempt state

Before the bridge touches the browser it must durably record a local, non-protocol `attempt_started` entry containing the handoff ID and the immutable trigger-marker payload.

Therefore:

```text
persist attempt_started
  -> browser attempt
  -> on positive send confirmation: persist fetch_sent
  -> publish trigger_fetch_sent.json
```

If the process dies after `attempt_started`, restart treats that handoff as already attempted/uncertain and **must not automatically submit it again**.

If Web ACK later proves the uncertain/crashed browser attempt actually arrived, the bridge may publish only the missing trigger marker using the durable local payload and promote the local state to sent. No browser interaction is allowed in that reconciliation path.

A definitive/uncertain sender failure is likewise terminal until explicit operator retry.

## Browser rules

- Dedicated Chrome/Chromium profile only.
- CDP endpoint must parse as exactly `http://127.0.0.1:<port>`.
- Exact configured `https://chatgpt.com/c/...` conversation must already be open.
- Non-owning attachment: no browser/page lifecycle management or navigation repair.
- Fail closed on missing/ambiguous target, structural login/challenge evidence, missing/ambiguous composer, or uncertain submission.
- Composer lookup must prefer a visible semantic editable target and exclude hidden fallback controls.
- The final locator itself must resolve uniquely.
- Do not scrape/read assistant output to determine success or review completion.
- Login/challenge detection uses structural DOM attributes, not visible conversation text.
- Positive send confirmation comes only from local composer/input state while the exact target URL remains unchanged.

## Retry and race rules

- No automatic browser resend after a failed, uncertain, or crash-interrupted attempt.
- Only explicit operator retry may clear a local uncertain/failed attempt.
- A successful browser submission is locally durable before Git marker publication can race.
- `chatgpt_fetch_ack.json` may transiently reach Git before `trigger_fetch_sent.json` because Web ACK is intentionally immediate. This transient is valid only when a real doorbell exists.
- If Web ACK lands first, reconcile the missing bridge marker only; never resend the browser message.
- Expected append-only concurrency may be retried/reconciled without force push.
- If `chatgpt_review_published.json` already exists, a late trigger publication is refused as stale/order-breaking.
- Unexpected or conflicting Git state fails closed.

## Git transport rules

- Remote branch is source of truth for discovery and protocol state.
- The bridge uses an isolated detached worktree for its own marker commit.
- Consumer worktree dirtiness must never be reset or repaired by the bridge.
- Marker publication is fast-forward only; force push is forbidden.
- A Git command failure must never be interpreted as "marker absent". Marker absence must be positively distinguished from transport/ref failure.

## Web reviewer rules

On receipt of a fresh automated `fetch <handoff_id>`:

1. verify the matching remote handoff/doorbell;
2. immediately publish `chatgpt_fetch_ack.json` before substantive review;
3. perform the project's own review protocol independently;
4. publish review artifacts/state;
5. publish `chatgpt_review_published.json` last.

## Local configuration rules

- Conversation URL and browser/session secrets never belong in Git markers.
- `webgpt-bridge init` defaults config and runtime to a user-local directory outside the consumer repository.
- Marker root remains inside the consumer repository because markers are the durable audit bus.
- Runtime/log/dedup/worktree state may live outside the consumer repository and should not be committed.

## Non-goals

Protocol V1 does not launch or restart the local agent process. Reverse Web-to-agent process wake is a separate future component.
