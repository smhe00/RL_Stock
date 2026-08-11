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

The root must be configurable in the standalone package.

## Markers and ownership

| Marker | Owner | Meaning |
|---|---|---|
| `claude_work_complete.json` | Agent | Work, packet/status, commit/push and remote confirmation are complete; request Web review. |
| `trigger_fetch_sent.json` | Bridge | Exactly one browser-generated `fetch <handoff_id>` submission was positively confirmed. |
| `chatgpt_fetch_ack.json` | Web ChatGPT | Matching automated fetch was received; written before substantive review. |
| `chatgpt_review_published.json` | Web ChatGPT | Review artifacts/state are durable; this is Web reviewer final marker. |
| `claude_review_ack.json` | Agent | Matching Web review was consumed. |

All markers are append-only and immutable.

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

Filename/existence is authoritative for protocol state. The `event` field may use the filename-style value or a recognized semantic alias for backward compatibility.

## Agent finalization invariant

Every fresh handoff that requests Web review must finish in this exact order:

```text
1. work + review packet/status complete
2. commit + push
3. confirm remote state
4. publish claude_work_complete.json as the LAST agent push
```

A handoff already manually surfaced and reviewed must not receive a late doorbell.

## Bridge state machine

For each handoff with `claude_work_complete.json` on the remote:

```text
chatgpt_review_published exists -> DONE
chatgpt_fetch_ack exists        -> WAIT_FOR_REVIEW
trigger_fetch_sent exists       -> WAIT_FOR_FETCH_ACK
otherwise                       -> SEND_FETCH exactly once
```

The decision is marker-only. The bridge must not infer readiness from project status files.

## Browser rules

- Dedicated Chrome/Chromium profile only.
- Localhost CDP endpoint only.
- Exact configured ChatGPT conversation must already be open.
- Non-owning attachment: no browser/page lifecycle management.
- No `goto`, `new_page`, page/context/browser close, or browser self-repair.
- Fail closed on missing/ambiguous target, login/challenge/CAPTCHA, missing/ambiguous composer, or uncertain submission.
- Composer lookup must prefer a visible semantic editable target and exclude hidden fallback controls.
- Do not scrape/read assistant output to determine success or review completion.
- Positive send confirmation must come from local input/submit state while the target URL remains valid.

## Retry and race rules

- No automatic browser resend after a failed or uncertain attempt.
- A successful browser submission must be durably deduplicated locally before Git marker publication can race.
- If Web ACK lands before `trigger_fetch_sent.json`, reconcile the missing bridge marker only; never resend the browser message.
- Expected append-only same-handoff concurrency may be reconciled/retried safely without force push.
- Unexpected or conflicting remote changes fail closed.

## Web reviewer rules

On receipt of a fresh automated `fetch <handoff_id>`:

1. verify the matching remote handoff/doorbell;
2. immediately publish `chatgpt_fetch_ack.json` before substantive review;
3. perform the project's own review protocol independently;
4. publish review artifacts/state;
5. publish `chatgpt_review_published.json` last.

## Non-goals

Protocol V1 does not launch or restart the local agent process. Reverse Web-to-agent process wake is a separate future component.
