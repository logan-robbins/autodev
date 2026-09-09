from pathlib import Path

import pytest

from autodev.config import ConfigError, descriptor_path, load_project


def test_loads_peer_pillars_and_implicit_pods(file_project: Path):
    project = load_project(file_project)
    assert project.execution == "filesystem"
    assert [p.slug for p in project.pillars] == ["backend", "frontend"]
    assert len(project.pillar("backend").pod) == 1
    agent = project.agent("backend--worker")
    assert agent.template == "engineer"
    assert agent.write_roots == ("backend/output/worker/", "backend/src/")
    assert project.providers["codex"].model is None


def test_descriptor_discovery(file_project: Path):
    assert descriptor_path(cwd=file_project / "backend/src") == file_project / "autodev.toml"


@pytest.mark.parametrize("value", ["0", "99", "true", '"1"'])
def test_workspace_requires_canonical_schema(file_project: Path, value):
    path = file_project / "autodev.toml"
    path.write_text(path.read_text().replace("schema_version = 1", f"schema_version = {value}"))
    with pytest.raises(ConfigError, match="schema_version must be 1"):
        load_project(file_project)


@pytest.mark.parametrize("port", [0, 1023, 65536, '"8765"', "true"])
def test_invalid_port(file_project: Path, port):
    path = file_project / "autodev.toml"
    path.write_text(path.read_text().replace("ui_port = 8765", f"ui_port = {port}"))
    with pytest.raises(ConfigError, match="runtime.ui_port"):
        load_project(file_project)


@pytest.mark.parametrize("value", ["0", "1", '"true"'])
def test_invalid_permission_policy(file_project: Path, value):
    path = file_project / "autodev.toml"
    path.write_text(path.read_text().replace("bypass_permissions = false", f"bypass_permissions = {value}"))
    with pytest.raises(ConfigError, match="runtime.bypass_permissions"):
        load_project(file_project)


@pytest.mark.parametrize("pattern", ["{project}", "{project}:{agent}", "{project}-{agent}-{unknown}"])
def test_invalid_session_names(file_project: Path, pattern):
    path = file_project / "autodev.toml"
    path.write_text(path.read_text().replace("autodev-{project}-{agent}", pattern))
    with pytest.raises(ConfigError):
        load_project(file_project)


def test_git_profile_requires_repository_root(file_project: Path):
    path = file_project / "autodev.toml"
    path.write_text(path.read_text().replace('execution = "filesystem"', 'execution = "git"'))
    with pytest.raises(ConfigError, match="Git"):
        load_project(file_project)
