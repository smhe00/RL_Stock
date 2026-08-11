# Standalone Acceptance Contract

The standalone package may be labeled `1.0.0 / E2E VERIFIED` only after all items below pass without modifying the accepted embedded RL_Stock V1.

## A. Project-independence

- No import from RL_Stock strategy/research modules.
- No parsing of project-specific reviewer/agent state.
- Repository root, branch, remote, marker root and Web review repository locator are configurable.
- `webgpt-bridge init` can bootstrap a new consumer without modifying consumer project files or Git state.
- Local config/runtime can live outside the consumer repository.

## B. Protocol compatibility and routing

- Historical `web_fetch_bridge_v1` markers remain readable and are never rewritten.
- Marker ownership/append-only behavior is preserved.
- Standalone live wake uses `fetch repo=<owner/repo> handoff=<id>`.
- `[review].repository` is a strict GitHub `owner/repo` locator.
- Before browser interaction, the configured Git remote must resolve to the same `github.com/owner/repo`.
- Missing/mismatched/local-only remote must fail closed before browser interaction.
- Web reviewer must use the locator to resolve the exact repository before ACK.

## C. Browser safety

- Dedicated exact target conversation required.
- CDP endpoint exact loopback `http://127.0.0.1:<port>`.
- Non-owning CDP lifecycle: no navigation, page creation/close, context close, or browser close.
- Hidden fallback textarea excluded; semantic composer selector must resolve uniquely.
- Submission positively confirmed from local composer/input state only.
- No assistant-output scraping.
- Sender failure/uncertain submission is terminal until explicit retry.

## D. Crash-safe exactly-once behavior

- Durable local `attempt_started` state is written before browser interaction.
- Restart after an uncertain/crash-interrupted attempt cannot automatically touch the browser again.
- Positive send is promoted to `fetch_sent` before trigger publication races.
- ACK-proven uncertain receipt may reconcile only the missing trigger marker.

## E. Git transport safety

- Remote is source of truth.
- Bridge marker publication is append-only using isolated worktree.
- No force push.
- Git failure is not interpreted as marker absence.
- ACK-before-trigger race is marker-only reconciled.
- Late trigger is refused after `chatgpt_review_published.json`.

## F. Agent finalization

- Finalization accepts explicit handoff ID and code commit.
- Worktree must be clean.
- Code commit must be real and contained in the configured remote branch.
- Duplicate doorbell fails closed.
- Doorbell is the final review-requesting push.

## G. Test coverage

Standalone tests must cover at minimum:

- marker schema/ownership/event identity;
- timestamp validation;
- config/path hardening;
- `owner/repo` locator validation;
- GitHub remote locator parsing/mismatch rejection;
- routed wake payload formatting;
- bootstrap `init` round-trip;
- crash-safe attempt persistence;
- sender dedup/no auto-resend;
- ACK-before-trigger marker-only reconciliation;
- composer selection and non-owning CDP;
- Git failure vs marker absence;
- finalization durability;
- package version/project-independence contract.

## H. Fresh Web-accessible blank GitHub repository E2E

A clean disposable GitHub repository containing no RL_Stock project/reviewer state must prove:

```text
blank project work pushed
  -> claude_work_complete LAST
  -> standalone daemon discovers marker
  -> pre-browser repo locator == actual GitHub remote
  -> exactly one browser message:
       fetch repo=<owner/repo> handoff=<id>
  -> Web ChatGPT resolves that repository
  -> immediate chatgpt_fetch_ack in that repository
  -> substantive review / chatgpt_review_published
  -> later daemon scan/restart does not resend
```

No user-typed `fetch` is permitted.

A local bare remote is **not** an acceptable full Web E2E target for rc2; a future hub/mirror is separate work.

## I. Release evidence

Before `1.0.0`, retain:

- exact package commit;
- install/test commands and pytest count;
- disposable GitHub repository identity + HEAD;
- E2E handoff ID;
- marker sequence/commit evidence;
- routed wake payload evidence;
- proof no manual fetch;
- platform/Python/Chrome/Playwright versions;
- any limitations/defects;
- accepted limitation that reverse Web-to-agent process wake remains out of scope.
