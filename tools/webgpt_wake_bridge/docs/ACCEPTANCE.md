# Standalone Acceptance Contract

The standalone package may be labeled `1.0.0 / E2E VERIFIED` only after all items below pass without modifying the accepted embedded RL_Stock V1.

## A. Project-independence

- No import from RL_Stock strategy/research modules.
- No parsing of project-specific reviewer/agent state.
- No domain vocabulary required for operation.
- Repository root, branch, remote and marker root are configurable.
- `webgpt-bridge init` can bootstrap a new consumer without changing consumer project files or Git state.
- Local config/runtime can live outside the consumer repository by default.

## B. Protocol compatibility

- Existing `web_fetch_bridge_v1` marker files remain readable.
- Marker ownership and append-only behavior are preserved.
- Filename-style and accepted semantic event aliases are supported only when the normalized event matches the marker filename.
- Existing projects can adopt the package without rewriting historical markers.

## C. Browser safety

- Dedicated exact target conversation required.
- CDP endpoint must be exact loopback `http://127.0.0.1:<port>`.
- Non-owning CDP lifecycle.
- No navigation, page creation/close, context close, or browser close.
- Hidden fallback textarea excluded.
- Semantic composer selector itself must resolve uniquely.
- Submission is positively confirmed from composer/input state without reading assistant output.
- Login/challenge detection uses structural DOM metadata, not visible conversation text.
- Sender failure or uncertain submission is terminal for that attempt; no automatic resend.

## D. Crash-safe exactly-once behavior

- Durable local `attempt_started` state is written before browser interaction.
- Restart after an `attempt_started` crash cannot automatically touch the browser again for that handoff.
- Browser-positive send is promoted to durable `fetch_sent` before Git trigger publication.
- If a Web ACK proves an uncertain/crashed attempt arrived, only the missing trigger marker may be reconciled; no second browser action.
- Explicit operator retry is the only way to clear an uncertain/failed attempt.

## E. Git transport safety

- Remote is source of truth.
- Bridge-owned marker publication is append-only.
- Isolated bridge worktree must not reset/repair the consumer worktree.
- No force push.
- Expected append-only race can reconcile safely.
- Unexpected/conflicting remote change fails closed.
- Git command/ref failures are not silently interpreted as marker absence.
- ACK-before-trigger race is repaired marker-only, never by browser resend.
- A late trigger is refused once `chatgpt_review_published.json` already exists.

## F. Agent finalization

- Reusable finalization command/helper accepts explicit handoff ID and code commit.
- `code_commit` resolves to a real commit already contained in the configured remote branch.
- Timezone-aware timestamp.
- Duplicate doorbell fails closed.
- Remote state is confirmed before doorbell creation.
- Doorbell is published as the final review-request push.

## G. Test coverage

Standalone tests must cover at minimum:

- marker schema/ownership/cycle dependencies and event-file identity;
- timestamp validation;
- project/config path hardening;
- bootstrap `init` round-trip;
- crash-safe attempt persistence;
- sender fail-closed deduplication;
- ACK-before-trigger / uncertain-attempt marker-only reconciliation;
- semantic composer selection and unique locator requirement;
- non-owning CDP lifecycle;
- submission confirmation;
- Git marker absence vs Git failure distinction;
- mandatory doorbell finalization and remote code-commit durability;
- package version consistency and project-independence contract.

## H. Blank-repository E2E

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

After success, restarting/scanning the standalone daemon must not submit the same handoff again.

## I. Release evidence

Before `1.0.0`, retain:

- exact package commit tested;
- exact install/test commands and pytest count;
- blank demo repo HEAD;
- E2E handoff ID;
- marker sequence/commit evidence;
- proof no user-typed `fetch` was used;
- platform/Python/Chrome/Playwright versions;
- warnings/defects, if any;
- accepted limitation that reverse Web-to-agent process wake is out of scope.
