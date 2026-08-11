# Extraction / Migration Plan

## Phase 0 — Freeze accepted source

The embedded RL_Stock Web Fetch Bridge V1 remains the behavioral reference until standalone acceptance. Do not refactor it in place during extraction.

Reference behavior currently lives primarily in:

- `scripts/web_fetch_bridge.py`
- `scripts/finalize_handoff.py`
- `config/web_fetch_bridge.example.toml`
- `docs/web_bridge/README.md`
- `docs/HANDOFF_PROTOCOL.md`
- `tests/test_web_fetch_bridge.py`
- `tests/test_finalize_handoff.py`

## Phase 1 — Structural extraction

Split the accepted behavior into standalone modules:

```text
markers.py        marker schema, ownership, validation
config.py         standalone TOML loading
browser.py        non-owning CDP sender + composer selection
transport_git.py  remote marker discovery/publication/reconciliation
bridge.py         marker-only state machine + daemon
finalize.py       agent-side doorbell finalization
cli.py            init/check/daemon/finalize/reconcile commands
```

No behavior changes are allowed in this phase unless a copied test first demonstrates the need.

## Phase 2 — Test parity

Port the accepted V1 tests into `tools/webgpt_wake_bridge/tests/` and make them independent from the RL_Stock repository layout.

Acceptance target: all standalone tests pass while the original embedded tests continue to pass unchanged.

## Phase 3 — Usability layer

Add stable commands:

```text
webgpt-bridge init
webgpt-bridge check
webgpt-bridge daemon
webgpt-bridge finalize --handoff ... --code-commit ...
webgpt-bridge reconcile --handoff ...
```

`init` may create project-local templates, but must never write secrets or a ChatGPT conversation URL into tracked files.

## Phase 4 — Blank demo repository

Create a clean demo consumer containing no RL_Stock state. Validate the full marker/browser/reviewer round trip using the standalone package.

## Phase 5 — Freeze 1.0.0

Only after blank-repo E2E acceptance:

- set version `1.0.0`;
- mark `E2E VERIFIED` in README;
- record acceptance evidence;
- treat the standalone package as the canonical bridge implementation.

## Phase 6 — Consumer migration

Migrate RL_Stock as the first consumer. Replace embedded bridge execution with the installed/package command while preserving the existing marker protocol and historical evidence.

Do not delete the embedded reference implementation until the consumer migration has its own successful E2E smoke and rollback path.
