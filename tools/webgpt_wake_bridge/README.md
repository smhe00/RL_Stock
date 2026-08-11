# WebGPT Wake Bridge

Project-agnostic local infrastructure for waking one dedicated Web ChatGPT reviewer conversation from a durable Git handoff marker.

## Status

- Package candidate: **`0.9.0rc2`**
- Protocol compatibility: **`web_fetch_bridge_v1`**
- rc1 independent validation: core passed, multi-project Web routing defect found
- rc2 correction: explicit `owner/repo` routing + GitHub-remote consistency guard
- Independent Windows + Chrome/CDP + Web-accessible blank GitHub repository E2E: pending fresh Claude validation
- Promotion rule: only a passing independent E2E may promote this candidate to `1.0.0 / E2E VERIFIED`
- The accepted embedded RL_Stock V1 remains the rollback/reference implementation until standalone acceptance.

## What it does

A consumer project publishes one append-only review doorbell:

```text
<marker_root>/<handoff_id>/claude_work_complete.json
```

The standalone daemon watches only Git markers, attaches as a non-owning guest to an already-open dedicated Chrome/ChatGPT conversation, and submits exactly one routed wake message:

```text
fetch repo=<owner/repo> handoff=<handoff_id>
```

Web ChatGPT can therefore resolve the correct GitHub repository before writing `chatgpt_fetch_ack.json` and the final review marker.

The bridge does **not** parse project status YAML, research gates, issue states, trading logic, or business-domain files.

## Multi-project routing rule

For `once` / `daemon`, local config must contain:

```toml
[review]
repository = "owner/repo"
```

The configured project Git remote must itself resolve to the same `github.com/owner/repo`. The bridge validates this before touching the browser.

This deliberately means a local-only bare remote is **not** eligible for full Web review E2E in rc2. Such projects need a future Web-accessible hub/mirror mode; rc2 fails closed rather than sending an unroutable wake.

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
- A local `attempt_started` record + immutable trigger payload are persisted before browser interaction, so process crash cannot cause automatic resend on restart.
- Sender failure or uncertain submission is terminal until explicit operator retry.
- ACK-before-trigger recovery is marker-only; browser is never called again for that receipt.
- Live browser send requires an explicit `owner/repo` locator matching the configured GitHub remote.
- CDP endpoint must be exactly `http://127.0.0.1:<port>`.
- The exact dedicated `https://chatgpt.com/c/...` tab must already be open.
- Browser attachment is non-owning: no navigation, page creation, page/context close, or browser close.
- Composer targeting is semantic + visibility-aware; hidden fallback textarea is excluded; ambiguity fails closed.
- Submission confirmation reads only local composer/input state while the exact target URL remains unchanged.
- Login/challenge probes use structural DOM metadata, not conversation text.
- Assistant output is never scraped to determine send or review completion.
- Git marker writes are append-only; no force push.
- Conversation URL, credentials and cookies stay local and never belong in protocol markers.

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

## Fast reuse in another project

Generate a local configuration outside the consumer repository by default:

```powershell
webgpt-bridge init --repo D:\work\my_project --review-repository owner/repo
```

Then set only the dedicated reviewer conversation URL in the generated local TOML:

```toml
[review]
repository = "owner/repo"

[browser]
target_conversation_url = "https://chatgpt.com/c/<dedicated-reviewer-conversation>"
```

The local project `origin` (or configured remote) must point at the same GitHub repository.

## Validate local setup

```powershell
webgpt-bridge check --config <LOCAL_CONFIG>
webgpt-bridge noop --config <LOCAL_CONFIG> --hold-seconds 30
webgpt-bridge once --config <LOCAL_CONFIG>
webgpt-bridge daemon --config <LOCAL_CONFIG>
```

`check` and `noop` do not require a Web review repository to be reachable. `once` and `daemon` do: they fail closed before browser interaction if the repository locator is missing, local-only, or mismatched.

## Agent finalization

After project work, status and review packet are committed, pushed and remote-confirmed:

```powershell
webgpt-bridge finalize --config <LOCAL_CONFIG> --handoff <HANDOFF_ID> --code-commit <SHA>
```

The helper verifies the referenced commit is real, contained in the configured remote branch, and the worktree is clean. It creates only `claude_work_complete.json`; the agent commits/pushes that marker as the final review-requesting push.

## Explicit recovery

```powershell
webgpt-bridge retry --config <LOCAL_CONFIG> --handoff <HANDOFF_ID>
webgpt-bridge reconcile --config <LOCAL_CONFIG> --handoff <HANDOFF_ID>
```

Retry is explicit only. Reconciliation is marker-only.

## Final acceptance

The independent procedure is in `docs/FINAL_CLAUDE_TEST_PLAN.md`.

The next acceptance smoke must use a **fresh Web-accessible GitHub demo repository**, not a local bare remote, and must prove without user-typed `fetch`:

```text
doorbell LAST
-> standalone daemon
-> fetch repo=<owner/repo> handoff=<id>
-> Web ChatGPT resolves repo
-> immediate ACK
-> review_published
-> duplicate scan/restart does not resend
```

Do not label the package `1.0.0 / E2E VERIFIED` or migrate RL_Stock until that passes.

Reverse Web-to-agent process launch/wake remains out of scope for Protocol V1.
