# Reviewer Response — WEBGPT_WAKE_BRIDGE_STANDALONE_0_9_RC1_REVISIONS_REQUIRED_001_001

```yaml
protocol_version: 3
actor: web_chatgpt_reviewer
handoff_id: WEBGPT_WAKE_BRIDGE_STANDALONE_0_9_RC1_REVISIONS_REQUIRED_001_001
state: REVISIONS_REQUIRED
decision: STANDALONE_0_9_RC1_VALIDATION_ACCEPTED_REPOSITORY_ROUTING_CORRECTION_REQUIRED
reviewed_remote_head: ef6bd008dacb0a41bd3f9970291491228c2caf38
code_commit: 2844ddd4750265321136b866d2ecb973d3eb9011
report: tools/webgpt_wake_bridge/docs/validation_reports/VALIDATION_REPORT_0_9_0RC1.md
scope: LOCAL_PROTOCOL_INFRASTRUCTURE
```

## Review

The independent validation result is accepted as accurate and useful.

Verified from origin/main:

- candidate under test remained `2844ddd4750265321136b866d2ecb973d3eb9011` / `0.9.0rc1`;
- after the freeze, Claude changed only validation evidence/state and return-handoff markers, not standalone implementation code;
- the standalone suite reported `38 passed, 0 failed` in a fresh Python 3.12.10 environment;
- `init`, `check`, >=30 s non-owning `noop`, `finalize`, marker-only discovery, exactly-one browser submit, trigger publication, duplicate no-resend, duplicate-finalize fail-closed, no-force-push, and target preservation all passed;
- the blank consumer had no RL_Stock research/reviewer state;
- the user did not manually type the blank-demo fetch;
- the blank-demo browser fetch reached Web ChatGPT, but the wake payload contained only `fetch <handoff_id>` and therefore did not identify the consumer repository;
- for a local-only bare consumer remote, Web ChatGPT also had no remotely accessible repository in which to verify the doorbell or publish ACK/review markers.

The root cause is therefore a real standalone routing defect: single-project V1 relied on implicit repository context, while the reusable package removed that implicit context without adding an explicit Web-review repository locator.

This is not a regression in CDP/composer/daemon/finalization behavior. Those parts passed the independent smoke.

## Required correction direction

The next standalone candidate must make the Web-review route explicit and fail closed when it is not Web-accessible.

Minimum requirements for the correction:

- define a stable, validated Web-review repository locator for each consumer project;
- include sufficient locator information in the browser wake payload for Web ChatGPT to resolve the correct repository, branch and marker root without relying on conversation memory;
- do not leak local filesystem paths, credentials, cookies, tokens, or arbitrary remote URLs into the wake payload;
- preserve compatibility with embedded V1 single-project historical markers; do not rewrite old marker history;
- keep marker-only daemon semantics, exactly-once browser behavior, crash-safe dedup, non-owning CDP, no output scraping, no automatic resend and append-only Git publication;
- distinguish full Web E2E support from local-only Git transport tests: a consumer repository used for full Web review must be remotely accessible to the Web reviewer, or a separately designed Web-accessible hub/mirror transport must be used;
- do not pretend a local bare repository can receive Web-owned ACK/review markers directly;
- update `init`, config validation, protocol docs, acceptance plan and tests so repository routing is mechanically specified;
- add tests for locator validation, wake-message formatting, project ambiguity elimination, and fail-closed behavior when no Web-accessible locator is configured;
- produce a new release candidate (not `1.0.0`) and repeat independent blank-repository E2E using a Web-accessible disposable GitHub repository.

## Claude authorization

```yaml
authorized_next: []
```

Claude's independent validation assignment is complete. Claude must not modify the standalone implementation in response to this review. Web ChatGPT retains implementation ownership for the correction under the user's standing instruction that Claude participates only in final testing.

## Still forbidden

- standalone implementation fixes by Claude during this validation closeout;
- package promotion to `1.0.0` before a successful routed blank-repository E2E;
- RL_Stock migration to the standalone package;
- manual user `fetch` during the next blank E2E;
- browser self-repair/navigation/page/context/browser close;
- automatic browser resend;
- ChatGPT output scraping;
- CAPTCHA/protection bypass;
- unrelated financial research, backtests, strategy/canonical changes, QMT, account/order, paper/live, or RL work.
