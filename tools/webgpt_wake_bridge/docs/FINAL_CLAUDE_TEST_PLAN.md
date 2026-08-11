# Final Claude validation plan — test only

Claude participates only as the final independent validator of the standalone release candidate. **Do not redesign or modify package code during this validation.** If any command/test exposes a defect, record it precisely, return `REVISIONS_REQUIRED`, and stop the acceptance path.

## Scope and candidate

Validate only:

```text
tools/webgpt_wake_bridge/
```

Expected candidate version:

```text
0.9.0rc1
```

Do not modify the accepted embedded reference implementation:

```text
scripts/web_fetch_bridge.py
scripts/finalize_handoff.py
```

Do not switch RL_Stock to the standalone package during validation.

## 1. Freeze exact candidate commit

Before testing:

```powershell
git fetch origin
git status --short
git rev-parse HEAD
git rev-parse origin/main
```

Require a clean worktree and `HEAD == origin/main`. Record the exact candidate commit. Do not test a moving/uncommitted candidate.

## 2. Fresh package environment

From `tools/webgpt_wake_bridge`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[test]"
webgpt-bridge --version
pytest
```

Required:

```text
webgpt-bridge --version == 0.9.0rc1
pytest == PASS (all tests)
```

Record Python, Playwright, Chrome and Windows versions.

Do not install/start a Playwright-owned browser; the live smoke attaches to the existing externally managed Chrome over CDP.

## 3. Static safety verification

Independently inspect the candidate source and confirm:

- no RL_Stock research/trading imports or state parsing;
- marker-only daemon does not inspect `CLAUDE_STATUS.yaml`, `CHATGPT_REVIEW.yaml`, gates, research results, or financial state;
- normal sender performs no browser/page navigation or lifecycle ownership actions;
- no automatic browser resend path exists;
- no full-page/conversation-output scraping is used;
- login/challenge probes are structural only;
- exact target conversation is required;
- CDP endpoint is exact loopback only;
- Git publication never force-pushes;
- Git errors are not silently converted into marker absence.

Do not fail merely because documentation/comments describe forbidden operations; verify executable behavior/calls.

## 4. Blank consumer repository + `init`

Create a disposable blank Git repository unrelated to RL_Stock. It should contain only trivial demo content plus normal Git metadata; no RL_Stock status/reviewer files may be copied into it.

Create a local/bare remote or disposable GitHub test repo, set `main`, configure Git user identity, commit/push the initial content, and require local/remote HEAD equality.

Bootstrap through the standalone CLI rather than copying the RL_Stock config:

```powershell
webgpt-bridge init --repo <BLANK_REPO>
```

Record the generated local config path. Confirm:

- generated config is outside the blank consumer repo by default;
- generated runtime is outside the blank consumer repo by default;
- the consumer repo was not modified by `init`;
- `target_conversation_url` is blank until the operator fills it.

Edit the generated local config and set the exact already-open dedicated Web ChatGPT reviewer conversation URL. Do not commit the local config.

## 5. Local safety checks

With the dedicated Chrome profile already running on `127.0.0.1:9222` and the exact reviewer conversation already open:

```powershell
webgpt-bridge check --config <LOCAL_CONFIG>
webgpt-bridge noop --config <LOCAL_CONFIG> --hold-seconds 30
```

Required:

- `check` passes without browser action or Git mutation;
- no-op attaches for >=30 s without typing/clicking/navigation/page creation/page close/context close/browser close;
- exact target URL/title metadata is unchanged before/after;
- dedicated Chrome remains alive and usable.

If no-op fails, stop and return `REVISIONS_REQUIRED`; do not navigate/repair the browser from the bridge.

## 6. Exactly-once blank-repo autowake E2E

Start the standalone daemon:

```powershell
webgpt-bridge daemon --config <LOCAL_CONFIG>
```

Create a fresh unique blank-repo handoff ID. Commit/push trivial demo work first and record its real remote-contained code commit SHA.

Run:

```powershell
webgpt-bridge finalize --config <LOCAL_CONFIG> --handoff <FRESH_ID> --code-commit <SHA>
```

Verify the generated `claude_work_complete.json` stores the resolved real code commit. Commit and push only that doorbell as the **FINAL push** for the demo handoff.

### Mandatory observation

**Do not type `fetch` manually.** Do not use the embedded RL_Stock bridge for this demo handoff.

Expected sequence:

```text
blank repo claude_work_complete.json remote
-> standalone daemon auto-discovers marker only
-> exactly one browser-generated `fetch <FRESH_ID>` reaches Web ChatGPT
-> standalone trigger_fetch_sent.json remote
-> Web ChatGPT immediate chatgpt_fetch_ack.json
-> Web ChatGPT substantive review
-> Web ChatGPT chatgpt_review_published.json
```

The Web reviewer may use the handoff only as an infrastructure acceptance smoke; no RL_Stock research work is authorized by this demo.

## 7. Duplicate / crash-safety checks

After successful E2E:

- run another standalone scan or restart the standalone daemon; same handoff must not be sent again;
- rerun `finalize` for the same handoff; duplicate doorbell must fail closed;
- confirm no force push occurred;
- confirm target browser tab remains open and unchanged;
- inspect local runtime `dedup.json` and confirm the handoff is terminally recorded as sent.

Unit tests must already cover the pre-browser `attempt_started` crash window. If practical without risking the successful target, additionally simulate that state in a non-browser/fake test and confirm restart does not invoke a second sender.

If an ACK-before-trigger race occurs naturally, confirm reconciliation is marker-only. Do not intentionally create a second browser submission merely to force this race.

## 8. Validation report — no code fixes

Create one concise report under:

```text
tools/webgpt_wake_bridge/docs/validation_reports/
```

Include:

- exact candidate commit tested;
- package version;
- exact commands;
- pytest pass/fail count;
- Python/Playwright/Chrome/Windows versions;
- blank demo repo path/name and remote HEAD;
- E2E handoff ID;
- doorbell/trigger/ACK/review marker evidence and order;
- proof no user-typed `fetch` was used;
- duplicate/no-resend evidence;
- any warnings or defects;
- final recommendation exactly one of:

```text
ACCEPT_1_0_0
REVISIONS_REQUIRED
```

If `REVISIONS_REQUIRED`, do not edit package code in this validation session. Report the smallest reproducible defect and stop.

If `ACCEPT_1_0_0`, do not bump the version yourself; Web ChatGPT will review the evidence and perform/authorize release promotion separately.

## 9. Return result to Web ChatGPT

After the validation report/status is committed and pushed, use the existing accepted RL_Stock handoff protocol only to surface the **validation result** to Web ChatGPT. Publish the required fresh doorbell LAST so the already accepted embedded V1 can automatically wake Web ChatGPT.

This final return path is transport for the test report only; it must not modify the standalone candidate being tested after the recorded candidate commit.
