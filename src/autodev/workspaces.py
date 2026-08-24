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


def sparse_paths(project: ProjectConfig, agent: AgentConfig) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            (
                *AUTOMATIC_CONTEXT,
                *project.context_roots,
                *agent.read_roots,
                *agent.write_roots,
            )
        )
    )


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
) -> Workspace:
    branch = workspace_branch(project, agent)
    destination = workspace_path(project, agent, home=home)
    ref = base_ref or project.base_branch
    _git(project.root, "rev-parse", "--verify", f"{ref}^{{commit}}")

    if destination.exists():
        _validate_existing(destination, branch)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        branch_exists = (
            _git(
                project.root,
                "show-ref",
                "--verify",
                "--quiet",
                f"refs/heads/{branch}",
                check=False,
            ).returncode
            == 0
        )
        if branch_exists:
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

    patterns = "\n".join(sparse_paths(project, agent)) + "\n"
    _git(destination, "sparse-checkout", "init", "--no-cone")
    _git(destination, "sparse-checkout", "set", "--no-cone", "--stdin", input_text=patterns)
    _git(destination, "checkout", branch)
    return Workspace(path=destination, branch=branch)


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
