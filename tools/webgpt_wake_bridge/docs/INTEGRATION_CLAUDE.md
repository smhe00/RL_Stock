# Claude Code integration

The bridge is independent from Claude's project state machine. Claude needs only project setup plus the durable review-request finalization invariant.

## One-time project setup

For a project whose configured Git remote is a Web-accessible GitHub repository:

```powershell
webgpt-bridge init --repo <PROJECT_REPO> --review-repository <OWNER/REPO>
```

Edit the generated local config and set the exact dedicated reviewer conversation URL. Keep config/runtime local; only protocol markers belong in project Git history.

`[review].repository` must match the configured `github.com` Git remote. `once`/`daemon` verify this before browser interaction. A local-only/non-GitHub remote fails closed; hub/mirror mode is not part of rc2.

Standalone wake payload:

```text
fetch repo=<OWNER/REPO> handoff=<HANDOFF_ID>
```

This explicit repository identity is mandatory for multi-project Web routing.

## Required agent rule

For every fresh handoff that requests Web ChatGPT review:

```text
1. finish project work/tests
2. update the project's own review packet/status if applicable
3. commit and push all work
4. require clean worktree
5. confirm local HEAD == configured remote branch HEAD
6. choose a real code commit contained in that remote branch
7. run `webgpt-bridge finalize ...`
8. commit/push only claude_work_complete.json as the FINAL review-request push
9. stop and wait for chatgpt_review_published.json
```

The daemon never infers readiness from READY/BLOCKED/TEST_FAILED or project YAML.

## Suggested CLAUDE.md snippet

```text
WEBGPT REVIEW WAKE-UP (mandatory):
The local bridge config must contain the correct [review].repository = "owner/repo", matching the configured GitHub remote. Before requesting review, all project work/status/packet commits must be pushed, the worktree must be clean, and local HEAD must match the configured remote branch. Then run:

  webgpt-bridge finalize --config <LOCAL_CONFIG> --handoff <HANDOFF_ID> --code-commit <REMOTE_CONTAINED_CODE_SHA>

Commit/push only the generated <marker_root>/<HANDOFF_ID>/claude_work_complete.json as the FINAL review-request push. Never create a late doorbell for an already reviewed handoff. Never automatically resend a failed/uncertain handoff. Wait for chatgpt_review_published.json before consuming review.
```

## Must not

- Do not manually type `fetch` during an autowake smoke.
- Do not edit bridge-owned `trigger_fetch_sent.json`.
- Do not edit Web-owned ACK/review markers.
- Do not create a second doorbell for the same handoff.
- Do not substitute project state for the doorbell.
- Do not repair/navigate/close browser state through the bridge.
- Do not use a local-only remote for full Web E2E and then treat missing ACK as success.

## Review consumption

After matching `chatgpt_review_published.json`, consume the project review and publish `claude_review_ack.json`. Do not create a new work-complete doorbell merely to acknowledge a completed review.

Reverse Web-to-Claude process launch/restart remains out of scope.
