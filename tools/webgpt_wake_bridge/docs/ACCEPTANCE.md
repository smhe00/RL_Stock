# Standalone Acceptance Contract

The standalone package may be labeled `1.0.0 / E2E VERIFIED` only after all items below pass without modifying the accepted embedded RL_Stock V1.

## A. Project-independence

- No import from RL_Stock strategy/research modules.
- No parsing of project-specific reviewer/agent state.
- No domain vocabulary required for operation.
- Repository root, branch, remote and marker root are configurable.

## B. Protocol compatibility

- Existing `web_fetch_bridge_v1` marker files remain readable.
- Marker ownership and append-only behavior preserved.
- Filename-style and accepted semantic event aliases supported.
- Existing projects can adopt the package without rewriting historical markers.

## C. Browser safety

- Dedicated exact target conversation required.
- Non-owning CDP lifecycle.
- No navigation, page creation/close, context close, or browser close.
- Hidden fallback textarea excluded.
- Ambiguous composer fails closed.
- Submission is positively confirmed without reading assistant output.
- Sender failure is terminal for that attempt; no automatic resend.

## D. Git transport safety

- Remote is source of truth.
- Bridge-owned marker publication is append-only.
- No force push.
- Expected append-only race can reconcile safely.
- Unexpected/conflicting remote change fails closed.
- ACK-before-trigger race is repaired marker-only, never by browser resend.

## E. Agent finalization

- Reusable finalization command/helper accepts explicit handoff id and code commit.
- Timezone-aware timestamp.
- Duplicate doorbell fails closed.
- Remote state is confirmed before doorbell creation.
- Doorbell is published as final review-request push.

## F. Test parity

At minimum, port the accepted embedded V1 coverage for:

- marker schema/ownership/order;
- timestamp validation;
- sender fail-closed deduplication;
- semantic composer selection;
- non-owning CDP lifecycle;
- submission confirmation;
- Git race reconciliation;
- mandatory doorbell finalization.

## G. Blank-repository E2E

A clean demo repository, with no RL_Stock files or states, must prove:

```text
agent finalization
  -> claude_work_complete LAST on remote
  -> standalone daemon discovers marker
  -> exactly one browser-generated fetch reaches Web ChatGPT
  -> chatgpt_fetch_ack
  -> reviewer publishes review_published
  -> agent can consume and acknowledge
```

No user-typed `fetch` is permitted during this acceptance smoke.

## H. Release evidence

Before `1.0.0`, retain:

- exact package commit;
- test command/results;
- E2E handoff id;
- marker sequence evidence;
- platform/Chrome/Playwright versions;
- accepted limitations, especially that reverse Web-to-agent process wake is out of scope.
