import json
import subprocess
from pathlib import Path

import pytest

from webgpt_wake_bridge.errors import BridgeError
from webgpt_wake_bridge.transport_git import GitTransport


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


def trigger(handoff: str) -> str:
    return json.dumps({
        "protocol": "web_fetch_bridge_v1",
        "handoff_id": handoff,
        "event": "trigger_fetch_sent.json",
        "timestamp": "2026-08-11T09:18:39+00:00",
    }) + "\n"


def test_publish_marker_uses_isolated_worktree_and_is_append_only(tmp_path):
    repo = init_repo(tmp_path)
    transport = GitTransport(repo, repo / ".runtime", Path("docs/web_bridge"), "origin", "main")
    handoff = "DEMO_001"
    assert not transport.marker_exists(handoff, "trigger_fetch_sent.json")
    transport.publish_bridge_marker(handoff, "trigger_fetch_sent.json", trigger(handoff))
    assert transport.marker_exists(handoff, "trigger_fetch_sent.json")
    assert not (repo / "docs/web_bridge" / handoff / "trigger_fetch_sent.json").exists()
    with pytest.raises(BridgeError):
        transport.publish_bridge_marker(handoff, "trigger_fetch_sent.json", trigger(handoff))


def test_missing_remote_ref_is_error_not_marker_absence(tmp_path):
    repo = init_repo(tmp_path)
    transport = GitTransport(repo, repo / ".runtime_missing", Path("docs/web_bridge"), "origin", "missing")
    with pytest.raises(BridgeError):
        transport.marker_exists("DEMO_404", "trigger_fetch_sent.json")


def test_review_published_blocks_late_trigger(tmp_path):
    repo = init_repo(tmp_path)
    handoff = "DEMO_002"
    review = repo / "docs/web_bridge" / handoff / "chatgpt_review_published.json"
    review.parent.mkdir(parents=True)
    review.write_text(json.dumps({
        "protocol": "web_fetch_bridge_v1",
        "handoff_id": handoff,
        "event": "chatgpt_review_published.json",
        "timestamp": "2026-08-11T09:18:39+00:00",
    }) + "\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", str(review.relative_to(repo))], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "review"], check=True)
    subprocess.run(["git", "-C", str(repo), "push", "-q"], check=True)
    transport = GitTransport(repo, repo / ".runtime", Path("docs/web_bridge"), "origin", "main")
    with pytest.raises(BridgeError):
        transport.publish_bridge_marker(handoff, "trigger_fetch_sent.json", trigger(handoff))
