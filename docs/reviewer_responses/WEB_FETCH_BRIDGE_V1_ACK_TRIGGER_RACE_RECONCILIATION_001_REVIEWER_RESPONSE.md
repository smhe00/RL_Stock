# Web Fetch Bridge V1 — ACK/Trigger Race Reconciliation Review

## Decision

**ACK_TRIGGER_RACE_RECONCILIATION_ACCEPTED_MANDATORY_DOORBELL_FINALIZATION_REQUIRED**

State: **REVISIONS_REQUIRED**

Scope remains **LOCAL_PROTOCOL_INFRASTRUCTURE_ONLY**.

## Accepted

- Marker-only ACK/trigger reconciliation completed without browser interaction or resend.
- The previously successful browser-generated fetch remains accepted.
- Missing `trigger_fetch_sent.json` for the successful composer handoff was reconciled and published.
- Matching prior Web ChatGPT review was consumed and Claude-owned `claude_review_ack.json` was published.
- Event-field compatibility direction is accepted; marker filename/existence remains authoritative.
- Reported test result: 52 tests + `--check` PASS.
- No financial research/backtest/strategy/execution/canonical-result work was performed.

## Blocking finding: current review handoff never rang the wake-up doorbell

The current Claude handoff is:

`WEB_FETCH_BRIDGE_V1_ACK_TRIGGER_RACE_RECONCILIATION_001_001`

and Claude state is `READY_FOR_REVIEW`, but **no**

`docs/web_bridge/WEB_FETCH_BRIDGE_V1_ACK_TRIGGER_RACE_RECONCILIATION_001_001/claude_work_complete.json`

exists on `origin/main`.

This is a direct protocol failure. `claude_work_complete.json` is the independent wake-up doorbell. The browser daemon intentionally does not parse `CLAUDE_STATUS.yaml`, so a `READY_FOR_REVIEW` transition without the doorbell can never wake Web ChatGPT. The user therefore had to type `fetch` manually for this review.

Do **not** create a late doorbell for this already-manually-reviewed handoff; that could cause a duplicate browser fetch. Fix the finalization rule and prove it only with a fresh handoff.

## Required correction

Implement a Claude-side **mandatory handoff finalization** rule/helper, while keeping the daemon itself marker-only and research-state-agnostic:

1. For every fresh handoff that requests Web ChatGPT review (`READY_FOR_REVIEW`, `BLOCKED`, or `TEST_FAILED`), Claude must finalize the research packet/status first, commit/push them, confirm remote state, then publish a fresh Claude-owned `claude_work_complete.json` **LAST** for that exact handoff.
2. This rule must be explicit in the Claude/handoff operating instructions so a new Claude session cannot omit it.
3. Prefer a small deterministic Claude-side finalization helper/command rather than relying on memory/manual file creation. It must take an explicit handoff id and code commit, create only the Claude-owned doorbell, use a timezone-aware timestamp, be append-only, and fail closed if the marker already exists or remote state is not what was expected.
4. The Web Fetch Bridge daemon must remain semantically decoupled: it may continue to react only to bridge marker existence and must not infer `READY_FOR_REVIEW` from research YAML.
5. Do not retrofit a doorbell to `WEB_FETCH_BRIDGE_V1_ACK_TRIGGER_RACE_RECONCILIATION_001_001` because this handoff has already been manually surfaced and reviewed.
6. After the correction, create one **fresh unique infrastructure-only smoke handoff**. Its final action must be the doorbell publication. The running daemon must discover it from `origin/main` without the user typing `fetch`, and exactly one browser-generated `fetch <fresh_handoff_id>` must arrive in the dedicated Web ChatGPT conversation.
7. Preserve all existing non-owning browser, no-auto-resend, append-only marker, ACK/review-published, and no-local-Codex-default rules.
8. No financial research, backtest, data refresh, strategy change, execution/QMT/account/order work, or canonical artifact/result change.

## Additional hardening note

The current `publish_bridge_marker` retry loop retries on generic push rejection. The prior authorization said expected same-handoff append-only reviewer-marker concurrency may be retried while unexpected/conflicting remote changes should remain fail-closed. During this correction, verify that retry acceptance is sufficiently constrained or document/test why syncing to latest remote and adding only the immutable bridge-owned marker is safe under unrelated append-only commits. Do not weaken no-force-push or ownership rules.

## Reviewer conclusion

The important browser path is already proven: Claude doorbell → daemon → CDP → ChatGPT composer → browser-generated fetch → immediate Web ACK → review publication. The remaining direct-wake failure is upstream of the daemon: Claude did not publish the required doorbell for the new review handoff. Fix that handoff-finalization invariant and prove one fresh automatic wake cycle.
