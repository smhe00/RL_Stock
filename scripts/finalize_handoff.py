"""Claude-side mandatory handoff finalization helper (Web Fetch Bridge V1).

Creates the Claude-owned wake-up doorbell `claude_work_complete.json` for a fresh
handoff that requests Web ChatGPT review. This is the LAST step of Claude's
handoff finalization order:

    packet/status complete -> commit/push -> remote confirmation
        -> claude_work_complete.json (LAST, this helper)

The helper:
  - takes an explicit handoff_id and code_commit;
  - creates ONLY the Claude-owned doorbell under docs/web_bridge/<handoff_id>/;
  - uses a timezone-aware UTC timestamp;
  - is append-only: fails closed if the doorbell already exists (locally or on
    origin/main);
  - fails closed if remote state is unexpected (the doorbell must land on top of
    the confirmed remote HEAD; pass --expect-head to verify).

It does NOT commit/push. The doorbell commit/push must be performed by Claude as
the final push so the gate ordering invariant (doorbell LAST) is preserved.

Usage:
  python scripts/finalize_handoff.py --handoff <HANDOFF_ID> --code-commit <SHA> \
      [--expect-head <SHA>]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HANDOFF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,159}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
BRIDGE_ROOT = Path("docs/web_bridge")
DOORBELL = "claude_work_complete.json"


class FinalizeError(RuntimeError):
    """Fail-closed finalization error."""


def _repo_root() -> Path:
    # The helper is always invoked from the repository root (Claude runs it there).
    # Resolving from cwd keeps it testable and independent of where the script lives.
    return Path.cwd().resolve()


def _atomic_write_text(path: Path, text: str) -> None:
    import os
    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if Path(tmp).exists():
            Path(tmp).unlink()


def _git(repo: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=repo, text=True, encoding="utf-8",
            stderr=subprocess.STDOUT,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise FinalizeError(f"git {' '.join(args[:2])} failed: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handoff", required=True, help="fresh handoff_id (review-requesting)")
    parser.add_argument("--code-commit", required=True, help="implementation commit SHA")
    parser.add_argument("--expect-head", default="",
                        help="expected remote origin/main HEAD to confirm before finalizing")
    args = parser.parse_args()

    if not HANDOFF_RE.fullmatch(args.handoff):
        print(f"finalize error: unsafe handoff_id {args.handoff!r}")
        return 2
    if not GIT_SHA_RE.fullmatch(args.code_commit):
        print(f"finalize error: code_commit must be a git SHA, got {args.code_commit!r}")
        return 2

    repo = _repo_root()
    target = repo / BRIDGE_ROOT / args.handoff / DOORBELL

    # Append-only: refuse if the doorbell already exists locally.
    if target.exists():
        print(f"finalize error: {DOORBELL} already exists locally; append-only fail closed")
        return 2

    # Remote-state confirmation: doorbell must land on the expected remote HEAD.
    try:
        _git(repo, "fetch", "origin", "main")
    except FinalizeError as exc:
        print(f"finalize error: cannot fetch origin/main: {exc}")
        return 2
    remote_head = _git(repo, "rev-parse", "origin/main")
    if args.expect_head:
        if _git(repo, "rev-parse", "--short", "origin/main") != args.expect_head[:7] \
                and remote_head != args.expect_head:
            print(f"finalize error: remote HEAD {remote_head} does not match --expect-head {args.expect_head}")
            return 2
    else:
        # Without an explicit expectation, require that origin/main is not ahead of
        # our local main in a way that would make the doorbell stale.
        local_head = _git(repo, "rev-parse", "HEAD")
        if local_head != remote_head:
            print(
                f"finalize error: local HEAD {local_head} != origin/main {remote_head}; "
                "pull --ff-only first (remote confirmation required before doorbell)"
            )
            return 2

    marker = {
        "protocol": "web_fetch_bridge_v1",
        "handoff_id": args.handoff,
        "event": DOORBELL,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "code_commit": args.code_commit,
    }
    text = json.dumps(marker, ensure_ascii=False) + "\n"
    _atomic_write_text(target, text)
    print(f"finalized doorbell: {target.relative_to(repo)}")
    print(f"  handoff_id  = {args.handoff}")
    print(f"  code_commit = {args.code_commit}")
    print(f"  timestamp   = {marker['timestamp']}")
    print("  remote HEAD = {0}".format(remote_head))
    print("NEXT: git add <doorbell>, commit, and push as the FINAL push of the gate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
