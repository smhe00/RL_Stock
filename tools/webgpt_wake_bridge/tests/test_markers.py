import json
from pathlib import Path

import pytest

from webgpt_wake_bridge.errors import BridgeError
from webgpt_wake_bridge.markers import MARKER_ORDER, MarkerStore, validate_marker, validate_timestamp


def marker(handoff: str, event: str) -> dict:
    return {
        "protocol": "web_fetch_bridge_v1",
        "handoff_id": handoff,
        "event": event,
        "timestamp": "2026-08-11T09:18:39+00:00",
    }


def test_timezone_aware_required():
    validate_timestamp("2026-08-11T09:18:39+00:00")
    with pytest.raises(BridgeError):
        validate_timestamp("2026-08-11T09:18:39")


def test_semantic_event_alias_is_backward_compatible_only_for_matching_file():
    validate_marker(Path("chatgpt_fetch_ack.json"), marker("H_001", "CHATGPT_FETCH_ACK"))
    with pytest.raises(BridgeError):
        validate_marker(Path("claude_work_complete.json"), marker("H_001", "CHATGPT_FETCH_ACK"))


def test_marker_order_matches_one_complete_review_cycle():
    assert MARKER_ORDER == [
        "claude_work_complete.json",
        "trigger_fetch_sent.json",
        "chatgpt_fetch_ack.json",
        "chatgpt_review_published.json",
        "claude_review_ack.json",
    ]


def test_marker_store_append_only_and_ownership(tmp_path):
    store = MarkerStore(tmp_path, Path("docs/web_bridge"))
    path = store.write_bridge_marker("H_001", "trigger_fetch_sent.json")
    assert json.loads(path.read_text())["event"] == "trigger_fetch_sent.json"
    with pytest.raises(BridgeError):
        store.write_bridge_marker("H_001", "trigger_fetch_sent.json")
    with pytest.raises(BridgeError):
        store.write_bridge_marker("H_002", "chatgpt_fetch_ack.json")


def test_handoff_path_cannot_escape_repo(tmp_path):
    store = MarkerStore(tmp_path, Path("docs/web_bridge"))
    with pytest.raises(BridgeError):
        store.handoff_dir("../bad")


def test_ack_before_trigger_is_allowed_transient_but_terminal_dependencies_are_enforced(tmp_path):
    store = MarkerStore(tmp_path, Path("docs/web_bridge"))
    directory = store.handoff_dir("H_003")
    directory.mkdir(parents=True)
    (directory / "claude_work_complete.json").write_text(
        json.dumps(marker("H_003", "claude_work_complete.json")), encoding="utf-8"
    )
    (directory / "chatgpt_fetch_ack.json").write_text(
        json.dumps(marker("H_003", "CHATGPT_FETCH_ACK")), encoding="utf-8"
    )
    assert store.ordered_markers("H_003") == [
        "claude_work_complete.json", "chatgpt_fetch_ack.json"
    ]

    (directory / "chatgpt_review_published.json").write_text(
        json.dumps(marker("H_003", "CHATGPT_REVIEW_PUBLISHED")), encoding="utf-8"
    )
    assert "chatgpt_review_published.json" in store.ordered_markers("H_003")

    # A Claude review ACK without a published Web review is never valid.
    other = store.handoff_dir("H_004")
    other.mkdir(parents=True)
    (other / "claude_review_ack.json").write_text(
        json.dumps(marker("H_004", "CLAUDE_REVIEW_ACK")), encoding="utf-8"
    )
    with pytest.raises(BridgeError):
        store.ordered_markers("H_004")
