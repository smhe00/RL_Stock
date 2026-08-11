# WebGPT Wake Bridge Standalone 0.9.0rc1 — Independent Validation Report

## Recommendation

```text
REVISIONS_REQUIRED
```

The standalone package core (init / check / noop / finalize / marker-only daemon /
exactly-once CDP fetch / trigger publication / dedup no-resend) works. The blank-repo
autowake E2E **failed to complete its Web-side ACK loop** because the wake message
carries no project/repository identity, so the remote Web ChatGPT reviewer cannot
resolve the consumer repository to publish ACK/review markers back into it.

## 1. Candidate under test

| Item | Value |
|---|---|
| Candidate commit | `2844ddd4750265321136b866d2ecb973d3eb9011` |
| Package version | `0.9.0rc1` (`webgpt-bridge --version`) |
| Repo sync | `HEAD == origin/main == 2844ddd`, clean worktree at start |
| Python | 3.12.10 |
| Playwright | 1.62.0 (installed in fresh standalone venv) |
| pytest | 9.1.1 |
| Chrome (CDP) | 151.0.7922.76 |
| Windows | 10.0.19045.6466 |

Fresh environment: `python -m venv .venv` in `tools/webgpt_wake_bridge/`, then
`pip install -e ".[test]"`. Package installed as `webgpt-wake-bridge-0.9.0rc1`.

## 2. Static safety verification (independent review) — PASS

- No RL_Stock research/status YAML parsing: source references only marker filenames
  (`chatgpt_review_published.json` etc.), never `CLAUDE_STATUS.yaml` /
  `CHATGPT_REVIEW.yaml` / gates / research results. PASS.
- Non-owning browser: `browser.py` has no `page.goto`, `new_page`, `page.close`,
  `context.close`, or `browser.close`; only `driver.stop()` on the owned Playwright
  driver. PASS.
- No auto-resend: `bridge.py`/`browser.py` contain no resend/retry loop that re-injects
  a fetch. PASS.
- No assistant-output scraping: `_composer_text` reads only the input element's local
  state; login/challenge probes are structural selectors. PASS.
- Exact target conversation required (`chatgpt.com/c/...`, path `/c/`). PASS.
- CDP endpoint exact loopback only (`http://127.0.0.1:<port>`). PASS.
- Git transport: `transport_git.py` uses only non-force `push HEAD:branch`, syncs the
  isolated worktree to latest remote before publish, validates marker payload before
  publication, and raises on Git failure (never converts a Git error into marker
  absence). PASS.

## 3. Unit tests

```text
python -m pytest   ->   38 passed, 0 failed
```

Full suite in the fresh standalone venv. PASS.

## 4. Blank consumer repository + `init` — PASS

Disposable blank repo (no RL_Stock state):

```text
path:    C:\Users\peter\AppData\Local\Temp\wgb_blank_demo\blank_repo
remote:  C:\Users\peter\AppData\Local\Temp\wgb_blank_demo\blank_origin.git  (bare, local)
HEAD:    f15b805d1e2dbba4c85018a9e76e3796c4060535
content: README.md, demo.txt, docs/web_bridge/<handoff>/...
```

Bootstrap (standalone CLI, not copied config):

```text
webgpt-bridge init --repo <blank_repo> --config-path ...\bridge.local.toml --runtime-dir ...\runtime
```

Verified:
- generated config + runtime live **outside** the blank consumer repo; PASS
- blank repo untouched by `init` (clean worktree); PASS
- `target_conversation_url` blank until operator filled it; PASS

Local config filled with the dedicated already-open Web ChatGPT reviewer conversation
`https://chatgpt.com/c/6a78742a-f90c-83ee-9761-3bd204d8ace0`.

## 5. Local safety checks — PASS

```text
webgpt-bridge check --config <local>     -> PASS (no browser action, no git mutation)
webgpt-bridge noop --config <local> --hold-seconds 30 -> PASS
```

Target URL/title identical before/after noop; dedicated Chrome stayed alive. PASS.

## 6. Blank-repo autowake E2E — PARTIAL (FAILED at Web ACK loop)

Fresh handoff:

```text
WEBGPT_WAKE_BRIDGE_STANDALONE_BLANK_DEMO_001
```

Sequence observed on the blank remote (`origin/main`):

```text
f15b805  claude_work_complete.json   (standalone finalize, FINAL push, tz-aware UTC,
                                      code_commit=ae5c50a real remote demo commit)
2ea7418  trigger_fetch_sent.json     (standalone daemon, exactly one fetch)
```

Daemon evidence (`runtime/logs/webgpt_wake_bridge.log`):

```text
event=bridge_daemon_started
event=bridge_scan outcomes=WEBGPT_WAKE_BRIDGE_STANDALONE_BLANK_DEMO_001:FETCH_SENT
```

- The standalone daemon auto-discovered the doorbell from `origin/main` (no
  `CLAUDE_STATUS.yaml` parse). PASS.
- It submitted exactly one browser-generated `fetch WEBGPT_WAKE_BRIDGE_STANDALONE_BLANK_DEMO_001`
  (composer filled then cleared = submission positively confirmed; read-only probe
  showed composer `prompt-textarea` visible and empty). PASS.
- The user did **not** type `fetch` at any point. PASS (no manual action performed).
- `trigger_fetch_sent.json` published. PASS.

**FAILED**: Web ChatGPT `chatgpt_fetch_ack.json` never arrived within ~16 minutes
(polled `origin/main`; only 2 markers present, no ACK). Target tab title stayed
`L1结果通过但需修正文案` and the message-author structural count stayed unchanged
(user=2, assistant=3).

### Root-cause defect (smallest reproducible)

The standalone wake message is only:

```text
fetch WEBGPT_WAKE_BRIDGE_STANDALONE_BLANK_DEMO_001
```

It carries **no project / repository identity**. The remote Web ChatGPT reviewer that
receives the fetch has no way to resolve which Git repository (and remote) holds the
handoff markers, so it cannot publish `chatgpt_fetch_ack.json` /
`chatgpt_review_published.json` back. In this blank-repo smoke the consumer remote is a
local bare repository that a remote reviewer cannot reach at all — but even with a
reachable remote, the reviewer cannot *know* which one without a locator in the message.

This is the single-project → multi-project reuse gap: the embedded single-project
bridge worked because the reviewer already knew the one RL_Stock repository. The
standalone generalization drops that implicit identity and never re-adds it explicitly.

Reproduce: start standalone daemon against any fresh blank repo, finalize a fresh
handoff, let the daemon send exactly one fetch. The fetch reaches the conversation but
no Web ACK is ever published because the reviewer cannot resolve the repo.

## 7. Duplicate / crash-safety checks — PASS

- Restart/scan of the daemon: the same handoff was **not** sent again (dedup
  `fetch_sent` terminal; log shows no second `fetch_send_start`). PASS.
- Rerun `finalize` for the same handoff:

```text
webgpt-bridge error: doorbell already exists locally; append-only fail closed   (exit 2)
```

  PASS (fail-closed).
- No force-push: blank remote history is linear (4 commits). PASS.
- Target tab remained open and unchanged. PASS.
- `dedup.json` records the handoff terminally as `fetch_sent` and includes the
  `attempt_started` crash-safe field (empty here). PASS.
- `attempt_started` pre-browser crash window is covered by unit tests (38 passed).
  PASS.

## 8. Environment versions

```text
Python   3.12.10
Playwright 1.62.0
Chrome   151.0.7922.76 (CDP on 127.0.0.1:9222)
Windows  10.0.19045.6466
```

## 9. Defect summary / recommendation

- Recommendation: **REVISIONS_REQUIRED**
- Defect: wake message lacks a stable project/repository locator, so the Web reviewer
  cannot route ACK/review markers back to the correct consumer repository.
- Suggested direction (not implemented, no code changes made in this validation):
  include a repo locator in the wake message, e.g.
  `fetch smhe00/webgpt-wake-bridge-demo WEBGPT_WAKE_BRIDGE_STANDALONE_BLANK_DEMO_001`
  or structured `fetch project=<project_id> handoff=<handoff_id>`, letting the reviewer
  resolve the GitHub repo, read the handoff markers, and immediately ACK. A fixed
  "wake hub" repository is a viable long-term option for local/air-gapped consumer
  remotes.

No standalone package source was modified during this validation. The accepted
embedded Web Fetch Bridge V1 was not modified.
