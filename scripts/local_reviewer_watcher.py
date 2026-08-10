"""Local Claude-to-Codex reviewer watcher.

The Codex subprocess is read-only. This process validates the structured result
and writes only reviewer-owned protocol files after STOP-WRITE checks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import tomllib
from typing import Callable, Protocol

import yaml


TRIGGER_STATES = frozenset({"READY_FOR_REVIEW", "BLOCKED", "TEST_FAILED"})
REVIEWER_STATES = frozenset({"REVIEW_COMPLETE", "REVISIONS_REQUIRED", "BLOCKED"})
HANDOFF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,159}$")
CLAUDE_STATUS = Path("docs/agent_state/CLAUDE_STATUS.yaml")
REVIEWER_STATE = Path("docs/reviewer_state/CHATGPT_REVIEW.yaml")
PACKET_ROOT = Path("docs/review_packets")
RESPONSE_ROOT = Path("docs/reviewer_responses")


class ReviewError(RuntimeError):
    """A fail-closed local-review error."""


@dataclass(frozen=True)
class WatcherConfig:
    repo_root: Path
    poll_interval_seconds: float
    codex_command: str
    codex_timeout_seconds: int
    runtime_dir: Path
    output_schema: Path
    max_log_bytes: int
    log_backups: int
    remote: str = "origin"
    remote_branch: str = "main"
    publish_checkpoint: bool = True
    allow_authorized_next: bool = False


@dataclass(frozen=True)
class ClaudeHandoff:
    handoff_id: str
    state: str
    packet: str
    code_commit: str
    packet_available: bool = True


@dataclass(frozen=True)
class GuardToken:
    git_head: str
    claude_status_digest: str
    packet_digest: str
    reviewer_state_digest: str


@dataclass(frozen=True)
class ReviewPayload:
    handoff_id: str
    reviewer_state: str
    decision: str
    response_markdown: str
    passed: list[str]
    revision_required: list[str]
    authorized_next: list[str]
    forbidden_next: list[str]
    notes: list[str]
    reviewed_packet: str
    reviewed_commit: str


class ReviewRunner(Protocol):
    def run(self, handoff: ClaudeHandoff) -> ReviewPayload: ...


class CheckpointPublisher(Protocol):
    def prepare(self, guard: GuardToken) -> None: ...

    def publish(
        self, paths: list[Path], handoff: ClaudeHandoff, guard: GuardToken
    ) -> None: ...


def _repo_path(repo_root: Path, relative: str | Path) -> Path:
    path = (repo_root / relative).resolve()
    try:
        path.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ReviewError(f"path escapes repository: {relative}") from exc
    return path


def _digest(path: Path) -> str:
    if not path.exists():
        return "MISSING"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(repo_root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args],
            cwd=repo_root,
            text=True,
            encoding="utf-8",
            stderr=subprocess.STDOUT,
        ).strip()
    except (OSError, UnicodeError, subprocess.CalledProcessError) as exc:
        raise ReviewError(f"git command failed: {' '.join(args[:2])}") from exc


def _fetch(config: WatcherConfig) -> None:
    _git(config.repo_root, "fetch", config.remote, config.remote_branch)


def _remote_ref(config: WatcherConfig) -> str:
    return f"{config.remote}/{config.remote_branch}"


def _git_show(config: WatcherConfig, relative: str | Path) -> str:
    path = Path(relative).as_posix()
    return _git(config.repo_root, "show", f"{_remote_ref(config)}:{path}")


def _load_yaml_mapping(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ReviewError(f"cannot read protocol YAML: {path.name}") from exc
    return _load_yaml_text(text, path.name)


def _parse_top_level_scalars(text: str) -> dict[str, str]:
    """Compatibility parser for legacy status files with unquoted nested text."""
    values: dict[str, str] = {}
    for raw in text.splitlines():
        if not raw or raw[0].isspace() or raw.lstrip().startswith("#") or ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        values[key.strip()] = value.strip().strip('"\'')
    return values


def _load_yaml_text(text: str, label: str) -> dict:
    try:
        value = yaml.safe_load(text)
    except yaml.YAMLError:
        value = _parse_top_level_scalars(text)
    if not isinstance(value, dict):
        raise ReviewError(f"protocol YAML must be a mapping: {label}")
    return value


def _handoff_from_mapping(data: dict, packet_available: bool = True) -> ClaudeHandoff:
    if str(data.get("actor", "")).strip() != "claude":
        raise ReviewError("CLAUDE_STATUS actor must be claude")

    handoff_id = str(data.get("handoff_id", "")).strip()
    if not HANDOFF_RE.fullmatch(handoff_id):
        raise ReviewError("handoff_id is missing or unsafe")

    return ClaudeHandoff(
        handoff_id=handoff_id,
        state=str(data.get("state", "")).strip().upper(),
        packet=str(data.get("packet", "") or "").strip().replace("\\", "/"),
        code_commit=str(data.get("code_commit", "") or "").strip(),
        packet_available=packet_available,
    )


def read_handoff(repo_root: Path) -> ClaudeHandoff:
    data = _load_yaml_mapping(_repo_path(repo_root, CLAUDE_STATUS))
    handoff = _handoff_from_mapping(data)

    if handoff.packet:
        packet_path = _repo_path(repo_root, handoff.packet)
        try:
            packet_path.relative_to(_repo_path(repo_root, PACKET_ROOT))
        except ValueError as exc:
            raise ReviewError("packet must stay under docs/review_packets") from exc

    return ClaudeHandoff(
        handoff_id=handoff.handoff_id,
        state=handoff.state,
        packet=handoff.packet,
        code_commit=handoff.code_commit,
        packet_available=(not handoff.packet or packet_path.is_file()),
    )


def read_remote_handoff(config: WatcherConfig) -> ClaudeHandoff:
    _fetch(config)
    status_text = _git_show(config, CLAUDE_STATUS)
    data = _load_yaml_text(status_text, CLAUDE_STATUS.as_posix())
    handoff = _handoff_from_mapping(data)
    if handoff.packet:
        packet = Path(handoff.packet)
        if packet.is_absolute() or ".." in packet.parts:
            raise ReviewError("remote packet path is unsafe")
        if packet.as_posix() == PACKET_ROOT.as_posix() or not packet.as_posix().startswith(
            PACKET_ROOT.as_posix() + "/"
        ):
            raise ReviewError("remote packet must stay under docs/review_packets")
        try:
            _git_show(config, handoff.packet)
            available = True
        except ReviewError:
            available = False
    else:
        available = True
    return ClaudeHandoff(
        handoff_id=handoff.handoff_id,
        state=handoff.state,
        packet=handoff.packet,
        code_commit=handoff.code_commit,
        packet_available=available,
    )


def capture_guard(repo_root: Path, handoff: ClaudeHandoff) -> GuardToken:
    """Local-file guard retained for deterministic unit tests."""
    packet_digest = "NO_PACKET" if not handoff.packet else _digest(
        _repo_path(repo_root, handoff.packet)
    )
    return GuardToken(
        git_head=_git(repo_root, "rev-parse", "HEAD"),
        claude_status_digest=_digest(_repo_path(repo_root, CLAUDE_STATUS)),
        packet_digest=packet_digest,
        reviewer_state_digest=_digest(_repo_path(repo_root, REVIEWER_STATE)),
    )


def capture_remote_guard(config: WatcherConfig, handoff: ClaudeHandoff) -> GuardToken:
    _fetch(config)
    ref = _remote_ref(config)
    status_text = _git_show(config, CLAUDE_STATUS)
    packet_digest = "NO_PACKET"
    if handoff.packet:
        try:
            packet_digest = hashlib.sha256(
                _git_show(config, handoff.packet).encode("utf-8")
            ).hexdigest()
        except ReviewError:
            packet_digest = "MISSING"
    try:
        reviewer_text = _git_show(config, REVIEWER_STATE)
        reviewer_digest = hashlib.sha256(reviewer_text.encode("utf-8")).hexdigest()
    except ReviewError:
        reviewer_digest = "MISSING"
    return GuardToken(
        git_head=_git(config.repo_root, "rev-parse", ref),
        claude_status_digest=hashlib.sha256(status_text.encode("utf-8")).hexdigest(),
        packet_digest=packet_digest,
        reviewer_state_digest=reviewer_digest,
    )


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


class StateStore:
    """Persistent exactly-once claims for automatic handoff processing."""

    def __init__(self, path: Path):
        self.path = path

    def _read(self) -> dict:
        if not self.path.exists():
            return {"schema_version": 1, "handoffs": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ReviewError("local reviewer state file is unreadable") from exc
        if not isinstance(data, dict) or not isinstance(data.get("handoffs"), dict):
            raise ReviewError("local reviewer state file has an invalid schema")
        return data

    def seen(self, handoff_id: str) -> bool:
        return handoff_id in self._read()["handoffs"]

    def mark(self, handoff_id: str, state: str) -> None:
        data = self._read()
        data["handoffs"][handoff_id] = {
            "state": state,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        _atomic_write_text(self.path, json.dumps(data, indent=2, sort_keys=True) + "\n")

    def forget(self, handoff_id: str) -> bool:
        data = self._read()
        removed = data["handoffs"].pop(handoff_id, None) is not None
        if removed:
            _atomic_write_text(self.path, json.dumps(data, indent=2, sort_keys=True) + "\n")
        return removed


def _string_list(value: object, field: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ReviewError(f"Codex result field {field} must be a string array")
    return [item.strip() for item in value if item.strip()]


def validate_payload(
    raw: object, handoff: ClaudeHandoff, allow_authorized_next: bool
) -> ReviewPayload:
    if not isinstance(raw, dict):
        raise ReviewError("Codex result must be a JSON object")

    payload = ReviewPayload(
        handoff_id=str(raw.get("handoff_id", "")).strip(),
        reviewer_state=str(raw.get("reviewer_state", "")).strip(),
        decision=str(raw.get("decision", "")).strip(),
        response_markdown=str(raw.get("response_markdown", "")).strip(),
        passed=_string_list(raw.get("passed"), "passed"),
        revision_required=_string_list(raw.get("revision_required"), "revision_required"),
        authorized_next=_string_list(raw.get("authorized_next"), "authorized_next"),
        forbidden_next=_string_list(raw.get("forbidden_next"), "forbidden_next"),
        notes=_string_list(raw.get("notes"), "notes"),
        reviewed_packet=str(raw.get("reviewed_packet", "") or "").strip().replace("\\", "/"),
        reviewed_commit=str(raw.get("reviewed_commit", "") or "").strip(),
    )
    if payload.handoff_id != handoff.handoff_id:
        raise ReviewError("Codex result handoff_id does not match")
    if payload.reviewer_state not in REVIEWER_STATES:
        raise ReviewError("Codex result reviewer_state is not terminal")
    if not payload.decision or not payload.response_markdown:
        raise ReviewError("Codex result lacks a decision or response")
    if payload.reviewed_packet != handoff.packet:
        raise ReviewError("Codex result packet does not match")
    if payload.reviewed_commit != handoff.code_commit:
        raise ReviewError("Codex result code_commit does not match")
    if payload.authorized_next and not allow_authorized_next:
        raise ReviewError("automated review attempted to authorize a next step")
    return payload


class CodexExecRunner:
    def __init__(self, config: WatcherConfig):
        self.config = config

    def _prompt(self, handoff: ClaudeHandoff) -> str:
        packet_line = handoff.packet or "(no packet; review CLAUDE_STATUS failure details)"
        return f"""You are the local RL_Stock reviewer. Follow AGENTS.md and the local reviewer protocol.

Review handoff_id: {handoff.handoff_id}
Claude state: {handoff.state}
Packet: {packet_line}
Code commit claimed by Claude: {handoff.code_commit}
Authoritative review ref: {_remote_ref(self.config)}

First use the installed GitHub skill/connector to orient to repository
smhe00/RL_Stock and cross-check the remote handoff context. Then read all
handoff/protocol files from the authoritative remote ref (use git show), the exact
commit/diff, and existing evidence. Do not rely on uncommitted working-tree files.
Do not modify any file. Do not run a new financial backtest or experiment, start Claude,
contact QMT, or perform paper/live work.
Do not loosen a frozen constraint or authorize a new research branch. authorized_next
must be an empty array. Return only the JSON object required by the supplied schema.
Bind reviewed_packet and reviewed_commit exactly to the values above.
"""

    def run(self, handoff: ClaudeHandoff) -> ReviewPayload:
        runtime_tmp = self.config.runtime_dir / "tmp"
        runtime_tmp.mkdir(parents=True, exist_ok=True)
        result_path = runtime_tmp / f"review-{handoff.handoff_id}.json"
        if result_path.exists():
            result_path.unlink()

        command = [
            self.config.codex_command,
            "--ask-for-approval",
            "never",
            "--cd",
            str(self.config.repo_root),
            "exec",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--output-schema",
            str(self.config.output_schema),
            "--output-last-message",
            str(result_path),
            self._prompt(handoff),
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=self.config.repo_root,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.config.codex_timeout_seconds,
                check=False,
            )
            if completed.returncode != 0:
                raise ReviewError(f"codex exec failed with exit code {completed.returncode}")
            if not result_path.exists():
                raise ReviewError("codex exec produced no structured result")
            try:
                raw = json.loads(result_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise ReviewError("codex exec result is not valid JSON") from exc
            return validate_payload(raw, handoff, self.config.allow_authorized_next)
        except subprocess.TimeoutExpired as exc:
            raise ReviewError("codex exec timed out") from exc
        except OSError as exc:
            raise ReviewError("codex executable could not be started") from exc
        finally:
            if result_path.exists():
                result_path.unlink()


class GitCheckpointPublisher:
    """Fast-forward a clean main and optionally publish reviewer-only outputs."""

    def __init__(self, config: WatcherConfig):
        self.config = config

    def prepare(self, guard: GuardToken) -> None:
        branch = _git(self.config.repo_root, "rev-parse", "--abbrev-ref", "HEAD")
        if branch != self.config.remote_branch:
            raise ReviewError("watcher must run on the configured main branch")
        if _git(
            self.config.repo_root,
            "status",
            "--porcelain",
            "--untracked-files=normal",
        ):
            raise ReviewError("working tree is not clean before reviewer checkpoint")
        _git(
            self.config.repo_root,
            "merge",
            "--ff-only",
            _remote_ref(self.config),
        )
        if _git(self.config.repo_root, "rev-parse", "HEAD") != guard.git_head:
            raise ReviewError("local main did not align to reviewed remote HEAD")

    def publish(
        self, paths: list[Path], handoff: ClaudeHandoff, guard: GuardToken
    ) -> None:
        if not self.config.publish_checkpoint:
            return

        _fetch(self.config)
        if _git(
            self.config.repo_root, "rev-parse", _remote_ref(self.config)
        ) != guard.git_head:
            raise ReviewError("remote changed before reviewer checkpoint")

        relative = [path.relative_to(self.config.repo_root).as_posix() for path in paths]
        _git(self.config.repo_root, "add", "--", *relative)
        staged = _git(
            self.config.repo_root, "diff", "--cached", "--name-only"
        ).splitlines()
        if set(staged) != set(relative):
            raise ReviewError("staged checkpoint contains unexpected files")
        _git(
            self.config.repo_root,
            "commit",
            "-m",
            f"review(local-codex): {handoff.handoff_id}",
            "--",
            *relative,
        )
        _fetch(self.config)
        if _git(
            self.config.repo_root, "rev-parse", _remote_ref(self.config)
        ) != guard.git_head:
            raise ReviewError("remote changed after reviewer commit and before push")
        _git(
            self.config.repo_root,
            "push",
            self.config.remote,
            f"HEAD:{self.config.remote_branch}",
        )


class NoopCheckpointPublisher:
    """Test helper that performs no Git mutation."""

    def prepare(self, guard: GuardToken) -> None:
        del guard

    def publish(
        self, paths: list[Path], handoff: ClaudeHandoff, guard: GuardToken
    ) -> None:
        del paths, handoff, guard


GuardProvider = Callable[[Path, ClaudeHandoff], GuardToken]


class ReviewCoordinator:
    def __init__(
        self,
        config: WatcherConfig,
        state_store: StateStore,
        runner: ReviewRunner,
        publisher: CheckpointPublisher,
        logger: logging.Logger,
        guard_provider: GuardProvider = capture_guard,
        after_response_hook: Callable[[], None] | None = None,
    ):
        self.config = config
        self.state_store = state_store
        self.runner = runner
        self.publisher = publisher
        self.logger = logger
        self.guard_provider = guard_provider
        self.after_response_hook = after_response_hook

    def _response_path(self, handoff: ClaudeHandoff) -> Path:
        name = f"{handoff.handoff_id}_REVIEWER_RESPONSE.md"
        return _repo_path(self.config.repo_root, RESPONSE_ROOT / name)

    def _render_response(
        self, handoff: ClaudeHandoff, payload: ReviewPayload, guard: GuardToken
    ) -> str:
        packet = handoff.packet or "(none)"
        body = payload.response_markdown.rstrip()
        return (
            f"# Local Codex reviewer response — {handoff.handoff_id}\n\n"
            f"- reviewer_state: `{payload.reviewer_state}`\n"
            f"- decision: `{payload.decision}`\n"
            f"- packet: `{packet}`\n"
            f"- code_commit: `{handoff.code_commit}`\n"
            f"- reviewed_remote_head: `{guard.git_head}`\n\n"
            f"{body}\n"
        )

    def _render_state(
        self,
        handoff: ClaudeHandoff,
        payload: ReviewPayload,
        response_path: Path,
        guard: GuardToken,
    ) -> str:
        relative_response = response_path.relative_to(self.config.repo_root).as_posix()
        data = {
            "protocol_version": 3,
            "actor": "codex_reviewer",
            "handoff_id": handoff.handoff_id,
            "state": payload.reviewer_state,
            "reviewed_packet": {
                "path": handoff.packet,
                "commit": handoff.code_commit,
            },
            "code_commit": handoff.code_commit,
            "reviewed_remote_head": guard.git_head,
            "decision": payload.decision,
            "response": {"path": relative_response},
            "passed": payload.passed,
            "revision_required": payload.revision_required,
            "authorized_next": payload.authorized_next,
            "forbidden_next": payload.forbidden_next,
            "notes": payload.notes,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)

    def run(self, handoff: ClaudeHandoff) -> str:
        if self.state_store.seen(handoff.handoff_id):
            return "DUPLICATE"

        initial_guard = self.guard_provider(self.config.repo_root, handoff)
        self.state_store.mark(handoff.handoff_id, "INFLIGHT")
        self.logger.info(
            "event=review_started handoff=%s state=%s", handoff.handoff_id, handoff.state
        )
        try:
            # Codex must load the same AGENTS.md/protocol snapshot it reviews.
            self.publisher.prepare(initial_guard)
            payload = self.runner.run(handoff)
            if self.guard_provider(self.config.repo_root, handoff) != initial_guard:
                self.state_store.mark(handoff.handoff_id, "STOP_WRITE")
                self.logger.warning(
                    "event=stop_write_before_response handoff=%s state=%s",
                    handoff.handoff_id,
                    handoff.state,
                )
                return "STOP_WRITE_BEFORE_RESPONSE"

            response_path = self._response_path(handoff)
            _atomic_write_text(
                response_path,
                self._render_response(handoff, payload, initial_guard),
            )
            if self.after_response_hook is not None:
                self.after_response_hook()

            if self.guard_provider(self.config.repo_root, handoff) != initial_guard:
                self.state_store.mark(handoff.handoff_id, "STOP_WRITE")
                self.logger.warning(
                    "event=stop_write_before_state handoff=%s state=%s",
                    handoff.handoff_id,
                    handoff.state,
                )
                return "STOP_WRITE_BEFORE_STATE"

            state_path = _repo_path(self.config.repo_root, REVIEWER_STATE)
            _atomic_write_text(
                state_path,
                self._render_state(handoff, payload, response_path, initial_guard),
            )
            self.publisher.publish(
                [response_path, state_path], handoff, initial_guard
            )
            self.state_store.mark(handoff.handoff_id, "COMPLETED")
            self.logger.info(
                "event=review_completed handoff=%s state=%s result=%s",
                handoff.handoff_id,
                handoff.state,
                payload.reviewer_state,
            )
            return "COMPLETED"
        except Exception:
            self.state_store.mark(handoff.handoff_id, "FAILED")
            self.logger.exception(
                "event=review_failed handoff=%s state=%s",
                handoff.handoff_id,
                handoff.state,
                exc_info=False,
            )
            return "FAILED"


class LocalReviewerWatcher:
    def __init__(
        self,
        config: WatcherConfig,
        coordinator: ReviewCoordinator,
        handoff_reader: Callable[[WatcherConfig], ClaudeHandoff] = read_remote_handoff,
    ):
        self.config = config
        self.coordinator = coordinator
        self.handoff_reader = handoff_reader

    def scan_once(self, force: bool = False) -> str:
        del force

        try:
            handoff = self.handoff_reader(self.config)
        except ReviewError as exc:
            self.coordinator.logger.warning(
                "event=fetch_or_status_unreadable reason=%s", str(exc)
            )
            return "STATUS_UNREADABLE"

        if handoff.state not in TRIGGER_STATES:
            return "IGNORED_STATE"
        if self.coordinator.state_store.seen(handoff.handoff_id):
            return "DUPLICATE"

        if handoff.state == "READY_FOR_REVIEW":
            if not handoff.packet or not handoff.packet_available:
                self.coordinator.logger.info(
                    "event=waiting_packet handoff=%s state=%s",
                    handoff.handoff_id,
                    handoff.state,
                )
                return "WAITING_PACKET"

        return self.coordinator.run(handoff)

    def run_forever(self) -> None:
        self.coordinator.logger.info("event=watcher_started")
        while True:
            try:
                self.scan_once()
                time.sleep(self.config.poll_interval_seconds)
            except KeyboardInterrupt:
                self.coordinator.logger.info("event=watcher_stopped")
                return
            except Exception:
                self.coordinator.logger.exception("event=watcher_scan_failed", exc_info=False)
                time.sleep(self.config.poll_interval_seconds)


def load_config(path: Path, repo_root: Path) -> WatcherConfig:
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise ReviewError(f"cannot read watcher config: {path}") from exc

    runtime_dir = _repo_path(repo_root, str(raw.get("runtime_dir", "runtime/local_reviewer")))
    output_schema = _repo_path(
        repo_root, str(raw.get("output_schema", "config/local_reviewer_output.schema.json"))
    )
    return WatcherConfig(
        repo_root=repo_root.resolve(),
        poll_interval_seconds=max(1.0, float(raw.get("poll_interval_seconds", 60.0))),
        codex_command=str(raw.get("codex_command", "codex")),
        codex_timeout_seconds=max(60, int(raw.get("codex_timeout_seconds", 1800))),
        runtime_dir=runtime_dir,
        output_schema=output_schema,
        max_log_bytes=max(65536, int(raw.get("max_log_bytes", 1048576))),
        log_backups=max(1, int(raw.get("log_backups", 3))),
        remote=str(raw.get("remote", "origin")),
        remote_branch=str(raw.get("remote_branch", "main")),
        publish_checkpoint=bool(raw.get("publish_checkpoint", True)),
        allow_authorized_next=bool(raw.get("allow_authorized_next", False)),
    )


def configure_logging(config: WatcherConfig) -> logging.Logger:
    log_dir = config.runtime_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("local_reviewer")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    file_handler = RotatingFileHandler(
        log_dir / "local_reviewer.log",
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


def build_service(
    config: WatcherConfig,
    runner: ReviewRunner | None = None,
    guard_provider: GuardProvider | None = None,
    publisher: CheckpointPublisher | None = None,
    handoff_reader: Callable[[WatcherConfig], ClaudeHandoff] = read_remote_handoff,
    after_response_hook: Callable[[], None] | None = None,
) -> LocalReviewerWatcher:
    config.runtime_dir.mkdir(parents=True, exist_ok=True)
    logger = configure_logging(config)
    state_store = StateStore(config.runtime_dir / "state.json")
    actual_runner = runner or CodexExecRunner(config)
    actual_guard = guard_provider or (
        lambda repo_root, handoff: capture_remote_guard(config, handoff)
    )
    actual_publisher = publisher or GitCheckpointPublisher(config)
    coordinator = ReviewCoordinator(
        config,
        state_store,
        actual_runner,
        actual_publisher,
        logger,
        actual_guard,
        after_response_hook,
    )
    return LocalReviewerWatcher(config, coordinator, handoff_reader)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--retry-handoff", default="")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    config_path = args.config
    if not config_path.is_absolute():
        config_path = repo_root / config_path

    try:
        config = load_config(config_path.resolve(), repo_root)
        if not config.output_schema.is_file():
            raise ReviewError("output schema file is missing")
        if shutil.which(config.codex_command) is None and not Path(
            config.codex_command
        ).is_file():
            raise ReviewError("codex executable is not available")
        service = build_service(config)
        if args.retry_handoff:
            if not HANDOFF_RE.fullmatch(args.retry_handoff):
                raise ReviewError("retry handoff ID is unsafe")
            service.coordinator.state_store.forget(args.retry_handoff)
        if args.once:
            outcome = service.scan_once(force=True)
            print(f"local reviewer outcome: {outcome}")
            return 0 if outcome not in {"FAILED", "STATUS_UNREADABLE"} else 1
        service.run_forever()
        return 0
    except ReviewError as exc:
        print(f"local reviewer error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
