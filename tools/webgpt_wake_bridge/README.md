# WebGPT Wake Bridge

Project-agnostic local infrastructure for waking a dedicated Web ChatGPT reviewer conversation from a Git handoff marker.

## Status

- Package: `0.2.0.dev0`
- Protocol compatibility: `web_fetch_bridge_v1`
- Extraction implementation: **complete enough for independent verification**
- Real Windows/Chrome blank-repo E2E: **pending final Claude validation**
- Accepted embedded RL_Stock V1 remains untouched and is still the production reference until standalone acceptance.

## What it does

A consumer project publishes one append-only review doorbell:

```text
<marker_root>/<handoff_id>/claude_work_complete.json
```

The standalone daemon watches only Git markers, connects as a non-owning guest to an already-open dedicated Chrome/ChatGPT conversation, submits exactly one:

```text
fetch <handoff_id>
```

and publishes `trigger_fetch_sent.json`. Web ChatGPT then uses the same durable protocol for ACK/review markers.

The bridge does **not** parse project status YAML, research gates, issue states, trading logic, or business-domain files.

## Protocol

Default marker root:

```text
docs/web_bridge/<handoff_id>/
```

Sequence:

```text
claude_work_complete.json
  -> trigger_fetch_sent.json
  -> chatgpt_fetch_ack.json
  -> chatgpt_review_published.json
  -> claude_review_ack.json
```

The bridge owns only `trigger_fetch_sent.json`.

## Safety invariants

- Git remote is the durable source of truth.
- Review triggering is marker-only and project-state-agnostic.
- `claude_work_complete.json` is the mandatory review doorbell and is pushed LAST by the agent.
- Browser submit is exactly-once per locally recorded attempt; sender failure is terminal until explicit retry.
- Browser send-success is persisted locally **before** Git trigger publication, preventing crash/race-driven browser resend.
- ACK-before-trigger races are reconciled marker-only; reconciliation never touches the browser.
- CDP endpoint must be localhost.
- Exact dedicated `https://chatgpt.com/c/...` tab must already be open.
- No `goto`, `new_page`, page/context close, or `browser.close()`.
- Hidden fallback textarea is excluded; ambiguous composer fails closed.
- Submission confirmation reads composer state only; assistant output is never scraped.
- Marker writes are append-only; no force push.
- Conversation URL, cookies and credentials stay in ignored local config.

## Layout

```text
tools/webgpt_wake_bridge/
├─ pyproject.toml
├─ config/bridge.example.toml
├─ scripts/
│  ├─ start_chrome_cdp.bat
│  └─ run_daemon.bat
├─ docs/
│  ├─ PROTOCOL.md
│  ├─ ACCEPTANCE.md
│  ├─ MIGRATION_PLAN.md
│  ├─ INTEGRATION_CLAUDE.md
│  └─ FINAL_CLAUDE_TEST_PLAN.md
├─ src/webgpt_wake_bridge/
│  ├─ markers.py
│  ├─ config.py
│  ├─ browser.py
│  ├─ transport_git.py
│  ├─ bridge.py
│  ├─ finalize.py
│  └─ cli.py
└─ tests/
```

## Install for development

From this directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[test]"
```

Chrome is externally managed; the bridge attaches to it over CDP.

## Configure one consumer project

Copy:

```text
config/bridge.example.toml -> bridge.local.toml
```

Set `repo_root` to the consumer repository and put the exact dedicated reviewer conversation URL in the local file. Never commit that local TOML.

Validate without browser action or Git mutation:

```powershell
webgpt-bridge check --config .\bridge.local.toml
```

Optional 30-second non-owning CDP lifecycle probe:

```powershell
webgpt-bridge noop --config .\bridge.local.toml --hold-seconds 30
```

Run one marker scan or the daemon:

```powershell
webgpt-bridge once --config .\bridge.local.toml
webgpt-bridge daemon --config .\bridge.local.toml
```

## Agent finalization

After packet/status work is committed, pushed and remote-confirmed:

```powershell
webgpt-bridge finalize --config .\bridge.local.toml --handoff <HANDOFF_ID> --code-commit <SHA>
```

This creates only `claude_work_complete.json` locally. The agent must commit/push that marker as the **FINAL push** of the review-requesting handoff.

## Release rule

Do not label this subtree `1.0.0 / E2E VERIFIED` and do not switch RL_Stock to it until `docs/FINAL_CLAUDE_TEST_PLAN.md` passes in a clean demo repository with no user-typed `fetch`.
