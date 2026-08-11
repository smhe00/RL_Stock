from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .errors import BridgeError
from .markers import (
    BRIDGE_OWNED_MARKERS,
    atomic_write_text,
    validate_handoff_id,
    validate_marker,
)


class GitTransport:
    """Append-only marker transport using an isolated detached git worktree."""

    def __init__(self, repo_root: Path, runtime_dir: Path, marker_root: Path, remote: str = "origin", branch: str = "main"):
        self.repo_root = repo_root.resolve()
        self.runtime_dir = runtime_dir.resolve()
        self.marker_root = marker_root
        self.remote = remote
        self.branch = branch
        self.worktree = self.runtime_dir / "bridge_worktree"

    def _cwd(self) -> Path:
        return self.worktree if self.worktree.is_dir() else self.repo_root

    def _git(self, *args: str) -> str:
        try:
            return subprocess.check_output(
                ["git", *args], cwd=self._cwd(), text=True, encoding="utf-8", stderr=subprocess.STDOUT
            ).strip()
        except (OSError, UnicodeError, subprocess.CalledProcessError) as exc:
            raise BridgeError(f"git command failed: {' '.join(args[:3])}") from exc

    def _ensure_worktree(self) -> None:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        if (self.worktree / ".git").exists():
            return
        try:
            subprocess.run(
                ["git", "fetch", self.remote, self.branch],
                cwd=self.repo_root,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                ["git", "worktree", "add", "--detach", str(self.worktree), f"{self.remote}/{self.branch}"],
                cwd=self.repo_root,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:  # noqa: BLE001
            raise BridgeError(f"cannot create isolated bridge worktree: {exc}") from exc

    def fetch(self) -> None:
        self._ensure_worktree()
        self._git("fetch", self.remote, self.branch)

    def sync_worktree(self) -> None:
        self.fetch()
        self._git("reset", "--hard", f"{self.remote}/{self.branch}")

    def remote_head(self) -> str:
        self.fetch()
        return self._git("rev-parse", f"{self.remote}/{self.branch}")

    def _rel(self, handoff_id: str, name: str) -> Path:
        validate_handoff_id(handoff_id)
        return self.marker_root / handoff_id / name

    def marker_exists(self, handoff_id: str, name: str) -> bool:
        """Return marker existence without conflating absence with Git failure."""
        rel = self._rel(handoff_id, name)
        listing = self._git(
            "ls-tree", "--name-only", f"{self.remote}/{self.branch}", "--", rel.as_posix()
        )
        return any(line.strip() == rel.as_posix() for line in listing.splitlines())

    def marker_text(self, handoff_id: str, name: str) -> str | None:
        rel = self._rel(handoff_id, name)
        if not self.marker_exists(handoff_id, name):
            return None
        return self._git("show", f"{self.remote}/{self.branch}:{rel.as_posix()}")

    def list_handoff_dirs(self) -> set[str]:
        self.fetch()
        prefix = self.marker_root.as_posix().rstrip("/") + "/"
        tree = self._git(
            "ls-tree", "-r", "--name-only", f"{self.remote}/{self.branch}", "--", prefix
        )
        dirs: set[str] = set()
        root_parts = len(self.marker_root.parts)
        for line in tree.splitlines():
            parts = Path(line).parts
            if len(parts) > root_parts:
                dirs.add(parts[root_parts])
        return dirs

    @staticmethod
    def _validate_publish_payload(handoff_id: str, name: str, content: str) -> None:
        try:
            marker = json.loads(content)
        except (TypeError, json.JSONDecodeError) as exc:
            raise BridgeError("bridge marker content must be valid JSON") from exc
        validate_marker(Path(name), marker, expected_owner="bridge_trigger")
        if marker.get("handoff_id") != handoff_id:
            raise BridgeError("bridge marker payload handoff_id does not match publish target")

    def publish_bridge_marker(self, handoff_id: str, name: str, content: str) -> None:
        if name not in BRIDGE_OWNED_MARKERS:
            raise BridgeError(f"bridge may only publish {sorted(BRIDGE_OWNED_MARKERS)}")
        validate_handoff_id(handoff_id)
        self._validate_publish_payload(handoff_id, name, content)

        rel = self._rel(handoff_id, name)
        last_error: BridgeError | None = None
        for _ in range(3):
            self.sync_worktree()
            target = self.worktree / rel
            if target.exists() or self.marker_exists(handoff_id, name):
                raise BridgeError(f"bridge marker {name} already exists; append-only")
            if self.marker_exists(handoff_id, "chatgpt_review_published.json"):
                raise BridgeError("review_published already exists; refusing stale trigger publication")
            target.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(target, content)
            try:
                self._git("add", "--", rel.as_posix())
                self._git("commit", "-m", f"bridge: {handoff_id} {name}")
                self._git("push", self.remote, f"HEAD:{self.branch}")
                # Push success is the durable publication boundary. A later refresh is
                # best-effort only; failure here must not turn a successful push into an
                # apparent send/publication failure.
                try:
                    self.fetch()
                except BridgeError:
                    pass
                return
            except BridgeError as exc:
                last_error = exc
            finally:
                target.unlink(missing_ok=True)
        raise BridgeError(f"marker publish failed after concurrent remote changes: {last_error}")
