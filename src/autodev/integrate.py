"""Merge one verified, owned agent branch into a project's base branch."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from autodev.config import AgentConfig, ProjectConfig
from autodev.contracts import verify_agent, verify_pillar
from autodev.state import project_paths
from autodev.storage import atomic_json, locked
from autodev.workspaces import (
    Workspace,
    copy_workspace,
    file_manifest,
    path_is_owned,
    snapshot_path,
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
    with locked(project_paths(project.id).home / "integration.lock"):
        if project.execution == "filesystem":
            return _integrate_files(project, agent)
        return _integrate_git(project, agent)


def verify_integration(project: ProjectConfig, agent: AgentConfig, root: Path) -> None:
    verify_agent(project, agent, root)
    for pillar in project.pillars:
        verify_pillar(pillar, workspace=root, interface_only=pillar.state == "interface-ready")


def _integrate_git(project: ProjectConfig, agent: AgentConfig) -> str:
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
            "--no-renames",
            "-z",
            f"{project.base_branch}...{branch}",
        ).stdout.split("\0")
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
        verify_integration(project, agent, project.root)
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
        expected_tree = _git(project, "write-tree").stdout.strip()
        expected_files = file_manifest(project.root)
        verify_integration(project, agent, project.root)
        if file_manifest(project.root) != expected_files or _git(project, "write-tree").stdout.strip() != expected_tree:
            raise IntegrationError("verification modified files or the Git index; integration aborted")
        _git(project, "diff", "--check", "--cached")
        _git(project, "commit", "-m", f"Merge Autodev agent {agent.id}")
    except Exception:
        _git(project, "merge", "--abort", check=False)
        raise

    _git(project, "merge", "--ff-only", project.base_branch, cwd=source.path)
    return f"merged {branch} into {project.base_branch} and refreshed its worktree"


def _integrate_files(project: ProjectConfig, agent: AgentConfig) -> str:
    source = Workspace(workspace_path(project, agent), "")
    metadata_path = snapshot_path(source)
    if not metadata_path.is_file():
        raise IntegrationError(f"Harness Agent workspace does not exist: {source.path}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    baseline = metadata["files"]
    current = file_manifest(source.path)
    changed = sorted(p for p in set(baseline) | set(current) if baseline.get(p) != current.get(p))
    violations = [p for p in changed if not path_is_owned(p, agent)]
    if violations:
        raise IntegrationError(f"changes outside ownership: {', '.join(violations)}")
    published = file_manifest(project.root)
    for path in changed:
        if published.get(path) != baseline.get(path):
            raise IntegrationError(f"publication conflict at {path}; reconcile with the current workspace first")
        if current.get(path, "").startswith("symlink:"):
            raise IntegrationError(f"cannot publish a symlink: {path}")
    with tempfile.TemporaryDirectory(prefix="integration-", dir=project_paths(project.id).home) as directory:
        candidate = Path(directory) / "candidate"
        copy_workspace(project.root, candidate)
        for name in changed:
            target = candidate / name
            if name in current:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source.path / name, target)
            else:
                target.unlink()
        expected = file_manifest(candidate)
        verify_integration(project, agent, candidate)
        if file_manifest(candidate) != expected or file_manifest(source.path) != current:
            raise IntegrationError("files changed during verification; retry with stable artifacts")
        if file_manifest(project.root) != published:
            raise IntegrationError("published workspace changed during verification; retry")
        # Keep backups until every replacement succeeds. Runtime publications serialize
        # on integration.lock; external readers should consume a completed delivery.
        backup = Path(directory) / "backup"
        applied = []
        try:
            for name in changed:
                target = project.root / name
                previous = backup / name
                if target.is_file():
                    previous.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(target, previous)
                applied.append(name)
                if name in current:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    staged = target.with_name(f".{target.name}.autodev-publish")
                    try:
                        shutil.copy2(candidate / name, staged)
                        staged.replace(target)
                    finally:
                        staged.unlink(missing_ok=True)
                else:
                    target.unlink()
        except Exception:
            for name in reversed(applied):
                target, previous = project.root / name, backup / name
                if previous.exists():
                    shutil.copy2(previous, target)
                else:
                    target.unlink(missing_ok=True)
            raise
    # Preserve unrelated context and refresh its baseline only for paths published.
    metadata["files"] = current
    atomic_json(metadata_path, metadata)
    return f"published {agent.id}: {len(changed)} owned path(s) verified against all Pillar contracts"
