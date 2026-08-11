# Extraction / Migration Plan

## Current status

```text
Phase 0  Freeze accepted embedded V1                    COMPLETE
Phase 1  Standalone structural extraction               COMPLETE
Phase 2  Standalone test suite / safety hardening        COMPLETE (execution pending validator)
Phase 3  Reusable CLI/bootstrap usability layer          COMPLETE
Phase 4  Independent blank-repository Windows/CDP E2E    PENDING CLAUDE VALIDATION
Phase 5  Promote to 1.0.0 / E2E VERIFIED                 BLOCKED ON PHASE 4
Phase 6  Migrate RL_Stock to standalone consumer         NOT STARTED
```

The standalone candidate is `0.9.0rc1` until Phase 4 passes.

## Phase 0 — Freeze accepted source

The embedded RL_Stock Web Fetch Bridge V1 remains the accepted behavioral/rollback reference until standalone acceptance. It is not refactored in place during extraction.

Reference behavior lives primarily in:

- `scripts/web_fetch_bridge.py`
- `scripts/finalize_handoff.py`
- `config/web_fetch_bridge.example.toml`
- `docs/web_bridge/README.md`
- `docs/HANDOFF_PROTOCOL.md`
- `tests/test_web_fetch_bridge.py`
- `tests/test_finalize_handoff.py`

## Phase 1 — Structural extraction — COMPLETE

Accepted behavior has been split into standalone modules:

```text
bootstrap.py      clean per-consumer local bootstrap
markers.py        marker schema, ownership, validation
config.py         standalone TOML/config hardening
browser.py        non-owning CDP sender + composer selection
transport_git.py  remote marker discovery/publication
bridge.py         marker-only daemon + crash-safe dedup/reconciliation
finalize.py       agent-side doorbell finalization
cli.py            init/check/daemon/finalize/retry/reconcile commands
```

The implementation is project-state-agnostic and remains protocol-compatible with `web_fetch_bridge_v1`.

## Phase 2 — Test suite / hardening — IMPLEMENTED, EXECUTION PENDING

Standalone tests now cover protocol, browser, transport, finalization, bootstrap, CLI and package-independence contracts under `tools/webgpt_wake_bridge/tests/`.

The independent validator must execute the full suite from a fresh environment. Until that execution passes, this phase is not release evidence.

## Phase 3 — Reusable usability layer — COMPLETE

Stable candidate commands:

```text
webgpt-bridge init --repo <consumer>
webgpt-bridge check --config <local-config>
webgpt-bridge noop --config <local-config>
webgpt-bridge once --config <local-config>
webgpt-bridge daemon --config <local-config>
webgpt-bridge finalize --config <local-config> --handoff ... --code-commit ...
webgpt-bridge retry --config <local-config> --handoff ...
webgpt-bridge reconcile --config <local-config> --handoff ...
```

`init` defaults config/runtime outside the consumer repository and leaves the dedicated ChatGPT conversation URL blank for the operator to fill locally.

## Phase 4 — Blank demo repository — NEXT

Claude acts only as independent validator and follows:

```text
docs/FINAL_CLAUDE_TEST_PLAN.md
```

A clean demo consumer containing no RL_Stock state must prove the full standalone marker/browser/reviewer round trip without any user-typed `fetch`.

If any defect is found, Claude reports `REVISIONS_REQUIRED` and does not edit candidate code.

## Phase 5 — Freeze 1.0.0

Only after Phase 4 returns accepted evidence:

- Web ChatGPT reviews the validation packet;
- version may be promoted from `0.9.0rc1` to `1.0.0`;
- README may be marked `E2E VERIFIED`;
- exact test/E2E evidence is retained;
- standalone package becomes the canonical reusable implementation.

Claude must not self-promote the version during validation.

## Phase 6 — Consumer migration

RL_Stock becomes the first consumer only after standalone `1.0.0` acceptance. Replace embedded execution with the installed/package command while preserving the existing marker protocol and historical evidence.

Do not delete the embedded reference implementation until consumer migration has its own successful E2E smoke and rollback path.
