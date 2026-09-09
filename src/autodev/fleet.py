"""Read-only operator telemetry across Pillars; never a worker task assignment API."""

from __future__ import annotations

import re
import shutil
import subprocess
import threading
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from autodev.config import ConfigError, ProjectConfig, load_project
from autodev.sessions import session_name
from autodev.state import project_paths
from autodev.storage import locked
from autodev.tasks import TaskStore


def session_snapshot() -> tuple[dict[str, str], str | None]:
    tmux = shutil.which("tmux")
    if not tmux:
        return {}, "tmux is unavailable; session state cannot be observed."
    try:
        result = subprocess.run(
            [tmux, "list-panes", "-a", "-F", "#{session_name}\t#{pane_current_command}"],
            text=True,
            capture_output=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {}, f"Session observation failed: {exc}"
    if result.returncode:
        if any(text in result.stderr for text in ("no server running", "No such file or directory")):
            return {}, None
        return {}, result.stderr.strip() or "Session observation failed."
    return dict(line.split("\t", 1) for line in result.stdout.splitlines() if "\t" in line), None


def task_counts(tasks: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(task["status"] for task in tasks)
    return {
        "total": len(tasks),
        "open": len(tasks) - counts["completed"],
        "running": counts["running"],
        "blocked": counts["blocked"],
        "completed": counts["completed"],
        "ready": sum(t["status"] == "queued" and t["ready"] for t in tasks),
        "waiting": sum(t["status"] == "queued" and not t["ready"] for t in tasks),
    }


def fleet_snapshot(project: ProjectConfig) -> dict[str, Any]:
    sessions, session_error = session_snapshot()
    pillars, events, errors = [], [], []
    if session_error:
        errors.append(session_error)
    for pillar in project.pillars:
        # Trusted human operator view. No Harness Agent gets this cross-Pod view
        # in its prompt or through its scoped ledger commands.
        store = TaskStore(project, pillar.agents[0])
        ledger_error = None
        try:
            with locked(store.lock):
                ledgers = store._all()
        except (ConfigError, OSError, RuntimeError) as exc:
            ledger_error = str(exc)
            errors.append(f"{pillar.slug}: {exc}")
            ledgers = {a.id: [] for a in pillar.agents}
        all_tasks = [t for tasks in ledgers.values() for t in tasks]
        states = {t["id"]: t["status"] for t in all_tasks}
        tasks = [
            dict(t, ready=t["status"] == "queued" and all(states.get(d) == "completed" for d in t["dependencies"]))
            for t in all_tasks
        ]
        agents = []
        for agent in pillar.agents:
            own = [t for t in tasks if t["agent"] == agent.id]
            current = next((t for t in own if t["status"] == "running"), None)
            name = session_name(project, agent)
            running = name in sessions
            counts = task_counts(own)
            status = (
                "unknown"
                if session_error or ledger_error
                else "interrupted"
                if current and not running
                else "working"
                if current
                else "blocked"
                if counts["blocked"]
                else "idle"
                if running
                else "offline"
            )
            agents.append(
                {
                    "id": agent.id,
                    "local_id": agent.local_id,
                    "pillar": pillar.slug,
                    "template": agent.template,
                    "role": agent.role,
                    "provider": agent.provider,
                    "purpose": agent.purpose,
                    "session": name,
                    "running": running,
                    "status": status,
                    "pane_command": sessions.get(name),
                    "counts": counts,
                    "current_task": current["id"] if current else None,
                    "write_roots": agent.write_roots,
                    "deliverables": [
                        {"id": d.id, "path": f"{pillar.slug}/{d.path}", "format": d.format} for d in agent.deliverables
                    ],
                }
            )
        counts = task_counts(tasks)
        online = sum(a["running"] for a in agents)
        interrupted = sum(a["status"] == "interrupted" for a in agents)
        status = (
            "unknown"
            if ledger_error or session_error
            else "attention"
            if counts["blocked"] or interrupted
            else "active"
            if counts["running"]
            else "ready"
            if counts["ready"]
            else "waiting"
            if counts["waiting"]
            else "idle"
            if online
            else "offline"
        )
        pillars.append(
            {
                "slug": pillar.slug,
                "summary": pillar.summary,
                "responsibility": pillar.responsibility,
                "consumption": pillar.consumption,
                "constraints": pillar.constraints,
                "interface_state": pillar.state,
                "dependencies": pillar.dependencies,
                "outputs": [
                    {"id": d.id, "path": d.path, "format": d.format, "description": d.description}
                    for d in pillar.outputs
                ],
                "status": status,
                "counts": counts,
                "online": online,
                "interrupted": interrupted,
                "agents": agents,
                "tasks": tasks,
                "error": ledger_error,
            }
        )
        for task in tasks:
            for event in task.get("events", []):
                events.append(
                    dict(event, task=task["id"], title=task["title"], agent=task["agent"], pillar=pillar.slug)
                )
    all_tasks = [task for p in pillars for task in p["tasks"]]
    counts = task_counts(all_tasks)
    counts.update(
        pillars=len(pillars),
        agents=len(project.agents),
        online=sum(p["online"] for p in pillars),
        interrupted=sum(p["interrupted"] for p in pillars),
    )
    return {
        "project": {"id": project.id, "name": project.name, "root": str(project.root), "execution": project.execution},
        "observed_at": datetime.now(UTC).isoformat(),
        "refresh_seconds": 2,
        "counts": counts,
        "pillars": pillars,
        "errors": errors,
        "events": sorted(events, key=lambda e: e["at"], reverse=True)[:100],
    }


class FleetMonitor:
    """Share a short-lived observation across browser clients without N×agent polls."""

    def __init__(self, descriptor: Path, identity: str) -> None:
        self.descriptor, self.identity = descriptor, identity
        self.lock = threading.Lock()
        self.updated = 0.0
        self.value: dict[str, Any] | None = None

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            if self.value is None or time.monotonic() - self.updated >= 1:
                project = load_project(self.descriptor)
                if project.id != self.identity:
                    raise ConfigError("running UI project identity changed")
                self.value = fleet_snapshot(project)
                self.updated = time.monotonic()
            return self.value

    def invalidate(self) -> None:
        with self.lock:
            self.updated = 0


def agent_output(project: ProjectConfig, identity: str) -> dict[str, str]:
    agent = project.agent(identity)
    text, source = "", "session"
    tmux = shutil.which("tmux")
    if tmux:
        try:
            result = subprocess.run(
                [tmux, "capture-pane", "-p", "-t", session_name(project, agent), "-S", "-120"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ConfigError(f"Cannot read session output: {exc}") from exc
        if result.returncode == 0:
            text = result.stdout[-24000:]
    if not text:
        source = "log"
        path = project_paths(project.id).logs / f"{agent.id}.log"
        if path.is_file():
            with path.open("rb") as stream:
                stream.seek(max(0, path.stat().st_size - 24000))
                text = stream.read(24000).decode("utf-8", errors="replace")
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    return {"agent": identity, "text": text, "source": source}
