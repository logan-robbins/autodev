from __future__ import annotations

import subprocess
from pathlib import Path

from autodev.config import load_project
from autodev.workspaces import (
    ensure_workspace,
    ownership_violations,
    sparse_paths,
    workspace_branch,
)


def test_materializes_external_sparse_agent_worktree(project_repo: Path, tmp_path: Path) -> None:
    project = load_project(project_repo)
    agent = project.agent("backend--worker")

    workspace = ensure_workspace(project, agent, home=tmp_path / "autodev-state")

    assert workspace.branch == "autodev/sample-project/backend--worker"
    assert (workspace.path / "backend" / "src" / "app.py").is_file()
    assert not (workspace.path / "frontend" / "src" / "app.js").exists()
    assert (workspace.path / "autodev.toml").is_file()
    assert workspace.path.is_relative_to(tmp_path / "autodev-state")
    assert (
        workspace_branch(project, agent)
        in subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=project_repo,
            text=True,
            stdout=subprocess.PIPE,
            check=True,
        ).stdout
    )


def test_ownership_gate_detects_context_edits(project_repo: Path, tmp_path: Path) -> None:
    project = load_project(project_repo)
    agent = project.agent("backend--worker")
    workspace = ensure_workspace(project, agent, home=tmp_path / "state")
    (workspace.path / "README.md").write_text("unauthorized\n", encoding="utf-8")

    assert ownership_violations(workspace, agent) == ("README.md",)


def test_sparse_paths_include_core_context_and_owned_roots(project_repo: Path) -> None:
    project = load_project(project_repo)
    paths = sparse_paths(project, project.agent("backend--worker"))

    assert "README.md" in paths
    assert "AGENTS.md" in paths
    assert "CLAUDE.md" in paths
    assert "autodev.toml" in paths
    assert "backend/src/" in paths


def test_clean_filesystem_refresh_removes_revoked_context(file_project: Path):
    path = file_project / "backend/pillar.toml"
    path.write_text(path.read_text().replace("read_roots = [", 'read_roots = ["private/", '))
    private = file_project / "backend/private/notes.txt"
    private.parent.mkdir()
    private.write_text("Scoped context")
    project = load_project(file_project)
    workspace = ensure_workspace(project, project.agent("backend--worker"))
    assert (workspace.path / "backend/private/notes.txt").exists()
    path.write_text(path.read_text().replace('"private/", ', ""))
    project = load_project(file_project)
    ensure_workspace(project, project.agent("backend--worker"))
    assert not (workspace.path / "backend/private/notes.txt").exists()
    assert private.read_text() == "Scoped context"


def test_git_preparation_rejects_uncommitted_pillar_contract(project_repo: Path):
    import pytest

    from autodev.workspaces import WorkspaceError

    path = project_repo / "backend/pillar.toml"
    path.write_text(path.read_text() + "\n")
    project = load_project(project_repo)
    with pytest.raises(WorkspaceError, match="commit current contract backend/pillar.toml"):
        ensure_workspace(project, project.agent("backend--worker"))
