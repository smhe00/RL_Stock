# WebGPT Wake Bridge Standalone 0.9.0rc1 — Final Validation Authorization

## Decision

`STANDALONE_WEBGPT_WAKE_BRIDGE_0_9_RC1_READY_FOR_INDEPENDENT_VALIDATION`

The user explicitly requested that Web ChatGPT implement the standalone reusable package and that Claude participate only at the final testing stage.

The standalone candidate is under:

```text
tools/webgpt_wake_bridge/
```

Candidate package version:

```text
0.9.0rc1
```

Protocol compatibility:

```text
web_fetch_bridge_v1
```

The accepted embedded RL_Stock Web Fetch Bridge V1 remains the production/reference rollback path and must not be modified by this validation.

## Evidence before validation

- Standalone implementation, tests and documentation have been isolated under `tools/webgpt_wake_bridge/`.
- Diff from embedded-V1 closeout commit `db4fe6191abaa578040431cac1a6069a9009671c` through the pre-validation candidate shows standalone extraction changes only under that subtree.
- Candidate version is consistent between `pyproject.toml` and package `__init__.py`.
- Static design review has addressed project independence, marker identity/ownership, exact-loopback CDP validation, exact target conversation, non-owning browser behavior, structural login/challenge probes, semantic composer selection, crash-safe pre-browser attempt persistence, marker-only ACK reconciliation, Git failure-vs-absence distinction, append-only Git transport, remote-contained code commit validation, clean-worktree finalization and reusable external runtime/bootstrap.
- This authorization does **not** claim that the standalone pytest suite or real Windows/Chrome/CDP blank-repository E2E has already passed. Those are the purpose of the authorized validation.

## Authorized next — exactly one task

```yaml
task: WEBGPT_WAKE_BRIDGE_STANDALONE_FINAL_VALIDATION_001
scope: LOCAL_PROTOCOL_INFRASTRUCTURE_VALIDATION_ONLY
implementation_changes_allowed: false
```

Claude must follow exactly:

```text
tools/webgpt_wake_bridge/docs/FINAL_CLAUDE_TEST_PLAN.md
```

### Required validation behavior

1. Fetch `origin/main` and begin from a clean synchronized repository.
2. Record the exact candidate HEAD/package version under test.
3. Act as an independent validator, not as package developer.
4. Create a fresh Python environment and install `tools/webgpt_wake_bridge` with test extras.
5. Require `webgpt-bridge --version` to report `0.9.0rc1`.
6. Run the complete standalone pytest suite and record exact pass/fail count.
7. Independently inspect static safety/project-independence constraints.
8. Create a clean disposable consumer repository with no RL_Stock state/protocol files except the standalone marker directory created for the smoke.
9. Bootstrap it with standalone `webgpt-bridge init`; do not copy RL_Stock config/state into the demo.
10. Use an ignored/local config and existing dedicated Chrome reviewer conversation.
11. Run standalone `check` and >=30-second `noop`; any target/session mutation is a failure.
12. Start the **standalone** daemon and create one fresh unique blank-demo handoff.
13. Use standalone `finalize` with a real remote-contained demo code commit; publish its `claude_work_complete.json` as the final demo-agent push.
14. The user must not type `fetch`; the standalone daemon must deliver exactly one browser-generated `fetch <fresh_id>` to Web ChatGPT.
15. Verify remote trigger marker, Web fetch ACK, Web review-published marker, duplicate/no-resend behavior and finalization duplicate fail-closed behavior.
16. Do not intentionally force a second browser send to manufacture a race.
17. Write one validation report under `tools/webgpt_wake_bridge/docs/validation_reports/` containing exact evidence and exactly one recommendation: `ACCEPT_1_0_0` or `REVISIONS_REQUIRED`.
18. If any defect occurs, **do not fix package code** in this validation task. Record the smallest reproducible defect, return `REVISIONS_REQUIRED`, and stop.
19. If all validation passes, **do not bump to 1.0.0** and do not migrate RL_Stock. Return `ACCEPT_1_0_0`; Web ChatGPT will review evidence before promotion.
20. After the validation report/status are committed and pushed, use the already accepted embedded V1 handoff/doorbell mechanism only to automatically wake Web ChatGPT with the validation result.

## Forbidden in this validation

- Editing standalone implementation source to make tests pass.
- Editing embedded `scripts/web_fetch_bridge.py` or `scripts/finalize_handoff.py`.
- Migrating RL_Stock to the standalone package.
- Promoting the package version to 1.0.0.
- Manual user-typed `fetch` during the blank-repo E2E.
- Automatic browser resend after failure/uncertainty.
- Browser navigation/self-repair/page creation/page close/context close/browser close.
- ChatGPT assistant-output scraping.
- CAPTCHA/platform-protection bypass.
- Automatic Claude process launch/restart work.
- Financial research, backtests, data refresh, strategy/canonical-result changes, QMT, accounts, orders, paper/live trading, PPO/SAC/TD3/RL retraining.

## Success definition

`ACCEPT_1_0_0` is justified only if a fresh blank consumer repository proves, without manual `fetch`:

```text
standalone finalize doorbell LAST
-> standalone marker-only daemon
-> exactly one CDP browser fetch
-> Web ChatGPT immediate ACK
-> Web review_published
-> no duplicate send on restart/scan
```

Until that independent evidence exists, the candidate remains `0.9.0rc1`.
