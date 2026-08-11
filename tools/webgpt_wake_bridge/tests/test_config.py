from pathlib import Path

import pytest

from webgpt_wake_bridge.config import load_config, validate_cdp_endpoint
from webgpt_wake_bridge.errors import BridgeError


def init_git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    return repo


def write_config(tmp_path: Path, repo: Path, *, url: str = "", marker_root: str = "docs/web_bridge") -> Path:
    path = tmp_path / "bridge.local.toml"
    path.write_text(f'''[project]\nrepo_root = "{repo.as_posix()}"\nremote = "origin"\nbranch = "main"\nmarker_root = "{marker_root}"\n\n[browser]\ncdp_endpoint = "http://127.0.0.1:9222"\ntarget_conversation_url = "{url}"\n\n[runtime]\nruntime_dir = ".runtime/webgpt_wake_bridge"\n''', encoding="utf-8")
    return path


def test_config_is_project_agnostic_and_paths_are_consumer_relative(tmp_path):
    repo = init_git_repo(tmp_path)
    cfg = load_config(write_config(tmp_path, repo, marker_root="docs/../docs/web_bridge"))
    assert cfg.repo_root == repo.resolve()
    assert cfg.marker_root == Path("docs/web_bridge")
    assert cfg.runtime_dir == (repo / ".runtime/webgpt_wake_bridge").resolve()


def test_live_commands_require_exact_conversation_url(tmp_path):
    repo = init_git_repo(tmp_path)
    with pytest.raises(BridgeError):
        load_config(write_config(tmp_path, repo), require_url=True)
    cfg = load_config(write_config(tmp_path, repo, url="https://chatgpt.com/c/demo"), require_url=True)
    assert cfg.target_conversation_url == "https://chatgpt.com/c/demo"
    with pytest.raises(BridgeError):
        load_config(write_config(tmp_path, repo, url="https://chatgpt.com.evil.example/c/demo"), require_url=True)


def test_non_localhost_or_spoofed_cdp_fails_closed(tmp_path):
    repo = init_git_repo(tmp_path)
    path = write_config(tmp_path, repo)
    text = path.read_text(encoding="utf-8").replace("http://127.0.0.1:9222", "http://192.168.1.2:9222")
    path.write_text(text, encoding="utf-8")
    with pytest.raises(BridgeError):
        load_config(path)
    with pytest.raises(BridgeError):
        validate_cdp_endpoint("http://127.0.0.1.evil.example:9222")
    with pytest.raises(BridgeError):
        validate_cdp_endpoint("https://127.0.0.1:9222")


def test_marker_root_cannot_escape_or_be_repo_root(tmp_path):
    repo = init_git_repo(tmp_path)
    with pytest.raises(BridgeError):
        load_config(write_config(tmp_path, repo, marker_root="../outside"))
    with pytest.raises(BridgeError):
        load_config(write_config(tmp_path, repo, marker_root="."))
