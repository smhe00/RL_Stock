# WebGPT Wake Bridge

Project-agnostic local infrastructure for waking one dedicated Web ChatGPT reviewer conversation from a durable Git handoff marker.

## Status

- Package candidate: **`0.9.0rc1`**
- Protocol compatibility: **`web_fetch_bridge_v1`**
- Structural extraction / hardening: complete
- Independent Windows + Chrome/CDP + blank-repository E2E: pending final Claude validation
- Promotion rule: only a passing independent E2E may promote this candidate to `1.0.0 / E2E VERIFIED`
- The already accepted embedded RL_Stock V1 remains untouched and is still the rollback/reference implementation until standalone acceptance.

## What it does

A consumer project publishes one append-only review doorbell:

```text
<marker_root>/<handoff_id>/claude_work_complete.json
```

The standalone daemon watches only Git markers, attaches as a non-owning guest to an already-open dedicated Chrome/ChatGPT conversation, and submits exactly one:

```text
fetch <handoff_id>
```

It then publishes `trigger_fetch_sent.json`. Web ChatGPT uses the same durable protocol for immediate ACK and review-published markers.

The bridge does **not** parse project status YAML, research gates, issue states, trading logic, or business-domain files.

## Protocol cycle

Default marker root:

```text
docs/web_bridge/<handoff_id>/
```

One review cycle is:

```text
claude_work_complete.json
  -> trigger_fetch_sent.json
  -> chatgpt_fetch_ack.json
  -> chatgpt_review_published.json
  -> claude_review_ack.json
```

The bridge owns only `trigger_fetch_sent.json`; all other markers are observed read-only.

## Safety invariants

- Git remote is the durable source of truth.
- Trigger decisions are marker-only and project-state-agnostic.
- `claude_work_complete.json` is the mandatory review doorbell and is pushed LAST by the agent.
- A local `attempt_started` record + immutable trigger payload are persisted **before browser interaction**. A process crash therefore cannot cause an automatic resend on restart.
- Sender failure or uncertain submission is terminal until an explicit operator retry.
- If Web ACK proves a crashed/uncertain submission arrived, the missing trigger marker is reconciled marker-only; the browser is never called again for that receipt.
- CDP endpoint is parsed and must be exactly `http://127.0.0.1:<port>`.
- The exact dedicated `https://chatgpt.com/c/...` tab must already be open.
- Browser attachment is non-owning: no navigation, page creation, page/context close, or browser close.
- Composer targeting is semantic + visibility-aware; hidden fallback textarea is excluded; non-unique selectors fail closed.
- Submission confirmation reads only composer/input state while the exact target URL remains unchanged.
- Login/challenge probes use structural DOM metadata, not conversation text.
- Assistant output is never scraped to determine send or review completion.
- Git marker writes are append-only; no force push.
- Remote/branch/path configuration is validated conservatively.
- Conversation URL, cookies and credentials stay in local config and never belong in protocol markers.

## Install for validation/development

From `tools/webgpt_wake_bridge`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[test]"
webgpt-bridge --version
pytest
```

The bridge connects to an externally managed Chrome over CDP; it does not require a Playwright-managed browser lifecycle.

## Fast reuse in another project

Generate a project-local configuration **outside the consumer repository by default**:

```powershell
webgpt-bridge init --repo D:\work\my_project
```

The command prints the generated `*.local.toml` path. Its default runtime directory is also outside the consumer repository, under the user's local home tree. `init` does not modify consumer project files or Git state.

Edit only the generated local file and set:

```toml
target_conversation_url = "https://chatgpt.com/c/<dedicated-reviewer-conversation>"
```

Keep that URL local and untracked.

If desired, `config/bridge.example.toml` is also available as a manual template.

## Start the dedicated Chrome session

A convenience script is provided for Windows:

```text
scripts/start_chrome_cdp.bat
```

It is operator-invoked only. The bridge daemon never launches, navigates, repairs, or closes Chrome automatically. Log in to ChatGPT in that dedicated profile and open the exact reviewer conversation before running the bridge.

## Validate local setup

No browser action / no Git mutation:

```powershell
webgpt-bridge check --config <LOCAL_CONFIG>
```

30-second non-owning lifecycle probe:

```powershell
webgpt-bridge noop --config <LOCAL_CONFIG> --hold-seconds 30
```

Run one scan or the daemon:

```powershell
webgpt-bridge once --config <LOCAL_CONFIG>
webgpt-bridge daemon --config <LOCAL_CONFIG>
```

## Agent finalization

After project work, status and review packet are committed, pushed and remote-confirmed:

```powershell
webgpt-bridge finalize --config <LOCAL_CONFIG> --handoff <HANDOFF_ID> --code-commit <SHA>
```

The helper verifies that `code_commit` is a real commit already contained in the configured remote branch. It creates only `claude_work_complete.json` locally. The agent must commit/push that marker as the **FINAL push** of the review-requesting handoff.

Then the agent stops and waits for `chatgpt_review_published.json`.

## Explicit recovery commands

An uncertain/failed attempt is never automatically retried:

```powershell
webgpt-bridge retry --config <LOCAL_CONFIG> --handoff <HANDOFF_ID>
```

Use this only after an operator has decided a new browser attempt is appropriate.

If Web ACK already proves receipt and only `trigger_fetch_sent.json` is missing:

```powershell
webgpt-bridge reconcile --config <LOCAL_CONFIG> --handoff <HANDOFF_ID>
```

Reconciliation is marker-only and never touches the browser.

## Package layout

```text
tools/webgpt_wake_bridge/
├─ pyproject.toml
├─ config/bridge.example.toml
├─ scripts/
├─ docs/
├─ src/webgpt_wake_bridge/
│  ├─ bootstrap.py
│  ├─ markers.py
│  ├─ config.py
│  ├─ browser.py
│  ├─ transport_git.py
│  ├─ bridge.py
│  ├─ finalize.py
│  └─ cli.py
└─ tests/
```

## Final acceptance

The exact independent validation procedure is in `docs/FINAL_CLAUDE_TEST_PLAN.md`.

Do not label this package `1.0.0 / E2E VERIFIED` and do not migrate RL_Stock to it until that plan passes in a blank consumer repository **without any user-typed `fetch`**.

Reverse Web-to-agent process launch/wake is intentionally out of scope for Protocol V1.
