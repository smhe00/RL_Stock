# Web Fetch Bridge V1 implementation review

```yaml
handoff_id: WEB_FETCH_BRIDGE_V1_IMPLEMENTATION_AND_SINGLE_E2E_SMOKE_001
review_state: REVISIONS_REQUIRED
decision: WEB_FETCH_BRIDGE_V1_CORE_ACCEPTED_BUT_E2E_TRANSPORT_INCOMPLETE_CORRECTION_REQUIRED
reviewed_remote_head: 15d99aacc1a84042a4a97b8ed2b98b85c8c4f609
reviewed_code_commit: e343ab5
scope: LOCAL_PROTOCOL_INFRASTRUCTURE_ONLY
```

## Summary

The marker-only state-machine concept is directionally accepted, and the unit-level separation from the research protocol is good. However, the delivered implementation is not yet an end-to-end Web Fetch Bridge and therefore is **not accepted as operational**.

The absence of an automatic `fetch <handoff_id>` in the dedicated Web ChatGPT conversation is explained by structural gaps, not merely by the missing local URL/Playwright prerequisite.

## Blocking findings

1. **No Claude doorbell marker was published.**
   - `docs/web_bridge/` on `main` contains only `README.md`.
   - The current handoff is `READY_FOR_REVIEW` in `CLAUDE_STATUS.yaml`, but there is no `docs/web_bridge/WEB_FETCH_BRIDGE_V1_IMPLEMENTATION_AND_SINGLE_E2E_SMOKE_001/claude_work_complete.json`.
   - Because the bridge is intentionally marker-only, the trigger had no legal input and therefore could not fire.

2. **The bridge has no automatic remote marker watcher/daemon.**
   - `scripts/web_fetch_bridge.py` currently requires explicit `--handoff <id>`.
   - The default no-handoff path exits with `provide --handoff <id>` / "scheduled trigger reserved".
   - This does not satisfy the approved design in which the trigger autonomously notices a new Claude marker and sends exactly one fetch.

3. **Marker transport is local-filesystem only, while the approved protocol is GitHub-marker driven.**
   - `MarkerStore` reads/writes the local worktree only.
   - `trigger_fetch_sent.json` is created locally but is not committed/pushed to GitHub by the bridge.
   - `wait_for_ack()` polls only the local file, so it cannot observe a Web ChatGPT `chatgpt_fetch_ack.json` pushed remotely unless some unrelated process updates the worktree.
   - Thus the bridge is not actually decoupled through GitHub yet.

4. **The E2E smoke was not run.**
   - The fail-closed behavior is acceptable for the first implementation attempt, but it does not close the user-authorized single E2E smoke gate.
   - The correction must actually deliver one browser-generated `fetch <fresh_handoff_id>` into the dedicated conversation.

5. **CDP live-session behavior still needs a real smoke check.**
   - Do not require Playwright's bundled Chromium merely to attach to the user's already-running Chrome unless runtime proves it necessary; the Python Playwright package is the actual bridge dependency for `connect_over_cdp`.
   - The live smoke must confirm the dedicated Chrome process/session remains alive after one send.
   - The current composer lookup is textarea-only; live verification must support the current ChatGPT composer in a fail-closed way without scraping assistant output.

## Authorized correction only

Claude is authorized to perform **WEB_FETCH_BRIDGE_V1_E2E_TRANSPORT_CORRECTION_001** with these frozen requirements:

1. Keep the wake-up bridge semantically independent from `CLAUDE_STATUS.yaml`, `CHATGPT_REVIEW.yaml`, PREP/RUN, M2, 03110, and all research states. Trigger decisions remain marker-only.
2. Add a real autonomous watcher/daemon mode that discovers eligible handoffs by inspecting **GitHub/`origin/main` bridge markers only**. A 5-10 second polling interval is acceptable. Do not invoke local Codex.
3. Do not mutate or fast-forward a dirty Claude worktree in order to watch markers. Use safe git plumbing or an isolated bridge worktree/temporary checkout. Remote-head changes must fail closed; never force-push.
4. Implement GitHub transport for bridge markers:
   - Claude-owned `claude_work_complete.json` must be committed/pushed only after code, tests, packet, and Claude status are already remotely complete.
   - bridge-owned `trigger_fetch_sent.json` must be append-only and committed/pushed by the trigger after a successful browser submission.
   - bridge observation of `chatgpt_fetch_ack.json` / `chatgpt_review_published.json` must refresh from `origin/main`, not rely on an unrelated local pull.
   - if browser submission succeeds but publishing `trigger_fetch_sent` fails, record durable local sent state and **do not auto-resend**; fail closed for operator inspection.
5. Add the missing Claude marker integration. For the fresh smoke handoff, the **last Claude-side protocol action before waiting** must be creation+push of `claude_work_complete.json`.
6. Local browser target must remain uncommitted. To remove the current manual URL blocker, support either:
   - ignored `target_conversation_url`, or
   - deterministic discovery of exactly one already-open `https://chatgpt.com/c/*` conversation page in the dedicated CDP profile; 0 or >1 matching pages must fail closed.
7. Install the Python `playwright` package locally if absent. Do not require downloading a separate Chromium binary when attaching to the user's existing Chrome unless a concrete runtime error proves it necessary.
8. Use the user's existing dedicated Chrome CDP setup:
   - endpoint `http://127.0.0.1:9222`
   - executable `C:\Program Files\Google\Chrome\Application\chrome.exe`
   - profile `C:\ChatGPT_Automation_Profile`
   The bridge must not expose CDP beyond localhost.
9. The sender remains input-only: no parsing/scraping ChatGPT assistant output. It may inspect only minimal page state needed to identify the dedicated conversation/composer and login/challenge failure gates.
10. Verify the current ChatGPT composer selector live and fail closed on ambiguity. The smoke must prove exactly one `fetch <handoff_id>` was submitted.
11. Add tests for:
   - remote marker discovery independent of research YAML;
   - no trigger without remote `claude_work_complete`;
   - automatic discovery without explicit `--handoff`;
   - remote `trigger_fetch_sent` publication;
   - remote ACK observation;
   - remote-head race STOP-WRITE;
   - send-success/publish-failure no-resend;
   - restart dedup;
   - exact-one-open-chatgpt-tab discovery fallback;
   - dedicated Chrome remains usable after sender disconnect.
12. Run **one fresh E2E smoke**. It is not sufficient to call the CLI manually with an explicit handoff. Required sequence:

```text
Claude pushes correction implementation + packet/status
Claude pushes fresh claude_work_complete marker LAST
bridge daemon discovers marker from origin/main
bridge sends exactly one fetch <fresh_handoff_id> through CDP
bridge publishes trigger_fetch_sent marker
Web ChatGPT receives the fetch and publishes chatgpt_fetch_ack before substantive review
Web ChatGPT publishes review + chatgpt_review_published marker
Claude consumes review and publishes claude_review_ack
```

13. No financial research, backtest, data refresh, strategy/canonical artifact change, trading prototype, QMT/account/order action, instrument substitution, 03110 repair, or RL reopening is authorized.

## Reviewer-side behavior for the fresh E2E smoke

When the browser-generated `fetch <fresh_handoff_id>` arrives in the dedicated Web ChatGPT conversation, Web ChatGPT will:

1. verify the matching remote bridge handoff and trigger marker state;
2. publish `chatgpt_fetch_ack.json` immediately, before substantive review;
3. perform the normal GitHub review;
4. publish reviewer response/state;
5. publish `chatgpt_review_published.json` last.

The current manually surfaced handoff is **not** treated as a bridge-generated fetch and therefore no synthetic `chatgpt_fetch_ack` marker will be created for it.

## Gate status

```yaml
accepted:
  - marker-only wake-up protocol concept
  - append-only ownership model
  - local CDP thin virtual-finger direction
  - fail-closed / no-auto-resend intent
not_accepted_yet:
  - operational Web Fetch Bridge
  - GitHub marker transport
  - autonomous trigger
  - E2E smoke
revision_required:
  - remote marker transport + daemon + Claude doorbell + live E2E correction
authorized_next:
  - WEB_FETCH_BRIDGE_V1_E2E_TRANSPORT_CORRECTION_001
```
