from __future__ import annotations

import subprocess
from pathlib import Path

from autodev.config import AgentConfig, load_project
from autodev.workspaces import (
    branch_exists,
    ensure_workspace,
    ownership_violations,
    remove_workspace,
    sparse_paths,
    workspace_branch,
    workspace_path,
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


def _tw_agent() -> AgentConfig:
    return AgentConfig(
        id="tw-replay-engine",
        provider="claude",
        purpose="Document.",
        goal="Document the shipped pillar.",
        write_roots=("product/pillars/replay-engine/README.md", "product/pillars/replay-engine/TECHNICAL.md"),
        read_roots=("src/impl/replay-engine/", "product/pillars/replay-engine/"),
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


def test_remove_workspace_tears_down_worktree_and_branch(project_repo: Path, tmp_path: Path) -> None:
    home = tmp_path / "state"
    project = load_project(project_repo)
    agent = project.agent("backend")
    workspace = ensure_workspace(project, agent, home=home)
    branch = workspace_branch(project, agent)
    assert workspace.path.exists()
    assert branch_exists(project.root, branch)

    assert remove_workspace(project, agent, home=home) is True
    assert not workspace_path(project, agent, home=home).exists()
    assert not branch_exists(project.root, branch)
    # Idempotent: a second teardown finds nothing to remove.
    assert remove_workspace(project, agent, home=home) is False


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


# --- J2b: the document kind keeps src/impl on disk ---------------------------


def test_document_sparse_paths_keep_impl(project_repo: Path) -> None:
    project = load_project(project_repo)
    agent = _tw_agent()

    document = sparse_paths(project, agent, kind="document")
    assert "src/impl/replay-engine/" in document  # TW reads the pillar source for docs
    assert "!src/impl/" not in document  # never carved out (unlike integrate)

    integrate = sparse_paths(project, agent, kind="integrate")
    assert "src/impl/replay-engine/" not in integrate  # contrast: integrate strips it


def test_document_worktree_has_pillar_source_on_disk(project_repo: Path, tmp_path: Path) -> None:
    impl = project_repo / "src" / "impl" / "replay-engine"
    impl.mkdir(parents=True)
    (impl / "store.py").write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=project_repo, check=True)
    subprocess.run(["git", "commit", "-m", "impl"], cwd=project_repo, check=True)

    project = load_project(project_repo)
    workspace = ensure_workspace(project, _tw_agent(), home=tmp_path / "state", kind="document")
    assert (workspace.path / "src" / "impl" / "replay-engine" / "store.py").is_file()


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
