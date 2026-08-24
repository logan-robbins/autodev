from pathlib import Path

import pytest

from autodev.config import ConfigError, load_project
from autodev.state import Registry, autodev_home, project_paths


def test_registry_tracks_external_descriptors(project_repo: Path, tmp_path: Path) -> None:
    registry = Registry(home=tmp_path / "state")
    project = load_project(project_repo)

    registry.register(project)

    assert registry.entries() == {"sample-project": project_repo / "autodev.toml"}
    assert registry.resolve("sample-project").root == project_repo
    assert str(project_repo) not in str(project_paths(project.id, home=registry.home).worktrees)
    registry.unregister("sample-project")
    assert registry.entries() == {}


def test_registry_fails_fast_on_unknown_project(tmp_path: Path) -> None:
    registry = Registry(home=tmp_path / "state")
    with pytest.raises(ConfigError, match="not registered"):
        registry.resolve("missing")


def test_autodev_home_honors_explicit_override(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "central-state"
    monkeypatch.setenv("AUTODEV_HOME", str(target))
    assert autodev_home() == target


def test_project_paths_expose_runs_directory(tmp_path: Path) -> None:
    paths = project_paths("acme", home=tmp_path / "state")
    assert paths.runs == paths.home / "runs"
    assert paths.runs.parent == paths.home
