import json
from pathlib import Path

import pytest

from webgpt_wake_bridge.errors import BridgeError
from webgpt_wake_bridge.markers import MarkerStore, validate_marker, validate_timestamp


def test_timezone_aware_required():
    validate_timestamp("2026-08-11T09:18:39+00:00")
    with pytest.raises(BridgeError):
        validate_timestamp("2026-08-11T09:18:39")


def test_semantic_event_alias_is_backward_compatible():
    marker = {
        "protocol": "web_fetch_bridge_v1",
        "handoff_id": "H_001",
        "event": "CHATGPT_FETCH_ACK",
        "timestamp": "2026-08-11T09:18:39+00:00",
    }
    validate_marker(Path("chatgpt_fetch_ack.json"), marker)


def test_marker_event_must_match_filename():
    marker = {
        "protocol": "web_fetch_bridge_v1",
        "handoff_id": "H_001",
        "event": "CHATGPT_FETCH_ACK",
        "timestamp": "2026-08-11T09:18:39+00:00",
    }
    with pytest.raises(BridgeError):
        validate_marker(Path("claude_work_complete.json"), marker)


def test_marker_store_append_only_and_ownership(tmp_path):
    store = MarkerStore(tmp_path, Path("docs/web_bridge"))
    path = store.write_bridge_marker("H_001", "trigger_fetch_sent.json")
    assert json.loads(path.read_text())["event"] == "trigger_fetch_sent.json"
    with pytest.raises(BridgeError):
        store.write_bridge_marker("H_001", "trigger_fetch_sent.json")
    with pytest.raises(BridgeError):
        store.write_bridge_marker("H_002", "chatgpt_fetch_ack.json")


def test_ack_before_trigger_is_valid_transient(tmp_path):
    store = MarkerStore(tmp_path, Path("docs/web_bridge"))
    d = store.handoff_dir("H_003")
    d.mkdir(parents=True)
    common = {
        "protocol": "web_fetch_bridge_v1",
        "handoff_id": "H_003",
        "timestamp": "2026-08-11T09:18:39+00:00",
    }
    (d / "claude_work_complete.json").write_text(
        json.dumps({**common, "event": "claude_work_complete.json"}), encoding="utf-8"
    )
    (d / "chatgpt_fetch_ack.json").write_text(
        json.dumps({**common, "event": "CHATGPT_FETCH_ACK"}), encoding="utf-8"
    )
    assert store.ordered_markers("H_003") == ["claude_work_complete.json", "chatgpt_fetch_ack.json"]


def test_terminal_review_requires_ack(tmp_path):
    store = MarkerStore(tmp_path, Path("docs/web_bridge"))
    d = store.handoff_dir("H_004")
    d.mkdir(parents=True)
    common = {
        "protocol": "web_fetch_bridge_v1",
        "handoff_id": "H_004",
        "timestamp": "2026-08-11T09:18:39+00:00",
    }
    (d / "claude_work_complete.json").write_text(
        json.dumps({**common, "event": "claude_work_complete.json"}), encoding="utf-8"
    )
    (d / "chatgpt_review_published.json").write_text(
        json.dumps({**common, "event": "chatgpt_review_published.json"}), encoding="utf-8"
    )
    with pytest.raises(BridgeError):
        store.ordered_markers("H_004")


def test_handoff_path_cannot_escape_repo(tmp_path):
    store = MarkerStore(tmp_path, Path("docs/web_bridge"))
    with pytest.raises(BridgeError):
        store.handoff_dir("../bad")
