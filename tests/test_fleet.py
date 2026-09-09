from pathlib import Path
from unittest.mock import Mock

import pytest

from autodev.config import ConfigError, load_project
from autodev.fleet import FleetMonitor, fleet_snapshot
from autodev.sessions import session_name
from autodev.tasks import TaskStore


def assign(store, title):
    return store.create(store.actor, title, acceptance=("Publish a verified output.",))


def test_fleet_observes_pillar_workloads_and_agent_progress(file_project: Path, monkeypatch):
    project = load_project(file_project)
    backend = TaskStore(project, project.agent("backend--worker"))
    frontend = TaskStore(project, project.agent("frontend--worker"))
    one = assign(backend, "Build the backend interface")
    two = assign(frontend, "Implement the consumer")
    backend.claim()
    backend.progress(one["id"], "Implementing the response schema.")
    frontend.claim()
    frontend.block(two["id"], "Need source material.")
    monkeypatch.setattr(
        "autodev.fleet.session_snapshot", lambda: ({session_name(project, backend.actor): "codex"}, None)
    )
    snapshot = fleet_snapshot(project)
    assert snapshot["counts"] == {
        "total": 2,
        "open": 2,
        "running": 1,
        "blocked": 1,
        "completed": 0,
        "ready": 0,
        "waiting": 0,
        "pillars": 2,
        "agents": 2,
        "online": 1,
        "interrupted": 0,
    }
    assert snapshot["pillars"][0]["status"] == "active"
    assert snapshot["pillars"][1]["status"] == "attention"
    agent = snapshot["pillars"][0]["agents"][0]
    assert agent["status"] == "working" and agent["current_task"] == one["id"]
    assert any(e["message"] == "Implementing the response schema." for e in snapshot["events"])
    # Operator visibility doesn't widen the worker's task API.
    with pytest.raises(ConfigError, match="visible"):
        backend.get(two["id"])


def test_stopped_session_does_not_appear_as_active_execution(file_project: Path, monkeypatch):
    project = load_project(file_project)
    store = TaskStore(project, project.agents[0])
    assign(store, "Work interrupted")
    store.claim()
    monkeypatch.setattr("autodev.fleet.session_snapshot", lambda: ({}, None))
    snapshot = fleet_snapshot(project)
    assert snapshot["counts"]["interrupted"] == 1
    assert snapshot["pillars"][0]["agents"][0]["status"] == "interrupted"
    assert snapshot["pillars"][0]["status"] == "attention"


def test_unreadable_pod_does_not_hide_healthy_pods(file_project: Path, monkeypatch):
    project = load_project(file_project)
    for a in project.agents:
        assign(TaskStore(project, a), a.id)
    (file_project / "backend/tasks/worker/ledger.json").write_text("broken")
    monkeypatch.setattr("autodev.fleet.session_snapshot", lambda: ({}, None))
    snapshot = fleet_snapshot(project)
    assert snapshot["pillars"][0]["error"]
    assert snapshot["pillars"][0]["status"] == "unknown"
    assert snapshot["pillars"][1]["counts"]["open"] == 1
    assert snapshot["errors"]


def test_fifty_plus_agents_use_one_session_observation(file_project: Path, monkeypatch):
    path = file_project / "backend/pillar.toml"
    with path.open("a") as stream:
        for number in range(59):
            stream.write(f'\n[[agents]]\nid = "worker-{number}"\ntemplate = "engineer"\nprovider = "codex"\n')
    project = load_project(file_project)
    for a in project.agents:
        assign(TaskStore(project, a), f"Work for {a.id}")
    sessions = Mock(return_value=({session_name(project, a): "codex" for a in project.agents}, None))
    monkeypatch.setattr("autodev.fleet.session_snapshot", sessions)
    snapshot = fleet_snapshot(project)
    sessions.assert_called_once()
    assert snapshot["counts"]["agents"] == 61
    assert snapshot["counts"]["open"] == 61
    assert snapshot["pillars"][0]["counts"]["open"] == 60
    assert snapshot["counts"]["online"] == 61


def test_monitor_shares_snapshots_and_reloads_after_invalidation(file_project: Path, monkeypatch):
    project = load_project(file_project)
    observe = Mock(return_value={"value": 1})
    monkeypatch.setattr("autodev.fleet.fleet_snapshot", observe)
    monitor = FleetMonitor(project.descriptor, project.id)
    assert monitor.snapshot() == monitor.snapshot()
    assert observe.call_count == 1
    monitor.invalidate()
    monitor.snapshot()
    assert observe.call_count == 2


def test_agent_output_timeout_is_an_actionable_error(file_project: Path, monkeypatch):
    import subprocess

    from autodev.fleet import agent_output

    project = load_project(file_project)
    monkeypatch.setattr("autodev.fleet.shutil.which", lambda _: "/test/tmux")
    monkeypatch.setattr("autodev.fleet.subprocess.run", Mock(side_effect=subprocess.TimeoutExpired("tmux", 3)))
    with pytest.raises(ConfigError, match="Cannot read session output"):
        agent_output(project, project.agents[0].id)
