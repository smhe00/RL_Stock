# Web Fetch Bridge V1 — User Authorization

Date: 2026-08-11
Reviewer: Web ChatGPT
Scope: LOCAL_PROTOCOL infrastructure only

## Decision

**USER_AUTHORIZED_WEB_FETCH_BRIDGE_V1_IMPLEMENTATION_AND_SINGLE_E2E_SMOKE**

The user explicitly selected a marker-driven Chrome CDP + Playwright wake-up bridge so that Web ChatGPT remains the planner/reviewer while the local trigger only replaces the manual `fetch` keystroke.

This authorization supersedes the prior local-Codex-as-default-reviewer direction. The existing local Codex reviewer may remain available as an optional unattended mode, but it MUST NOT be invoked by default for this bridge.

## Architectural rule

The wake-up bridge is completely decoupled from the research/reviewer protocol.

- Research protocol remains canonical in:
  - `docs/agent_state/CLAUDE_STATUS.yaml`
  - `docs/review_packets/`
  - `docs/reviewer_state/CHATGPT_REVIEW.yaml`
  - `docs/reviewer_responses/`
- Wake-up protocol MUST use independent append-only marker files.
- The trigger MUST NOT parse or interpret research states such as READY_FOR_REVIEW, BLOCKED, TEST_FAILED, PREP, RUN, M2, 03110, or `authorized_next`.
- The trigger's only semantic action is: detect marker state -> send exactly one `fetch <handoff_id>` to the dedicated Web ChatGPT conversation -> wait for marker progress.
- GitHub remains the canonical audit/transport bus for the bridge markers.

## Frozen marker protocol

Use an append-only directory per handoff/cycle:

`docs/web_bridge/<handoff_id>/`

Required marker ownership and order:

1. `claude_review_ack.json` — Claude only. Means Claude has consumed the immediately preceding matching Web ChatGPT review before beginning/continuing authorized work. For the first bridge bootstrap cycle this may reference the prior completed reviewer state.
2. `claude_work_complete.json` — Claude only. Created **only after** Claude's work, tests, packet/status updates, commit, push, and remote verification are complete. This is the wake-up doorbell for the trigger.
3. `trigger_fetch_sent.json` — bridge trigger only. Created after it has successfully submitted exactly one `fetch <handoff_id>` to the dedicated Web ChatGPT conversation.
4. `chatgpt_fetch_ack.json` — Web ChatGPT only. On receiving the automatic fetch, Web ChatGPT MUST create/push this marker immediately, before substantive review. It proves the fetch was received and makes the trigger wait.
5. `chatgpt_review_published.json` — Web ChatGPT only. Created/pushed **last**, only after reviewer response + `CHATGPT_REVIEW.yaml` are fully published and remote-verified.
6. Claude consumes the review and creates the next cycle's `claude_review_ack.json`; after completing the newly authorized work, it creates the next `claude_work_complete.json`.

Each marker is immutable once created. No actor modifies another actor's marker. Do not use one shared mutable bridge YAML.

Minimum marker fields:

```json
{
  "protocol": "web_fetch_bridge_v1",
  "handoff_id": "...",
  "event": "...",
  "timestamp": "ISO-8601"
}
```

Markers may include commit/reference fields, but MUST NOT duplicate full review contents or contain credentials/account data.

## Trigger state machine

The trigger works **only** from marker existence for a handoff. It MUST NOT inspect the research state machine to decide whether to send fetch.

For a handoff with `claude_work_complete.json`:

- if `chatgpt_review_published.json` exists -> DONE; never send.
- else if `chatgpt_fetch_ack.json` exists -> WAIT_FOR_REVIEW; never send.
- else if `trigger_fetch_sent.json` exists -> WAIT_FOR_FETCH_ACK; never send again automatically.
- else -> send exactly one `fetch <handoff_id>` to the configured dedicated ChatGPT thread, then create/push `trigger_fetch_sent.json`.

If a send was attempted but no `chatgpt_fetch_ack.json` appears within a configurable timeout (default 120 s), fail closed and notify/log. **Do not automatically resend fetch.** Operator retry must be explicit.

The bridge MUST preserve handoff de-duplication across restart using GitHub markers as source of truth; local runtime state may be only a cache.

## Browser/CDP requirements

Implement Playwright/Python using Chromium CDP as a thin virtual finger only.

- Prefer `connect_over_cdp()` to a dedicated Chrome/Chromium profile.
- Remote-debugging endpoint must be localhost only.
- Dedicated browser profile should contain ChatGPT only; do not reuse a browser profile containing broker, banking, mail, or other sensitive sessions.
- Fail closed on login screen, CAPTCHA/challenge, wrong conversation, missing composer, multiple ambiguous target tabs, page generation already in progress if it prevents a safe one-shot submit, or Playwright/CDP timeout.
- Do not scrape, parse, or interpret ChatGPT review output. Review completion is known only through GitHub `chatgpt_review_published.json`.
- Do not bypass CAPTCHA, rate limits, or browser/platform protections.

The user supplied a dedicated ChatGPT conversation for this bridge. **Do not commit its conversation URL to tracked Git files.** Put the target URL only in an ignored local configuration file. If the URL cannot be obtained safely from local operator/runtime context, stop with one explicit setup requirement rather than leaking it into the repository.

## Implementation scope

Claude is authorized to:

- refactor the current `local_reviewer_watcher.py` or add a separate bridge implementation; prefer a separate clearly named bridge module if that keeps the old optional local-Codex mode isolated;
- add/update `config/*.example.*`, ignored local config pattern, Windows launcher, docs, `.gitignore`, and bridge tests;
- add `docs/web_bridge/` marker protocol support;
- keep existing local Codex reviewer mode optional, but default bridge mode MUST NOT invoke `codex exec`;
- add Windows notification/logging and explicit retry tooling;
- add deterministic unit tests for marker-only state transitions, dedup/restart, timeout/no-resend, ownership, wrong-thread/CDP fail-closed behavior, and marker ordering;
- perform **one single end-to-end communication smoke test** if the dedicated CDP browser session is available locally.

The single E2E smoke must demonstrate, in order:

`claude_work_complete` -> trigger submits `fetch <handoff_id>` -> `trigger_fetch_sent` -> Web ChatGPT writes `chatgpt_fetch_ack` -> Web ChatGPT publishes review -> `chatgpt_review_published` -> Claude consumes review -> `claude_review_ack`.

If CDP/profile/session prerequisites are not available, implementation/tests may complete but the live browser smoke MUST fail closed and the packet must state the exact minimal manual prerequisite. Do not weaken safety to force a pass.

## Hard prohibitions

This authorization does NOT permit:

- new financial research, backtests, data refresh, strategy changes, or result changes;
- any modification to MaxDiv 120/0.5, M2, accepted canonical artifacts/results, or the unresolved 03110 STOP;
- trading prototype work;
- QMT, market-data action, account access, orders, paper/forward/live trading;
- PPO/SAC/TD3 or any RL reopening;
- automatic Claude launch/restart orchestration as part of the bridge;
- default local Codex reviewer invocation;
- parsing ChatGPT page output as protocol state;
- committing the dedicated ChatGPT conversation URL, authentication material, cookies, browser profile data, or sensitive session data.

## Required handoff

When complete, Claude MUST create a new unique handoff ID and review packet documenting:

- exact code commit(s);
- changed files;
- tests and results;
- bridge state machine and ownership proof;
- whether the dedicated CDP E2E smoke actually ran;
- if it ran, exact marker sequence and timestamps/commits;
- if it did not run, the single minimal remaining manual prerequisite;
- confirmation that research/canonical artifacts and strategy logic are unchanged.

No further step is automatically authorized after that handoff. Web ChatGPT will review it.
