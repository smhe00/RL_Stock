# READY_FOR_CLAUDE_VALIDATION

Status: **READY_FOR_CLAUDE_VALIDATION**

Candidate package: **WebGPT Wake Bridge `0.9.0rc1`**

Protocol: **`web_fetch_bridge_v1`**

Validation task: **`WEBGPT_WAKE_BRIDGE_STANDALONE_FINAL_VALIDATION_001`**

Authoritative validation plan:

```text
tools/webgpt_wake_bridge/docs/FINAL_CLAUDE_TEST_PLAN.md
```

Reviewer authorization:

```text
docs/reviewer_responses/WEBGPT_WAKE_BRIDGE_STANDALONE_0_9_RC1_VALIDATION_AUTHORIZATION.md
```

Pre-authorization standalone candidate baseline:

```text
0fb2a344626f099df4456949962302ec3a8cc65d
```

The commit containing this readiness file is the final repository HEAD Claude must initially fetch and record before validation. No standalone implementation changes are authorized after this readiness point unless the independent validator returns `REVISIONS_REQUIRED` and Web ChatGPT subsequently opens a separate correction task.

## Freeze assertions

- Standalone implementation lives under `tools/webgpt_wake_bridge/`.
- The accepted embedded RL_Stock Web Fetch Bridge V1 has not been modified by standalone extraction.
- Package and `pyproject.toml` both declare `0.9.0rc1`.
- Static/manual implementation review has no known open blocker.
- The standalone pytest suite has been authored but is **not claimed passed by Web ChatGPT**; Claude must execute it independently from a fresh environment.
- Real standalone Windows/Chrome/CDP blank-repository E2E has **not** yet been claimed; Claude must perform it.
- Claude is test-only: no candidate source fixes, no 1.0.0 bump, no RL_Stock migration.
- If any failure occurs, Claude writes evidence and returns `REVISIONS_REQUIRED` without modifying candidate code.
- If all required validation passes, Claude returns `ACCEPT_1_0_0`; Web ChatGPT separately reviews evidence before release promotion.

## Required final E2E proof

Without any user-typed `fetch`:

```text
blank consumer work committed/pushed
-> standalone finalize creates doorbell
-> doorbell pushed LAST
-> standalone marker-only daemon discovers it
-> exactly one browser-generated fetch reaches Web ChatGPT
-> Web ChatGPT immediate fetch ACK
-> Web ChatGPT review_published
-> later daemon scan/restart does not resend same handoff
```

The already accepted embedded V1 may be used only after validation evidence is committed, as the transport that wakes Web ChatGPT with Claude's final validation result.
