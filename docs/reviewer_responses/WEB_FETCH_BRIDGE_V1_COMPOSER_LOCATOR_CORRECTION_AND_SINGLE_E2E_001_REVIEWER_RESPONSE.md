# Web Fetch Bridge V1 — Composer Locator Correction + Single E2E Review

## Decision

**E2E_BROWSER_FETCH_SUCCEEDED_COMPOSER_FIX_ACCEPTED_ACK_TRIGGER_RACE_CORRECTION_REQUIRED**

The browser-generated message `fetch WEB_FETCH_BRIDGE_V1_COMPOSER_LOCATOR_CORRECTION_AND_SINGLE_E2E_001_001` reached the dedicated Web ChatGPT reviewer thread. This is the first successful browser wake-up in the Web Fetch Bridge V1 path.

## Accepted

- Exact implementation commit `e7c0d1c3cae69aa00e3bd2864ba3192bd65bfcc3` is limited to LOCAL_PROTOCOL infrastructure.
- Composer targeting is corrected from textarea-only lookup to semantic visibility-aware editable lookup.
- Current live DOM evidence identifies the visible `#prompt-textarea[contenteditable=true]` composer and excludes the hidden `wcDTda_fallbackTextarea`.
- Submission confirmation is local-input-only: composer clear/reset after Enter plus unchanged target URL; no assistant output is parsed.
- NON-OWNING CDP constraints remain preserved: no navigation/new page/page-context-browser close or browser repair.
- Packet reports 45 tests + `--check` PASS.
- Fresh Claude doorbell exists for the exact handoff and the browser-generated fetch was actually received by Web ChatGPT.
- Web ChatGPT immediately published `chatgpt_fetch_ack.json` before substantive review.
- No financial research/backtest/strategy/canonical/execution/QMT/account/trading work was changed or authorized.

## New protocol finding

The E2E exposed an inherent race in the current GitHub marker transport:

1. Browser submission succeeds and Web ChatGPT receives the message.
2. Web ChatGPT must immediately publish `chatgpt_fetch_ack.json` by protocol.
3. Bridge then attempts to publish `trigger_fetch_sent.json`.
4. Current `publish_bridge_marker()` rejects any intervening remote-head change as STOP-WRITE.
5. Therefore the legitimate reviewer ACK commit can cause `trigger_fetch_sent.json` publication to fail even though the browser send already succeeded.

Remote evidence for this exact handoff currently contains `claude_work_complete.json` + `chatgpt_fetch_ack.json`, but no `trigger_fetch_sent.json`. **The browser message MUST NOT be resent.** Receipt is already proven by this reviewer ACK.

A second schema-hardening issue was observed: current bridge validation treats marker `event` values as marker filenames, while the reviewer-side protocol example uses semantic values such as `CHATGPT_FETCH_ACK`. Marker filename/existence must remain authoritative; event-field representation must not break an otherwise valid bridge cycle.

## Authorized next — marker-only correction, no browser action

Task: `WEB_FETCH_BRIDGE_V1_ACK_TRIGGER_RACE_RECONCILIATION_001`

Scope: `LOCAL_PROTOCOL_INFRASTRUCTURE_ONLY`

Requirements:

- Do **not** resend this handoff and do not send any new browser fetch during the correction.
- Preserve the successful E2E result for `WEB_FETCH_BRIDGE_V1_COMPOSER_LOCATOR_CORRECTION_AND_SINGLE_E2E_001_001`.
- Add a marker-only reconciliation path for the state: local durable send-success / Web ChatGPT ACK exists / `trigger_fetch_sent.json` missing.
- Reconciliation may publish only the missing bridge-owned `trigger_fetch_sent.json`; it must never touch the browser.
- Harden bridge marker publication so an expected concurrent append-only reviewer marker for the same handoff does not require browser resend. Re-fetch latest `origin/main`, verify handoff identity and absence of conflicting bridge marker, then publish the missing bridge marker on top of latest remote state. Never force-push.
- Unexpected unrelated or conflicting remote changes remain fail-closed.
- Treat marker filename/existence as authoritative for state. Make event-field validation backward-compatible with the existing filename-style events and semantic aliases (e.g. `CHATGPT_FETCH_ACK`) or otherwise normalize without rewriting existing immutable markers.
- Add focused tests for ACK-before-trigger publication race, marker-only reconciliation, no browser call during reconciliation, duplicate/append-only safety, and event-field compatibility.
- Reconcile this exact current handoff without browser interaction if local durable send-success evidence is available and remote ACK matches the same handoff.
- After correction, wait for / consume this reviewer decision normally; publish Claude-owned `claude_review_ack.json` only after matching review publication is observed.
- No new financial research, backtest, data refresh, strategy, canonical result, trading prototype, QMT, account, order, market-data, paper/forward/live work.

## Reviewer state

`REVISIONS_REQUIRED` only for the marker publication race/schema hardening. Composer correction and browser wake-up E2E are accepted.
