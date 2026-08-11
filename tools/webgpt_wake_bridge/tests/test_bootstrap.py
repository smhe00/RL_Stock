from pathlib import Path

import pytest

from webgpt_wake_bridge.bootstrap import default_config_path, default_runtime_dir, project_key, write_initial_config
from webgpt_wake_bridge.config import load_config
from webgpt_wake_bridge.errors import BridgeError


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "consumer"
    (repo / ".git").mkdir(parents=True)
    return repo


def test_project_key_is_stable_and_path_specific(tmp_path):
    a = make_repo(tmp_path / "a")
    b = make_repo(tmp_path / "b")
    assert project_key(a) == project_key(a)
    assert project_key(a) != project_key(b)


def test_default_bootstrap_locations_are_user_local_not_consumer_repo(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    config_path = default_config_path(repo)
    runtime = default_runtime_dir(repo)
    assert str(config_path).startswith(str(home))
    assert str(runtime).startswith(str(home))
    assert not str(config_path).startswith(str(repo))
    assert not str(runtime).startswith(str(repo))


def test_write_initial_config_round_trips_and_refuses_overwrite(tmp_path):
    repo = make_repo(tmp_path)
    config_path = tmp_path / "local" / "consumer.local.toml"
    runtime = tmp_path / "runtime"
    created = write_initial_config(
        repo,
        config_path=config_path,
        runtime_dir=runtime,
        review_repository="owner/demo",
    )
    assert created == config_path.resolve()
    assert not (repo / "docs").exists()

    cfg = load_config(created)
    assert cfg.repo_root == repo.resolve()
    assert cfg.marker_root == Path("docs/web_bridge")
    assert cfg.runtime_dir == runtime.resolve()
    assert cfg.review_repository == "owner/demo"
    assert cfg.target_conversation_url is None

    with pytest.raises(BridgeError):
        write_initial_config(repo, config_path=config_path, runtime_dir=runtime)
