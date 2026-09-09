from __future__ import annotations

import shutil
import subprocess
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
    descriptor.write_text(descriptor.read_text() + f'\n[providers.codex]\ncommand = "{fake_cli}"\n')
    subprocess.run(["git", "add", "autodev.toml"], cwd=project_repo, check=True)
    subprocess.run(["git", "commit", "-m", "Configure test harness"], cwd=project_repo, check=True, capture_output=True)
    monkeypatch.setenv("AUTODEV_HOME", str(tmp_path / "state"))
    project = load_project(project_repo)
    agent = project.agent("backend--worker")
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
        assert status.session == "autodev-sample-project-backend--worker"
    finally:
        stop_session(project, agent)
    assert not session_exists(name)


def test_two_native_sessions_read_and_complete_their_own_ledgers(file_project: Path, tmp_path: Path, monkeypatch):
    import json
    import sys
    import time

    from autodev.operations import ensure_agents
    from autodev.tasks import TaskStore

    if shutil.which("tmux") is None:
        pytest.skip("tmux is required")
    descriptor = file_project / "backend/pillar.toml"
    descriptor.write_text(
        descriptor.read_text() + '\n[[agents]]\nid = "colleague"\ntemplate = "researcher"\nprovider = "codex"\n'
    )
    fake = tmp_path / "fake-harness"
    fake.write_text(f"""#!{sys.executable}
import json, os, time
from pathlib import Path
from autodev.config import load_project
from autodev.tasks import TaskStore
project = load_project(os.environ['AUTODEV_PROJECT_DESCRIPTOR'])
agent = project.agent(os.environ['AUTODEV_AGENT_ID'])
store = TaskStore(project, agent)
assert all(task['agent'] == agent.id for task in store.list())
task = store.claim()
output = Path.cwd() / agent.pillar / agent.deliverables[0].path
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps({{'status':'completed','summary':agent.id,'evidence':['Executed native session test'], 'artifacts':[]}}))
store.complete(task['id'])
time.sleep(30)
""")
    fake.chmod(0o755)
    manifest = file_project / "autodev.toml"
    manifest.write_text(manifest.read_text() + f"\n[providers.codex]\ncommand = {json.dumps(str(fake))}\n")
    project = load_project(file_project)
    agents = project.pillar("backend").agents
    for agent in agents:
        TaskStore(project, agent).create(agent, "Deliver output", acceptance=("Produce a validated result.",))
    try:
        ensure_agents(project, agents, base_ref=None, start=True, send_initial_goal=True)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if all(TaskStore(project, a).list()[0]["status"] == "completed" for a in agents):
                break
            time.sleep(0.05)
        assert all(TaskStore(project, a).list()[0]["status"] == "completed" for a in agents)
        assert len({session_name(project, a) for a in agents}) == 2
        for agent in agents:
            assert (
                json.loads((file_project / "backend" / agent.deliverables[0].path).read_text())["summary"] == agent.id
            )
    finally:
        for agent in agents:
            stop_session(project, agent)
