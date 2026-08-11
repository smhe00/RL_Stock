import json
import subprocess
from pathlib import Path

import pytest

from webgpt_wake_bridge.config import BridgeConfig
from webgpt_wake_bridge.errors import BridgeError
from webgpt_wake_bridge.finalize import finalize_handoff


def init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    remote = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", "-b", "main"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "test"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
    (repo / "README.md").write_text("demo\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "init"], check=True)
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", str(remote)], check=True)
    subprocess.run(["git", "-C", str(repo), "push", "-q", "-u", "origin", "main"], check=True)
    return repo


def cfg(repo: Path) -> BridgeConfig:
    return BridgeConfig(
        repo_root=repo,
        marker_root=Path("docs/web_bridge"),
        remote="origin", branch="main",
        cdp_endpoint="http://127.0.0.1:9222",
        chrome_profile_path="C:/profile", target_conversation_url=None,
        poll_interval_s=5, fetch_ack_timeout_s=120,
        runtime_dir=repo / ".runtime", max_log_bytes=65536, log_backups=1,
    )


def head(repo: Path) -> str:
    return subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()


def test_finalize_creates_tz_aware_append_only_doorbell(tmp_path):
    repo = init_repo(tmp_path)
    expected = head(repo)
    path = finalize_handoff(cfg(repo), "DEMO_001", expected[:7])
    marker = json.loads(path.read_text(encoding="utf-8"))
    assert marker["handoff_id"] == "DEMO_001"
    assert marker["timestamp"].endswith("+00:00")
    assert marker["code_commit"] == expected
    with pytest.raises(BridgeError):
        finalize_handoff(cfg(repo), "DEMO_001", expected[:7])


def test_finalize_fails_when_local_not_remote_confirmed(tmp_path):
    repo = init_repo(tmp_path)
    (repo / "local.txt").write_text("local\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "local.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "local"], check=True)
    with pytest.raises(BridgeError):
        finalize_handoff(cfg(repo), "DEMO_002", head(repo)[:7])


def test_finalize_rejects_nonexistent_or_unrelated_code_commit(tmp_path):
    repo = init_repo(tmp_path)
    with pytest.raises(BridgeError):
        finalize_handoff(cfg(repo), "DEMO_003", "deadbee")

    # Create a real commit on a side branch, then return to remote-confirmed main.
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", "-b", "side"], check=True)
    (repo / "side.txt").write_text("side\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "side.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "side"], check=True)
    side_commit = head(repo)
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", "main"], check=True)
    assert head(repo) != side_commit
    with pytest.raises(BridgeError):
        finalize_handoff(cfg(repo), "DEMO_004", side_commit)
