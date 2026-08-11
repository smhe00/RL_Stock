from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .errors import BridgeError

PROTOCOL = "web_fetch_bridge_v1"
HANDOFF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,159}$")
MARKER_OWNERS = {
    "claude_review_ack.json": "claude",
    "claude_work_complete.json": "claude",
    "trigger_fetch_sent.json": "bridge_trigger",
    "chatgpt_fetch_ack.json": "web_chatgpt",
    "chatgpt_review_published.json": "web_chatgpt",
}
MARKER_ORDER = list(MARKER_OWNERS)
BRIDGE_OWNED_MARKERS = {"trigger_fetch_sent.json"}
EVENT_ALIASES = {
    "CLAUDE_REVIEW_ACK": "claude_review_ack.json",
    "CLAUDE_WORK_COMPLETE": "claude_work_complete.json",
    "TRIGGER_FETCH_SENT": "trigger_fetch_sent.json",
    "CHATGPT_FETCH_ACK": "chatgpt_fetch_ack.json",
    "CHATGPT_REVIEW_PUBLISHED": "chatgpt_review_published.json",
}
REQUIRED_MARKER_FIELDS = ("protocol", "handoff_id", "event", "timestamp")
FORBIDDEN_MARKER_FIELDS = ("api_key", "token", "cookie", "password", "secret")


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def validate_handoff_id(handoff_id: str) -> str:
    if not HANDOFF_RE.fullmatch(handoff_id):
        raise BridgeError("handoff_id is missing or unsafe")
    return handoff_id


def validate_timestamp(raw: object) -> None:
    if not isinstance(raw, str) or not raw.strip():
        raise BridgeError("marker timestamp must be a non-empty string")
    try:
        ts = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise BridgeError(f"marker timestamp is not ISO-8601: {raw}") from exc
    if ts.tzinfo is None or ts.utcoffset() is None:
        raise BridgeError(f"marker timestamp must be timezone-aware: {raw}")


def validate_marker(path: Path, marker: dict, expected_owner: str | None = None) -> None:
    if not isinstance(marker, dict):
        raise BridgeError(f"marker {path.name} is not a JSON object")
    missing = [field for field in REQUIRED_MARKER_FIELDS if field not in marker]
    if missing:
        raise BridgeError(f"marker {path.name} missing fields {missing}")
    if marker.get("handoff_id") and not HANDOFF_RE.fullmatch(str(marker["handoff_id"])):
        raise BridgeError(f"marker {path.name} has unsafe handoff_id")
    for field in FORBIDDEN_MARKER_FIELDS:
        if marker.get(field):
            raise BridgeError(f"marker {path.name} must not contain {field}")
    if marker.get("protocol") != PROTOCOL:
        raise BridgeError(f"marker {path.name} has wrong protocol")
    event = marker.get("event")
    if event not in MARKER_ORDER and event not in EVENT_ALIASES:
        raise BridgeError(f"marker {path.name} has unknown event")
    if expected_owner is not None and MARKER_OWNERS.get(path.name) != expected_owner:
        raise BridgeError(f"marker {path.name} is not owned by {expected_owner}")
    validate_timestamp(marker.get("timestamp"))


class MarkerStore:
    """Append-only marker access inside one consumer repository."""

    def __init__(self, repo_root: Path, marker_root: Path):
        self.repo_root = repo_root.resolve()
        self.marker_root = marker_root

    def handoff_dir(self, handoff_id: str) -> Path:
        validate_handoff_id(handoff_id)
        path = (self.repo_root / self.marker_root / handoff_id).resolve()
        try:
            path.relative_to(self.repo_root)
        except ValueError as exc:
            raise BridgeError("marker path escapes repository") from exc
        return path

    def exists(self, handoff_id: str, name: str) -> bool:
        if name not in MARKER_OWNERS:
            raise BridgeError(f"unknown marker name {name}")
        return (self.handoff_dir(handoff_id) / name).is_file()

    def read(self, handoff_id: str, name: str) -> dict:
        path = self.handoff_dir(handoff_id) / name
        try:
            marker = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise BridgeError(f"marker {name} unreadable") from exc
        validate_marker(path, marker)
        if marker.get("handoff_id") != handoff_id:
            raise BridgeError(f"marker {name} handoff mismatch")
        return marker

    def ordered_markers(self, handoff_id: str) -> list[str]:
        directory = self.handoff_dir(handoff_id)
        present = [name for name in MARKER_ORDER if (directory / name).is_file()]
        if "chatgpt_review_published.json" in present and "claude_work_complete.json" not in present:
            raise BridgeError("chatgpt_review_published without claude_work_complete")
        return present

    def write_bridge_marker(self, handoff_id: str, name: str, extra: dict | None = None) -> Path:
        if name not in BRIDGE_OWNED_MARKERS:
            raise BridgeError(f"bridge may only write {sorted(BRIDGE_OWNED_MARKERS)}")
        path = self.handoff_dir(handoff_id) / name
        if path.exists():
            raise BridgeError(f"bridge marker {name} already exists; append-only")
        marker = {
            "protocol": PROTOCOL,
            "handoff_id": handoff_id,
            "event": name,
            "timestamp": utcnow_iso(),
        }
        if extra:
            marker.update(extra)
        validate_marker(path, marker, expected_owner="bridge_trigger")
        atomic_write_text(path, json.dumps(marker, indent=2, sort_keys=True) + "\n")
        return path
