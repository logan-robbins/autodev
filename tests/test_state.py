from pathlib import Path

import pytest

from autodev.config import ConfigError, load_project
from autodev.state import (
    Registry,
    autodev_home,
    project_paths,
    read_role_law,
    write_role_law,
)


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


def test_role_law_round_trips_at_mode_0600(tmp_path: Path) -> None:
    home = tmp_path / "state"
    path = write_role_law("acme", "engineering", "Own a Leaf; red tests first.", home=home)
    assert read_role_law("acme", "engineering", home=home) == "Own a Leaf; red tests first."
    assert path.stat().st_mode & 0o777 == 0o600


def test_role_law_lives_outside_any_worktree(project_repo: Path, tmp_path: Path) -> None:
    home = tmp_path / "state"
    path = write_role_law("sample-project", "product-manager", "law", home=home)
    assert home in path.parents
    assert project_repo not in path.parents


def test_read_missing_role_law_fails_fast(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="no composed law"):
        read_role_law("acme", "engineering", home=tmp_path / "state")
