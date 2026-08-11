# Final Claude validation plan — rc2 test only

Claude is the independent validator. **Do not modify standalone implementation code during validation.** Any defect => write evidence, return `REVISIONS_REQUIRED`, stop.

## Candidate

Validate only `tools/webgpt_wake_bridge/`.

Expected version:

```text
0.9.0rc2
```

Do not modify embedded `scripts/web_fetch_bridge.py` / `scripts/finalize_handoff.py`. Do not migrate RL_Stock.

## 1. Freeze candidate

```powershell
git fetch origin
git status --short
git rev-parse HEAD
git rev-parse origin/main
```

Require clean worktree and equal HEADs. Record exact candidate commit.

## 2. Fresh environment

From `tools/webgpt_wake_bridge`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[test]"
webgpt-bridge --version
pytest
```

Require version `0.9.0rc2` and all tests PASS. Record Python, Playwright, Chrome, Windows versions.

## 3. Independent static checks

Confirm:

- no RL_Stock business/research state dependency;
- routed payload is `fetch repo=<owner/repo> handoff=<id>`;
- live browser commands require `[review].repository`;
- configured Git remote must resolve to the same github.com owner/repo before browser interaction;
- local-only/non-GitHub remote fails closed before browser interaction;
- no browser navigation/lifecycle ownership;
- no assistant-output scraping;
- no automatic resend;
- no force push;
- Git failures are not treated as marker absence.

## 4. Create a fresh Web-accessible blank GitHub demo repository

The rc1 local-bare-repo smoke is intentionally not reused.

Create one disposable **private GitHub repository** under the authenticated user account, with a unique name such as:

```text
webgpt-wake-bridge-demo-<timestamp>
```

Use `gh repo create ... --private` if authenticated. The repository must contain only trivial demo content and `docs/web_bridge/...`; do not copy RL_Stock reviewer/status files.

Keep this GitHub repository alive until Web ChatGPT has completed ACK/review for the smoke. Do not delete it during validation.

Record exact `owner/repo`, remote URL and HEAD.

## 5. Bootstrap standalone config

Use:

```powershell
webgpt-bridge init \
  --repo <BLANK_GITHUB_REPO_WORKTREE> \
  --review-repository <OWNER/REPO>
```

Confirm config/runtime are outside the blank repo by default and `init` did not modify tracked project content.

Set only the existing dedicated reviewer conversation URL in the local config.

## 6. Local safety probes

With dedicated Chrome already open on CDP:

```powershell
webgpt-bridge check --config <LOCAL_CONFIG>
webgpt-bridge noop --config <LOCAL_CONFIG> --hold-seconds 30
```

Both must pass; exact target URL/title unchanged. Do not repair/navigate browser on failure.

Also deliberately test routing fail-closed in a separate disposable local-only repo/config: `once`/`daemon` must refuse before browser interaction because the remote is not github.com.

## 7. Fresh routed E2E

Start standalone daemon:

```powershell
webgpt-bridge daemon --config <LOCAL_CONFIG>
```

Create trivial demo work, commit/push it, then fresh unique handoff. Run:

```powershell
webgpt-bridge finalize --config <LOCAL_CONFIG> --handoff <FRESH_ID> --code-commit <SHA>
```

Commit/push only `claude_work_complete.json` as the FINAL review-request push.

**Do not type `fetch` manually. Do not use embedded RL_Stock bridge for the demo handoff.**

Expected exact routed wake:

```text
fetch repo=<OWNER/REPO> handoff=<FRESH_ID>
```

Expected durable sequence in the blank GitHub repo:

```text
claude_work_complete.json
-> trigger_fetch_sent.json
-> Web ChatGPT chatgpt_fetch_ack.json
-> Web ChatGPT substantive infrastructure review
-> Web ChatGPT chatgpt_review_published.json
```

The Web reviewer must resolve the repo from the wake payload itself; no implicit RL_Stock context is allowed.

## 8. Duplicate/exactly-once checks

After review-published:

- rescan/restart standalone daemon; no second browser fetch;
- duplicate finalize for same handoff fails closed;
- no force push;
- target browser tab remains open/unchanged;
- dedup state records terminal sent state.

## 9. Validation report

Write one new report under `tools/webgpt_wake_bridge/docs/validation_reports/` containing:

- candidate commit/version;
- exact commands + pytest count;
- environment versions;
- disposable GitHub `owner/repo` + HEAD;
- routed wake text;
- handoff ID;
- marker order/commits;
- proof no manual fetch;
- local-only remote fail-closed evidence;
- duplicate no-resend evidence;
- recommendation exactly `ACCEPT_1_0_0` or `REVISIONS_REQUIRED`.

Do not fix code if validation fails. Do not bump to 1.0.0 if it passes.

## 10. Return result

After report/status are pushed to RL_Stock, use the already accepted embedded V1 only as transport to wake Web ChatGPT with the validation result. That return handoff is separate from the blank demo E2E.
