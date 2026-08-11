from __future__ import annotations

import json
import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Protocol

from .config import BridgeConfig
from .errors import BridgeError
from .markers import PROTOCOL, atomic_write_text, utcnow_iso, validate_handoff_id, validate_marker
from .transport_git import GitTransport


class FetchSender(Protocol):
    def send(self, handoff_id: str) -> None: ...


def trigger_marker_text(handoff_id: str, *, timestamp: str | None = None) -> str:
    validate_handoff_id(handoff_id)
    marker = {
        "protocol": PROTOCOL,
        "handoff_id": handoff_id,
        "event": "trigger_fetch_sent.json",
        "timestamp": timestamp or utcnow_iso(),
    }
    validate_marker(Path("trigger_fetch_sent.json"), marker, expected_owner="bridge_trigger")
    return json.dumps(marker, indent=2, sort_keys=True) + "\n"


def configure_logging(config: BridgeConfig) -> logging.Logger:
    log_dir = config.runtime_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(f"webgpt_wake_bridge:{config.repo_root}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler = RotatingFileHandler(
        log_dir / "webgpt_wake_bridge.log",
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


class RemoteMarkerWatcher:
    """Marker-only daemon. It never reads consumer-project research/status files.

    Local dedup state is deliberately more conservative than the remote marker
    protocol. `attempt_started` is persisted before touching the browser, closing the
    crash window where a submitted message could otherwise be resent after restart.
    An uncertain/failed attempt is never retried automatically.
    """

    def __init__(self, config: BridgeConfig, transport: GitTransport, sender: FetchSender, logger: logging.Logger):
        self.config = config
        self.transport = transport
        self.sender = sender
        self.logger = logger
        self.dedup_path = config.runtime_dir / "dedup.json"

    def _load_state(self) -> dict:
        state = {"attempt_started": {}, "fetch_sent": {}, "attempt_failed": {}}
        if not self.dedup_path.exists():
            return state
        try:
            loaded = json.loads(self.dedup_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return state
        if isinstance(loaded, dict):
            for key in state:
                if isinstance(loaded.get(key), dict):
                    state[key] = loaded[key]
        return state

    def _save_state(self, state: dict) -> None:
        atomic_write_text(self.dedup_path, json.dumps(state, indent=2, sort_keys=True) + "\n")

    def _seen(self, handoff_id: str) -> bool:
        state = self._load_state()
        return any(handoff_id in state[key] for key in ("attempt_started", "fetch_sent", "attempt_failed"))

    def _mark_started(self, handoff_id: str, marker_text: str) -> None:
        state = self._load_state()
        state["attempt_started"][handoff_id] = {
            "timestamp": utcnow_iso(),
            "marker": marker_text,
        }
        self._save_state(state)

    def _mark_failed(self, handoff_id: str, reason: str, marker_text: str) -> None:
        state = self._load_state()
        state["attempt_started"].pop(handoff_id, None)
        state["attempt_failed"][handoff_id] = {
            "timestamp": utcnow_iso(),
            "reason": reason,
            "marker": marker_text,
        }
        self._save_state(state)

    def _mark_sent(self, handoff_id: str, marker_text: str) -> None:
        state = self._load_state()
        state["attempt_started"].pop(handoff_id, None)
        state["attempt_failed"].pop(handoff_id, None)
        state["fetch_sent"][handoff_id] = {"timestamp": utcnow_iso(), "marker": marker_text}
        self._save_state(state)

    def clear_failure(self, handoff_id: str) -> bool:
        """Explicit operator retry clears only uncertain/failed attempts, never sent ones."""
        validate_handoff_id(handoff_id)
        state = self._load_state()
        removed = False
        for key in ("attempt_started", "attempt_failed"):
            removed = state[key].pop(handoff_id, None) is not None or removed
        if removed:
            self._save_state(state)
        return removed

    def _remote_marker_valid(self, handoff_id: str, name: str) -> bool:
        text = self.transport.marker_text(handoff_id, name)
        if text is None:
            return False
        try:
            marker = json.loads(text)
            validate_marker(Path(name), marker)
            return marker.get("handoff_id") == handoff_id
        except (json.JSONDecodeError, BridgeError) as exc:
            raise BridgeError(f"remote marker {name} is invalid for {handoff_id}") from exc

    def discover_eligible_handoffs(self) -> list[str]:
        eligible: list[str] = []
        for handoff_id in sorted(self.transport.list_handoff_dirs()):
            try:
                validate_handoff_id(handoff_id)
            except BridgeError:
                continue
            if self.transport.marker_exists(handoff_id, "chatgpt_review_published.json"):
                continue
            if self.transport.marker_exists(handoff_id, "chatgpt_fetch_ack.json"):
                continue
            if self.transport.marker_exists(handoff_id, "trigger_fetch_sent.json"):
                continue
            if self.transport.marker_exists(handoff_id, "claude_work_complete.json"):
                self._remote_marker_valid(handoff_id, "claude_work_complete.json")
                eligible.append(handoff_id)
        return eligible

    def _durable_attempt_marker(self, handoff_id: str) -> str | None:
        state = self._load_state()
        for key in ("fetch_sent", "attempt_started", "attempt_failed"):
            record = state[key].get(handoff_id)
            if isinstance(record, dict) and record.get("marker"):
                return str(record["marker"])
        return None

    def _attempt_handoffs(self) -> list[str]:
        state = self._load_state()
        ids: set[str] = set()
        for key in ("fetch_sent", "attempt_started", "attempt_failed"):
            ids.update(state[key])
        return sorted(ids)

    def reconcile_missing_trigger(self, handoff_id: str) -> str:
        """Publish only the missing trigger when a Web ACK proves browser receipt.

        This works even after a crash/uncertain sender result because the trigger
        marker text is persisted before the browser action. Reconciliation never
        calls the browser.
        """
        validate_handoff_id(handoff_id)
        self.transport.fetch()
        marker_text = self._durable_attempt_marker(handoff_id)
        if not marker_text:
            return "NOT_SENT_LOCALLY"
        if self.transport.marker_exists(handoff_id, "trigger_fetch_sent.json"):
            return "ALREADY_PUBLISHED"
        if not self.transport.marker_exists(handoff_id, "chatgpt_fetch_ack.json"):
            return "NO_MATCHING_ACK"
        self._remote_marker_valid(handoff_id, "chatgpt_fetch_ack.json")
        self.transport.publish_bridge_marker(handoff_id, "trigger_fetch_sent.json", marker_text)
        self._mark_sent(handoff_id, marker_text)
        return "RECONCILE_PUBLISHED"

    def scan_once(self) -> list[str]:
        outcomes: list[str] = []
        for handoff_id in self.discover_eligible_handoffs():
            if self._seen(handoff_id):
                continue

            # Precompute + persist the bridge marker before browser interaction. If the
            # process dies at any later point, restart sees attempt_started and will not
            # automatically submit the handoff again.
            marker = trigger_marker_text(handoff_id)
            self._mark_started(handoff_id, marker)
            try:
                self.sender.send(handoff_id)
            except Exception as exc:  # noqa: BLE001
                self._mark_failed(handoff_id, str(exc), marker)
                outcomes.append(f"{handoff_id}:SEND_FAILED_FAIL_CLOSED")
                continue

            self._mark_sent(handoff_id, marker)
            try:
                self.transport.publish_bridge_marker(handoff_id, "trigger_fetch_sent.json", marker)
                outcomes.append(f"{handoff_id}:FETCH_SENT")
            except Exception as exc:  # noqa: BLE001 - any transport failure is fail-closed
                self.logger.warning("event=trigger_publish_failed handoff=%s reason=%s", handoff_id, exc)
                outcomes.append(f"{handoff_id}:PUBLISH_FAILED_FAIL_CLOSED")

        # ACK-before-trigger or crash-window recovery. This path never calls browser.
        for handoff_id in self._attempt_handoffs():
            if self.transport.marker_exists(handoff_id, "trigger_fetch_sent.json"):
                continue
            if not self.transport.marker_exists(handoff_id, "chatgpt_fetch_ack.json"):
                continue
            try:
                result = self.reconcile_missing_trigger(handoff_id)
            except Exception as exc:  # noqa: BLE001 - reconciliation also fails closed
                self.logger.warning("event=reconcile_failed handoff=%s reason=%s", handoff_id, exc)
                outcomes.append(f"{handoff_id}:RECONCILE_FAILED")
            else:
                if result == "RECONCILE_PUBLISHED":
                    outcomes.append(f"{handoff_id}:RECONCILE_PUBLISHED")
        return outcomes

    def run_forever(self) -> None:
        self.logger.info("event=bridge_daemon_started repo=%s", self.config.repo_root)
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
