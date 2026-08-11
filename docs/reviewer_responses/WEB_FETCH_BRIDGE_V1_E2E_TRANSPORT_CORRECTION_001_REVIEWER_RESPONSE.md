# Web Fetch Bridge V1 — E2E Transport Correction Review

```yaml
handoff_id: WEB_FETCH_BRIDGE_V1_E2E_TRANSPORT_CORRECTION_001_001
state: REVISIONS_REQUIRED
decision: WEB_FETCH_BRIDGE_V1_TRANSPORT_CORE_ACCEPTED_E2E_RETRY_AND_FAIL_CLOSED_FIX_REQUIRED
reviewed_remote_head: 92d3a52a821fc5f698731eacf858cef1a6596cdc
reviewed_code_commit: c977265a736ddb91b0f989fce48068f3b5fc7e6f
scope: LOCAL_PROTOCOL_INFRASTRUCTURE_ONLY
```

## Review conclusion

The transport correction materially fixes the prior architecture gap: a fresh Claude `claude_work_complete.json` doorbell is now present on `origin/main`; the daemon discovered it from remote markers; GitHub marker transport, isolated bridge worktree, remote-head STOP-WRITE, append-only publication, and marker-only discovery are implemented. The live attempt also reached the dedicated Chrome CDP endpoint successfully.

The end-to-end bridge is **not yet accepted**, because no browser-generated `fetch <handoff_id>` reached the dedicated Web ChatGPT conversation. The live attempt failed before submission because the dedicated CDP profile exposed only `https://chatgpt.com/` and no open `https://chatgpt.com/c/*` page.

## Passed

- REMOTE_CLAUDE_WORK_COMPLETE_DOORBELL_PRESENT
- AUTONOMOUS_ORIGIN_MAIN_MARKER_DISCOVERY_IMPLEMENTED
- RESEARCH_PROTOCOL_DECOUPLED_FROM_WAKEUP_MARKERS
- GITHUB_MARKER_TRANSPORT_IMPLEMENTED
- ISOLATED_BRIDGE_WORKTREE_DIRECTION_ACCEPTED
- REMOTE_HEAD_STOP_WRITE_AND_NO_FORCE_PUSH_DIRECTION_ACCEPTED
- BRIDGE_OWNERSHIP_REMAINS_TRIGGER_FETCH_SENT_ONLY
- PLAYWRIGHT_CDP_CONNECT_REACHED_DEDICATED_CHROME
- EXACT_ONE_CONVERSATION_OR_IGNORED_TARGET_URL_ROUTING_DIRECTION_ACCEPTED
- NO_CODEX_DEFAULT_REVIEWER
- NO_FINANCIAL_RESEARCH_BACKTEST_EXECUTION_OR_CANONICAL_CHANGE

## Revisions required

1. **SEND failure is not actually terminal/fail-closed in daemon mode.**
   `RemoteMarkerWatcher.scan_once()` only persists dedup after `FETCH_SENT` or after a send-success/publish-failure path. When `CdpFetchSender.send()` returns `SEND_FAILED_FAIL_CLOSED` (for example zero `/c/` tabs, login/challenge, missing composer, CDP failure), the handoff remains remotely eligible and locally unseen, so the daemon retries every 5–10 seconds. This violates the frozen fail-closed contract and can repeatedly disturb the dedicated browser.

   Required correction: persist a local terminal attempt-failure record for that handoff on any sender failure and skip all automatic retries. A retry must require an explicit operator action/flag that clears or supersedes that local failure exactly once. Never create `trigger_fetch_sent.json` unless the message was actually submitted.

2. **True E2E smoke remains incomplete.**
   After the user/environment provides exactly one open `https://chatgpt.com/c/*` page in the dedicated CDP profile (or an ignored local `target_conversation_url`), run a fresh autonomous marker-driven smoke. The bridge must discover a fresh remote Claude doorbell without `--handoff`, submit exactly one `fetch <fresh_handoff_id>`, and remotely publish `trigger_fetch_sent.json`.

3. **Marker timestamp audit bug.**
   The current append-only `claude_work_complete.json` contains `2026-08-11T15:12:00+00:00`, which is eight hours ahead of the actual UTC instant corresponding to local 15:12+08. Do not mutate the append-only old marker. For the fresh handoff, generate the timestamp from an actual timezone-aware UTC clock (or explicit local +08:00 clock) and add a deterministic test/validation preventing this class of timezone-label mismatch where practical.

4. **Playwright lifecycle should be explicit.**
   Keep the externally launched dedicated Chrome session intact. Store the object returned by `sync_playwright().start()` and stop the Playwright driver explicitly after disconnect. Do not close/navigate unrelated tabs. The target routing must either reuse the exact configured conversation or the exact-one `/c/` tab; zero/multiple remains fail-closed.

## Browser-page observation

The GitHub evidence says the CDP-connected dedicated profile contained only the ChatGPT home page at the time of the failed smoke. Therefore the bridge did not submit a fetch and did not create a remote `trigger_fetch_sent.json`. The observed return to the ChatGPT home page is consistent with the dedicated profile not actually holding the intended conversation at smoke time; the current evidence does **not** prove that the bridge intentionally navigated the conversation back to home.

Playwright's connected-browser `browser.close()` API disconnects the connected Browser object/browser-server connection rather than being a reliable semantic "detach" primitive for our externally managed session, so the implementation should still make lifecycle ownership explicit and prove the target tab remains unchanged after a failed attempt.

## Authorized next — immediate correction only

```yaml
authorized_next:
  - task: WEB_FETCH_BRIDGE_V1_FAIL_CLOSED_AND_TRUE_E2E_RETRY_001
    scope: LOCAL_PROTOCOL_INFRASTRUCTURE_ONLY
    requirements:
      - persist sender-failure dedup so daemon never automatically retries a failed browser attempt
      - add explicit operator retry mechanism only; no automatic retry
      - keep trigger_fetch_sent absent unless a fetch was actually submitted
      - use a fresh unique handoff for the real smoke
      - fresh Claude doorbell must be pushed last with a correct timezone-aware timestamp
      - daemon must discover the fresh doorbell from origin/main automatically
      - dedicated Chrome must have exactly one chatgpt.com/c/* conversation open OR ignored local target URL
      - send exactly one `fetch <fresh_handoff_id>`
      - publish trigger_fetch_sent remotely after successful submission
      - then wait for Web ChatGPT chatgpt_fetch_ack / chatgpt_review_published markers
      - preserve browser/session/tab usability after the attempt
      - add tests for send-failure no-auto-retry and explicit retry only
      - no new financial research, backtest, strategy, execution, QMT, account or trading work
```

No further branch is authorized after the fresh E2E handoff; wait for Web ChatGPT review.
