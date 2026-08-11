from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from .errors import BridgeError


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
    path = (repo_root / relative).resolve()
    try:
        path.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise BridgeError(f"path escapes repository: {relative}") from exc
    return path


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
    repo_root = Path(repo_raw).expanduser().resolve()
    if not (repo_root / ".git").exists():
        raise BridgeError(f"repo_root is not a git worktree: {repo_root}")

    marker_root = Path(str(project.get("marker_root", "docs/web_bridge")))
    _inside_repo(repo_root, marker_root)
    runtime_dir = _inside_repo(repo_root, str(runtime.get("runtime_dir", ".runtime/webgpt_wake_bridge")))
    cdp = str(browser.get("cdp_endpoint", "http://127.0.0.1:9222"))
    if not cdp.lower().startswith("http://127.0.0.1"):
        raise BridgeError("CDP endpoint must be localhost only")
    url = str(browser.get("target_conversation_url", "")).strip() or None
    if require_url and not url:
        raise BridgeError("target_conversation_url is required in the ignored local config")
    if url and not url.startswith("https://chatgpt.com/c/"):
        raise BridgeError("target_conversation_url must be a dedicated chatgpt.com/c/... conversation")

    return BridgeConfig(
        repo_root=repo_root,
        marker_root=marker_root,
        remote=str(project.get("remote", "origin")),
        branch=str(project.get("branch", "main")),
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
