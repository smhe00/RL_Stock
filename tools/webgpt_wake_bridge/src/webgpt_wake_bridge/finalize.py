from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .config import BridgeConfig
from .errors import BridgeError
from .markers import PROTOCOL, atomic_write_text, utcnow_iso, validate_handoff_id, validate_marker

GIT_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")
DOORBELL = "claude_work_complete.json"


def _git(repo: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=repo, text=True, encoding="utf-8", stderr=subprocess.STDOUT
        ).strip()
    except (OSError, UnicodeError, subprocess.CalledProcessError) as exc:
        raise BridgeError(f"git command failed: {' '.join(args[:3])}") from exc


def _is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=repo,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        raise BridgeError("git merge-base failed") from exc
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    raise BridgeError("git merge-base failed")


def finalize_handoff(config: BridgeConfig, handoff_id: str, code_commit: str, expect_head: str = "") -> Path:
    """Create the Claude-owned review doorbell locally; caller commits/pushes it LAST.

    The referenced code commit must resolve to a real commit object and already be
    contained in the configured remote branch. A doorbell must never advertise work
    that exists only locally or on an unrelated branch.
    """
    validate_handoff_id(handoff_id)
    if not GIT_SHA_RE.fullmatch(code_commit):
        raise BridgeError("code_commit must be a 7-40 character git SHA")

    target = config.repo_root / config.marker_root / handoff_id / DOORBELL
    if target.exists():
        raise BridgeError("doorbell already exists locally; append-only fail closed")

    _git(config.repo_root, "fetch", config.remote, config.branch)
    remote_ref = f"{config.remote}/{config.branch}"
    remote_head = _git(config.repo_root, "rev-parse", remote_ref)
    local_head = _git(config.repo_root, "rev-parse", "HEAD")
    if expect_head:
        expected = _git(config.repo_root, "rev-parse", expect_head)
        if remote_head != expected:
            raise BridgeError(f"remote HEAD {remote_head} != expected {expected}")
    elif local_head != remote_head:
        raise BridgeError("local HEAD != remote HEAD; remote confirmation required before doorbell")

    # Resolve the supplied SHA specifically as a commit object, then require it to be
    # part of the remote branch already confirmed above.
    try:
        resolved_code_commit = _git(config.repo_root, "rev-parse", f"{code_commit}^{{commit}}")
    except BridgeError as exc:
        raise BridgeError("code_commit does not resolve to a commit object") from exc
    if not _is_ancestor(config.repo_root, resolved_code_commit, remote_head):
        raise BridgeError("code_commit is not contained in the configured remote branch")

    rel = config.marker_root / handoff_id / DOORBELL
    # `git ls-tree` distinguishes a genuinely absent path (empty output) from a Git
    # failure. Remote query failures must not be treated as permission to duplicate.
    remote_marker = _git(
        config.repo_root,
        "ls-tree",
        "--name-only",
        remote_ref,
        "--",
        rel.as_posix(),
    )
    if any(line.strip() == rel.as_posix() for line in remote_marker.splitlines()):
        raise BridgeError("doorbell already exists on remote; append-only fail closed")

    marker = {
        "protocol": PROTOCOL,
        "handoff_id": handoff_id,
        "event": DOORBELL,
        "timestamp": utcnow_iso(),
        "code_commit": resolved_code_commit,
    }
    validate_marker(target, marker, expected_owner="claude")
    atomic_write_text(target, json.dumps(marker, ensure_ascii=False) + "\n")
    return target
