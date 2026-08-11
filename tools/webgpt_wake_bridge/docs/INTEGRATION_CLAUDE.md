# Claude Code integration

The bridge is intentionally independent from Claude's project state machine. Claude only needs one finalization invariant.

## Required agent rule

For every fresh handoff that requests Web ChatGPT review:

```text
1. finish the work and tests
2. write/update the project's review packet/status
3. commit and push all work
4. confirm local HEAD == configured remote branch HEAD
5. run `webgpt-bridge finalize ...`
6. commit and push only the resulting `claude_work_complete.json` as the FINAL push
7. stop and wait for `chatgpt_review_published.json`
```

Do not infer wake-up from READY/BLOCKED/TEST_FAILED or any other project state. The daemon never reads those states.

## Suggested CLAUDE.md snippet

```text
WEBGPT REVIEW WAKE-UP (mandatory):
When a fresh handoff needs Web ChatGPT review, all project work/status/packet commits must be pushed first. Confirm the configured remote branch is current, then run:

  webgpt-bridge finalize --config <LOCAL_CONFIG> --handoff <HANDOFF_ID> --code-commit <CODE_SHA>

Commit/push the generated <marker_root>/<HANDOFF_ID>/claude_work_complete.json as the FINAL push. Never create a late doorbell for an already manually surfaced/reviewed handoff. Never resend a handoff automatically. Wait for chatgpt_review_published.json before consuming the review.
```

## What Claude must not do

- Do not type `fetch` into ChatGPT manually during an autowake acceptance smoke.
- Do not edit bridge-owned `trigger_fetch_sent.json`.
- Do not edit Web ChatGPT-owned ACK/review markers.
- Do not create a second doorbell for the same handoff.
- Do not use project YAML/status as a substitute for the doorbell.
