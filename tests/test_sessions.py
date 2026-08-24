from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from autodev.config import load_project
from autodev.sessions import (
    RunContext,
    _new_session_args,
    _session_env,
    agent_status,
    autodev_command,
    require_tmux,
    session_exists,
    session_name,
    start_session,
    stop_session,
)
from autodev.workspaces import ensure_workspace


def test_autodev_command_uses_absolute_interpreter() -> None:
    assert autodev_command() == [sys.executable, "-m", "autodev"]


def test_new_session_args_carry_run_env_pairs(project_repo: Path, monkeypatch) -> None:
    monkeypatch.setenv("AUTODEV_HOME", "/tmp/state-x")
    project = load_project(project_repo)
    env = _session_env(project, RunContext(run_id="book-7", role="engineering", kind="implement"))
    args = _new_session_args("sess", Path("/work"), ["claude", "go"], env)

    assert "-e" in args
    assert "AUTODEV_RUN_ID=book-7" in args
    assert "AUTODEV_ROLE=engineering" in args
    assert "AUTODEV_KIND=implement" in args
    assert "AUTODEV_PROJECT=sample-project" in args
    assert "AUTODEV_HOME=/tmp/state-x" in args
    # the launch command is always last so tmux runs it.
    assert args[-1] == "claude go"


def test_new_session_args_without_env_are_unchanged() -> None:
    args = _new_session_args("sess", Path("/work"), ["claude", "go"], {})
    assert args == ["new-session", "-d", "-s", "sess", "-c", "/work", "claude go"]


def test_session_env_exports_provider_when_set(project_repo: Path) -> None:
    project = load_project(project_repo)
    env = _session_env(project, RunContext(run_id="r", role="engineering", kind="implement", provider="claude"))
    assert env["AUTODEV_PROVIDER"] == "claude"


@pytest.mark.skipif(shutil.which("tmux") is None, reason="tmux is required")
def test_starts_installed_cli_in_namespaced_tmux_session(project_repo: Path, tmp_path: Path, monkeypatch) -> None:
    fake_cli = tmp_path / "fake-codex"
    fake_cli.write_text("#!/bin/sh\nexec sleep 30\n", encoding="utf-8")
    fake_cli.chmod(0o755)
    descriptor = project_repo / "autodev.toml"
    descriptor.write_text(
        descriptor.read_text(encoding="utf-8").replace(
            "[[agents]]",
            f'[providers.codex]\ncommand = "{fake_cli}"\n\n[[agents]]',
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AUTODEV_HOME", str(tmp_path / "state"))
    project = load_project(project_repo)
    agent = project.agent("backend")
    workspace = ensure_workspace(project, agent)
    name = session_name(project, agent)
    if session_exists(name):
        stop_session(project, agent)

    try:
        assert start_session(project, agent, workspace, send_initial_goal=False) is True
        assert session_exists(name)
        assert start_session(project, agent, workspace, send_initial_goal=False) is False
        status = agent_status(project, agent)
        assert status.running is True
        assert status.worktree_exists is True
        assert status.session == "autodev-sample-project-backend"
    finally:
        stop_session(project, agent)
    assert not session_exists(name)


@pytest.mark.skipif(shutil.which("tmux") is None, reason="tmux is required")
def test_run_context_exports_env_a_hook_verb_can_read(project_repo: Path, tmp_path: Path, monkeypatch) -> None:
    fake_cli = tmp_path / "fake-codex"
    fake_cli.write_text("#!/bin/sh\nexec sleep 30\n", encoding="utf-8")
    fake_cli.chmod(0o755)
    descriptor = project_repo / "autodev.toml"
    descriptor.write_text(
        descriptor.read_text(encoding="utf-8").replace(
            "[[agents]]",
            f'[providers.codex]\ncommand = "{fake_cli}"\n\n[[agents]]',
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AUTODEV_HOME", str(tmp_path / "state"))
    project = load_project(project_repo)
    agent = project.agent("backend")
    workspace = ensure_workspace(project, agent)
    name = session_name(project, agent)
    if session_exists(name):
        stop_session(project, agent)

    try:
        assert start_session(
            project,
            agent,
            workspace,
            send_initial_goal=False,
            run=RunContext(run_id="book-7", role="engineering", kind="implement"),
        )
        shown = subprocess.run(
            [require_tmux(), "show-environment", "-t", name, "AUTODEV_RUN_ID"],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        assert shown == "AUTODEV_RUN_ID=book-7"
    finally:
        stop_session(project, agent)
