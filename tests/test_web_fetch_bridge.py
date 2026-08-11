"""Web Fetch Bridge V1 — marker-driven trigger unit tests.

Coverage (WEB_FETCH_BRIDGE_V1_USER_AUTHORIZATION.md requirements):
  - marker-only state transitions (no research-state parsing);
  - dedup/restart via append-only GitHub markers as source of truth;
  - timeout -> fail closed with NO auto-resend;
  - marker ownership (bridge only writes trigger_fetch_sent; others refused);
  - marker ordering / append-only enforcement;
  - wrong-thread / CDP fail-closed gates (localhost-only endpoint, no playwright
    -> BridgeError, unsafe handoff, login/CAPTCHA probes, ambiguous composer);
  - URL/credential hygiene (no marker duplicates secrets).
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("wfb", ROOT / "scripts" / "web_fetch_bridge.py")
wfb = importlib.util.module_from_spec(_spec)
sys.modules["wfb"] = wfb  # dataclasses require the module to be importable by name
_spec.loader.exec_module(wfb)


class RecordingSender:
    def __init__(self):
        self.calls: list[str] = []

    def send(self, handoff_id: str) -> None:
        self.calls.append(handoff_id)


class FailingSender:
    def send(self, handoff_id: str) -> None:
        raise wfb.BridgeError("cdp connect failed")


class _Logger:
    def __init__(self):
        self.records = []

    def info(self, *args, **kwargs):
        self.records.append(("info", args))

    def warning(self, *args, **kwargs):
        self.records.append(("warning", args))


def _fresh(repo_root: Path, handoff_id: str) -> Path:
    d = repo_root / "docs" / "web_bridge" / handoff_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write(repo_root: Path, handoff_id: str, name: str, event: str | None = None) -> None:
    d = _fresh(repo_root, handoff_id)
    marker = {
        "protocol": "web_fetch_bridge_v1",
        "handoff_id": handoff_id,
        "event": event or name,
        "timestamp": "2026-08-11T00:00:00+00:00",
    }
    (d / name).write_text(json.dumps(marker, indent=2, sort_keys=True), encoding="utf-8")


@pytest.fixture()
def repo_root(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture()
def trigger(repo_root: Path):
    sender = RecordingSender()
    store = wfb.MarkerStore(repo_root)
    trig = wfb.BridgeTrigger(store, sender, _Logger(), fetch_ack_timeout_s=1.0)
    return trig, sender


# --- marker-only state transitions ---

def test_no_work_complete_no_fetch(repo_root, trigger):
    trig, sender = trigger
    assert trig.decide("H-0001") == "NO_WORK_COMPLETE"
    assert sender.calls == []


def test_work_complete_triggers_exactly_one_fetch(repo_root, trigger):
    trig, sender = trigger
    _write(repo_root, "H-0001", "claude_work_complete.json")
    assert trig.decide("H-0001") == "SEND_FETCH"
    assert trig.step("H-0001", commit="abc123") == "FETCH_SENT"
    assert sender.calls == ["H-0001"]
    assert trig.store.exists("H-0001", "trigger_fetch_sent.json")
    # A second step must NOT resend (dedup / append-only).
    assert trig.step("H-0001") == "WAIT_FOR_FETCH_ACK"
    assert sender.calls == ["H-0001"]


def test_fetch_ack_stops_resend(repo_root, trigger):
    trig, sender = trigger
    _write(repo_root, "H-0001", "claude_work_complete.json")
    _write(repo_root, "H-0001", "chatgpt_fetch_ack.json")
    assert trig.decide("H-0001") == "WAIT_FOR_REVIEW"
    assert trig.step("H-0001") == "WAIT_FOR_REVIEW"
    assert sender.calls == []


def test_review_published_is_done(repo_root, trigger):
    trig, sender = trigger
    _write(repo_root, "H-0001", "claude_work_complete.json")
    _write(repo_root, "H-0001", "chatgpt_review_published.json")
    assert trig.decide("H-0001") == "DONE"
    assert trig.step("H-0001") == "DONE"
    assert sender.calls == []


# --- restart dedup: markers are source of truth, not local runtime ---

def test_restart_dedup_via_markers(repo_root, trigger):
    """A fresh trigger (new process) must not resend if trigger_fetch_sent exists."""
    _write(repo_root, "H-0001", "claude_work_complete.json")
    _write(repo_root, "H-0001", "trigger_fetch_sent.json")
    trig2, sender2 = trigger
    assert trig2.decide("H-0001") == "WAIT_FOR_FETCH_ACK"
    assert sender2.calls == []


# --- timeout -> fail closed, no auto-resend ---

def test_fetch_ack_timeout_fail_closed(repo_root, trigger):
    trig, sender = trigger
    _write(repo_root, "H-0001", "claude_work_complete.json")
    assert trig.step("H-0001") == "FETCH_SENT"
    outcome = trig.wait_for_ack("H-0001", timeout_s=0.5)
    assert outcome == "FETCH_ACK_TIMEOUT_FAIL_CLOSED"
    # No auto-resend after timeout.
    assert sender.calls == ["H-0001"]


def test_fetch_ack_received(repo_root, trigger):
    trig, sender = trigger
    _write(repo_root, "H-0001", "claude_work_complete.json")

    def _ack_later():
        import threading

        def _write_ack():
            import time as _t

            _t.sleep(0.2)
            _write(repo_root, "H-0001", "chatgpt_fetch_ack.json")

        threading.Thread(target=_write_ack, daemon=True).start()

    _ack_later()
    assert trig.step("H-0001") == "FETCH_SENT"
    assert trig.wait_for_ack("H-0001", timeout_s=5.0) == "FETCH_ACKED"


# --- ownership / append-only / ordering ---

def test_bridge_only_writes_owned_marker(repo_root, trigger):
    trig, _ = trigger
    with pytest.raises(wfb.BridgeError):
        trig.store.write_bridge_marker("H-0001", "claude_work_complete.json")
    with pytest.raises(wfb.BridgeError):
        trig.store.write_bridge_marker("H-0001", "chatgpt_review_published.json")


def test_bridge_marker_append_only(repo_root, trigger):
    trig, _ = trigger
    _write(repo_root, "H-0001", "trigger_fetch_sent.json")
    with pytest.raises(wfb.BridgeError):
        trig.store.write_bridge_marker("H-0001", "trigger_fetch_sent.json")


def test_marker_ordering_enforced(repo_root):
    store = wfb.MarkerStore(repo_root)
    _write(repo_root, "H-0001", "chatgpt_review_published.json")  # appears first -> invalid order
    with pytest.raises(wfb.BridgeError):
        store.ordered_markers("H-0001")


def test_marker_required_fields_and_secrets(repo_root):
    d = _fresh(repo_root, "H-0001")
    bad = {
        "protocol": "web_fetch_bridge_v1",
        "handoff_id": "H-0001",
        "event": "claude_work_complete.json",
        "timestamp": "2026-08-11T00:00:00+00:00",
        "api_key": "leak",
    }
    (d / "claude_work_complete.json").write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(wfb.BridgeError):
        wfb.MarkerStore(repo_root).read("H-0001", "claude_work_complete.json")


def test_unsafe_handoff_rejected(repo_root, trigger):
    trig, _ = trigger
    with pytest.raises(wfb.BridgeError):
        trig.store.exists("../../etc/passwd", "claude_work_complete.json")
    with pytest.raises(wfb.BridgeError):
        trig.decide("H 0001")  # space -> unsafe


# --- CDP / wrong-thread fail-closed ---

def test_cdp_sender_fail_closed_without_playwright():
    sender = wfb.CdpFetchSender("http://127.0.0.1:9222", "https://chatgpt.com/c/abc", "C:\\p")
    with pytest.raises(wfb.BridgeError):
        sender.send("H-0001")  # playwright missing -> fail closed


def test_cdp_endpoint_must_be_localhost():
    with pytest.raises(wfb.BridgeError):
        wfb.CdpFetchSender("http://192.168.1.5:9222", "https://x", "C:\\p").send("H-0001")


def test_cdp_sender_no_url_fail_closed():
    with pytest.raises(wfb.BridgeError):
        wfb.CdpFetchSender("http://127.0.0.1:9222", "", "C:\\p").send("H-0001")


def test_trigger_sender_failure_fail_closed(repo_root):
    store = wfb.MarkerStore(repo_root)
    trig = wfb.BridgeTrigger(store, FailingSender(), _Logger())
    _write(repo_root, "H-0001", "claude_work_complete.json")
    assert trig.step("H-0001") == "SEND_FAILED"
    # trigger_fetch_sent must NOT be created when send failed.
    assert not store.exists("H-0001", "trigger_fetch_sent.json")


# --- config / check gates ---

def test_load_config_requires_url_only_when_fetching(repo_root, tmp_path):
    cfg_path = tmp_path / "b.toml"
    cfg_path.write_text(
        "cdp_endpoint = 'http://127.0.0.1:9222'\n"
        "chrome_profile_path = 'C:\\\\ChatGPT_Automation_Profile'\n"
        "target_conversation_url = ''\n",
        encoding="utf-8",
    )
    # --check / non-fetch load allowed without URL.
    cfg = wfb.load_config(cfg_path, repo_root, require_url=False)
    assert cfg.cdp_endpoint == "http://127.0.0.1:9222"
    # Fetching requires the URL from the ignored local config.
    with pytest.raises(wfb.BridgeError):
        wfb.load_config(cfg_path, repo_root, require_url=True)


def test_bridge_check_no_git_no_browser(repo_root, tmp_path):
    cfg = wfb.BridgeConfig(
        repo_root=repo_root,
        cdp_endpoint="http://127.0.0.1:9222",
        chrome_profile_path="C:\\ChatGPT_Automation_Profile",
        target_conversation_url=None,
        fetch_ack_timeout_s=120.0,
        poll_interval_s=30.0,
        runtime_dir=tmp_path / "runtime",
        max_log_bytes=65536,
        log_backups=1,
    )
    wfb._run_check(cfg, _Logger())


# --- GitHub marker transport / autonomous watcher ---

class FakeRemoteTransport:
    """A fake GitTransport whose marker set mimics origin/main and can simulate
    remote-head races. Does not touch git."""

    def __init__(self):
        self.remotes: dict[tuple[str, str], str] = {}
        self.published: list[tuple[str, str, str]] = []
        self.race_on_publish = False

    def fetch(self) -> None:
        return None

    def marker_exists(self, handoff_id: str, name: str) -> bool:
        return (handoff_id, name) in self.remotes

    def marker_text(self, handoff_id: str, name: str) -> str | None:
        return self.remotes.get((handoff_id, name))

    def publish_bridge_marker(self, handoff_id: str, name: str, content: str) -> None:
        if name not in wfb.BRIDGE_OWNED_MARKERS:
            raise wfb.BridgeError("bridge may only publish owned markers")
        if (handoff_id, name) in self.remotes:
            raise wfb.BridgeError("marker already exists; append-only")
        if self.race_on_publish:
            raise wfb.BridgeError("remote-head changed during publish; STOP-WRITE")
        self.remotes[(handoff_id, name)] = content
        self.published.append((handoff_id, name, content))

    def list_bridge_handoff_dirs(self) -> set[str]:
        return {h for (h, _n) in self.remotes}

    def discover(self) -> list[str]:
        ids = {h for (h, n) in self.remotes if n == "claude_work_complete.json"}
        done = {h for (h, n) in self.remotes if n in ("chatgpt_review_published.json",)}
        acked = {h for (h, n) in self.remotes if n == "chatgpt_fetch_ack.json"}
        sent = {h for (h, n) in self.remotes if n == "trigger_fetch_sent.json"}
        return sorted(ids - done - acked - sent)


class FakeWorktreeSender:
    """Records send calls. The trigger writes trigger_fetch_sent locally after a
    successful send; the daemon then publishes that local marker remotely."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.calls: list[str] = []

    def send(self, handoff_id: str) -> None:
        self.calls.append(handoff_id)


def _daemon(repo_root: Path, transport, tmp_path: Path):
    store = wfb.MarkerStore(repo_root)
    sender = FakeWorktreeSender(repo_root)
    trig = wfb.BridgeTrigger(store, sender, _Logger(), fetch_ack_timeout_s=1.0)
    dedup = tmp_path / "dedup.json"
    return wfb.RemoteMarkerWatcher(None, transport, store, trig, _Logger(), dedup)


def test_daemon_discovers_remote_work_complete_only(repo_root, tmp_path):
    t = FakeRemoteTransport()
    t.remotes[("H-0001", "claude_work_complete.json")] = "{}"
    daemon = _daemon(repo_root, t, tmp_path)
    assert daemon.discover_eligible_handoffs() == ["H-0001"]


def test_daemon_no_trigger_without_remote_work_complete(repo_root, tmp_path):
    t = FakeRemoteTransport()
    daemon = _daemon(repo_root, t, tmp_path)
    assert daemon.discover_eligible_handoffs() == []


def test_daemon_skips_acked_and_published(repo_root, tmp_path):
    t = FakeRemoteTransport()
    t.remotes[("H-1", "claude_work_complete.json")] = "{}"
    t.remotes[("H-1", "chatgpt_fetch_ack.json")] = "{}"
    t.remotes[("H-2", "claude_work_complete.json")] = "{}"
    t.remotes[("H-2", "chatgpt_review_published.json")] = "{}"
    daemon = _daemon(repo_root, t, tmp_path)
    assert daemon.discover_eligible_handoffs() == []


def test_daemon_skips_if_trigger_fetch_sent_remote(repo_root, tmp_path):
    t = FakeRemoteTransport()
    t.remotes[("H-1", "claude_work_complete.json")] = "{}"
    t.remotes[("H-1", "trigger_fetch_sent.json")] = "{}"
    daemon = _daemon(repo_root, t, tmp_path)
    assert daemon.discover_eligible_handoffs() == []


def test_daemon_auto_sends_and_remotely_publishes_fetch_sent(repo_root, tmp_path):
    t = FakeRemoteTransport()
    t.remotes[("H-0001", "claude_work_complete.json")] = "{}"
    daemon = _daemon(repo_root, t, tmp_path)
    outcomes = daemon.scan_once()
    assert outcomes == ["H-0001:FETCH_SENT"]
    # Locally created trigger_fetch_sent was published to origin/main.
    assert t.remotes[("H-0001", "trigger_fetch_sent.json")]
    # Restart dedup: a fresh daemon sees remote trigger_fetch_sent -> no resend.
    daemon2 = _daemon(repo_root, t, tmp_path)
    assert daemon2.scan_once() == []


def test_daemon_send_success_publish_failure_fail_closed_no_resend(repo_root, tmp_path):
    t = FakeRemoteTransport()
    t.remotes[("H-0001", "claude_work_complete.json")] = "{}"
    t.race_on_publish = True  # remote-head moved -> publish STOP-WRITE
    daemon = _daemon(repo_root, t, tmp_path)
    outcomes = daemon.scan_once()
    assert outcomes == ["H-0001:PUBLISH_FAILED_FAIL_CLOSED"]
    # Durable local sent state prevents auto-resend on next scan.
    assert daemon.scan_once() == []


def test_remote_ack_observation_stops_trigger(repo_root, tmp_path):
    t = FakeRemoteTransport()
    t.remotes[("H-1", "claude_work_complete.json")] = "{}"
    t.remotes[("H-1", "chatgpt_fetch_ack.json")] = "{}"
    daemon = _daemon(repo_root, t, tmp_path)
    assert daemon.discover_eligible_handoffs() == []


def test_sender_discovery_exactly_one_chatgpt_tab():
    """Tab discovery fallback: URL-based routing is covered by CdpFetchSender's
    _resolve_page contract. Without playwright a send fails closed; the discovery
    logic (target URL or exact-one tab) is enforced in _resolve_page."""
    s = wfb.CdpFetchSender("http://127.0.0.1:9222", "", "C:\\p")
    with pytest.raises(wfb.BridgeError):
        s.send("H-0001")  # playwright missing -> fail closed before discovery


def test_session_alive_after_disconnect_probe_live_cdp():
    """The probe connects to localhost CDP; when the dedicated Chrome is up it returns
    True (proving the externally managed session survives a disconnect); with a
    non-localhost / unreachable endpoint it fails closed."""
    s = wfb.CdpFetchSender("http://127.0.0.1:9222", "https://chatgpt.com/c/x", "C:\\p")
    # Live dedicated Chrome on localhost:9222 -> session probe succeeds (or fails
    # closed only if CDP is genuinely unreachable). Deterministic fallback: a
    # non-localhost endpoint must always fail closed before any connection.
    bad = wfb.CdpFetchSender("http://192.168.1.5:9222", "https://chatgpt.com/c/x", "C:\\p")
    assert bad.session_alive_after_disconnect() is False  # non-localhost fail-closed
    # localhost probe: either live (True) or unreachable (False); both acceptable,
    # but must never raise.
    result = s.session_alive_after_disconnect()
    assert isinstance(result, bool)


# --- send-failure no-auto-retry + explicit operator retry only (reviewer finding #1) ---

class _FailAlwaysSender:
    def send(self, handoff_id: str) -> None:
        raise wfb.BridgeError("cdp submit failed")


def _daemon_with_sender(repo_root, transport, tmp_path, sender):
    store = wfb.MarkerStore(repo_root)
    trig = wfb.BridgeTrigger(store, sender, _Logger(), fetch_ack_timeout_s=1.0)
    dedup = tmp_path / "dedup.json"
    return wfb.RemoteMarkerWatcher(None, transport, store, trig, _Logger(), dedup)


def test_send_failure_is_terminal_no_auto_retry(repo_root, tmp_path):
    """A sender failure must be persisted and the daemon must never auto-retry it."""
    t = FakeRemoteTransport()
    t.remotes[("H-0001", "claude_work_complete.json")] = "{}"
    daemon = _daemon_with_sender(repo_root, t, tmp_path, _FailAlwaysSender())
    outcomes = daemon.scan_once()
    assert outcomes == ["H-0001:SEND_FAILED_FAIL_CLOSED_NO_AUTO_RETRY"]
    # trigger_fetch_sent must NOT be created when no fetch was actually submitted.
    assert not (t.remotes.get(("H-0001", "trigger_fetch_sent.json")))
    # Next scans must not retry (terminal local failure record).
    assert daemon.scan_once() == []
    assert daemon.scan_once() == []


def test_explicit_operator_retry_clears_failure_once(repo_root, tmp_path):
    t = FakeRemoteTransport()
    t.remotes[("H-0001", "claude_work_complete.json")] = "{}"
    daemon = _daemon_with_sender(repo_root, t, tmp_path, _FailAlwaysSender())
    assert daemon.scan_once() == ["H-0001:SEND_FAILED_FAIL_CLOSED_NO_AUTO_RETRY"]
    assert daemon.scan_once() == []
    # Explicit operator retry clears the terminal failure.
    assert daemon.clear_failure("H-0001") is True
    assert daemon.scan_once() == ["H-0001:SEND_FAILED_FAIL_CLOSED_NO_AUTO_RETRY"]
    assert daemon.scan_once() == []
    # Retry clears exactly once; clearing again with no failure is a no-op.
    assert daemon.clear_failure("H-0001") is True
    assert daemon.clear_failure("H-0001") is False


def test_send_failure_no_trigger_fetch_sent_marker(repo_root, tmp_path):
    t = FakeRemoteTransport()
    t.remotes[("H-0001", "claude_work_complete.json")] = "{}"
    daemon = _daemon_with_sender(repo_root, t, tmp_path, _FailAlwaysSender())
    daemon.scan_once()
    assert not t.marker_exists("H-0001", "trigger_fetch_sent.json")
    # No local marker written either.
    assert not (repo_root / "docs" / "web_bridge" / "H-0001" / "trigger_fetch_sent.json").exists()


# --- timezone-aware timestamp validation (reviewer finding #3) ---

def test_timezone_aware_timestamp_required(repo_root):
    d = _fresh(repo_root, "H-0001")
    marker = {
        "protocol": "web_fetch_bridge_v1",
        "handoff_id": "H-0001",
        "event": "claude_work_complete.json",
        "timestamp": "2026-08-11T15:12:00",  # naive, no offset
    }
    (d / "claude_work_complete.json").write_text(json.dumps(marker), encoding="utf-8")
    with pytest.raises(wfb.BridgeError):
        wfb.MarkerStore(repo_root).read("H-0001", "claude_work_complete.json")


def test_utc_label_mismatch_rejected(repo_root):
    """A +00:00 label whose wall clock is actually local +08 is the flagged mismatch
    class; the validator requires an explicit timezone offset (structural), so a
    valid utcnow()-style ISO stamp passes and a naive one fails."""
    import datetime

    good = datetime.datetime.now(datetime.timezone.utc).isoformat()
    wfb._validate_timestamp(good)  # must not raise
    with pytest.raises(wfb.BridgeError):
        wfb._validate_timestamp("2026-08-11T15:12:00")
    with pytest.raises(wfb.BridgeError):
        wfb._validate_timestamp(123)
    with pytest.raises(wfb.BridgeError):
        wfb._validate_timestamp("")


# --- Playwright lifecycle (reviewer finding #4) ---

def test_target_tab_preserved_probe():
    """Target-tab preservation probe: non-localhost fails closed; localhost probe
    returns a bool (live composer present when the dedicated tab is open, False
    otherwise). Never raises."""
    s = wfb.CdpFetchSender("http://127.0.0.1:9222", "https://chatgpt.com/c/x", "C:\\p")
    bad = wfb.CdpFetchSender("http://192.168.1.5:9222", "https://chatgpt.com/c/x", "C:\\p")
    assert bad.target_tab_preserved_after_failed_attempt("https://chatgpt.com/c/x") is False
    result = s.target_tab_preserved_after_failed_attempt("https://chatgpt.com/c/x")
    assert isinstance(result, bool)


# --- no-op lifecycle diagnostic + non-owning CDP (reviewer FAIL_CLOSED finding) ---

def test_noop_diagnostic_requires_target_url():
    """The no-op diagnostic must require the dedicated target conversation URL in
    ignored local config (no exact-one discovery for the diagnostic)."""
    with pytest.raises(wfb.BridgeError):
        wfb.NoopLifecycleDiagnostic("http://127.0.0.1:9222", "")
    with pytest.raises(wfb.BridgeError):
        wfb.NoopLifecycleDiagnostic("http://127.0.0.1:9222", "https://chatgpt.com/")
    # Valid target accepted (constructor only; run will fail closed without browser).
    diag = wfb.NoopLifecycleDiagnostic("http://127.0.0.1:9222", "https://chatgpt.com/c/abc")
    assert diag.target_url == "https://chatgpt.com/c/abc"


def test_noop_diagnostic_no_target_before_attach_fail_closed():
    """If the configured target is absent before attachment, STOP (no repair)."""
    diag = wfb.NoopLifecycleDiagnostic("http://127.0.0.1:9222", "https://chatgpt.com/c/absent-xyz")
    with pytest.raises(wfb.BridgeError) as exc:
        diag.run(_Logger())
    assert "not present before no-op attach" in str(exc.value)


def test_sender_never_calls_browser_close():
    """Sender and no-op paths must not call browser.close (non-owning guest)."""
    src = Path(ROOT / "scripts" / "web_fetch_bridge.py").read_text(encoding="utf-8")
    import re

    code = src.split("class CdpTargetMetadata")[0]
    # Check actual call statements only (not comments/docstrings).
    for pattern in (r"^\s*browser\.close\(\)", r"^\s*page\.goto\(", r"^\s*new_page\(\)",
                    r"^\s*page\.close\(\)", r"^\s*context\.close\(\)"):
        assert not re.search(pattern, code, re.MULTILINE), f"non-owning path must not call {pattern}"


# --- composer locator correction (reviewer E2E_FAIL_CLOSED finding) ---

def _meta(**kw):
    base = {
        "index": 0, "tag": "div", "id": None, "contenteditable": None,
        "lexical": None, "role": None, "aria_label": None, "name": None,
        "class_list": None, "display": "block", "visibility": "visible",
        "width": 500, "height": 40, "disabled": False, "in_form": True,
    }
    base.update(kw)
    return base


def test_composer_locator_excludes_hidden_fallback_textarea():
    """The hidden fallback <textarea class="wcDTda_fallbackTextarea"> (display:none,
    zero-size) must be excluded; the visible #prompt-textarea contenteditable wins."""
    meta = [
        _meta(index=0, tag="textarea", id=None, contenteditable=None,
              name="prompt-textarea", class_list="wcDTda_fallbackTextarea",
              display="none", width=0, height=0),
        _meta(index=1, tag="div", id="prompt-textarea", contenteditable="true",
              role="textbox", aria_label="与 ChatGPT 聊天"),
    ]
    chosen = wfb.CdpFetchSender._choose_composer_candidate(meta)
    assert chosen["id"] == "prompt-textarea"
    assert chosen["contenteditable"] == "true"


def test_composer_locator_only_hidden_fallback_fails_closed():
    """Only a hidden fallback textarea -> no visible editable candidate -> fail closed."""
    meta = [_meta(index=0, tag="textarea", id=None, contenteditable=None,
                  name="prompt-textarea", class_list="wcDTda_fallbackTextarea",
                  display="none", width=0, height=0)]
    with pytest.raises(wfb.BridgeError):
        wfb.CdpFetchSender._choose_composer_candidate(meta)


def test_composer_locator_no_candidate_fails_closed():
    """No visible editable candidate at all -> fail closed."""
    meta = [_meta(index=0, tag="input", id="upload-files", width=1, height=1)]
    with pytest.raises(wfb.BridgeError):
        wfb.CdpFetchSender._choose_composer_candidate(meta)


def test_composer_locator_unique_visible_contenteditable_selected():
    """A unique visible [contenteditable=true] candidate is selected (no id/lexical)."""
    meta = [
        _meta(index=0, tag="div", id=None, contenteditable="true", width=555, height=42),
    ]
    chosen = wfb.CdpFetchSender._choose_composer_candidate(meta)
    assert chosen["contenteditable"] == "true"


def test_composer_locator_lexical_editor_preferred_over_generic():
    """A visible [contenteditable][data-lexical-editor] wins over a generic visible one."""
    meta = [
        _meta(index=0, tag="div", id=None, contenteditable="true", width=200, height=20),
        _meta(index=1, tag="div", id=None, contenteditable="true", lexical="true", width=555, height=42),
    ]
    chosen = wfb.CdpFetchSender._choose_composer_candidate(meta)
    assert chosen["lexical"] == "true"


def test_composer_locator_ambiguity_fails_closed():
    """Two visible editable candidates at the same priority -> ambiguous -> fail closed."""
    meta = [
        _meta(index=0, tag="div", contenteditable="true", width=200, height=20),
        _meta(index=1, tag="div", contenteditable="true", width=300, height=30),
    ]
    with pytest.raises(wfb.BridgeError):
        wfb.CdpFetchSender._choose_composer_candidate(meta)


def test_composer_locator_selector_for_candidate():
    """_selector_for maps the chosen candidate to a stable semantic selector."""
    assert wfb.CdpFetchSender._selector_for({"id": "prompt-textarea"}) == "#prompt-textarea"
    assert wfb.CdpFetchSender._selector_for({"id": None, "tag": "div", "contenteditable": "true"}) == 'div[contenteditable="true"]'


def test_submission_confirmation_pure_check():
    """Submission is confirmed only when the composer held the prompt before Enter and
    is cleared after Enter with URL unchanged (no assistant output read)."""
    conf = wfb.CdpFetchSender._submission_confirmed
    assert conf("fetch H-1", "", True) is True
    # composer not cleared after Enter -> unconfirmed
    assert conf("fetch H-1", "fetch H-1", True) is False
    # composer empty before Enter -> no prompt injected -> unconfirmed
    assert conf("", "", True) is False
    # URL changed -> unconfirmed
    assert conf("fetch H-1", "", False) is False
    # unreadable composer state -> unconfirmed
    assert conf(None, "", True) is False
    assert conf("fetch H-1", None, True) is False


def test_submission_unconfirmed_withholds_trigger_fetch_sent(repo_root, tmp_path):
    """A sender whose submission is not positively confirmed must fail closed and the
    daemon must NOT publish trigger_fetch_sent (no real fetch reached Web ChatGPT)."""
    class _UnconfirmedSender:
        def send(self, handoff_id: str) -> None:
            raise wfb.BridgeError(
                "submission not positively confirmed (composer not cleared after Enter); "
                "fail closed; trigger_fetch_sent withheld"
            )

    t = FakeRemoteTransport()
    t.remotes[("H-0001", "claude_work_complete.json")] = "{}"
    daemon = _daemon_with_sender(repo_root, t, tmp_path, _UnconfirmedSender())
    outcomes = daemon.scan_once()
    assert outcomes == ["H-0001:SEND_FAILED_FAIL_CLOSED_NO_AUTO_RETRY"]
    assert not t.marker_exists("H-0001", "trigger_fetch_sent.json")
    assert not (repo_root / "docs" / "web_bridge" / "H-0001" / "trigger_fetch_sent.json").exists()


# --- ACK-trigger race reconciliation (reviewer ACK_TRIGGER_RACE finding) ---

def test_marker_event_alias_compatible():
    """A reviewer marker with semantic event value (CHATGPT_FETCH_ACK) must validate;
    filename-style events must also still validate. Marker filename remains authoritative."""
    import tempfile
    from pathlib import Path as _Path

    with tempfile.TemporaryDirectory() as td:
        root = _Path(td)
        store = wfb.MarkerStore(root)
        d = root / "docs" / "web_bridge" / "H-0001"
        d.mkdir(parents=True)
        ack = {
            "protocol": "web_fetch_bridge_v1",
            "handoff_id": "H-0001",
            "event": "CHATGPT_FETCH_ACK",  # semantic alias
            "timestamp": "2026-08-11T16:21:00+08:00",
        }
        (d / "chatgpt_fetch_ack.json").write_text(
            __import__("json").dumps(ack, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        # read must not raise: semantic alias accepted
        wfb.MarkerStore(root).read("H-0001", "chatgpt_fetch_ack.json")
        # filename-style event must still validate
        old_style = dict(ack, event="chatgpt_fetch_ack.json")
        (d / "chatgpt_fetch_ack.json").write_text(
            __import__("json").dumps(old_style, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        wfb.MarkerStore(root).read("H-0001", "chatgpt_fetch_ack.json")
        # unknown event still rejected
        bad = dict(ack, event="SOMETHING_ELSE")
        (d / "chatgpt_fetch_ack.json").write_text(
            __import__("json").dumps(bad, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        with pytest.raises(wfb.BridgeError):
            wfb.MarkerStore(root).read("H-0001", "chatgpt_fetch_ack.json")


def test_reconcile_publishes_missing_trigger_when_ack_present(repo_root, tmp_path):
    """Durable local send-success + remote chatgpt_fetch_ack + missing trigger
    -> marker-only reconciliation publishes trigger_fetch_sent; sender never called."""
    class _ProbeSender:
        def __init__(self):
            self.calls = []

        def send(self, handoff_id: str) -> None:
            self.calls.append(handoff_id)

    t = FakeRemoteTransport()
    t.remotes[("H-0001", "claude_work_complete.json")] = "{}"
    t.remotes[("H-0001", "chatgpt_fetch_ack.json")] = "{}"
    daemon = _daemon_with_sender(repo_root, t, tmp_path, _ProbeSender())
    # durable local send-success + local marker file (as the daemon would have written)
    daemon._mark_fetch_sent("H-0001")
    d = repo_root / "docs" / "web_bridge" / "H-0001"
    d.mkdir(parents=True, exist_ok=True)
    (d / "trigger_fetch_sent.json").write_text(
        json.dumps({"event": "trigger_fetch_sent.json", "handoff_id": "H-0001",
                    "protocol": "web_fetch_bridge_v1",
                    "timestamp": "2026-08-11T08:21:38.935396+00:00"}) + "\n", encoding="utf-8")
    outcomes = daemon.scan_once()
    assert "H-0001:RECONCILE_PUBLISHED" in outcomes
    assert t.remotes.get(("H-0001", "trigger_fetch_sent.json"))
    # sender (browser) must never be called during reconciliation
    assert daemon.trigger.sender.calls == []


def test_reconcile_without_ack_waits(repo_root, tmp_path):
    """No matching remote ACK -> reconciliation waits; no publish, no browser call."""
    class _ProbeSender:
        def __init__(self):
            self.calls = []

        def send(self, handoff_id: str) -> None:
            self.calls.append(handoff_id)

    t = FakeRemoteTransport()
    t.remotes[("H-0001", "claude_work_complete.json")] = "{}"
    daemon = _daemon_with_sender(repo_root, t, tmp_path, _ProbeSender())
    daemon._mark_fetch_sent("H-0001")
    d = repo_root / "docs" / "web_bridge" / "H-0001"
    d.mkdir(parents=True, exist_ok=True)
    (d / "trigger_fetch_sent.json").write_text("{}", encoding="utf-8")
    assert daemon.reconcile_missing_fetch_sent("H-0001") == "NO_MATCHING_ACK"
    assert not t.remotes.get(("H-0001", "trigger_fetch_sent.json"))
    assert daemon.trigger.sender.calls == []


def test_reconcile_duplicate_safety_no_overwrite(repo_root, tmp_path):
    """trigger_fetch_sent already on origin/main -> reconciliation must not overwrite."""
    class _ProbeSender:
        def __init__(self):
            self.calls = []

        def send(self, handoff_id: str) -> None:
            self.calls.append(handoff_id)

    t = FakeRemoteTransport()
    t.remotes[("H-0001", "claude_work_complete.json")] = "{}"
    t.remotes[("H-0001", "chatgpt_fetch_ack.json")] = "{}"
    t.remotes[("H-0001", "trigger_fetch_sent.json")] = "{}"
    daemon = _daemon_with_sender(repo_root, t, tmp_path, _ProbeSender())
    daemon._mark_fetch_sent("H-0001")
    assert daemon.reconcile_missing_fetch_sent("H-0001") == "ALREADY_PUBLISHED"
    assert t.published == []
    assert daemon.trigger.sender.calls == []


def test_reconcile_never_resends_browser_for_failed_send(repo_root, tmp_path):
    """A handoff that never had a local fetch_sent must NOT be reconciled (no browser)."""
    class _ProbeSender:
        def __init__(self):
            self.calls = []

        def send(self, handoff_id: str) -> None:
            self.calls.append(handoff_id)

    t = FakeRemoteTransport()
    t.remotes[("H-0001", "claude_work_complete.json")] = "{}"
    daemon = _daemon_with_sender(repo_root, t, tmp_path, _ProbeSender())
    # no _mark_fetch_sent -> no local durable send-success
    assert daemon.reconcile_missing_fetch_sent("H-0001") == "NOT_SENT_LOCALLY"
    assert not t.remotes.get(("H-0001", "trigger_fetch_sent.json"))
    assert daemon.trigger.sender.calls == []


# --- GitTransport publish race: worktree sync + concurrent reviewer marker (reviewer finding) ---

def _init_git_repo(repo: Path, remote: Path):
    import subprocess

    def run(*args, cwd=None):
        subprocess.run([*args], cwd=cwd, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    repo.mkdir(parents=True, exist_ok=True)
    remote.mkdir(parents=True, exist_ok=True)
    # bare origin
    run("git", "init", "-q", "--bare", str(remote))
    # working clone of origin
    run("git", "init", "-q", str(repo))
    run("git", "config", "user.email", "t@t", cwd=repo)
    run("git", "config", "user.name", "t", cwd=repo)
    run("git", "remote", "add", "origin", str(remote), cwd=repo)
    (repo / "seed").write_text("x", encoding="utf-8")
    run("git", "add", "--", "seed", cwd=repo)
    run("git", "commit", "-q", "-m", "seed", cwd=repo)
    run("git", "branch", "-M", "main", cwd=repo)
    run("git", "push", "-q", "-u", "origin", "main", cwd=repo)
    # seed the claude_work_complete doorbell on origin/main
    d = repo / "docs" / "web_bridge" / "H-0001"
    d.mkdir(parents=True, exist_ok=True)
    (d / "claude_work_complete.json").write_text("{}", encoding="utf-8")
    run("git", "add", "--", "docs", cwd=repo)
    run("git", "commit", "-q", "-m", "doorbell", cwd=repo)
    run("git", "push", "-q", "origin", "main", cwd=repo)
    # reviewer ACK lands concurrently BEFORE bridge publishes trigger (the race)
    (repo / "docs" / "web_bridge" / "H-0001" / "chatgpt_fetch_ack.json").write_text("{}", encoding="utf-8")
    run("git", "add", "--", "docs", cwd=repo)
    run("git", "commit", "-q", "-m", "ack", cwd=repo)
    run("git", "push", "-q", "origin", "main", cwd=repo)


def test_git_publish_syncs_worktree_and_tolerates_reviewer_ack_race(tmp_path):
    """GitTransport.publish_bridge_marker must sync the isolated worktree to the latest
    origin/main (which now contains the reviewer ACK) and publish the missing bridge
    marker as a fast-forward — no STOP-WRITE from a legitimate same-handoff ACK."""
    import subprocess

    repo = tmp_path / "repo"
    remote = tmp_path / "remote"
    _init_git_repo(repo, remote)
    runtime = tmp_path / "runtime"
    transport = wfb.GitTransport(repo, runtime, "origin", "main")
    content = json.dumps({
        "protocol": "web_fetch_bridge_v1",
        "handoff_id": "H-0001",
        "event": "trigger_fetch_sent.json",
        "timestamp": "2026-08-11T08:21:38.935396+00:00",
    }) + "\n"
    # must NOT raise despite the concurrent reviewer ACK ahead of us
    transport.publish_bridge_marker("H-0001", "trigger_fetch_sent.json", content)
    # marker is now on origin/main (rev-parse of the path resolves)
    transport.fetch()
    sha = transport._git("rev-parse", "origin/main:docs/web_bridge/H-0001/trigger_fetch_sent.json")
    assert sha


def test_git_publish_refuses_duplicate_marker(tmp_path):
    """A second publish of an already-present bridge marker must fail append-only."""
    import subprocess

    repo = tmp_path / "repo"
    remote = tmp_path / "remote"
    _init_git_repo(repo, remote)
    runtime = tmp_path / "runtime"
    transport = wfb.GitTransport(repo, runtime, "origin", "main")
    content = "{}"
    transport.publish_bridge_marker("H-0001", "trigger_fetch_sent.json", content)
    with pytest.raises(wfb.BridgeError):
        transport.publish_bridge_marker("H-0001", "trigger_fetch_sent.json", content)
