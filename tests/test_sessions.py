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


@pytest.mark.skipif(shutil.which("tmux") is None, reason="tmux is required")
def test_long_initial_prompt_is_transported_literally(file_project, tmp_path, monkeypatch):
    import json
    import sys
    import time

    target = tmp_path / "received.json"
    marker = tmp_path / "must-not-exist"
    prompt = ("Long research context: αβ\n" * 3000) + f"'$(touch {marker})`touch {marker}`"
    fake = tmp_path / "fake-long-prompt"
    fake.write_text(
        f"#!{sys.executable}\nimport sys,json,time\nfrom pathlib import Path\n"
        f"Path({str(target)!r}).write_text(json.dumps(sys.argv[-1]))\ntime.sleep(30)\n"
    )
    fake.chmod(0o755)
    descriptor = file_project / "autodev.toml"
    descriptor.write_text(descriptor.read_text() + f"\n[providers.codex]\ncommand = {json.dumps(str(fake))}\n")
    project = load_project(file_project)
    agent = project.agent("backend--worker")
    workspace = ensure_workspace(project, agent)
    monkeypatch.setattr("autodev.sessions.render_goal", lambda *args: prompt)
    try:
        start_session(project, agent, workspace, send_initial_goal=True)
        deadline = time.monotonic() + 5
        while not target.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert json.loads(target.read_text()) == prompt
        assert not marker.exists()
    finally:
        stop_session(project, agent)


def test_long_follow_up_uses_a_temporary_buffer(file_project, monkeypatch):
    from autodev.sessions import send_goal

    project = load_project(file_project)
    agent = project.agent("backend--worker")
    prompt = "A bounded research question\n" * 3000
    calls, transferred, temporary = [], [], []
    monkeypatch.setattr("autodev.sessions.session_exists", lambda *args: True)
    monkeypatch.setattr("autodev.sessions.render_goal", lambda *args: prompt)

    def tmux(*args):
        calls.append(args)
        if args[0] == "load-buffer":
            temporary.append(Path(args[-1]))
            transferred.append(temporary[-1].read_text())

    monkeypatch.setattr("autodev.sessions._tmux", tmux)
    assert send_goal(project, agent) == prompt
    assert transferred == [prompt]
    assert [c[0] for c in calls] == ["load-buffer", "paste-buffer", "delete-buffer", "send-keys"]
    assert all(len(arg) < 1000 for call in calls for arg in call)
    assert not temporary[0].exists()


@pytest.mark.skipif(shutil.which("tmux") is None, reason="tmux is required")
@pytest.mark.parametrize("profile_fixture", ["file_project", "project_repo"])
@pytest.mark.parametrize("provider", ["codex", "claude"])
def test_every_native_launch_has_individual_identity_without_task_prompt(request, profile_fixture, provider, tmp_path):
    import json
    import sys
    import time

    from autodev.workspaces import changed_paths

    root = request.getfixturevalue(profile_fixture)
    received = tmp_path / "received"
    received.mkdir()
    fake = tmp_path / "fake-identity-harness"
    fake.write_text(f"""#!{sys.executable}
import json, os, sys, time
from pathlib import Path
identity = Path(os.environ['AUTODEV_IDENTITY_FILE'])
Path({str(received)!r}, os.environ['AUTODEV_AGENT_ID'] + '.json').write_text(json.dumps({{
    'argv': sys.argv[1:], 'identity': identity.read_text(), 'path': str(identity),
    'cwd': str(Path.cwd()),
}}))
time.sleep(30)
""")
    fake.chmod(0o755)
    descriptor = root / "autodev.toml"
    descriptor.write_text(descriptor.read_text() + f"\n[providers.{provider}]\ncommand = {json.dumps(str(fake))}\n")
    for pillar in ("backend", "frontend"):
        path = root / pillar / "pillar.toml"
        path.write_text(path.read_text().replace('provider = "codex"', f'provider = "{provider}"'))
    if profile_fixture == "project_repo":
        subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Configure fake harness"], cwd=root, check=True, capture_output=True)
    project = load_project(root)
    identities = []
    try:
        for agent in project.agents:
            workspace = ensure_workspace(project, agent)
            assert start_session(project, agent, workspace, send_initial_goal=False)
            result = received / f"{agent.id}.json"
            deadline = time.monotonic() + 5
            while not result.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            observed = json.loads(result.read_text())
            text = observed["identity"]
            assert f"You are `{agent.id}`" in text
            assert agent.instructions in text
            assert f"{agent.pillar}/{agent.deliverables[0].path}" in text
            assert "Read your tasks:" not in text  # no transient startup task preview
            assert observed["cwd"] == str(workspace.path)
            if provider == "codex":
                injected = next(a for a in observed["argv"] if a.startswith("developer_instructions="))
                assert json.loads(injected.split("=", 1)[1]) == text
            else:
                assert observed["argv"][observed["argv"].index("--append-system-prompt") + 1] == text
            assert not Path(observed["path"]).is_relative_to(workspace.path)
            assert changed_paths(workspace) == ()
            stop_session(project, agent)
            assert Path(observed["path"]).read_text() == text
            identities.append(text)
        assert len(set(identities)) == len(project.agents)
    finally:
        for agent in project.agents:
            stop_session(project, agent)
