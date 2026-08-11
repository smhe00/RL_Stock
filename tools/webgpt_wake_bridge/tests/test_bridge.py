import json
import logging
from pathlib import Path

from webgpt_wake_bridge.bridge import RemoteMarkerWatcher
from webgpt_wake_bridge.config import BridgeConfig
from webgpt_wake_bridge.errors import BridgeError


class FakeTransport:
    def __init__(self):
        self.markers = {}
        self.publish_calls = []
        self.fail_first_publish = False

    def list_handoff_dirs(self):
        return {handoff for handoff, _ in self.markers}

    def marker_exists(self, handoff, name):
        return (handoff, name) in self.markers

    def marker_text(self, handoff, name):
        return self.markers.get((handoff, name))

    def publish_bridge_marker(self, handoff, name, content):
        self.publish_calls.append((handoff, name))
        if self.fail_first_publish:
            self.fail_first_publish = False
            raise BridgeError("simulated remote race")
        self.markers[(handoff, name)] = content


class Sender:
    def __init__(self, fail=False, on_send=None):
        self.calls = 0
        self.fail = fail
        self.on_send = on_send

    def send(self, handoff):
        self.calls += 1
        if self.on_send:
            self.on_send(handoff)
        if self.fail:
            raise RuntimeError("send failed")


def marker(handoff, event):
    return json.dumps({
        "protocol": "web_fetch_bridge_v1",
        "handoff_id": handoff,
        "event": event,
        "timestamp": "2026-08-11T09:18:39+00:00",
    })


def config(tmp_path):
    return BridgeConfig(
        repo_root=tmp_path,
        marker_root=Path("docs/web_bridge"),
        remote="origin", branch="main",
        cdp_endpoint="http://127.0.0.1:9222",
        chrome_profile_path="C:/profile",
        target_conversation_url="https://chatgpt.com/c/x",
        poll_interval_s=5, fetch_ack_timeout_s=120,
        runtime_dir=tmp_path / ".runtime",
        max_log_bytes=65536, log_backups=1,
    )


def test_successful_send_is_deduped_before_publish(tmp_path):
    t = FakeTransport()
    h = "H_001"
    t.markers[(h, "claude_work_complete.json")] = marker(h, "claude_work_complete.json")
    sender = Sender()
    watcher = RemoteMarkerWatcher(config(tmp_path), t, sender, logging.getLogger("test"))
    assert watcher.scan_once() == [f"{h}:FETCH_SENT"]
    assert sender.calls == 1
    watcher.scan_once()
    assert sender.calls == 1


def test_sender_failure_is_terminal_no_auto_retry(tmp_path):
    t = FakeTransport()
    h = "H_002"
    t.markers[(h, "claude_work_complete.json")] = marker(h, "claude_work_complete.json")
    sender = Sender(fail=True)
    watcher = RemoteMarkerWatcher(config(tmp_path), t, sender, logging.getLogger("test"))
    assert watcher.scan_once() == [f"{h}:SEND_FAILED_FAIL_CLOSED"]
    watcher.scan_once()
    assert sender.calls == 1


def test_ack_before_trigger_reconciles_without_resend(tmp_path):
    t = FakeTransport()
    h = "H_003"
    t.markers[(h, "claude_work_complete.json")] = marker(h, "claude_work_complete.json")

    def ack_on_send(handoff):
        t.markers[(handoff, "chatgpt_fetch_ack.json")] = marker(handoff, "CHATGPT_FETCH_ACK")

    sender = Sender(on_send=ack_on_send)
    t.fail_first_publish = True
    watcher = RemoteMarkerWatcher(config(tmp_path), t, sender, logging.getLogger("test"))
    outcomes = watcher.scan_once()
    assert f"{h}:PUBLISH_FAILED_FAIL_CLOSED" in outcomes
    assert f"{h}:RECONCILE_PUBLISHED" in outcomes
    assert sender.calls == 1
    assert t.marker_exists(h, "trigger_fetch_sent.json")
