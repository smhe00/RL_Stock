# Reviewer Response — Web Fetch Bridge V1 Fail-Closed + True E2E Retry

```yaml
handoff_id: WEB_FETCH_BRIDGE_V1_FAIL_CLOSED_AND_TRUE_E2E_RETRY_001_001
state: REVISIONS_REQUIRED
decision: WEB_FETCH_BRIDGE_V1_FAIL_CLOSED_CORE_ACCEPTED_BROWSER_LIFECYCLE_DIAGNOSTIC_REQUIRED
reviewed_remote_head: be696af4e12dc6acaeea369f2bb289ba6d2b6e73
code_commit: 90264e3
scope: LOCAL_PROTOCOL_INFRASTRUCTURE_ONLY
```

## Accepted

- sender failure is now terminal and no longer auto-retries;
- operator retry is explicit;
- trigger_fetch_sent remains absent when no browser message was submitted;
- timestamp validation is timezone-aware;
- origin/main marker watcher and GitHub marker transport remain accepted;
- no financial research/backtest/strategy/execution/QMT/account/trading work occurred.

## Blocking browser issue

The dedicated Chrome conversation has now been observed by the user to fall back to `https://chatgpt.com/` more than once during bridge development/testing. The repository does not contain an explicit Chrome restart/launch path, and the current fallback path with no configured target URL does not intentionally call `page.goto()`. However the sender still calls `browser.close()` after a `connect_over_cdp()` attachment. Playwright documents `Browser.close()` on a connected browser as a browser-level disconnect/cleanup operation, and `connect_over_cdp()` is explicitly lower-fidelity than the native Playwright protocol. Until we prove lifecycle neutrality on this exact dedicated Chrome session, no further real fetch submission is authorized.

## Required correction

1. Add a **no-op lifecycle diagnostic** that does not type, click, navigate, create pages, or close pages/contexts.
2. The diagnostic must require the dedicated target conversation URL in ignored local config. Do not use the exact-one `/c/*` discovery fallback for the diagnostic.
3. Before Playwright attachment, query the local Chrome DevTools target list and record only target URL/title metadata needed for diagnosis (no ChatGPT output/content).
4. Attach with `connect_over_cdp()` and hold for at least 30 seconds without page mutation.
5. **Do not call `browser.close()`** in the no-op diagnostic or normal long-running daemon path. Prefer one long-lived Playwright/CDP connection owned by the daemon; terminate only the Playwright driver/process connection when the daemon itself exits.
6. After the 30-second no-op period, re-check the DevTools target list and prove the configured `https://chatgpt.com/c/...` target is still present and unchanged.
7. If the page becomes `https://chatgpt.com/` during a pure no-op probe, STOP and report that as an environment/CDP/ChatGPT-session issue. Do not attempt navigation repair.
8. If the no-op probe passes, refactor the sender to **never call `page.goto()`**, `new_page()`, `page.close()`, `context.close()`, or `browser.close()` in normal operation. The configured target conversation must already exist and match exactly; otherwise fail closed.
9. After refactor, run a second no-op preservation probe. Only if both no-op probes pass may one fresh E2E fetch handoff be attempted.
10. The fresh E2E must use a new unique handoff and exactly one `fetch <handoff_id>`; then publish trigger_fetch_sent and wait for Web ChatGPT ACK markers as before.

## Forbidden

No financial research, backtest, data refresh, strategy/canonical change, trading prototype, QMT, account, market-data, order, paper/forward/live work, RL reopening, local-Codex default reviewer, automatic Claude launch, ChatGPT output scraping, CAPTCHA/protection bypass, or browser self-repair/navigation.

## Browser operating rule

For this dedicated reviewer profile, the bridge is a **non-owning guest** of the browser. It may observe the configured target URL and inject exactly one fetch message only after lifecycle preservation is proven. It must not manage browser/page lifecycle.
