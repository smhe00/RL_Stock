# Local Claude to Codex reviewer workflow

## Data flow

```text
Claude Code
  writes CLAUDE_STATUS.yaml + review_packets/, then pushes gate/checkpoint
          |
          v
local_reviewer_watcher.py (git fetch origin main every 60 seconds)
          |
          v
codex exec --sandbox read-only --ephemeral
  uses GitHub skill for remote context and returns schema-validated review JSON
          |
          v
watcher remote STOP-WRITE guard
          |
          +--> reviewer_responses/<handoff>_REVIEWER_RESPONSE.md
          +--> reviewer_state/CHATGPT_REVIEW.yaml
          |
reviewer-only commit + non-force push gate/checkpoint
          |
          v
Claude fetches and reads the matching reviewer response
          |
          v
GitHub checkpoint after local gate completion
```

The watcher does not start Claude. Its Git operations are limited to fetch,
fast-forward synchronization of a clean `main`, and an optional reviewer-only
gate/checkpoint commit and non-force push.

## Start on Windows

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_local_reviewer.ps1
```

The launcher prefers `.venv\Scripts\python.exe`, verifies that `codex` is on
`PATH`, creates the ignored runtime directories, and starts the watcher.

One scan only:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_local_reviewer.ps1 -Once
```

Use a private config override when needed:

```powershell
Copy-Item .\config\local_reviewer.example.toml .\config\local_reviewer.local.toml
powershell -ExecutionPolicy Bypass -File .\scripts\start_local_reviewer.ps1 `
  -ConfigPath .\config\local_reviewer.local.toml
```

`*.local.toml` is ignored. Do not put credentials in this file. `codex exec`
reuses the locally saved Codex CLI authentication. Git uses the repository's
existing `origin` credentials.

## State machine

```text
fetch failure ----------------------------------> RETRY_NEXT_MINUTE
non-trigger remote state -----------------------> IDLE
trigger state + missing READY packet ----------> WAITING_PACKET
trigger state + unseen handoff ----------------> INFLIGHT
INFLIGHT + Codex/process/schema failure --------> FAILED_NO_AUTO_RETRY
INFLIGHT + changed HEAD/status/packet ----------> STOP_WRITE_NO_AUTO_RETRY
INFLIGHT + valid stable result ----------------> COMPLETED
seen handoff -----------------------------------> DUPLICATE_IGNORED
```

Handoff processing records are stored in ignored
`runtime/local_reviewer/state.json`. An operator can explicitly retry a failed
or STOP-WRITE handoff:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_local_reviewer.ps1 `
  -RetryHandoff HANDOFF_ID -Once
```

Use this only after inspecting why the prior attempt stopped. A changed Claude
handoff should normally receive a new `handoff_id` instead.

## Logs

The watcher creates:

```text
runtime/local_reviewer/logs/local_reviewer.log
```

Logs rotate and are not committed. They contain operational metadata only, not
review contents or account/market data.

## Git checkpoint

By default, after the matching terminal reviewer state is safely produced:

1. The watcher verifies remote HEAD and remote Claude status again.
2. It fast-forwards a clean local `main` to the reviewed `origin/main`.
3. It writes only the reviewer response and reviewer state.
4. It stages only those two reviewer-owned files, commits them as a gate
   checkpoint, and pushes without force.
5. A rejected push or unexpected remote change is a STOP/FAILED condition; the
   watcher never rebases, force-pushes, or broadens the commit.

Set `publish_checkpoint = false` in a private config to require a manual
reviewer checkpoint instead.

The protocol therefore retains the web reviewer's GitHub synchronization model,
but reduces monitoring latency from roughly hourly to one minute.
