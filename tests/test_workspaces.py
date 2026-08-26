from __future__ import annotations

import subprocess
from pathlib import Path

from autodev.config import AgentConfig, load_project
from autodev.workspaces import (
    ensure_workspace,
    ownership_violations,
    sparse_paths,
    workspace_branch,
)


def _integrator_agent() -> AgentConfig:
    return AgentConfig(
        id="integrator",
        provider="codex",
        purpose="Integrate.",
        goal="Integrate and verify.",
        write_roots=("src/impl/book/",),
        read_roots=("contracts/", "tests/"),
    )


def test_materializes_external_sparse_agent_worktree(project_repo: Path, tmp_path: Path) -> None:
    project = load_project(project_repo)
    agent = project.agent("backend")

    workspace = ensure_workspace(project, agent, home=tmp_path / "autodev-state")

    assert workspace.branch == "autodev/sample-project/backend"
    assert (workspace.path / "src" / "backend" / "app.py").is_file()
    assert not (workspace.path / "src" / "frontend" / "app.js").exists()
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
    agent = project.agent("backend")
    workspace = ensure_workspace(project, agent, home=tmp_path / "state")
    (workspace.path / "README.md").write_text("unauthorized\n", encoding="utf-8")

    assert ownership_violations(workspace, agent) == ("README.md",)


def test_sparse_paths_include_core_context_and_owned_roots(project_repo: Path) -> None:
    project = load_project(project_repo)
    paths = sparse_paths(project, project.agent("backend"))

    assert "README.md" in paths
    assert "AGENTS.md" in paths
    assert "CLAUDE.md" in paths
    assert "autodev.toml" in paths
    assert "src/backend/" in paths


def test_integrate_sparse_paths_exclude_impl(project_repo: Path) -> None:
    project = load_project(project_repo)
    agent = _integrator_agent()

    default = sparse_paths(project, agent)
    assert "src/impl/book/" in default  # normally visible

    integrate = sparse_paths(project, agent, kind="integrate")
    assert "src/impl/book/" not in integrate  # carved out for the integrator
    assert "!src/impl/" in integrate  # and negated so it stays off disk
    assert "contracts/" in integrate  # eval signals remain visible


def test_integrate_worktree_has_no_impl_on_disk(project_repo: Path, tmp_path: Path) -> None:
    # Give the repo a src/impl file the integrator must not see.
    impl = project_repo / "src" / "impl" / "book"
    impl.mkdir(parents=True)
    (impl / "store.py").write_text("SECRET = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=project_repo, check=True)
    subprocess.run(["git", "commit", "-m", "impl"], cwd=project_repo, check=True)

    project = load_project(project_repo)
    workspace = ensure_workspace(project, _integrator_agent(), home=tmp_path / "state", kind="integrate")
    assert not (workspace.path / "src" / "impl" / "book" / "store.py").exists()
