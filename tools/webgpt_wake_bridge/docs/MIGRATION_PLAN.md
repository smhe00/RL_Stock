# Extraction / Migration Plan

## Current status

```text
Phase 0  Freeze accepted embedded V1                    COMPLETE
Phase 1  Standalone structural extraction               COMPLETE
Phase 2  Standalone test suite / safety hardening        COMPLETE (fresh rc2 execution pending)
Phase 3  Reusable CLI/bootstrap usability layer          COMPLETE
Phase 4a rc1 blank local-repo validation                 COMPLETE -> REVISIONS_REQUIRED (routing gap)
Phase 4b rc2 routed blank GitHub E2E                     PENDING CLAUDE VALIDATION
Phase 5  Promote to 1.0.0 / E2E VERIFIED                 BLOCKED ON PHASE 4b
Phase 6  Migrate RL_Stock to standalone consumer         NOT STARTED
```

Current standalone candidate: `0.9.0rc2`.

## rc1 finding and rc2 correction

rc1 proved the standalone core but exposed that `fetch <handoff_id>` had no repository identity outside the single known RL_Stock project. A local bare consumer remote also could not receive Web-owned ACK/review markers.

rc2 corrects this without introducing a hub:

```text
fetch repo=<owner/repo> handoff=<handoff_id>
```

Before browser interaction, `once`/`daemon` require `[review].repository` and verify that the configured Git remote resolves to the same `github.com/owner/repo`. Local-only/non-GitHub remotes fail closed.

A future hub/mirror for local-only/air-gapped projects is separate scope.

## Standalone modules

```text
bootstrap.py      per-consumer local bootstrap
markers.py        marker schema/ownership
config.py         config/path/repository routing validation
browser.py        non-owning CDP sender + routed wake payload
transport_git.py  Git marker transport + GitHub remote identity guard
bridge.py         marker-only daemon + crash-safe dedup/reconciliation
finalize.py       doorbell finalization
cli.py            init/check/noop/once/daemon/finalize/retry/reconcile
```

## Phase 4b — routed blank GitHub demo

Claude remains test-only and follows `docs/FINAL_CLAUDE_TEST_PLAN.md`.

The new smoke must use a fresh Web-accessible disposable GitHub repository containing no RL_Stock state. It must prove Web ChatGPT can resolve the repo solely from the routed wake payload, write ACK/review markers there, and that the daemon does not resend.

Any defect => `REVISIONS_REQUIRED`, no validator code fixes.

## Phase 5 — 1.0.0

Only after accepted Phase 4b evidence:

- Web ChatGPT reviews evidence;
- version may be promoted from `0.9.0rc2` to `1.0.0`;
- README may be marked `E2E VERIFIED`;
- standalone becomes canonical reusable implementation.

## Phase 6 — first consumer migration

RL_Stock migrates only after standalone 1.0.0 acceptance. Preserve existing `web_fetch_bridge_v1` history and keep embedded V1 as rollback until migration has its own E2E smoke.
