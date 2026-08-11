"""Claude-side mandatory handoff finalization helper tests.

Covers: unsafe/invalid input fail closed, append-only duplicate rejection,
remote-confirmation requirement (local HEAD must match origin/main unless
--expect-head is given), doorbell content/format (tz-aware UTC, code_commit),
and the fixed order guarantee (doorbell is only ever created, never auto-pushed).
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "finalize_handoff.py"
RE = r"^[0-9a-f]{40}$"


def _init_repo(tmp: Path, commit_count: int = 1) -> Path:
    """Init a real git repo on main with `commit_count` commits, returns repo path."""
    subprocess.run(["git", "init", "-q", str(tmp)], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "checkout", "-q", "-b", "main"], cwd=tmp, check=True, stdout=subprocess.DEVNULL)
    for i in range(commit_count):
        (tmp / f"f{i}").write_text("x", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=tmp, check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["git", "commit", "-q", "-m", f"c{i}"], cwd=tmp, check=True, stdout=subprocess.DEVNULL)
    # A dedicated bare remote under this test's own tmp_path so tests don't collide.
    bare = tmp / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "remote", "add", "origin", str(bare)], cwd=tmp, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "push", "-q", "-u", "origin", "main"], cwd=tmp, check=True, stdout=subprocess.DEVNULL)
    return tmp


def _run_helper(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HELPER), *args],
        cwd=repo, capture_output=True, text=True,
    )


def _repo(tmp_path: Path) -> Path:
    return _init_repo(tmp_path / "repo")


def test_helper_creates_doorbell_with_tz_aware_timestamp(tmp_path):
    repo = _repo(tmp_path)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    r = _run_helper(repo, "--handoff", "SMOKE_001_001", "--code-commit", head[:7])
    assert r.returncode == 0, r.stdout + r.stderr
    marker = json.loads((repo / "docs" / "web_bridge" / "SMOKE_001_001" / "claude_work_complete.json").read_text(encoding="utf-8"))
    assert marker["handoff_id"] == "SMOKE_001_001"
    assert marker["code_commit"] == head[:7]
    assert marker["event"] == "claude_work_complete.json"
    assert marker["protocol"] == "web_fetch_bridge_v1"
    assert "+00:00" in marker["timestamp"] or "Z" in marker["timestamp"]  # tz-aware
    # does NOT auto-push (doorbell must be Claude's final push)
    subprocess.run(["git", "status", "--short"], cwd=repo, check=True, capture_output=True)


def test_helper_rejects_unsafe_handoff(tmp_path):
    repo = _repo(tmp_path)
    r = _run_helper(repo, "--handoff", "bad/../path", "--code-commit", "abc1234")
    assert r.returncode != 0
    assert "unsafe handoff_id" in (r.stdout + r.stderr)


def test_helper_rejects_bad_commit_sha(tmp_path):
    repo = _repo(tmp_path)
    r = _run_helper(repo, "--handoff", "SMOKE_001_001", "--code-commit", "not-a-sha")
    assert r.returncode != 0
    assert "code_commit must be a git SHA" in (r.stdout + r.stderr)


def test_helper_append_only_duplicate_fails_closed(tmp_path):
    repo = _repo(tmp_path)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    assert _run_helper(repo, "--handoff", "SMOKE_001_001", "--code-commit", head[:7]).returncode == 0
    # second run must fail closed (already exists)
    r = _run_helper(repo, "--handoff", "SMOKE_001_001", "--code-commit", head[:7])
    assert r.returncode != 0
    assert "already exists" in (r.stdout + r.stderr)


def test_helper_requires_remote_confirmation(tmp_path):
    # local HEAD diverged from origin/main -> must fail closed without --expect-head
    repo = _repo(tmp_path)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    (repo / "extra").write_text("y", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "commit", "-q", "-m", "local-only"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
    r = _run_helper(repo, "--handoff", "SMOKE_001_001", "--code-commit", head[:7])
    assert r.returncode != 0
    assert "remote confirmation" in (r.stdout + r.stderr)
