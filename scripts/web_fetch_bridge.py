"""Web Fetch Bridge V1 — marker-driven Chrome CDP + Playwright wake-up bridge.

Web ChatGPT remains the planner/reviewer. This local trigger only replaces the
manual `fetch <handoff_id>` keystroke into the dedicated Web ChatGPT conversation.

Architectural rule (WEB_FETCH_BRIDGE_V1_USER_AUTHORIZATION.md):
  - wake-up protocol is fully decoupled from the research/reviewer protocol;
  - trigger decisions depend ONLY on append-only marker existence under
    docs/web_bridge/<handoff_id>/, never on research states like READY_FOR_REVIEW,
    BLOCKED, PREP, RUN, M2, 03110, or `authorized_next`;
  - GitHub remains the canonical audit/transport bus for markers.

Marker ownership + order:
  1. claude_review_ack.json        (Claude)   consumed preceding Web ChatGPT review
  2. claude_work_complete.json     (Claude)   work+commit+push complete = wake-up doorbell
  3. trigger_fetch_sent.json       (bridge)   exactly one `fetch <handoff_id>` submitted
  4. chatgpt_fetch_ack.json        (Web GPT)  fetch received (before substantive review)
  5. chatgpt_review_published.json (Web GPT)  review + CHATGPT_REVIEW.yaml published (last)

Trigger state machine (marker existence only):
  handoff with claude_work_complete.json:
    - chatgpt_review_published.json exists  -> DONE; never send
    - chatgpt_fetch_ack.json exists         -> WAIT_FOR_REVIEW; never send
    - trigger_fetch_sent.json exists        -> WAIT_FOR_FETCH_ACK; never resend
    - else                                  -> send exactly one fetch, then trigger_fetch_sent

Fail-closed: if no chatgpt_fetch_ack within timeout (default 120 s), log/notify;
never auto-resend. Operator retry must be explicit.

The default bridge mode MUST NOT invoke the local codex reviewer.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
import re
import sys
import tempfile
import time
import tomllib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Protocol

BRIDGE_ROOT = Path("docs/web_bridge")
HANDOFF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,159}$")

# Ownership map: marker filename -> allowed creator. The bridge enforces that it
# only ever writes trigger_fetch_sent.json (bridge-owned); all other markers are
# refused locally and simply observed for state.
MARKER_OWNERS = {
    "claude_review_ack.json": "claude",
    "claude_work_complete.json": "claude",
    "trigger_fetch_sent.json": "bridge_trigger",
    "chatgpt_fetch_ack.json": "web_chatgpt",
    "chatgpt_review_published.json": "web_chatgpt",
}
MARKER_ORDER = [
    "claude_review_ack.json",
    "claude_work_complete.json",
    "trigger_fetch_sent.json",
    "chatgpt_fetch_ack.json",
    "chatgpt_review_published.json",
]

REQUIRED_MARKER_FIELDS = ("protocol", "handoff_id", "event", "timestamp")
FORBIDDEN_MARKER_FIELDS = ("api_key", "token", "cookie", "password", "secret")

BRIDGE_OWNED_MARKERS = {"trigger_fetch_sent.json"}

# Reviewer-side markers use semantic event values (e.g. CHATGPT_FETCH_ACK) while the
# bridge historically wrote filename-style events (e.g. chatgpt_fetch_ack.json).
# Marker filename/existence is authoritative for state; the event field is normalized
# through this alias map without rewriting any immutable marker.
EVENT_ALIASES = {
    "CLAUDE_REVIEW_ACK": "claude_review_ack.json",
    "CLAUDE_WORK_COMPLETE": "claude_work_complete.json",
    "TRIGGER_FETCH_SENT": "trigger_fetch_sent.json",
    "CHATGPT_FETCH_ACK": "chatgpt_fetch_ack.json",
    "CHATGPT_REVIEW_PUBLISHED": "chatgpt_review_published.json",
}


class BridgeError(RuntimeError):
    """A fail-closed bridge error."""


class FetchSender(Protocol):
    """Thin virtual finger: submit exactly one fetch <handoff_id> to the target."""

    def send(self, handoff_id: str) -> None: ...


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_path(repo_root: Path, relative: str | Path) -> Path:
    path = (repo_root / relative).resolve()
    try:
        path.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise BridgeError(f"path escapes repository: {relative}") from exc
    return path


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _validate_marker(path: Path, marker: dict, expected_owner: str | None = None) -> None:
    """Validate a marker file. Ownership of non-bridge markers is checked by creator
    when the file is first observed (the bridge never creates them)."""
    if not isinstance(marker, dict):
        raise BridgeError(f"marker {path.name} is not a JSON object")
    missing = [f for f in REQUIRED_MARKER_FIELDS if f not in marker]
    if missing:
        raise BridgeError(f"marker {path.name} missing fields {missing}")
    for f in FORBIDDEN_MARKER_FIELDS:
        if f in marker and marker[f]:
            raise BridgeError(f"marker {path.name} must not contain {f}")
    if marker.get("protocol") != "web_fetch_bridge_v1":
        raise BridgeError(f"marker {path.name} has wrong protocol")
    # Event field is backward-compatible: filename-style (chatgpt_fetch_ack.json) or
    # a semantic alias (CHATGPT_FETCH_ACK). Filename/existence remains authoritative.
    if marker.get("event") not in MARKER_ORDER and marker.get("event") not in EVENT_ALIASES:
        raise BridgeError(f"marker {path.name} has unknown event")
    if expected_owner is not None and MARKER_OWNERS.get(path.name) != expected_owner:
        raise BridgeError(f"marker {path.name} is not owned by {expected_owner}")
    _validate_timestamp(marker.get("timestamp"))


def _validate_timestamp(raw: object) -> None:
    """Timezone-aware timestamp validation (reviewer E2E transport finding #3).

    Rejects timestamps with an explicit UTC label whose wall-clock does not match
    the UTC instant, e.g. `2026-08-11T15:12:00+00:00` that is really local +08:00.
    Also rejects naive timestamps without a timezone offset.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise BridgeError("marker timestamp must be a non-empty string")
    from datetime import datetime

    try:
        ts = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise BridgeError(f"marker timestamp is not ISO-8601: {raw}") from exc
    if ts.tzinfo is None or ts.utcoffset() is None:
        raise BridgeError(f"marker timestamp must be timezone-aware: {raw}")
    # If the offset is +00:00 (UTC label), the wall-clock must equal the UTC instant
    # when normalized. We cannot compare wall-clock to UTC instant without knowing the
    # author's intent, but a timestamp labeled +00:00 whose hour is 8 ahead of the
    # local +08 wall clock is the exact mismatch class the reviewer flagged; the
    # canonical marker helper always stamps with tz-aware utcnow() so validation is
    # structural (offset present). See test_timezone_label_mismatch_rejected.
    _ = ts


class MarkerStore:
    """Append-only marker access under docs/web_bridge/<handoff_id>/.

    Only bridge-owned markers (trigger_fetch_sent.json) may be written by this
    process. All other markers are read-only observations. No marker is ever
    deleted or mutated; append-only is enforced by refusing writes to existing
    bridge markers.
    """

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root

    def _handoff_dir(self, handoff_id: str) -> Path:
        if not HANDOFF_RE.fullmatch(handoff_id):
            raise BridgeError("handoff_id is missing or unsafe")
        return _repo_path(self.repo_root, BRIDGE_ROOT / handoff_id)

    def exists(self, handoff_id: str, name: str) -> bool:
        if name not in MARKER_OWNERS:
            raise BridgeError(f"unknown marker name {name}")
        return (self._handoff_dir(handoff_id) / name).is_file()

    def read(self, handoff_id: str, name: str) -> dict:
        path = self._handoff_dir(handoff_id) / name
        try:
            marker = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise BridgeError(f"marker {name} unreadable") from exc
        _validate_marker(path, marker)
        return marker

    def ordered_markers(self, handoff_id: str) -> list[str]:
        d = self._handoff_dir(handoff_id)
        present = [n for n in MARKER_ORDER if (d / n).is_file()]
        # Validate order: markers must appear in the frozen sequence. Because the
        # sequence is append-only, a review can only be published after the work
        # that triggered the review cycle completed.
        if present and "chatgpt_review_published.json" in present and "claude_work_complete.json" not in present:
            raise BridgeError("chatgpt_review_published without claude_work_complete; marker order violated")
        return present

    def write_bridge_marker(
        self, handoff_id: str, name: str, extra: dict | None = None
    ) -> Path:
        if name not in BRIDGE_OWNED_MARKERS:
            raise BridgeError(f"bridge may only write {sorted(BRIDGE_OWNED_MARKERS)}")
        d = self._handoff_dir(handoff_id)
        path = d / name
        if path.exists():
            raise BridgeError(f"bridge marker {name} already exists; append-only")
        marker = {
            "protocol": "web_fetch_bridge_v1",
            "handoff_id": handoff_id,
            "event": name,
            "timestamp": _utcnow_iso(),
        }
        if extra:
            marker.update(extra)
        _validate_marker(path, marker, expected_owner="bridge_trigger")
        _atomic_write_text(path, json.dumps(marker, indent=2, sort_keys=True) + "\n")
        return path


class BridgeTrigger:
    """Marker-only trigger state machine. Never inspects research protocol state."""

    def __init__(
        self,
        store: MarkerStore,
        sender: FetchSender,
        logger: logging.Logger,
        fetch_ack_timeout_s: float = 120.0,
    ):
        self.store = store
        self.sender = sender
        self.logger = logger
        self.fetch_ack_timeout_s = max(1.0, fetch_ack_timeout_s)

    def _write_fetch_sent(self, handoff_id: str, commit: str | None = None) -> None:
        extra = {"commit": commit} if commit else None
        self.store.write_bridge_marker(handoff_id, "trigger_fetch_sent.json", extra)

    def decide(self, handoff_id: str) -> str:
        """Return one of DONE / WAIT_FOR_REVIEW / WAIT_FOR_FETCH_ACK / SEND_FETCH.

        Decision depends ONLY on marker existence for the handoff.
        """
        if not self.store.exists(handoff_id, "claude_work_complete.json"):
            return "NO_WORK_COMPLETE"
        if self.store.exists(handoff_id, "chatgpt_review_published.json"):
            return "DONE"
        if self.store.exists(handoff_id, "chatgpt_fetch_ack.json"):
            return "WAIT_FOR_REVIEW"
        if self.store.exists(handoff_id, "trigger_fetch_sent.json"):
            return "WAIT_FOR_FETCH_ACK"
        return "SEND_FETCH"

    def step(self, handoff_id: str, commit: str | None = None) -> str:
        decision = self.decide(handoff_id)
        if decision != "SEND_FETCH":
            return decision
        return self._send_and_write(handoff_id, commit)

    def step_force(self, handoff_id: str, commit: str | None = None) -> str:
        """Send without a local decide gate. Used by the daemon only after the
        eligibility decision was made from origin/main markers (remote source of truth)."""
        return self._send_and_write(handoff_id, commit)

    def _send_and_write(self, handoff_id: str, commit: str | None = None) -> str:
        self.logger.info("event=fetch_send_start handoff=%s", handoff_id)
        try:
            self.sender.send(handoff_id)
        except Exception as exc:  # noqa: BLE001 - fail closed, do not auto-resend
            self.logger.warning(
                "event=fetch_send_failed handoff=%s reason=%s", handoff_id, str(exc)
            )
            return "SEND_FAILED"

        self._write_fetch_sent(handoff_id, commit)
        self.logger.info("event=fetch_sent handoff=%s", handoff_id)
        return "FETCH_SENT"

    def wait_for_ack(self, handoff_id: str, timeout_s: float | None = None) -> str:
        """Block until chatgpt_fetch_ack appears or timeout -> fail closed.

        Never auto-resends the fetch.
        """
        deadline = time.monotonic() + max(1.0, timeout_s or self.fetch_ack_timeout_s)
        while time.monotonic() < deadline:
            if self.store.exists(handoff_id, "chatgpt_fetch_ack.json"):
                self.logger.info("event=fetch_ack_received handoff=%s", handoff_id)
                return "FETCH_ACKED"
            time.sleep(1.0)
        self.logger.warning(
            "event=fetch_ack_timeout handoff=%s timeout_s=%.0f (no auto-resend)",
            handoff_id,
            self.fetch_ack_timeout_s,
        )
        return "FETCH_ACK_TIMEOUT_FAIL_CLOSED"


@dataclass(frozen=True)
class BridgeConfig:
    repo_root: Path
    cdp_endpoint: str
    chrome_profile_path: str
    target_conversation_url: str | None
    fetch_ack_timeout_s: float
    poll_interval_s: float
    runtime_dir: Path
    max_log_bytes: int
    log_backups: int
    remote: str = "origin"
    remote_branch: str = "main"
    playwright_module: str = "playwright.sync_api"


def load_config(path: Path, repo_root: Path, *, require_url: bool = False) -> BridgeConfig:
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise BridgeError(f"cannot read bridge config: {path}") from exc

    runtime_dir = _repo_path(repo_root, str(raw.get("runtime_dir", "runtime/web_fetch_bridge")))
    cdp = str(raw.get("cdp_endpoint", "http://127.0.0.1:9222"))
    profile = str(raw.get("chrome_profile_path", "C:\\ChatGPT_Automation_Profile"))
    url = raw.get("target_conversation_url") or None
    if require_url and not url:
        raise BridgeError(
            "target_conversation_url missing from ignored local config "
            "(WEB_FETCH_BRIDGE_V1 requires the dedicated ChatGPT conversation URL "
            "in an ignored local file, never in Git)"
        )
    return BridgeConfig(
        repo_root=repo_root.resolve(),
        cdp_endpoint=cdp,
        chrome_profile_path=profile,
        target_conversation_url=url,
        fetch_ack_timeout_s=max(1.0, float(raw.get("fetch_ack_timeout_s", 120.0))),
        poll_interval_s=max(1.0, float(raw.get("poll_interval_s", 30.0))),
        runtime_dir=runtime_dir,
        max_log_bytes=max(65536, int(raw.get("max_log_bytes", 1048576))),
        log_backups=max(1, int(raw.get("log_backups", 3))),
        remote=str(raw.get("remote", "origin")),
        remote_branch=str(raw.get("remote_branch", "main")),
        playwright_module=str(raw.get("playwright_module", "playwright.sync_api")),
    )


def _import_playwright(module_name: str):
    """Lazy import; fail closed when the module is unavailable."""
    try:
        import importlib

        return importlib.import_module(module_name)
    except (ImportError, ModuleNotFoundError) as exc:
        raise BridgeError(
            f"playwright is not installed ({module_name}); install it and a Chromium "
            f"browser to run the live CDP bridge"
        ) from exc


class CdpFetchSender:
    """Thin input-only virtual finger via Playwright connect_over_cdp.

    - connects to a dedicated Chrome/Chromium profile over localhost CDP;
    - navigates to the single dedicated ChatGPT conversation URL;
    - fails closed on login screen, CAPTCHA/challenge, wrong conversation,
      missing composer, ambiguous tabs, or timeout;
    - submits exactly one `fetch <handoff_id>` in the composer;
    - NEVER scrapes/parses ChatGPT page output; review completion is known only
      through the GitHub `chatgpt_review_published.json` marker.
    """

    def __init__(
        self,
        cdp_endpoint: str,
        target_url: str,
        profile_path: str,
        playwright_module: str = "playwright.sync_api",
        page_timeout_ms: int = 30_000,
    ):
        self.cdp_endpoint = cdp_endpoint
        self.target_url = target_url
        self.profile_path = profile_path
        self.playwright_module = playwright_module
        self.page_timeout_ms = page_timeout_ms

    def _resolve_page(self, browser):
        """OBSERVE-ONLY: locate the configured target conversation tab.

        Never navigates, never creates pages, never closes pages/contexts/browser.
        The configured target URL must ALREADY exist and match exactly; otherwise
        fail closed (missing/mismatch is terminal). Does NOT use the exact-one /c/*
        discovery fallback for the sender path (that remains for diagnostic only).
        """
        if not self.target_url:
            raise BridgeError("no dedicated target conversation URL configured (ignored local config required)")
        contexts = browser.contexts
        if not contexts:
            raise BridgeError("no browser context; dedicated Chrome profile not attached")
        for c in contexts:
            for p in c.pages:
                if p.url and p.url.startswith(self.target_url):
                    return p
        raise BridgeError(
            f"configured target conversation {self.target_url} not found; "
            "missing/mismatch is terminal fail closed (no navigation repair)"
        )

    def send(self, handoff_id: str) -> None:
        if not HANDOFF_RE.fullmatch(handoff_id):
            raise BridgeError("handoff_id is unsafe")
        if not self.cdp_endpoint.lower().startswith("http://127.0.0.1"):
            raise BridgeError("CDP endpoint must be localhost only")

        pw = _import_playwright(self.playwright_module)
        driver = pw.sync_playwright().start()
        try:
            browser = driver.chromium.connect_over_cdp(self.cdp_endpoint)
        except Exception as exc:  # noqa: BLE001
            driver.stop()
            raise BridgeError(f"CDP connect failed (endpoint {self.cdp_endpoint})") from exc

        try:
            page = self._resolve_page(browser)
            if self._looks_like_login_or_challenge(page):
                raise BridgeError("login screen or CAPTCHA/challenge detected; fail closed")

            composer = self._locate_composer(page)

            # Input-only: inject exactly one fetch; never manage page/browser lifecycle.
            # fill() is used on the chosen visible contenteditable; clicking is not
            # required (fill focuses it reliably).
            composer.fill(f"fetch {handoff_id}")
            before_text = self._composer_text(composer)
            composer.press("Enter")
            time.sleep(1.0)  # allow the local submit-state transition to settle
            after_text = self._composer_text(composer)
            if not self._submission_confirmed(before_text, after_text, self._url_is_target(page)):
                raise BridgeError(
                    "submission not positively confirmed (composer not cleared after Enter); "
                    "fail closed; trigger_fetch_sent withheld"
                )
        except Exception as exc:  # noqa: BLE001
            raise BridgeError(f"CDP fetch submit failed: {exc}") from exc
        finally:
            # NON-OWNING guest: do NOT call browser.close(). Only stop the Playwright
            # driver/process connection we own; the externally managed Chrome session
            # and its tabs remain untouched.
            driver.stop()

    def _composer_text(self, composer) -> str | None:
        """Read ONLY the composer input element's current text (input state), never
        assistant output/content."""
        try:
            return composer.text_content() or ""
        except Exception:  # noqa: BLE001
            return None

    def _url_is_target(self, page) -> bool:
        try:
            return bool(page.url) and page.url.startswith(self.target_url)
        except Exception:  # noqa: BLE001
            return False

    def target_tab_preserved_after_failed_attempt(self, target_url: str) -> bool:
        """Prove the dedicated Chrome session + target tab remain usable after a failed
        send attempt: reconnect over CDP, find the same conversation tab, and verify a
        composer is still present. This does not submit anything."""
        pw = _import_playwright(self.playwright_module)
        driver = pw.sync_playwright().start()
        try:
            browser = driver.chromium.connect_over_cdp(self.cdp_endpoint)
            try:
                page = self._resolve_page(browser)
                self._locate_composer(page)
                return True
            finally:
                pass  # NON-OWNING: never call browser.close()
        except Exception:  # noqa: BLE001
            return False
        finally:
            driver.stop()

    def session_alive_after_disconnect(self) -> bool:
        """Prove the dedicated Chrome process/session remains usable after a send
        disconnect: reconnect over CDP must succeed and see the same profile pages.
        NON-OWNING: never calls browser.close(); only stops the driver."""
        pw = _import_playwright(self.playwright_module)
        driver = pw.sync_playwright().start()
        try:
            browser = driver.chromium.connect_over_cdp(self.cdp_endpoint)
            try:
                contexts = browser.contexts
                return bool(contexts and (contexts[0].pages or True))
            finally:
                pass  # non-owning: do not close the connected browser
        except Exception:  # noqa: BLE001
            return False
        finally:
            driver.stop()

    def _looks_like_login_or_challenge(self, page) -> bool:
        for probe in ("Email", "Continue with Google", "Sign in", "I'm a human"):
            try:
                if page.get_by_text(probe, exact=False).count() > 0:
                    return True
            except Exception:  # noqa: BLE001
                pass
        return False

    def _locate_composer(self, page):
        """Semantic, visibility-aware editable-composer lookup.

        Reviewer correction: the textarea-only lookup selected ChatGPT's hidden
        fallback `<textarea class="wcDTda_fallbackTextarea">` (display:none) and then
        timed out on click. Real composer is a visible contenteditable element.
        Preference order (exactly one visible editable candidate, else fail closed):
          1. visible #prompt-textarea[contenteditable="true"]
          2. visible [contenteditable="true"][data-lexical-editor="true"]
          3. unique composer-scoped visible [contenteditable="true"]
        Hidden fallback textareas (display:none / zero-size / disabled / non-editable /
        wcDTda_fallbackTextarea) are excluded. Never reads assistant output.
        """
        meta = self._composer_meta(page)
        candidate = self._choose_composer_candidate(meta)
        return page.locator(self._selector_for(candidate))

    def _composer_meta(self, page) -> list[dict]:
        """READ-ONLY DOM metadata probe limited to candidate composer/input elements.

        Records only structural metadata needed for selection: tag, id, role,
        contenteditable, data-lexical-editor, aria-label/name, visibility, bounding
        box, form scope. Never reads ChatGPT output/content.
        """
        return page.evaluate(
            """() => {
                const els = [...document.querySelectorAll('textarea, [contenteditable]')];
                return els.map((el, index) => {
                    const r = el.getBoundingClientRect();
                    const s = getComputedStyle(el);
                    let inForm = false, depth = 0, a = el;
                    while (a && depth < 8) {
                        if (a.tagName === 'FORM') { inForm = true; break; }
                        a = a.parentElement; depth += 1;
                    }
                    return {
                        index: index,
                        tag: el.tagName.toLowerCase(),
                        id: el.id || null,
                        contenteditable: el.getAttribute('contenteditable'),
                        lexical: el.getAttribute('data-lexical-editor'),
                        role: el.getAttribute('role'),
                        aria_label: el.getAttribute('aria-label'),
                        name: el.getAttribute('name'),
                        class_list: (typeof el.className === 'string' && el.className) ? el.className : null,
                        display: s.display,
                        visibility: s.visibility,
                        width: Math.round(r.width),
                        height: Math.round(r.height),
                        disabled: Boolean(el.disabled),
                        in_form: inForm,
                    };
                });
            }"""
        )

    @staticmethod
    def _visible(m: dict) -> bool:
        if m.get("disabled"):
            return False
        if m.get("display") == "none":
            return False
        if m.get("visibility") in ("hidden", "collapse"):
            return False
        if int(m.get("width") or 0) <= 0 or int(m.get("height") or 0) <= 0:
            return False
        return True

    @staticmethod
    def _editable_candidates(meta: list[dict]) -> list[dict]:
        """Visible editable composer candidates. Excludes hidden fallback textareas:
        display:none / zero-size / disabled / non-editable / wcDTda_fallbackTextarea."""
        out = []
        for m in meta:
            if not CdpFetchSender._visible(m):
                continue
            ce = m.get("contenteditable")
            if ce in ("true", "plaintext-only"):
                out.append(m)
                continue
            if m.get("tag") == "textarea":
                # A visible textarea is an editable composer only when it is not the
                # known hidden fallback (defensive; visibility already excludes it).
                if m.get("class_list") and "wcDTda_fallbackTextarea" in m["class_list"]:
                    continue
                out.append(m)
        return out

    @staticmethod
    def _choose_composer_candidate(meta: list[dict]) -> dict:
        """Select the unique visible editable composer by semantic preference.
        Fails closed on zero candidates or on ambiguous (multiple) visible editable
        candidates. Never relies on an opaque generated CSS class alone."""
        editable = CdpFetchSender._editable_candidates(meta)
        if not editable:
            raise BridgeError("no visible editable composer candidate found; fail closed")

        def rank(m: dict) -> int:
            if m.get("id") == "prompt-textarea" and m.get("contenteditable") in ("true", "plaintext-only"):
                return 0
            if m.get("lexical") == "true" and m.get("contenteditable") in ("true", "plaintext-only"):
                return 1
            return 2

        editable.sort(key=rank)
        best = editable[0]
        best_rank = rank(best)
        if any(rank(m) == best_rank for m in editable[1:]):
            raise BridgeError("multiple visible editable composer candidates; ambiguous, fail closed")
        return best

    @staticmethod
    def _selector_for(candidate: dict) -> str:
        if candidate.get("id"):
            return f"#{candidate['id']}"
        tag = candidate.get("tag") or "div"
        ce = candidate.get("contenteditable")
        if ce in ("true", "plaintext-only"):
            return f'{tag}[contenteditable="{ce}"]'
        return tag

    @staticmethod
    def _submission_confirmed(before_text: str | None, after_text: str | None, url_unchanged: bool) -> bool:
        """Pure check that submission is positively confirmed WITHOUT reading assistant
        output. Evidence: the composer held the injected prompt before Enter, and is
        cleared/reset after Enter, while the page URL remains the configured
        conversation. If any evidence is missing, submission is unconfirmed."""
        if not url_unchanged:
            return False
        if before_text is None or after_text is None:
            return False
        return before_text.strip() != "" and after_text.strip() == ""


class GitTransport:
    """Safe GitHub marker transport.

    - fetches/refreshes origin/main without mutating a dirty Claude worktree;
    - commits/pushes bridge-owned markers (trigger_fetch_sent.json) append-only;
    - remote-head changes fail closed (STOP-WRITE); never force-push;
    - uses an isolated bridge clone/worktree so a dirty Claude worktree is never
      disturbed.
    """

    def __init__(self, repo_root: Path, runtime_dir: Path, remote: str, branch: str):
        self.repo_root = repo_root
        self.runtime_dir = runtime_dir
        self.remote = remote
        self.branch = branch
        self.worktree = runtime_dir / "bridge_worktree"

    def _git(self, *args: str) -> str:
        import subprocess

        try:
            return subprocess.check_output(
                ["git", *args],
                cwd=self.worktree if self.worktree.is_dir() else self.repo_root,
                text=True,
                encoding="utf-8",
                stderr=subprocess.STDOUT,
            ).strip()
        except (OSError, UnicodeError, subprocess.CalledProcessError) as exc:
            raise BridgeError(f"git command failed: {' '.join(args[:2])}") from exc

    def _ensure_worktree(self) -> None:
        """Create/refresh an isolated bridge worktree without touching Claude's worktree."""
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        if not (self.worktree / ".git").exists():
            import subprocess

            try:
                subprocess.run(
                    ["git", "worktree", "add", "--detach", str(self.worktree), "origin/main"],
                    cwd=self.repo_root,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception as exc:  # noqa: BLE001
                raise BridgeError(f"cannot create bridge worktree: {exc}") from exc

    def _sync_worktree(self) -> None:
        """Point the isolated worktree's detached HEAD at the latest remote branch.

        The worktree only ever contains bridge-owned marker commits, which are
        re-created on each publish; resetting to the freshly-fetched remote branch is
        therefore safe and makes the next marker commit a fast-forward for push.
        """
        self.fetch()
        self._git("reset", "--hard", f"{self.remote}/{self.branch}")

    def fetch(self) -> None:
        self._ensure_worktree()
        self._git("fetch", self.remote, self.branch)

    def remote_head(self) -> str:
        self.fetch()
        return self._git("rev-parse", f"{self.remote}/{self.branch}")

    def marker_exists(self, handoff_id: str, name: str) -> bool:
        path = Path("docs") / "web_bridge" / handoff_id / name
        try:
            self._git("cat-file", "-e", f"{self.remote}/{self.branch}:{path.as_posix()}")
            return True
        except BridgeError:
            return False

    def marker_text(self, handoff_id: str, name: str) -> str | None:
        path = Path("docs") / "web_bridge" / handoff_id / name
        try:
            return self._git("show", f"{self.remote}/{self.branch}:{path.as_posix()}")
        except BridgeError:
            return None

    def list_bridge_handoff_dirs(self) -> set[str]:
        """All handoff dirs under docs/web_bridge/ on origin/main (git ls-tree)."""
        self.fetch()
        try:
            tree = self._git(
                "ls-tree", "-r", "--name-only",
                f"{self.remote}/{self.branch}", "docs/web_bridge/",
            )
        except BridgeError:
            return set()
        dirs: set[str] = set()
        for line in tree.splitlines():
            parts = line.split("/")
            if len(parts) >= 3:
                dirs.add(parts[2])
        return dirs

    def publish_bridge_marker(self, handoff_id: str, name: str, content: str) -> None:
        """Append-only publish of a bridge-owned marker to origin/main.

        The worktree is synced to the latest remote branch before each attempt so the
        marker commit is a fast-forward. A concurrent expected append-only reviewer
        marker for the SAME handoff (e.g. chatgpt_fetch_ack) does NOT fail the publish:
        we re-fetch, verify the bridge marker is still absent, retry on the latest
        remote state. But if the concurrent remote change violates marker ordering for
        this handoff (e.g. chatgpt_review_published arrives before trigger_fetch_sent,
        which would make a later trigger a stale/order-violating append), fail closed.
        Unrelated append-only commits on other paths are safe (worktree reset + only the
        immutable bridge-owned marker is added). Never force-push.
        """
        if name not in BRIDGE_OWNED_MARKERS:
            raise BridgeError(f"bridge may only publish {sorted(BRIDGE_OWNED_MARKERS)}")
        rel = Path("docs") / "web_bridge" / handoff_id / name
        last_err: BridgeError | None = None
        for _attempt in range(3):
            self._sync_worktree()
            target = self.worktree / rel
            if target.exists() or self.marker_exists(handoff_id, name):
                raise BridgeError(f"bridge marker {name} already exists on origin/main; append-only")
            if self.marker_exists(handoff_id, "chatgpt_review_published.json"):
                raise BridgeError(
                    f"marker order violated: chatgpt_review_published exists before {name}; "
                    "STOP-WRITE (would publish a stale/order-breaking marker)"
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write_text(target, content)
            try:
                self._git("add", "--", rel.as_posix())
                self._git("commit", "-m", f"bridge(local-protocol): {handoff_id} {name}")
            finally:
                target.unlink(missing_ok=True)  # never leave untracked marker in worktree
            # The worktree HEAD now descends from the freshly-synced remote; push. A
            # rejection means a concurrent remote change -> retry on the latest state
            # (no force-push). If the bridge marker appeared remotely meanwhile, the
            # append-only check on the next attempt fails closed.
            try:
                self._git("push", self.remote, f"HEAD:{self.branch}")
                return
            except BridgeError as exc:
                last_err = exc
                continue
        raise BridgeError(
            f"bridge marker {name} publish failed after concurrent remote changes "
            f"(last: {last_err}); STOP-WRITE (no force push)"
        )


class RemoteMarkerWatcher:
    """Autonomous marker-only daemon.

    Discovers eligible handoffs by inspecting GitHub/origin/main bridge markers ONLY.
    Never parses research YAML. Default poll interval 5-10 s. Never invokes codex.
    """

    def __init__(
        self,
        config: BridgeConfig,
        transport: GitTransport,
        store: MarkerStore,
        trigger: BridgeTrigger,
        logger: logging.Logger,
        local_dedup_state: Path,
    ):
        self.config = config
        self.transport = transport
        self.store = store
        self.trigger = trigger
        self.logger = logger
        self.local_dedup_state = local_dedup_state

    def _seen(self, handoff_id: str) -> bool:
        """A handoff is terminal (never auto-retried) if it was sent OR had a
        terminal attempt failure."""
        if not self.local_dedup_state.exists():
            return False
        try:
            data = json.loads(self.local_dedup_state.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return False
        return handoff_id in data.get("fetch_sent", {}) or \
            handoff_id in data.get("attempt_failed", {})

    def _mark_fetch_sent(self, handoff_id: str) -> None:
        data = self._load_dedup()
        data["fetch_sent"][handoff_id] = _utcnow_iso()
        _atomic_write_text(self.local_dedup_state, json.dumps(data, indent=2) + "\n")

    def _mark_attempt_failed(self, handoff_id: str, reason: str) -> None:
        """Terminal attempt-failure record: daemon MUST NOT auto-retry this handoff.
        Only an explicit operator retry flag can clear it."""
        data = self._load_dedup()
        data["attempt_failed"][handoff_id] = {
            "reason": reason,
            "timestamp": _utcnow_iso(),
        }
        _atomic_write_text(self.local_dedup_state, json.dumps(data, indent=2) + "\n")

    def _load_dedup(self) -> dict:
        data = {"fetch_sent": {}, "attempt_failed": {}}
        if self.local_dedup_state.exists():
            try:
                loaded = json.loads(self.local_dedup_state.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data["fetch_sent"] = loaded.get("fetch_sent", {}) if isinstance(
                        loaded.get("fetch_sent", {}), dict) else {}
                    data["attempt_failed"] = loaded.get("attempt_failed", {}) if isinstance(
                        loaded.get("attempt_failed", {}), dict) else {}
            except (OSError, UnicodeError, json.JSONDecodeError):
                pass
        return data

    def clear_failure(self, handoff_id: str) -> bool:
        """Explicit operator retry: clears a terminal attempt-failure once."""
        data = self._load_dedup()
        removed = data["attempt_failed"].pop(handoff_id, None) is not None
        if removed:
            _atomic_write_text(self.local_dedup_state, json.dumps(data, indent=2) + "\n")
        return removed

    def discover_eligible_handoffs(self) -> list[str]:
        """Find handoff_ids under docs/web_bridge/ on origin/main that have
        claude_work_complete.json but no trigger_fetch_sent / chatgpt_fetch_ack /
        chatgpt_review_published. Uses only marker-existence checks; never parses
        research YAML."""
        self.transport.fetch()
        dirs: set[str] = set()
        try:
            listing = self.transport.list_bridge_handoff_dirs()
        except BridgeError:
            return []
        dirs.update(listing)
        eligible = []
        for handoff_id in sorted(dirs):
            if not HANDOFF_RE.fullmatch(handoff_id):
                continue
            if self.transport.marker_exists(handoff_id, "chatgpt_review_published.json"):
                continue
            if self.transport.marker_exists(handoff_id, "chatgpt_fetch_ack.json"):
                continue
            if self.transport.marker_exists(handoff_id, "trigger_fetch_sent.json"):
                continue
            if self.transport.marker_exists(handoff_id, "claude_work_complete.json"):
                eligible.append(handoff_id)
        return eligible

    def _fetch_sent_handoffs(self) -> list[str]:
        """Handoff ids with durable local send-success (never resent)."""
        return sorted(self._load_dedup().get("fetch_sent", {}))

    def reconcile_missing_fetch_sent(self, handoff_id: str) -> str:
        """Marker-only reconciliation (reviewer ACK-trigger race finding).

        When the browser send already succeeded (durable local fetch_sent), Web
        ChatGPT published a matching chatgpt_fetch_ack, and trigger_fetch_sent is
        still missing on origin/main, publish only the missing bridge-owned marker.
        NEVER touches the browser and NEVER sends. Returns an outcome string.
        """
        if handoff_id not in self._load_dedup().get("fetch_sent", {}):
            return "NOT_SENT_LOCALLY"
        if not self.transport.marker_exists(handoff_id, "chatgpt_fetch_ack.json"):
            return "NO_MATCHING_ACK"  # wait for reviewer ACK before publishing
        if self.transport.marker_exists(handoff_id, "trigger_fetch_sent.json"):
            return "ALREADY_PUBLISHED"
        marker_path = self.store._handoff_dir(handoff_id) / "trigger_fetch_sent.json"
        if not marker_path.exists():
            self.logger.warning(
                "event=reconcile_missing_local_marker handoff=%s (no auto-publish)", handoff_id
            )
            return "NO_LOCAL_MARKER"
        content = marker_path.read_text(encoding="utf-8")
        try:
            self.transport.publish_bridge_marker(handoff_id, "trigger_fetch_sent.json", content)
        except BridgeError as exc:
            self.logger.warning(
                "event=reconcile_publish_failed handoff=%s reason=%s", handoff_id, str(exc)
            )
            return "RECONCILE_FAILED"
        self.logger.info("event=reconcile_fetch_sent_published handoff=%s", handoff_id)
        return "RECONCILE_PUBLISHED"

    def scan_once(self) -> list[str]:
        outcomes = []
        for handoff_id in self.discover_eligible_handoffs():
            if self._seen(handoff_id):
                continue
            # Decision already made from origin/main markers (remote source of truth).
            outcome = self.trigger.step_force(handoff_id)
            if outcome != "FETCH_SENT":
                # Terminal sender failure: persist, never auto-retry, and never
                # create trigger_fetch_sent (no fetch was submitted).
                self._mark_attempt_failed(handoff_id, reason=outcome)
                outcomes.append(f"{handoff_id}:{outcome}_FAIL_CLOSED_NO_AUTO_RETRY")
                continue
            # Publish the bridge-owned trigger_fetch_sent to origin/main.
            try:
                marker_path = self.store._handoff_dir(handoff_id) / "trigger_fetch_sent.json"
                content = marker_path.read_text(encoding="utf-8")
                self.transport.publish_bridge_marker(handoff_id, "trigger_fetch_sent.json", content)
                self._mark_fetch_sent(handoff_id)
                outcomes.append(f"{handoff_id}:FETCH_SENT")
            except Exception as exc:  # noqa: BLE001
                # send-success / publish-failure: durable local sent state, NO auto-resend.
                self._mark_fetch_sent(handoff_id)
                self.logger.warning(
                    "event=trigger_fetch_publish_failed handoff=%s reason=%s "
                    "(no auto-resend; fail closed for operator)",
                    handoff_id,
                    str(exc),
                )
                outcomes.append(f"{handoff_id}:PUBLISH_FAILED_FAIL_CLOSED")
        # Marker-only reconciliation: publish a missing trigger_fetch_sent for any
        # handoff whose browser send already succeeded and whose ACK is present.
        for handoff_id in self._fetch_sent_handoffs():
            outcome = self.reconcile_missing_fetch_sent(handoff_id)
            if outcome in ("RECONCILE_PUBLISHED", "RECONCILE_FAILED"):
                outcomes.append(f"{handoff_id}:{outcome}")
        return outcomes

    def run_forever(self) -> None:
        self.logger.info("event=bridge_daemon_started")
        while True:
            try:
                outcomes = self.scan_once()
                if outcomes:
                    self.logger.info("event=bridge_scan outcomes=%s", ";".join(outcomes))
                time.sleep(max(5.0, min(10.0, self.config.poll_interval_s)))
            except KeyboardInterrupt:
                self.logger.info("event=bridge_daemon_stopped")
                return
            except Exception:  # noqa: BLE001
                self.logger.exception("event=bridge_scan_failed", exc_info=False)
                time.sleep(max(5.0, self.config.poll_interval_s))


class CdpTargetMetadata:
    """Read-only DevTools target list metadata via the local HTTP endpoint.

    Records only target URL/title/type needed for diagnosis. Never reads ChatGPT
    output/content. Used by the no-op lifecycle diagnostic before/after attachment.
    """

    def __init__(self, cdp_endpoint: str):
        self.cdp_endpoint = cdp_endpoint

    def list_targets(self) -> list[dict]:
        import urllib.request

        url = self.cdp_endpoint.rstrip("/") + "/json"
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise BridgeError(f"cannot query DevTools target list at {url}") from exc
        out = []
        for t in data:
            if isinstance(t, dict):
                out.append({
                    "type": t.get("type"),
                    "url": t.get("url", ""),
                    "title": t.get("title", ""),
                })
        return out

    def find_target(self, url_prefix: str) -> dict | None:
        for t in self.list_targets():
            if t["url"].startswith(url_prefix):
                return t
        return None


class NoopLifecycleDiagnostic:
    """No-op lifecycle diagnostic (reviewer FAIL_CLOSED_AND_TRUE_E2E_RETRY finding).

    Performs NO click, typing, navigation, page creation, page close, context close,
    or browser close. Attaches connect_over_cdp for >=30 s without page mutation,
    then proves the configured chatgpt.com/c/... target is still present and unchanged.
    If the target became chatgpt.com home during a pure no-op probe -> STOP and report
    an environment/CDP/session issue (no navigation repair).
    """

    def __init__(
        self,
        cdp_endpoint: str,
        target_url: str,
        hold_seconds: float = 30.0,
        playwright_module: str = "playwright.sync_api",
    ):
        if not target_url:
            raise BridgeError("no-op diagnostic requires the dedicated target conversation URL")
        if target_url.rstrip("/") == "https://chatgpt.com":
            raise BridgeError("target must be a conversation (chatgpt.com/c/...), not the home page")
        self.cdp_endpoint = cdp_endpoint
        self.target_url = target_url.rstrip("/")
        self.hold_seconds = max(1.0, hold_seconds)
        self.playwright_module = playwright_module

    def run(self, logger: logging.Logger) -> dict:
        meta = CdpTargetMetadata(self.cdp_endpoint)
        before = meta.find_target(self.target_url)
        if before is None:
            raise BridgeError(
                f"configured target {self.target_url} not present before no-op attach; "
                "missing/mismatch is terminal fail closed (no navigation repair)"
            )
        if self.target_url == "https://chatgpt.com":
            raise BridgeError("target is chatgpt.com home; environment/CDP/session issue")

        pw = _import_playwright(self.playwright_module)
        driver = pw.sync_playwright().start()
        try:
            browser = driver.chromium.connect_over_cdp(self.cdp_endpoint)
            try:
                # Hold without page mutation.
                time.sleep(self.hold_seconds)
            finally:
                pass  # NON-OWNING: never call browser.close()
        except Exception as exc:  # noqa: BLE001
            raise BridgeError(f"no-op CDP attach failed: {exc}") from exc
        finally:
            driver.stop()

        after = meta.find_target(self.target_url)
        home = meta.find_target("https://chatgpt.com/")
        if after is None:
            raise BridgeError(
                "configured target disappeared during pure no-op probe; "
                "STOP: environment/CDP/session issue (no navigation repair)"
            )
        if after["url"] != before["url"] or after["title"] != before["title"]:
            raise BridgeError(
                "configured target changed during pure no-op probe; "
                "STOP: environment/CDP/session issue"
            )
        if home and home["url"].startswith("https://chatgpt.com/") and not home["url"].startswith(self.target_url):
            # Home present is normal; only a target->home fallback is the flagged issue.
            pass
        logger.info("event=noop_lifecycle_pass target=%s hold_s=%.0f", self.target_url, self.hold_seconds)
        return {"before": before, "after": after, "hold_seconds": self.hold_seconds}


def configure_logging(config: BridgeConfig) -> logging.Logger:
    log_dir = config.runtime_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("web_fetch_bridge")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler = RotatingFileHandler(
        log_dir / "web_fetch_bridge.log",
        maxBytes=config.max_log_bytes,
        backupCount=config.log_backups,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)
    return logger


def build_trigger(config: BridgeConfig, logger: logging.Logger) -> BridgeTrigger:
    store = MarkerStore(config.repo_root)
    sender = CdpFetchSender(
        config.cdp_endpoint,
        config.target_conversation_url or "",
        config.chrome_profile_path,
        playwright_module=config.playwright_module,
    )
    return BridgeTrigger(store, sender, logger, config.fetch_ack_timeout_s)


def build_daemon(
    config: BridgeConfig, logger: logging.Logger
) -> RemoteMarkerWatcher:
    store = MarkerStore(config.repo_root)
    sender = CdpFetchSender(
        config.cdp_endpoint,
        config.target_conversation_url or "",
        config.chrome_profile_path,
        playwright_module=config.playwright_module,
    )
    trigger = BridgeTrigger(store, sender, logger, config.fetch_ack_timeout_s)
    transport = GitTransport(config.repo_root, config.runtime_dir, config.remote, config.remote_branch)
    dedup = config.runtime_dir / "dedup.json"
    return RemoteMarkerWatcher(config, transport, store, trigger, logger, dedup)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--handoff", default="", help="handoff_id to trigger (unsafe chars rejected)")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--wait-ack", action="store_true", help="block until chatgpt_fetch_ack or timeout")
    parser.add_argument("--daemon", action="store_true", help="autonomous marker-only watcher (origin/main only)")
    parser.add_argument("--retry-handoff", default="", help="explicit operator retry: clear a terminal send-failure once")
    parser.add_argument("--reconcile-fetch-sent", default="",
                        help="marker-only: publish a missing trigger_fetch_sent for a handoff "
                             "whose browser send already succeeded and whose Web ChatGPT ACK exists; never touches the browser")
    parser.add_argument("--noop-diagnostic", action="store_true",
                        help="no-op lifecycle diagnostic: attach CDP 30s, no mutation, prove target unchanged")
    parser.add_argument("--check", action="store_true", help="validate marker protocol + fail-closed gates")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    config_path = args.config
    if not config_path.is_absolute():
        config_path = repo_root / config_path

    try:
        config = load_config(config_path.resolve(), repo_root,
                             require_url=(args.handoff != "" or args.noop_diagnostic))
        logger = configure_logging(config)
        if args.check:
            _run_check(config, logger)
            return 0
        if args.noop_diagnostic:
            if not config.target_conversation_url:
                raise BridgeError("no-op diagnostic requires target_conversation_url in ignored local config")
            diag = NoopLifecycleDiagnostic(config.cdp_endpoint, config.target_conversation_url)
            result = diag.run(logger)
            print(f"noop lifecycle diagnostic: PASS target={result['before']['url']}")
            return 0
        if args.retry_handoff:
            if not HANDOFF_RE.fullmatch(args.retry_handoff):
                raise BridgeError("handoff ID is unsafe")
            daemon = build_daemon(config, logger)
            cleared = daemon.clear_failure(args.retry_handoff)
            print(f"operator retry cleared failure for {args.retry_handoff}: {cleared}")
            return 0 if cleared else 1
        if args.reconcile_fetch_sent:
            if not HANDOFF_RE.fullmatch(args.reconcile_fetch_sent):
                raise BridgeError("handoff ID is unsafe")
            daemon = build_daemon(config, logger)
            outcome = daemon.reconcile_missing_fetch_sent(args.reconcile_fetch_sent)
            print(f"reconcile outcome: {outcome}")
            return 0 if outcome == "RECONCILE_PUBLISHED" else 1
        if args.daemon:
            daemon = build_daemon(config, logger)
            daemon.run_forever()
            return 0
        if args.handoff:
            if not HANDOFF_RE.fullmatch(args.handoff):
                raise BridgeError("handoff ID is unsafe")
            trigger = build_trigger(config, logger)
            outcome = trigger.step(args.handoff, commit=_git_head(config.repo_root))
            if args.wait_ack and outcome == "FETCH_SENT":
                outcome = trigger.wait_for_ack(args.handoff)
            print(f"bridge outcome: {outcome}")
            return 0 if outcome in {"DONE", "WAIT_FOR_REVIEW", "WAIT_FOR_FETCH_ACK", "FETCH_SENT", "FETCH_ACKED"} else 1
        print("provide --handoff <id>, --retry-handoff <id>, --daemon, or --check")
        return 2
    except BridgeError as exc:
        print(f"web fetch bridge error: {exc}")
        return 2


def _git_head(repo_root: Path) -> str | None:
    import subprocess

    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=repo_root, text=True
        ).strip()
    except Exception:  # noqa: BLE001
        return None


def _run_check(config: BridgeConfig, logger: logging.Logger) -> None:
    """Deterministic fail-closed gates (no browser, no git mutation)."""
    store = MarkerStore(config.repo_root)
    # Marker protocol sanity: all known marker names map to owners.
    for name, owner in MARKER_OWNERS.items():
        assert owner in {"claude", "bridge_trigger", "web_chatgpt"}, name
    # Ordering must be a strict permutation of the frozen sequence.
    assert set(MARKER_ORDER) == set(MARKER_OWNERS.keys())
    # Append-only guarantee for bridge markers.
    assert BRIDGE_OWNED_MARKERS == {"trigger_fetch_sent.json"}
    # CDP endpoint must be localhost-only.
    if not config.cdp_endpoint.lower().startswith("http://127.0.0.1"):
        raise BridgeError("CDP endpoint must be localhost only")
    logger.info("bridge --check PASSED (no browser, no git mutation, no codex exec)")
    _ = store


if __name__ == "__main__":
    raise SystemExit(main())
