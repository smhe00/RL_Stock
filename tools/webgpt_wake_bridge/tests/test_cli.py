import json
import sys

import webgpt_wake_bridge.cli as cli_module
from webgpt_wake_bridge.cli import main
from webgpt_wake_bridge.config import load_config


def test_cli_init_then_check_and_marker_only_retry(tmp_path, monkeypatch, capsys):
    repo = tmp_path / "consumer"
    (repo / ".git").mkdir(parents=True)
    config_path = tmp_path / "config" / "consumer.local.toml"
    runtime = tmp_path / "runtime"

    monkeypatch.setattr(sys, "argv", [
        "webgpt-bridge", "init",
        "--repo", str(repo),
        "--config-path", str(config_path),
        "--runtime-dir", str(runtime),
        "--review-repository", "owner/demo",
    ])
    assert main() == 0
    assert config_path.exists()
    cfg = load_config(config_path)
    assert cfg.repo_root == repo.resolve()
    assert cfg.runtime_dir == runtime.resolve()
    assert cfg.review_repository == "owner/demo"
    assert cfg.target_conversation_url is None

    monkeypatch.setattr(sys, "argv", [
        "webgpt-bridge", "check", "--config", str(config_path),
    ])
    assert main() == 0
    output = capsys.readouterr().out
    assert "webgpt-bridge check: PASS" in output
    assert "review_repository: owner/demo" in output

    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / "dedup.json").write_text(json.dumps({
        "attempt_started": {},
        "fetch_sent": {},
        "attempt_failed": {
            "H_RETRY": {
                "timestamp": "2026-08-11T09:18:39+00:00",
                "reason": "test",
                "marker": "{}",
            }
        },
    }), encoding="utf-8")

    def browser_forbidden(*args, **kwargs):
        raise AssertionError("browser sender must not be constructed for retry")

    monkeypatch.setattr(cli_module, "CdpFetchSender", browser_forbidden)
    monkeypatch.setattr(sys, "argv", [
        "webgpt-bridge", "retry", "--config", str(config_path), "--handoff", "H_RETRY",
    ])
    assert main() == 0
    state = json.loads((runtime / "dedup.json").read_text(encoding="utf-8"))
    assert "H_RETRY" not in state["attempt_failed"]
