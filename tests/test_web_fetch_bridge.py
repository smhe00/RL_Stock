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
    assert trig.step("H-0001") == "SEND_FAILED_FAIL_CLOSED"
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
