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


def finalize_handoff(config: BridgeConfig, handoff_id: str, code_commit: str, expect_head: str = "") -> Path:
    """Create the Claude-owned review doorbell locally; caller commits/pushes it LAST."""
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

    rel = config.marker_root / handoff_id / DOORBELL
    try:
        _git(config.repo_root, "cat-file", "-e", f"{remote_ref}:{rel.as_posix()}")
    except BridgeError:
        pass
    else:
        raise BridgeError("doorbell already exists on remote; append-only fail closed")

    marker = {
        "protocol": PROTOCOL,
        "handoff_id": handoff_id,
        "event": DOORBELL,
        "timestamp": utcnow_iso(),
        "code_commit": code_commit.lower(),
    }
    validate_marker(target, marker, expected_owner="claude")
    atomic_write_text(target, json.dumps(marker, ensure_ascii=False) + "\n")
    return target
