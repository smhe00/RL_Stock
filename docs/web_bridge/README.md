# Web Fetch Bridge V1 — marker-driven wake-up bridge

Web ChatGPT remains the planner/reviewer. This local trigger only replaces the
manual `fetch <handoff_id>` keystroke into the dedicated Web ChatGPT conversation.

Authoritative spec: `docs/reviewer_responses/WEB_FETCH_BRIDGE_V1_USER_AUTHORIZATION.md`.

## Architecture rule

The wake-up bridge is **fully decoupled** from the research/reviewer protocol.

- Research protocol (canonical): `docs/agent_state/CLAUDE_STATUS.yaml`,
  `docs/review_packets/`, `docs/reviewer_state/CHATGPT_REVIEW.yaml`,
  `docs/reviewer_responses/`.
- Wake-up protocol: independent **append-only markers** under
  `docs/web_bridge/<handoff_id>/`.
- The trigger NEVER parses or interprets research states (READY_FOR_REVIEW,
  BLOCKED, PREP, RUN, M2, 03110, `authorized_next`, …). Its only semantic action
  is: detect marker state → send exactly one `fetch <handoff_id>` → wait for
  marker progress.
- GitHub remains the canonical audit/transport bus for bridge markers.

## Marker protocol (ownership + order)

| marker | owner | means |
|---|---|---|
| `claude_review_ack.json` | Claude | consumed the preceding matching review |
| `claude_work_complete.json` | Claude | work + commit + push complete (wake-up doorbell) |
| `trigger_fetch_sent.json` | bridge | exactly one `fetch <handoff_id>` submitted |
| `chatgpt_fetch_ack.json` | Web ChatGPT | fetch received (before substantive review) |
| `chatgpt_review_published.json` | Web ChatGPT | review + CHATGPT_REVIEW.yaml published (last) |

Each marker is immutable once created. No actor modifies another actor's marker.
There is no shared mutable bridge YAML.

Marker minimum fields:

```json
{
  "protocol": "web_fetch_bridge_v1",
  "handoff_id": "...",
  "event": "claude_work_complete.json",
  "timestamp": "2026-08-11T00:00:00+00:00"
}
```

Markers must NOT duplicate full review contents or contain credentials/account data.

## Trigger state machine (marker existence only)

For a handoff with `claude_work_complete.json`:

- `chatgpt_review_published.json` exists → **DONE**; never send.
- `chatgpt_fetch_ack.json` exists → **WAIT_FOR_REVIEW**; never send.
- `trigger_fetch_sent.json` exists → **WAIT_FOR_FETCH_ACK**; never resend.
- otherwise → send exactly one `fetch <handoff_id>`, then write `trigger_fetch_sent.json`.

If no `chatgpt_fetch_ack.json` appears within the configured timeout (default
120 s), the bridge fails closed and logs/notifies. **It never auto-resends.**
Operator retry must be explicit.

## CDP / browser requirements

- Playwright/Python `chromium.connect_over_cdp()` to a **dedicated** Chrome/Chromium
  profile.
- Remote-debugging endpoint must be localhost only (`http://127.0.0.1:9222`).
- The dedicated profile must contain only the ChatGPT session; never reuse a profile
  with broker/banking/mail/sensitive sessions.
- Fail closed on login screen, CAPTCHA/challenge, wrong conversation, missing
  composer, ambiguous tabs, or Playwright/CDP timeout.
- The bridge never scrapes/parses ChatGPT output. Review completion is known only
  through GitHub `chatgpt_review_published.json`.

The dedicated ChatGPT conversation URL lives **only** in the ignored local config
`config/web_fetch_bridge.local.toml` (already covered by `*.local.toml` in
`.gitignore`). Never commit the URL, auth material, cookies, or profile data.

## Setup

1. `pip install playwright && playwright install chromium` (one-time).
2. Start a dedicated Chrome with CDP:
   `chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\ChatGPT_Automation_Profile"`
   and log into ChatGPT in that profile.
3. Copy `config/web_fetch_bridge.example.toml` → `config/web_fetch_bridge.local.toml`
   and fill `target_conversation_url` with the dedicated conversation URL (local only).

## Usage

```bash
# deterministic fail-closed gates (no browser, no git mutation, no codex exec)
python scripts/web_fetch_bridge.py --config config/web_fetch_bridge.local.toml --check

# send exactly one fetch for a handoff whose claude_work_complete.json exists
python scripts/web_fetch_bridge.py --config config/web_fetch_bridge.local.toml --handoff H-0001 --wait-ack

# Windows
scripts\web_fetch_bridge.bat --check
scripts\web_fetch_bridge.bat --handoff H-0001 --wait-ack
```

## Ownership / fail-closed

- The bridge only ever writes `trigger_fetch_sent.json`. All other markers are
  read-only observations.
- Bridge markers are append-only: a second write to an existing bridge marker is
  rejected.
- Default bridge mode MUST NOT invoke the local codex reviewer (`codex exec`).
  The optional local-Codex unattended mode remains isolated in
  `scripts/local_reviewer_watcher.py` and is never used by this bridge.
