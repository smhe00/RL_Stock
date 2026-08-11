# WebGPT Wake Bridge Protocol V1

Protocol identifier: `web_fetch_bridge_v1`

## Purpose

Wake a dedicated Web ChatGPT reviewer conversation from a project without coupling the bridge to that project's business/research state machine.

## Actors

- **Agent**: owns work-complete and review-consumed markers.
- **Bridge**: marker watcher + Git transport + browser sender; owns only `trigger_fetch_sent.json`.
- **Web ChatGPT**: reviewer; owns fetch-ack and review-published markers.
- **GitHub consumer repository**: durable source of truth and audit bus for full Web E2E.

## Marker root

Default:

```text
docs/web_bridge/<handoff_id>/
```

The root is configurable but remains inside the consumer repository.

## Marker cycle

```text
claude_work_complete.json
  -> trigger_fetch_sent.json
  -> chatgpt_fetch_ack.json
  -> chatgpt_review_published.json
  -> claude_review_ack.json
```

All protocol markers are append-only and immutable. Filename/existence is authoritative; semantic `event` aliases remain backward-compatible but must normalize to the marker filename.

## Routed wake payload

The accepted single-project embedded V1 historically used:

```text
fetch <handoff_id>
```

Standalone multi-project operation must not depend on implicit repository context. rc2 therefore sends:

```text
fetch repo=<github_owner/github_repo> handoff=<handoff_id>
```

Rules:

- `repo` is a strict `owner/repo` locator, not a URL.
- `[review].repository` is required for live `once` / `daemon` commands.
- before browser interaction the configured project Git remote must resolve to the same `github.com/owner/repo`;
- a local-only/non-GitHub remote fails closed before browser interaction;
- Web ChatGPT uses `repo` to resolve the correct GitHub repository, verify the matching doorbell, and immediately publish ACK there.

Historical `fetch <handoff_id>` messages/markers remain valid for already-known single-project integrations; rc2 does not rewrite history.

## Agent finalization invariant

Every fresh review handoff ends in this order:

```text
1. work + packet/status complete
2. commit + push
3. confirm remote state and clean worktree
4. create claude_work_complete.json
5. commit/push that marker as the LAST agent push
```

The finalizer requires a real code commit already contained in the configured remote branch and refuses duplicate doorbells.

## Bridge state machine

For each remote handoff:

```text
chatgpt_review_published exists -> DONE
chatgpt_fetch_ack exists        -> WAIT / marker-only reconcile if trigger missing
trigger_fetch_sent exists       -> WAIT_FOR_FETCH_ACK
claude_work_complete only       -> candidate for one browser attempt
```

The decision is marker-only; project YAML/status is irrelevant.

## Crash-safe local state

Before browser interaction:

```text
persist attempt_started + immutable trigger payload
-> browser attempt
-> positive submit confirmation
-> persist fetch_sent
-> publish trigger_fetch_sent.json
```

A crash/uncertain attempt is never automatically resent. If a matching Web ACK later proves receipt, only the missing trigger marker may be reconciled.

## Browser rules

- exact localhost CDP endpoint `http://127.0.0.1:<port>`;
- exact already-open `https://chatgpt.com/c/...` conversation;
- non-owning attachment: no navigation, page creation, page/context/browser close;
- fail closed on login/challenge, missing/ambiguous composer, uncertain submission;
- hidden fallback controls excluded;
- no assistant-output scraping;
- success confirmation uses only composer/input state and unchanged target URL.

## Git transport rules

- configured remote branch is source of truth;
- live Web review additionally requires that remote to be a Web-accessible GitHub repository matching `[review].repository`;
- bridge marker publication uses an isolated detached worktree;
- no force push;
- Git failure is never treated as marker absence;
- stale trigger publication after `chatgpt_review_published.json` is refused.

## Web reviewer rules

On a fresh routed wake:

```text
fetch repo=<owner/repo> handoff=<id>
```

Web ChatGPT must:

1. resolve exactly `repo` through GitHub;
2. verify `<marker_root>/<id>/claude_work_complete.json` and, when already durable, `trigger_fetch_sent.json`;
3. immediately publish `chatgpt_fetch_ack.json` before substantive review;
4. perform the project's own review protocol;
5. publish review artifacts/state;
6. publish `chatgpt_review_published.json` last.

If `repo` is unavailable/ambiguous or the handoff does not exist there, fail closed and do not ACK another repository.

## Local-only repositories

rc2 intentionally does not implement a wake hub/mirror. A local-only or air-gapped consumer may use the standalone code for local mechanics, but it cannot complete remote Web-owned ACK/review markers without a separately designed Web-accessible hub/mirror.

## Non-goal

Protocol V1 does not launch/restart the local agent process. Reverse Web-to-agent process wake remains separate.
