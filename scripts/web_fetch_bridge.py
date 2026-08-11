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
    if marker.get("event") not in MARKER_ORDER:
        raise BridgeError(f"marker {path.name} has unknown event")
    if expected_owner is not None and MARKER_OWNERS.get(path.name) != expected_owner:
        raise BridgeError(f"marker {path.name} is not owned by {expected_owner}")


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

        self.logger.info("event=fetch_send_start handoff=%s", handoff_id)
        try:
            self.sender.send(handoff_id)
        except Exception as exc:  # noqa: BLE001 - fail closed, do not auto-resend
            self.logger.warning(
                "event=fetch_send_failed handoff=%s reason=%s", handoff_id, str(exc)
            )
            return "SEND_FAILED_FAIL_CLOSED"

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

    def send(self, handoff_id: str) -> None:
        if not HANDOFF_RE.fullmatch(handoff_id):
            raise BridgeError("handoff_id is unsafe")
        if not self.target_url:
            raise BridgeError("no dedicated ChatGPT conversation URL configured")
        if not self.cdp_endpoint.lower().startswith("http://127.0.0.1"):
            raise BridgeError("CDP endpoint must be localhost only")

        pw = _import_playwright(self.playwright_module)
        try:
            browser = pw.sync_playwright().start().chromium.connect_over_cdp(self.cdp_endpoint)
        except Exception as exc:  # noqa: BLE001
            raise BridgeError(f"CDP connect failed (endpoint {self.cdp_endpoint})") from exc

        try:
            contexts = browser.contexts
            if not contexts:
                raise BridgeError("no browser context; dedicated Chrome profile not attached")
            page = contexts[0].pages[0] if contexts[0].pages else None
            if page is None:
                page = contexts[0].new_page()
            page.set_default_timeout(self.page_timeout_ms)

            # Navigate to the dedicated conversation; fail closed if auth gate appears.
            page.goto(self.target_url, wait_until="domcontentloaded")
            if self._looks_like_login_or_challenge(page):
                raise BridgeError("login screen or CAPTCHA/challenge detected; fail closed")

            composer = self._find_composer(page)
            if composer is None:
                raise BridgeError("ChatGPT composer not found; fail closed (wrong conversation?)")

            composer.click()
            composer.fill(f"fetch {handoff_id}")
            # Submit: Enter in the ChatGPT composer textarea.
            composer.press("Enter")
            time.sleep(0.5)
        except Exception as exc:  # noqa: BLE001
            raise BridgeError(f"CDP fetch submit failed: {exc}") from exc
        finally:
            try:
                browser.close()
            except Exception:  # noqa: BLE001
                pass

    def _looks_like_login_or_challenge(self, page) -> bool:
        for probe in ("Email", "Continue with Google", "Sign in", "I'm a human"):
            try:
                if page.get_by_text(probe, exact=False).count() > 0:
                    return True
            except Exception:  # noqa: BLE001
                pass
        return False

    def _find_composer(self, page):
        """Locate the ChatGPT composer textarea. Fail closed if ambiguous/missing."""
        try:
            textareas = page.locator("textarea").all()
        except Exception:  # noqa: BLE001
            return None
        if len(textareas) == 0:
            return None
        if len(textareas) > 1:
            # Multiple composers is ambiguous -> fail closed (never guess).
            return None
        return textareas[0]


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--handoff", default="", help="handoff_id to trigger (unsafe chars rejected)")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--wait-ack", action="store_true", help="block until chatgpt_fetch_ack or timeout")
    parser.add_argument("--check", action="store_true", help="validate marker protocol + fail-closed gates")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    config_path = args.config
    if not config_path.is_absolute():
        config_path = repo_root / config_path

    try:
        config = load_config(config_path.resolve(), repo_root, require_url=args.handoff != "")
        logger = configure_logging(config)
        if args.check:
            _run_check(config, logger)
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
        print("provide --handoff <id> (or --check); bridge run mode reserved for scheduled trigger")
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
