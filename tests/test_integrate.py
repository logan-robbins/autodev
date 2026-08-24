from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from autodev.config import load_project
from autodev.integrate import IntegrationError, integrate
from autodev.workspaces import ensure_workspace


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def test_integrates_clean_owned_agent_commit(project_repo: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AUTODEV_HOME", str(tmp_path / "state"))
    project = load_project(project_repo)
    agent = project.agent("backend")
    workspace = ensure_workspace(project, agent)
    target = workspace.path / "src" / "backend" / "app.py"
    target.write_text("VALUE = 2\n", encoding="utf-8")
    git(workspace.path, "add", "src/backend/app.py")
    git(workspace.path, "commit", "-m", "Update backend")

    message = integrate(project, agent)

    assert message == "merged autodev/sample-project/backend into main and refreshed its worktree"
    assert (project_repo / "src" / "backend" / "app.py").read_text(encoding="utf-8") == "VALUE = 2\n"
    assert git(project_repo, "status", "--porcelain") == ""


def test_rejects_uncommitted_agent_work(project_repo: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AUTODEV_HOME", str(tmp_path / "state"))
    project = load_project(project_repo)
    agent = project.agent("backend")
    workspace = ensure_workspace(project, agent)
    (workspace.path / "src" / "backend" / "app.py").write_text("VALUE = 3\n", encoding="utf-8")

    with pytest.raises(IntegrationError, match="uncommitted changes"):
        integrate(project, agent)
