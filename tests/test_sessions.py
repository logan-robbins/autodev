from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from autodev.config import load_project
from autodev.sessions import (
    agent_status,
    session_exists,
    session_name,
    start_session,
    stop_session,
)
from autodev.workspaces import ensure_workspace


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
        assert start_session(project, agent, workspace, yolo=False, send_initial_goal=False) is True
        assert session_exists(name)
        assert start_session(project, agent, workspace, yolo=False, send_initial_goal=False) is False
        status = agent_status(project, agent)
        assert status.running is True
        assert status.worktree_exists is True
        assert status.session == "autodev-sample-project-backend"
    finally:
        stop_session(project, agent)
    assert not session_exists(name)
