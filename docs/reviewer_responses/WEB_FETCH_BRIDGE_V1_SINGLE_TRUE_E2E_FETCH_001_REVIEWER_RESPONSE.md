# Reviewer Response — Web Fetch Bridge V1 Single True E2E Fetch

Decision: **E2E_FAIL_CLOSED_ACCEPTED_COMPOSER_LOCATOR_CORRECTION_AUTHORIZED**

Scope: `LOCAL_PROTOCOL_INFRASTRUCTURE_ONLY`

## Findings

The single authorized E2E attempt behaved correctly at the protocol boundary:

- fresh handoff was used;
- Claude-owned `claude_work_complete.json` was pushed last;
- daemon auto-discovered the handoff from `origin/main`;
- exactly one browser submission attempt occurred;
- the attempt failed before a real ChatGPT submission because `_find_composer()` selected the hidden fallback `<textarea class="wcDTda_fallbackTextarea">`;
- no `trigger_fetch_sent.json` was published;
- no automatic resend occurred;
- target conversation URL/session remained preserved;
- no research/backtest/strategy/execution state was changed.

The blocker is therefore a narrow UI-adaptation defect, not a marker-protocol or browser-lifecycle defect.

## Authorized correction

Implement only the composer-location/submission correction below, then run one fresh E2E handoff.

1. Replace textarea-only lookup with a semantic, visibility-aware editable-composer lookup.
2. Before changing the locator, perform a **read-only DOM metadata probe** limited to candidate input elements. Allowed metadata: tag name, id, role, `contenteditable`, `data-lexical-editor`, aria-label/name, visibility, bounding box, and ancestor/form identity. Do not read assistant output/content.
3. Prefer stable semantic candidates in this order, while requiring **exactly one visible editable candidate**:
   - visible `#prompt-textarea[contenteditable="true"]`;
   - visible `[contenteditable="true"][data-lexical-editor="true"]`;
   - otherwise a visible `[contenteditable="true"]` only when uniquely scoped to the ChatGPT composer/form.
4. Explicitly exclude hidden fallback textarea(s), including `.wcDTda_fallbackTextarea`, `display:none`, zero-size, disabled, or non-editable nodes.
5. Do not rely on an opaque generated CSS class as the only selector. Semantic attributes + visibility + composer/form scope are required.
6. Playwright `fill()` may be used on the chosen visible contenteditable element; clicking is not required if `fill()` focuses it reliably. The exact text must be `fetch <fresh_handoff_id>`.
7. After `Enter`, confirm submission **without reading assistant output**. Acceptable evidence is composer/input clear/reset or equivalent local submit-state transition while URL remains the configured conversation. If submission cannot be positively confirmed, fail closed and do not publish `trigger_fetch_sent`.
8. Preserve the non-owning browser rules: no `goto`, `new_page`, page/context/browser close, browser repair, or unrelated tab mutation.
9. Preserve terminal fail-closed/no-auto-resend behavior.
10. Add focused tests for hidden fallback exclusion, unique visible contenteditable selection, ambiguous visible candidates fail-closed, and submission-confirmation failure withholding `trigger_fetch_sent`.
11. Use a **fresh unique handoff** for the next E2E; do not reuse `WEB_FETCH_BRIDGE_V1_SINGLE_TRUE_E2E_FETCH_001_001`.
12. Run exactly one fresh E2E after the correction. If browser submission succeeds, publish `trigger_fetch_sent.json` and wait for Web ChatGPT ACK/review markers. If any new blocker appears, stop and report BLOCKED without retry.

## Not authorized

No financial research, backtest, data refresh, strategy/canonical changes, trading prototype, QMT/account/order work, RL reopening, browser self-repair, automatic resend, or unrelated bridge redesign is authorized.

## Next task

`WEB_FETCH_BRIDGE_V1_COMPOSER_LOCATOR_CORRECTION_AND_SINGLE_E2E_001`
