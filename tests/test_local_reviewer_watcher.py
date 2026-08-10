from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scripts.local_reviewer_watcher import (
    ClaudeHandoff,
    GuardToken,
    NoopCheckpointPublisher,
    ReviewError,
    ReviewPayload,
    WatcherConfig,
    build_service,
    read_handoff,
    validate_payload,
)


class FakeRunner:
    def __init__(self, mutate=None):
        self.calls: list[str] = []
        self.mutate = mutate

    def run(self, handoff: ClaudeHandoff) -> ReviewPayload:
        self.calls.append(handoff.handoff_id)
        if self.mutate is not None:
            self.mutate()
        return ReviewPayload(
            handoff_id=handoff.handoff_id,
            reviewer_state="REVIEW_COMPLETE",
            decision="TEST_REVIEW_COMPLETE",
            response_markdown="The bounded test handoff is complete.",
            passed=["STATE_MACHINE_TEST"],
            revision_required=[],
            authorized_next=[],
            forbidden_next=["NEW_RESEARCH_BRANCH"],
            notes=["No financial experiment was run."],
            reviewed_packet=handoff.packet,
            reviewed_commit=handoff.code_commit,
        )


def _write_handoff(root: Path, state: str, handoff_id: str = "HANDOFF_001") -> None:
    path = root / "docs/agent_state/CLAUDE_STATUS.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "protocol_version: 3",
                "actor: claude",
                f"handoff_id: {handoff_id}",
                f"state: {state}",
                "code_commit: abc1234",
                "packet: docs/review_packets/PACKET.md",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _make_repo(root: Path, state: str = "READY_FOR_REVIEW") -> None:
    _write_handoff(root, state)
    packet = root / "docs/review_packets/PACKET.md"
    packet.parent.mkdir(parents=True, exist_ok=True)
    packet.write_text("# Packet\n", encoding="utf-8")
    reviewer = root / "docs/reviewer_state/CHATGPT_REVIEW.yaml"
    reviewer.parent.mkdir(parents=True, exist_ok=True)
    reviewer.write_text("protocol_version: 2\nstate: BLOCKED\n", encoding="utf-8")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "MISSING"


def _file_guard(root: Path, handoff: ClaudeHandoff) -> GuardToken:
    packet = root / handoff.packet if handoff.packet else None
    return GuardToken(
        git_head="remote-head-001",
        claude_status_digest=_digest(root / "docs/agent_state/CLAUDE_STATUS.yaml"),
        packet_digest=_digest(packet) if packet else "NO_PACKET",
        reviewer_state_digest=_digest(root / "docs/reviewer_state/CHATGPT_REVIEW.yaml"),
    )


def _service(
    root: Path,
    runner: FakeRunner,
    after_response_hook=None,
):
    schema = root / "schema.json"
    schema.write_text("{}\n", encoding="utf-8")
    config = WatcherConfig(
        repo_root=root,
        poll_interval_seconds=60.0,
        codex_command="codex",
        codex_timeout_seconds=60,
        runtime_dir=root / "runtime/local_reviewer",
        output_schema=schema,
        max_log_bytes=65536,
        log_backups=1,
        publish_checkpoint=False,
    )
    return build_service(
        config,
        runner=runner,
        guard_provider=_file_guard,
        publisher=NoopCheckpointPublisher(),
        handoff_reader=lambda cfg: read_handoff(cfg.repo_root),
        after_response_hook=after_response_hook,
    )


def test_running_does_not_trigger(tmp_path: Path) -> None:
    _make_repo(tmp_path, state="RUNNING")
    runner = FakeRunner()
    service = _service(tmp_path, runner)

    assert service.scan_once() == "IGNORED_STATE"
    assert runner.calls == []


@pytest.mark.parametrize("state", ["READY_FOR_REVIEW", "BLOCKED", "TEST_FAILED"])
def test_trigger_states_trigger_once(tmp_path: Path, state: str) -> None:
    _make_repo(tmp_path, state=state)
    runner = FakeRunner()
    service = _service(tmp_path, runner)

    assert service.scan_once() == "COMPLETED"
    assert runner.calls == ["HANDOFF_001"]
    assert (tmp_path / "docs/reviewer_responses/HANDOFF_001_REVIEWER_RESPONSE.md").is_file()
    reviewer_state = (tmp_path / "docs/reviewer_state/CHATGPT_REVIEW.yaml").read_text(
        encoding="utf-8"
    )
    assert "handoff_id: HANDOFF_001" in reviewer_state
    assert "authorized_next: []" in reviewer_state


def test_repeated_scan_is_not_triggered_twice(tmp_path: Path) -> None:
    _make_repo(tmp_path)
    runner = FakeRunner()
    service = _service(tmp_path, runner)

    assert service.scan_once() == "COMPLETED"
    assert service.scan_once() == "DUPLICATE"
    assert runner.calls == ["HANDOFF_001"]


def test_same_handoff_is_deduplicated_after_packet_change(tmp_path: Path) -> None:
    _make_repo(tmp_path)
    runner = FakeRunner()
    service = _service(tmp_path, runner)

    assert service.scan_once() == "COMPLETED"
    (tmp_path / "docs/review_packets/PACKET.md").write_text(
        "# Packet changed without a new handoff ID\n", encoding="utf-8"
    )
    assert service.scan_once() == "DUPLICATE"
    assert runner.calls == ["HANDOFF_001"]


def test_stop_write_before_first_reviewer_write(tmp_path: Path) -> None:
    _make_repo(tmp_path)

    def mutate_status() -> None:
        _write_handoff(tmp_path, "RUNNING")

    runner = FakeRunner(mutate=mutate_status)
    service = _service(tmp_path, runner)

    assert service.scan_once() == "STOP_WRITE_BEFORE_RESPONSE"
    assert not (
        tmp_path / "docs/reviewer_responses/HANDOFF_001_REVIEWER_RESPONSE.md"
    ).exists()
    original_state = (tmp_path / "docs/reviewer_state/CHATGPT_REVIEW.yaml").read_text(
        encoding="utf-8"
    )
    assert "handoff_id: HANDOFF_001" not in original_state


def test_stop_write_between_response_and_state(tmp_path: Path) -> None:
    _make_repo(tmp_path)
    packet = tmp_path / "docs/review_packets/PACKET.md"

    def mutate_packet() -> None:
        packet.write_text("# Remote packet changed mid-write\n", encoding="utf-8")

    runner = FakeRunner()
    service = _service(tmp_path, runner, after_response_hook=mutate_packet)

    assert service.scan_once() == "STOP_WRITE_BEFORE_STATE"
    assert (tmp_path / "docs/reviewer_responses/HANDOFF_001_REVIEWER_RESPONSE.md").is_file()
    original_state = (tmp_path / "docs/reviewer_state/CHATGPT_REVIEW.yaml").read_text(
        encoding="utf-8"
    )
    assert "handoff_id: HANDOFF_001" not in original_state


def test_automated_authorized_next_fails_closed() -> None:
    handoff = ClaudeHandoff(
        handoff_id="HANDOFF_001",
        state="READY_FOR_REVIEW",
        packet="docs/review_packets/PACKET.md",
        code_commit="abc1234",
    )
    raw = {
        "handoff_id": handoff.handoff_id,
        "reviewer_state": "REVIEW_COMPLETE",
        "decision": "UNSAFE_AUTO_BRANCH",
        "response_markdown": "Would open a new branch.",
        "passed": [],
        "revision_required": [],
        "authorized_next": ["NEW_RESEARCH_BRANCH"],
        "forbidden_next": [],
        "notes": [],
        "reviewed_packet": handoff.packet,
        "reviewed_commit": handoff.code_commit,
    }

    with pytest.raises(ReviewError, match="attempted to authorize"):
        validate_payload(raw, handoff, allow_authorized_next=False)
