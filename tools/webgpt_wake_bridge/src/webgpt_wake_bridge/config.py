from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .errors import BridgeError

REMOTE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,255}$")


@dataclass(frozen=True)
class BridgeConfig:
    repo_root: Path
    marker_root: Path
    remote: str
    branch: str
    cdp_endpoint: str
    chrome_profile_path: str
    target_conversation_url: str | None
    poll_interval_s: float
    fetch_ack_timeout_s: float
    runtime_dir: Path
    max_log_bytes: int
    log_backups: int
    playwright_module: str = "playwright.sync_api"


def _inside_repo(repo_root: Path, relative: str | Path) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute():
        path = candidate.resolve()
    else:
        path = (repo_root / candidate).resolve()
    try:
        path.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise BridgeError(f"path escapes repository: {relative}") from exc
    return path


def _resolve_runtime(repo_root: Path, raw: str) -> Path:
    expanded = os.path.expandvars(str(raw).strip())
    candidate = Path(expanded).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (repo_root / candidate).resolve()


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def validate_cdp_endpoint(raw: str) -> str:
    value = str(raw).strip().rstrip("/")
    try:
        parsed = urlparse(value)
        port = parsed.port
    except ValueError as exc:
        raise BridgeError("CDP endpoint is not a valid URL") from exc
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or port is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise BridgeError("CDP endpoint must be exactly http://127.0.0.1:<port>")
    return value


def validate_target_conversation_url(raw: str | None, *, required: bool = False) -> str | None:
    value = str(raw or "").strip().rstrip("/") or None
    if value is None:
        if required:
            raise BridgeError("target_conversation_url is required in the ignored local config")
        return None
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "chatgpt.com"
        or parsed.username is not None
        or parsed.password is not None
        or not parsed.path.startswith("/c/")
        or len(parsed.path) <= 3
        or parsed.fragment
    ):
        raise BridgeError("target_conversation_url must be a dedicated https://chatgpt.com/c/... conversation")
    return value


def validate_remote_name(raw: str) -> str:
    value = str(raw).strip()
    if not REMOTE_RE.fullmatch(value):
        raise BridgeError("[project].remote must be a simple configured Git remote name")
    return value


def validate_branch_name(raw: str) -> str:
    value = str(raw).strip()
    if (
        not BRANCH_RE.fullmatch(value)
        or ".." in value
        or "//" in value
        or "@{" in value
        or value.endswith(("/", ".", ".lock"))
        or "/." in value
    ):
        raise BridgeError("[project].branch is not a safe Git branch name")
    return value


def load_config(path: Path, *, require_url: bool = False) -> BridgeConfig:
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise BridgeError(f"cannot read bridge config: {path}") from exc

    project = raw.get("project", {})
    browser = raw.get("browser", {})
    runtime = raw.get("runtime", {})
    if not isinstance(project, dict) or not isinstance(browser, dict) or not isinstance(runtime, dict):
        raise BridgeError("config sections [project], [browser], [runtime] must be tables")

    repo_raw = str(project.get("repo_root", "")).strip()
    if not repo_raw:
        raise BridgeError("[project].repo_root is required")
    repo_root = Path(os.path.expandvars(repo_raw)).expanduser().resolve()
    git_path = repo_root / ".git"
    if not git_path.exists():
        raise BridgeError(f"repo_root is not a git worktree: {repo_root}")
    git_dir = git_path.resolve()

    marker_raw = str(project.get("marker_root", "docs/web_bridge")).strip()
    if not marker_raw:
        raise BridgeError("[project].marker_root must not be empty")
    marker_abs = _inside_repo(repo_root, marker_raw)
    marker_root = marker_abs.relative_to(repo_root)
    if marker_root == Path("."):
        raise BridgeError("marker_root must be a subdirectory of the consumer repository")
    if _is_within(marker_abs, git_dir):
        raise BridgeError("marker_root must not be inside .git")

    runtime_raw = str(runtime.get("runtime_dir", ".runtime/webgpt_wake_bridge")).strip()
    if not runtime_raw:
        raise BridgeError("[runtime].runtime_dir must not be empty")
    runtime_dir = _resolve_runtime(repo_root, runtime_raw)
    if runtime_dir == repo_root or runtime_dir.parent == runtime_dir:
        raise BridgeError("runtime_dir must not be the repository or filesystem root")
    if _is_within(runtime_dir, git_dir):
        raise BridgeError("runtime_dir must not be inside .git")
    # Runtime may intentionally live outside the repo. If it lives inside, it must
    # remain disjoint from the durable marker tree.
    if _is_within(runtime_dir, repo_root):
        if _is_within(runtime_dir, marker_abs) or _is_within(marker_abs, runtime_dir):
            raise BridgeError("runtime_dir and marker_root must not overlap")

    remote = validate_remote_name(str(project.get("remote", "origin")))
    branch = validate_branch_name(str(project.get("branch", "main")))
    cdp = validate_cdp_endpoint(str(browser.get("cdp_endpoint", "http://127.0.0.1:9222")))
    url = validate_target_conversation_url(
        str(browser.get("target_conversation_url", "")), required=require_url
    )

    return BridgeConfig(
        repo_root=repo_root,
        marker_root=marker_root,
        remote=remote,
        branch=branch,
        cdp_endpoint=cdp,
        chrome_profile_path=str(browser.get("chrome_profile_path", r"C:\ChatGPT_Automation_Profile")),
        target_conversation_url=url,
        poll_interval_s=max(1.0, float(runtime.get("poll_interval_s", 5.0))),
        fetch_ack_timeout_s=max(1.0, float(runtime.get("fetch_ack_timeout_s", 120.0))),
        runtime_dir=runtime_dir,
        max_log_bytes=max(65536, int(runtime.get("max_log_bytes", 1048576))),
        log_backups=max(1, int(runtime.get("log_backups", 3))),
        playwright_module=str(browser.get("playwright_module", "playwright.sync_api")),
    )
