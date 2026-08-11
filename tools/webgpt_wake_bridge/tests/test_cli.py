import sys
from pathlib import Path

from webgpt_wake_bridge.cli import main
from webgpt_wake_bridge.config import load_config


def test_cli_init_then_check(tmp_path, monkeypatch, capsys):
    repo = tmp_path / "consumer"
    (repo / ".git").mkdir(parents=True)
    config_path = tmp_path / "config" / "consumer.local.toml"
    runtime = tmp_path / "runtime"

    monkeypatch.setattr(sys, "argv", [
        "webgpt-bridge", "init",
        "--repo", str(repo),
        "--config-path", str(config_path),
        "--runtime-dir", str(runtime),
    ])
    assert main() == 0
    assert config_path.exists()
    cfg = load_config(config_path)
    assert cfg.repo_root == repo.resolve()
    assert cfg.runtime_dir == runtime.resolve()

    monkeypatch.setattr(sys, "argv", [
        "webgpt-bridge", "check", "--config", str(config_path),
    ])
    assert main() == 0
    output = capsys.readouterr().out
    assert "webgpt-bridge check: PASS" in output
