"""Run user-installed coding agents in namespaced tmux sessions."""

from __future__ import annotations

import shlex
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from autodev.config import AgentConfig, ProjectConfig, render_session_name
from autodev.prompts import render_goal
from autodev.providers import launch_command
from autodev.state import project_paths
from autodev.workspaces import (
    Workspace,
    git_status,
    ownership_violations,
    workspace_branch,
    workspace_path,
)


class SessionError(RuntimeError):
    """Raised when the tmux-backed agent runtime is unavailable."""


@dataclass(frozen=True)
class AgentStatus:
    project: str
    agent: str
    provider: str
    session: str
    running: bool
    pane_command: str | None
    worktree: str
    worktree_exists: bool
    branch: str
    git_status: str
    ownership_violations: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def require_tmux() -> str:
    path = shutil.which("tmux")
    if not path:
        raise SessionError("tmux is not installed or not on PATH")
    return path


def _tmux(*args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [require_tmux(), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "no output"
        raise SessionError(f"tmux {' '.join(args)} failed: {detail}")
    return result


def session_name(project: ProjectConfig, agent: AgentConfig) -> str:
    return render_session_name(project.session_pattern, project.id, agent)


def session_exists(name: str) -> bool:
    tmux = shutil.which("tmux")
    if not tmux:
        return False
    result = subprocess.run(
        [tmux, "has-session", "-t", name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def send_goal(project: ProjectConfig, agent: AgentConfig, *, dry_run: bool = False) -> str:
    name = session_name(project, agent)
    prompt = render_goal(project, agent)
    if dry_run:
        return prompt
    if not session_exists(name):
        raise SessionError(f"tmux session {name!r} is not running; run `autodev ensure` first")
    _tmux("send-keys", "-t", name, "-l", prompt)
    time.sleep(0.2)
    _tmux("send-keys", "-t", name, "C-m")
    return prompt


def start_session(
    project: ProjectConfig,
    agent: AgentConfig,
    workspace: Workspace,
    *,
    send_initial_goal: bool,
) -> bool:
    """Start one session and return True, or return False when it already exists."""
    name = session_name(project, agent)
    if session_exists(name):
        return False
    provider = project.providers[agent.provider]
    prompt = render_goal(project, agent) if send_initial_goal else None
    command = launch_command(
        provider,
        workspace.path,
        bypass_permissions=project.bypass_permissions,
        initial_prompt=prompt,
    )
    _tmux(
        "new-session",
        "-d",
        "-s",
        name,
        "-c",
        str(workspace.path),
        shlex.join(command),
    )

    paths = project_paths(project.id)
    paths.logs.mkdir(parents=True, exist_ok=True)
    log_path = paths.logs / f"{agent.id}.log"
    _tmux(
        "pipe-pane",
        "-o",
        "-t",
        name,
        f"tee -a {shlex.quote(str(log_path))} >/dev/null",
    )
    return True


def stop_session(project: ProjectConfig, agent: AgentConfig) -> bool:
    name = session_name(project, agent)
    if not session_exists(name):
        return False
    _tmux("kill-session", "-t", name)
    return True


def _pane_command(name: str) -> str | None:
    if not session_exists(name):
        return None
    result = subprocess.run(
        [require_tmux(), "display-message", "-p", "-t", name, "#{pane_current_command}"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.stdout.strip() or None


def agent_status(project: ProjectConfig, agent: AgentConfig, *, home: Path | None = None) -> AgentStatus:
    path = workspace_path(project, agent, home=home)
    branch = workspace_branch(project, agent)
    name = session_name(project, agent)
    status_text = ""
    violations: tuple[str, ...] = ()
    if (path / ".git").is_file():
        workspace = Workspace(path=path, branch=branch)
        try:
            status_text = git_status(workspace)
            violations = ownership_violations(workspace, agent)
        except RuntimeError as exc:
            status_text = f"ERROR: {exc}"
    return AgentStatus(
        project=project.id,
        agent=agent.id,
        provider=agent.provider,
        session=name,
        running=session_exists(name),
        pane_command=_pane_command(name),
        worktree=str(path),
        worktree_exists=(path / ".git").is_file(),
        branch=branch,
        git_status=status_text,
        ownership_violations=violations,
    )
