"""Merge one verified, owned agent branch into a project's base branch."""

from __future__ import annotations

import subprocess

from autodev.config import AgentConfig, ProjectConfig
from autodev.workspaces import (
    Workspace,
    path_is_owned,
    workspace_branch,
    workspace_path,
)


class IntegrationError(RuntimeError):
    """Raised when an agent branch is not safe to integrate."""


def _git(project: ProjectConfig, *args: str, cwd=None, check: bool = True) -> subprocess.CompletedProcess[str]:
    directory = cwd or project.root
    result = subprocess.run(
        ["git", *args],
        cwd=directory,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "no output"
        raise IntegrationError(f"git {' '.join(args)} failed in {directory}: {detail}")
    return result


def integrate(project: ProjectConfig, agent: AgentConfig) -> str:
    path = workspace_path(project, agent)
    branch = workspace_branch(project, agent)
    if not (path / ".git").is_file():
        raise IntegrationError(f"agent worktree does not exist: {path}")

    source = Workspace(path=path, branch=branch)
    source_status = _git(project, "status", "--porcelain", cwd=source.path).stdout.strip()
    if source_status:
        raise IntegrationError(f"agent worktree has uncommitted changes:\n{source_status}")

    root_branch = _git(project, "branch", "--show-current").stdout.strip()
    if root_branch != project.base_branch:
        raise IntegrationError(
            f"project checkout must be on base branch {project.base_branch!r}; found {root_branch!r}"
        )
    root_status = _git(project, "status", "--porcelain").stdout.strip()
    if root_status:
        raise IntegrationError(f"project checkout is dirty; resolve it before integration:\n{root_status}")

    changed = tuple(
        line
        for line in _git(
            project,
            "diff",
            "--name-only",
            f"{project.base_branch}...{branch}",
        ).stdout.splitlines()
        if line
    )
    violations = tuple(path for path in changed if not path_is_owned(path, agent))
    if violations:
        raise IntegrationError(
            f"branch {branch!r} changes paths outside agent {agent.id!r} ownership:\n" + "\n".join(violations)
        )

    if (
        _git(
            project,
            "merge-base",
            "--is-ancestor",
            branch,
            project.base_branch,
            check=False,
        ).returncode
        == 0
    ):
        return f"{branch} is already integrated into {project.base_branch}"

    _git(project, "diff", "--check", f"{project.base_branch}...{branch}")
    merge = _git(
        project,
        "merge",
        "--no-ff",
        "--no-commit",
        branch,
        check=False,
    )
    if merge.returncode:
        _git(project, "merge", "--abort", check=False)
        detail = merge.stderr.strip() or merge.stdout.strip() or "merge conflict"
        raise IntegrationError(
            f"cannot integrate {branch!r}; merge the base branch into the agent branch, "
            f"resolve and verify it, then retry: {detail}"
        )
    try:
        _git(project, "diff", "--check", "--cached")
        _git(project, "commit", "-m", f"Merge Autodev agent {agent.id}")
    except Exception:
        _git(project, "merge", "--abort", check=False)
        raise

    _git(project, "merge", "--ff-only", project.base_branch, cwd=source.path)
    return f"merged {branch} into {project.base_branch} and refreshed its worktree"
