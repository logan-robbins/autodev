"""Create isolated sparse Git worktrees for configured agents."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from autodev.config import AgentConfig, ProjectConfig
from autodev.state import project_paths

AUTOMATIC_CONTEXT = (
    ".agents/skills/",
    ".claude/",
    ".codex/",
    ".gitignore",
    "AGENTS.md",
    "AGENTS.override.md",
    "CLAUDE.md",
    "README.md",
    "autodev.toml",
)


class WorkspaceError(RuntimeError):
    """Raised when an isolated Git worktree cannot be prepared safely."""


@dataclass(frozen=True)
class Workspace:
    path: Path
    branch: str


def workspace_branch(project: ProjectConfig, agent: AgentConfig) -> str:
    return f"autodev/{project.id}/{agent.id}"


def workspace_path(project: ProjectConfig, agent: AgentConfig, *, home: Path | None = None) -> Path:
    return project_paths(project.id, home=home).worktrees / agent.id


# src/impl is the pod-private implementation; an integrator must never see it.
_IMPL_ROOT = "src/impl"


def _under_impl(pattern: str) -> bool:
    stripped = pattern.rstrip("/")
    return stripped == _IMPL_ROOT or stripped.startswith(_IMPL_ROOT + "/")


def sparse_paths(project: ProjectConfig, agent: AgentConfig, *, kind: str | None = None) -> tuple[str, ...]:
    """Sparse-checkout patterns for an agent, narrowed by the role/kind it runs.

    An ``integrate`` pass reads eval signals, not source: its worktree physically
    excludes ``src/impl/**`` (C5), so the boundary is enforced by what is on disk,
    not by a request the model could ignore. Every other kind — including
    ``document`` (the Technical Writer, which must read ``src/impl/<pillar>`` to
    write the docs) — keeps the full read set from ``read_roots``.
    """
    patterns = list(
        dict.fromkeys(
            (
                *AUTOMATIC_CONTEXT,
                *project.context_roots,
                *agent.read_roots,
                *agent.write_roots,
            )
        )
    )
    if kind == "integrate":
        patterns = [pattern for pattern in patterns if not _under_impl(pattern)]
        patterns.append(f"!{_IMPL_ROOT}/")
    return tuple(patterns)


def _git(
    cwd: Path,
    *args: str,
    input_text: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "no output"
        raise WorkspaceError(f"git {' '.join(args)} failed in {cwd}: {detail}")
    return result


def branch_exists(root: Path, branch: str) -> bool:
    """True when ``refs/heads/<branch>`` resolves in the repository at ``root``."""
    return _git(root, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}", check=False).returncode == 0


def _validate_existing(path: Path, branch: str) -> None:
    if not (path / ".git").is_file():
        raise WorkspaceError(f"{path} exists but is not an Autodev Git worktree")
    actual = _git(path, "branch", "--show-current").stdout.strip()
    if actual != branch:
        raise WorkspaceError(f"{path} is on branch {actual!r}; expected {branch!r}")


def ensure_workspace(
    project: ProjectConfig,
    agent: AgentConfig,
    *,
    base_ref: str | None = None,
    home: Path | None = None,
    kind: str | None = None,
) -> Workspace:
    branch = workspace_branch(project, agent)
    destination = workspace_path(project, agent, home=home)
    ref = base_ref or project.base_branch
    _git(project.root, "rev-parse", "--verify", f"{ref}^{{commit}}")

    if destination.exists():
        _validate_existing(destination, branch)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if branch_exists(project.root, branch):
            _git(project.root, "worktree", "add", "--no-checkout", str(destination), branch)
        else:
            _git(
                project.root,
                "worktree",
                "add",
                "--no-checkout",
                "-b",
                branch,
                str(destination),
                ref,
            )

    patterns = "\n".join(sparse_paths(project, agent, kind=kind)) + "\n"
    _git(destination, "sparse-checkout", "init", "--no-cone")
    _git(destination, "sparse-checkout", "set", "--no-cone", "--stdin", input_text=patterns)
    _git(destination, "checkout", branch)
    return Workspace(path=destination, branch=branch)


def remove_workspace(project: ProjectConfig, agent: AgentConfig, *, home: Path | None = None) -> bool:
    """Tear down one agent's sparse worktree and branch — the twin of ``ensure_workspace``.

    Same path/branch derivation as creation. Force-removes the worktree (an
    Autodev reset discards any unmerged pod work by design), then force-deletes
    the branch; the worktree must go first so Git will release the branch.
    Returns ``True`` when a worktree or branch existed. Only ever touches an
    Autodev-managed worktree under ``AUTODEV_HOME`` and its ``autodev/<project>/``
    branch — never the project working tree.
    """
    destination = workspace_path(project, agent, home=home)
    branch = workspace_branch(project, agent)
    removed = False
    if destination.exists():
        _git(project.root, "worktree", "remove", "--force", str(destination))
        removed = True
    if branch_exists(project.root, branch):
        _git(project.root, "branch", "-D", branch)
        removed = True
    return removed


def git_status(workspace: Workspace) -> str:
    return _git(workspace.path, "status", "--short").stdout.rstrip()


def changed_paths(workspace: Workspace) -> tuple[str, ...]:
    result = _git(workspace.path, "status", "--porcelain", "-z").stdout
    paths: list[str] = []
    entries = result.split("\0")
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if not entry:
            continue
        status = entry[:2]
        path = entry[3:]
        if (status[0] in {"R", "C"} or status[1] in {"R", "C"}) and index < len(entries) and entries[index]:
            path = entries[index]
            index += 1
        paths.append(path)
    return tuple(paths)


def path_is_owned(path: str, agent: AgentConfig) -> bool:
    candidate = path.rstrip("/")
    return any(
        candidate == root.rstrip("/") or candidate.startswith(root.rstrip("/") + "/") for root in agent.write_roots
    )


def ownership_violations(workspace: Workspace, agent: AgentConfig) -> tuple[str, ...]:
    return tuple(path for path in changed_paths(workspace) if not path_is_owned(path, agent))
