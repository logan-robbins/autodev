"""Run user-installed coding agents in namespaced tmux sessions."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from autodev.config import AgentConfig, ProjectConfig, render_session_name
from autodev.prompts import render_goal
from autodev.providers import launch_command
from autodev.state import project_paths
from autodev.trace import hook_config
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
class RunContext:
    """Binds a launched session to one orchestrator run so its hooks resolve.

    The env pairs below are exported into the tmux session (A5c); the fired hook
    verbs (``autodev trace emit`` / ``policy check`` / ``charter digest``) read
    them to find their run directory, role, and kind.
    """

    run_id: str
    role: str
    kind: str
    provider: str | None = None


def autodev_command() -> list[str]:
    """The argv a fired hook uses to re-enter Autodev.

    Absolute interpreter + ``-m autodev`` so it resolves regardless of the
    worker's PATH — the worker's shell may not have ``autodev`` on it.
    """
    return [sys.executable, "-m", "autodev"]


def _session_env(project: ProjectConfig, run: RunContext) -> dict[str, str]:
    env = {
        "AUTODEV_PROJECT": project.id,
        "AUTODEV_RUN_ID": run.run_id,
        "AUTODEV_ROLE": run.role,
        "AUTODEV_KIND": run.kind,
    }
    if run.provider:
        env["AUTODEV_PROVIDER"] = run.provider
    home = os.environ.get("AUTODEV_HOME")
    if home:
        env["AUTODEV_HOME"] = home
    return env


def _new_session_args(name: str, cwd: Path, command: list[str], env: dict[str, str]) -> list[str]:
    args = ["new-session", "-d", "-s", name, "-c", str(cwd)]
    for key in sorted(env):
        args.extend(["-e", f"{key}={env[key]}"])
    args.append(shlex.join(command))
    return args


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
    run: RunContext | None = None,
    law_file: Path | None = None,
) -> bool:
    """Start one session and return True, or return False when it already exists.

    When ``run`` is set the session carries its run env and the worker is
    launched with the hook spec, so every tool call folds into the run trace and
    the policy gate fires. ``law_file`` is the composed role law appended to the
    system prompt (C2, Claude only).
    """
    name = session_name(project, agent)
    if session_exists(name):
        return False
    provider = project.providers[agent.provider]
    prompt = render_goal(project, agent) if send_initial_goal else None
    env = _session_env(project, run) if run else {}
    spec = hook_config(run.run_id, autodev_command()) if run else None
    command = launch_command(
        provider,
        workspace.path,
        bypass_permissions=project.bypass_permissions,
        initial_prompt=prompt,
        hook_config=spec,
        law_file=law_file,
    )
    _tmux(*_new_session_args(name, workspace.path, command, env))

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
