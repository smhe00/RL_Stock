# WebGPT Wake Bridge

Standalone, project-agnostic delivery package extracted from the accepted RL_Stock Web Fetch Bridge V1.

## Status

- Package status: **STAGING / EXTRACTION IN PROGRESS**
- Source implementation: accepted RL_Stock Web Fetch Bridge V1
- Target release: `1.0.0`
- Compatibility target: `web_fetch_bridge_v1`
- Scope: local infrastructure only; no research/trading/business logic

## Goal

Provide a reusable local bridge that lets a local agent (initially Claude Code) wake a dedicated Web ChatGPT reviewer conversation after publishing a durable Git handoff doorbell.

The reusable package MUST remain independent from project-specific state machines. It must not understand or parse domain concepts such as research gates, trading states, backtests, RL models, or project-specific READY/BLOCKED semantics.

## Stable protocol contract

Project repositories expose only append-only markers under a configurable marker root, defaulting to:

```text
docs/web_bridge/<handoff_id>/
```

Marker sequence:

```text
claude_work_complete.json
    -> trigger_fetch_sent.json
    -> chatgpt_fetch_ack.json
    -> chatgpt_review_published.json
    -> claude_review_ack.json
```

The bridge itself is authoritative only for `trigger_fetch_sent.json`. Other markers are actor-owned and observed read-only.

## Non-negotiable invariants inherited from accepted V1

- Git remote is the durable source of truth.
- Trigger decisions are marker-only and project-state-agnostic.
- `claude_work_complete.json` is the review-request doorbell and must be the final Claude push for a fresh handoff.
- Exactly one automatic browser submission per handoff attempt.
- No automatic resend after a sender failure or uncertain submission.
- Browser operation is non-owning: no `goto`, `new_page`, page/context close, or browser close.
- The exact dedicated ChatGPT conversation must already be open.
- Composer targeting is semantic + visibility-aware; hidden fallback textarea is excluded.
- Submission success is confirmed from local composer state only; assistant output is never scraped.
- ACK/trigger marker races are reconciled marker-only; browser resend is forbidden when receipt is already proven.
- Marker writes are append-only and fail closed on ambiguity/conflict.
- No credentials, cookies, auth material, or conversation URL are committed.

## Target package layout

```text
tools/webgpt_wake_bridge/
├─ README.md
├─ pyproject.toml
├─ config/
│  └─ bridge.example.toml
├─ docs/
│  ├─ PROTOCOL.md
│  ├─ ACCEPTANCE.md
│  └─ MIGRATION_PLAN.md
├─ src/
│  └─ webgpt_wake_bridge/
│     └─ __init__.py
└─ tests/
```

## Extraction policy

1. Do **not** modify or delete the accepted RL_Stock V1 while extraction is in progress.
2. Copy/refactor behavior into this subtree with no RL_Stock business dependencies.
3. Preserve protocol compatibility first; cosmetic renaming is secondary.
4. Reach unit-test parity with the accepted V1 before switching any consumer.
5. Run a fresh end-to-end smoke in a blank/demo repository before declaring standalone `1.0.0`.
6. Only after standalone acceptance may RL_Stock switch from embedded implementation to this package.

## Intended reuse model

Install the bridge once on a workstation; each project supplies only:

- repository root / Git remote / branch,
- marker root,
- ignored local browser config,
- a short agent finalization instruction.

Browser/CDP fixes should then be upgraded once in the shared package rather than copied into every project.
