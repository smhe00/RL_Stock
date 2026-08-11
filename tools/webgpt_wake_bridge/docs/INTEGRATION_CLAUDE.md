# Claude Code integration

The bridge is intentionally independent from Claude's project state machine. Claude needs only the durable review-request finalization invariant.

## One-time project setup

Prefer operator/bootstrap setup outside the consumer repository:

```powershell
webgpt-bridge init --repo <PROJECT_REPO>
```

Edit the generated local config and set the exact dedicated reviewer conversation URL. Keep the config/runtime local; only protocol markers belong in the project Git history.

## Required agent rule

For every fresh handoff that requests Web ChatGPT review:

```text
1. finish project work and tests
2. write/update the project's own review packet/status if that project uses them
3. commit and push all work
4. require worktree clean
5. confirm local HEAD == configured remote branch HEAD
6. choose a real code commit already contained in that remote branch
7. run `webgpt-bridge finalize ...`
8. verify the only newly created review-request artifact is claude_work_complete.json
9. commit and push that doorbell as the FINAL push
10. stop and wait for chatgpt_review_published.json
```

The standalone daemon does not know or care whether the project calls its state READY/BLOCKED/TEST_FAILED, uses issues, packets, gates, or something else. It wakes Web ChatGPT only from the doorbell marker.

## Suggested CLAUDE.md snippet

```text
WEBGPT REVIEW WAKE-UP (mandatory):
When a fresh handoff needs Web ChatGPT review, all project work/status/packet commits must already be committed and pushed. The worktree must be clean and local HEAD must match the configured remote branch. Then run:

  webgpt-bridge finalize --config <LOCAL_CONFIG> --handoff <HANDOFF_ID> --code-commit <REMOTE_CONTAINED_CODE_SHA>

The finalizer must pass. Commit/push only the generated <marker_root>/<HANDOFF_ID>/claude_work_complete.json as the FINAL review-request push. Never create a late doorbell for an already manually surfaced/reviewed handoff. Never automatically resend a failed/uncertain handoff. Wait for chatgpt_review_published.json before consuming the review.
```

## What Claude must not do

- Do not type `fetch` into ChatGPT manually during an autowake acceptance smoke.
- Do not edit bridge-owned `trigger_fetch_sent.json`.
- Do not edit Web ChatGPT-owned ACK/review markers.
- Do not create a second doorbell for the same handoff.
- Do not use project YAML/status as a substitute for the doorbell.
- Do not call browser repair/navigation/lifecycle actions through the bridge.
- Do not interpret missing Git state after a Git error as permission to send.

## Review consumption

After matching `chatgpt_review_published.json` appears, the project may consume its own review artifacts according to its own protocol and publish `claude_review_ack.json` for that handoff.

Do **not** create another work-complete doorbell merely to acknowledge a completed review when there is no new review-requesting work; that would create a wake loop.

Reverse Web-to-Claude process launch/restart is not provided by Protocol V1.
