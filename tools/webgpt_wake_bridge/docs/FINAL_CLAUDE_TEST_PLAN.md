# Final Claude validation plan

Claude participates only at the final independent validation stage. It should not redesign the package unless a test exposes a concrete defect.

## Scope

Validate `tools/webgpt_wake_bridge/` only. Do not modify the accepted embedded `scripts/web_fetch_bridge.py` or `scripts/finalize_handoff.py` during this test.

## 1. Fresh environment

From `tools/webgpt_wake_bridge`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[test]"
webgpt-bridge --version
pytest
```

Record Python, Playwright, Chrome and Windows versions.

## 2. Static safety checks

Confirm package source contains no consumer-project business imports or state parsing. Confirm normal browser path contains none of:

```text
page.goto
new_page
page.close
context.close
browser.close
```

Confirm no ChatGPT assistant-output parsing exists.

## 3. Blank consumer repository

Create a new disposable Git repository with only:

```text
README.md
docs/web_bridge/
```

Create a bare/local remote (or disposable GitHub test repository), set `main`, and ensure local/remote HEAD agree.

Create an ignored `bridge.local.toml` pointing to this blank repo and the existing dedicated Web ChatGPT reviewer conversation.

Run:

```powershell
webgpt-bridge check --config .\bridge.local.toml
webgpt-bridge noop --config .\bridge.local.toml --hold-seconds 30
```

Both must pass with the exact target conversation unchanged.

## 4. Exactly-once autowake E2E

Start:

```powershell
webgpt-bridge daemon --config .\bridge.local.toml
```

Create a fresh unique handoff id. Commit/push any trivial demo work first, then run:

```powershell
webgpt-bridge finalize --config .\bridge.local.toml --handoff <FRESH_ID> --code-commit <SHA>
```

Commit and push the generated `claude_work_complete.json` as the FINAL push.

### Mandatory observation

Do **not** type `fetch` manually.

Expected sequence:

```text
claude_work_complete.json remote
-> daemon auto-discovers
-> exactly one browser-generated `fetch <FRESH_ID>` reaches Web ChatGPT
-> trigger_fetch_sent.json remote
-> Web ChatGPT chatgpt_fetch_ack.json
-> Web ChatGPT review + chatgpt_review_published.json
```

## 5. Failure/duplicate checks

After the successful send:

- restart/scan daemon; confirm the same handoff is not sent again;
- rerun finalize for the same handoff; it must fail closed;
- no force-push may occur;
- browser target remains open and unchanged.

If practical, simulate an ACK-before-trigger publication race and confirm marker-only reconciliation publishes only the missing trigger marker without a second browser call.

## 6. Evidence packet

Return one concise validation report containing:

- package commit tested;
- exact commands;
- pytest pass/fail count;
- blank demo repo HEAD;
- E2E handoff id;
- marker commit/order evidence;
- proof no user-typed fetch was used;
- any warnings or defects;
- final recommendation: `ACCEPT_1_0_0` or `REVISIONS_REQUIRED`.

Do not switch RL_Stock to the standalone package as part of this validation.
