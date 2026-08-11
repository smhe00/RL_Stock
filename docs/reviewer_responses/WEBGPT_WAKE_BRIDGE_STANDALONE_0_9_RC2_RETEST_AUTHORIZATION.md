# WebGPT Wake Bridge Standalone 0.9.0rc2 — Retest Authorization

Decision: `STANDALONE_0_9_RC2_ROUTING_CORRECTION_READY_FOR_INDEPENDENT_RETEST`

Candidate commit: `ca46798886ef61a16e8c96b19a7d154befefed14`

## rc1 defect accepted

The rc1 validator correctly found that a standalone wake containing only `fetch <handoff_id>` lacked repository identity, and that a local-only consumer remote could not receive Web-owned ACK/review markers.

## rc2 correction implemented by Web ChatGPT

The standalone candidate now:

- adds `[review].repository = "owner/repo"` to reusable local config;
- emits `fetch repo=<owner/repo> handoff=<handoff_id>`;
- validates the repository locator syntax;
- resolves the configured Git remote and requires it to be the same `github.com/owner/repo` before any browser interaction;
- rejects local-only/non-GitHub or mismatched remotes before browser sender construction;
- preserves all existing marker ownership, crash-safe dedup, non-owning CDP, no-output-scraping, append-only Git, and no-auto-resend invariants;
- bumps only the standalone candidate to `0.9.0rc2`;
- leaves embedded accepted V1 unchanged.

Static/code review is complete. This authorization deliberately does **not** claim the rc2 pytest suite or real routed E2E has passed.

## Authorized next

Claude is authorized only for `WEBGPT_WAKE_BRIDGE_STANDALONE_FINAL_VALIDATION_RC2_001` as independent validator.

Follow `tools/webgpt_wake_bridge/docs/FINAL_CLAUDE_TEST_PLAN.md` exactly.

For the fresh E2E, Claude may create one disposable **private GitHub repository** under the authenticated user account solely for this infrastructure validation. Keep it available until Web ChatGPT has completed ACK/review; do not delete it during the smoke.

Claude must not modify standalone implementation code. On any defect, report `REVISIONS_REQUIRED` and stop. On success, report `ACCEPT_1_0_0` but do not self-promote version or migrate RL_Stock.

No financial/research/trading work is authorized.
