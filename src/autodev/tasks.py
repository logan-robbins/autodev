"""Per-Harness-Agent task ledgers, maintained within one Pillar's Pod.

Workers can read and update their own ledger. A Project Manager template can
read and tend the ledgers of its own Pod. Runtime dependency checks do not
expose other workers' task contents to a worker.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from autodev.config import AgentConfig, ConfigError, ProjectConfig, _nonempty_string
from autodev.contracts import read_json, verify_agent
from autodev.pillars import agent_template, local_path
from autodev.state import project_paths
from autodev.storage import atomic_json, locked
from autodev.workspaces import Workspace, file_manifest, ownership_violations, workspace_branch, workspace_path


def contract_digest(project: ProjectConfig, agent: AgentConfig) -> str:
    pillar = project.pillar(agent.pillar)
    files = {project.descriptor, pillar.descriptor}
    for spec in (*pillar.inputs, *pillar.outputs, *agent.deliverables):
        if spec.schema:
            files.add(local_path(pillar.root, spec.schema))
    for dependency in pillar.dependencies:
        files.add(project.pillar(dependency).descriptor)
    payload = {str(path.relative_to(project.root)): path.read_text(encoding="utf-8") for path in sorted(files)}
    payload["@template"] = agent_template(agent.template, pillar.root)
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def record_event(task: dict[str, Any], stage: str, message: str) -> None:
    now = datetime.now(UTC).isoformat()
    task.update(stage=stage, updated_at=now, progress=message)
    task["events"] = [*task.get("events", []), {"at": now, "stage": stage, "message": message}][-100:]


def is_manager(project: ProjectConfig, agent: AgentConfig) -> bool:
    return agent.role == "project-manager"


class TaskStore:
    def __init__(self, project: ProjectConfig, actor: AgentConfig) -> None:
        self.project = project
        self.actor = project.agent(actor.id)
        self.pod = project.pillar(actor.pillar)
        self.manager = is_manager(project, actor)
        self.runtime = project_paths(project.id).home / "ledgers" / actor.pillar
        self.lock = self.runtime / ".lock"
        self.journal = self.runtime / "transaction.json"

    def _path(self, agent: AgentConfig) -> Path:
        return local_path(self.project.root, f"{agent.pillar}/tasks/{agent.local_id}/ledger.json", "task ledger")

    def _check_access(self, agent: AgentConfig, *, manage: bool = False) -> None:
        if agent.pillar != self.actor.pillar or (agent.id != self.actor.id and not self.manager):
            raise ConfigError("only the Project Manager Harness Agent may access other ledgers within its own Pod")
        if manage and not self.manager and any(is_manager(self.project, a) for a in self.pod.agents):
            raise ConfigError(
                "this Pod's Project Manager tends task assignments; workers update their own task progress"
            )

    def _recover(self) -> None:
        if self.journal.exists():
            for identity, tasks in read_json(self.journal).items():
                target = self.project.agent(identity)
                if target.pillar != self.actor.pillar:
                    raise ConfigError("ledger transaction crosses a Pillar boundary")
                atomic_json(self._path(target), {"schema_version": 1, "agent": identity, "tasks": tasks})
            self.journal.unlink()

    def _read(self, agent: AgentConfig) -> list[dict[str, Any]]:
        path = self._path(agent)
        if not path.exists():
            return []
        data = read_json(path)
        if (
            not isinstance(data, dict)
            or data.get("schema_version") != 1
            or data.get("agent") != agent.id
            or not isinstance(data.get("tasks"), list)
        ):
            raise ConfigError(f"invalid task ledger: {path}")
        seen = set()
        for task in data["tasks"]:
            if (
                not isinstance(task, dict)
                or any(
                    not isinstance(task.get(key), str) or not task[key]
                    for key in ("id", "title", "contract_digest", "created_at")
                )
                or task.get("agent") != agent.id
                or task.get("pillar") != agent.pillar
                or not isinstance(task.get("status"), str)
                or task["status"] not in {"queued", "running", "completed", "blocked"}
                or not isinstance(task.get("instructions"), str)
                or any(
                    not isinstance(task.get(key), list)
                    or any(not isinstance(value, str) or not value for value in task[key])
                    for key in ("acceptance", "dependencies")
                )
                or not task["acceptance"]
                or task["id"] in seen
            ):
                raise ConfigError(f"invalid task record in ledger: {path}")
            seen.add(task["id"])
        return data["tasks"]

    def _all(self) -> dict[str, list[dict[str, Any]]]:
        self._recover()
        return {agent.id: self._read(agent) for agent in self.pod.agents}

    def _commit(self, ledgers: dict[str, list[dict[str, Any]]]) -> None:
        if self.project.execution == "git":
            with locked(project_paths(self.project.id).home / "git-excludes.lock"):
                result = subprocess.run(
                    ["git", "rev-parse", "--git-path", "info/exclude"],
                    cwd=self.project.root,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                exclude = Path(result.stdout.strip())
                if not exclude.is_absolute():
                    exclude = self.project.root / exclude
                exclude.parent.mkdir(parents=True, exist_ok=True)
                text = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
                pattern = f"/{self.actor.pillar}/tasks/"
                if pattern not in text.splitlines():
                    with exclude.open("a", encoding="utf-8") as stream:
                        stream.write(f"\n{pattern}\n")
        atomic_json(self.journal, ledgers)
        self._recover()

    def _find(self, identity: str, ledgers: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
        for tasks in ledgers.values():
            for task in tasks:
                if task["id"] == identity:
                    return task
        raise ConfigError(f"unknown task in this Pod: {identity}")

    def _visible(self, ledgers: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
        records = [
            task for identity, tasks in ledgers.items() for task in tasks if self.manager or identity == self.actor.id
        ]
        statuses = {task["id"]: task["status"] for tasks in ledgers.values() for task in tasks}
        return [
            dict(
                task,
                ready=task["status"] == "queued" and all(statuses.get(d) == "completed" for d in task["dependencies"]),
            )
            for task in records
        ]

    def list(self) -> list[dict[str, Any]]:
        with locked(self.lock):
            return self._visible(self._all())

    def get(self, identity: str) -> dict[str, Any]:
        for task in self.list():
            if task["id"] == identity:
                return task
        raise ConfigError("task is not in a ledger visible to this Harness Agent")

    def create(
        self,
        agent: AgentConfig,
        title: str,
        *,
        instructions: str = "",
        dependencies: tuple[str, ...] = (),
        acceptance: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        self._check_access(agent, manage=True)
        _nonempty_string(title, "task title")
        if not acceptance or any(not isinstance(item, str) or not item.strip() for item in acceptance):
            raise ConfigError("tasks require explicit acceptance criteria")
        with locked(self.lock):
            ledgers = self._all()
            for dependency in dependencies:
                dependency_task = self._find(dependency, ledgers)
                if not self.manager and dependency_task["agent"] != self.actor.id:
                    raise ConfigError("cross-agent dependencies are assigned by the Pod's Project Manager")
            task = self._new(agent, title, instructions, dependencies, acceptance)
            ledgers[agent.id].append(task)
            self._commit({agent.id: ledgers[agent.id]})
            return task

    def _new(
        self,
        agent: AgentConfig,
        title: str,
        instructions: str,
        dependencies: tuple[str, ...],
        acceptance: tuple[str, ...],
    ) -> dict[str, Any]:
        task = {
            "id": uuid.uuid4().hex,
            "agent": agent.id,
            "pillar": agent.pillar,
            "title": title,
            "instructions": instructions,
            "acceptance": list(acceptance),
            "dependencies": list(dependencies),
            "contract_digest": contract_digest(self.project, agent),
            "status": "queued",
            "created_at": datetime.now(UTC).isoformat(),
            "delivery": None,
        }
        record_event(task, "queued", "Assignment added to the agent's ledger.")
        return task

    def active(self) -> dict[str, Any] | None:
        return next((t for t in self.list() if t["agent"] == self.actor.id and t["status"] == "running"), None)

    def claim(self) -> dict[str, Any] | None:
        with locked(self.lock):
            ledgers = self._all()
            running = next((t for t in ledgers[self.actor.id] if t["status"] == "running"), None)
            if running:
                self._check_contract(running)
                return running
            ready = next((t for t in self._visible(ledgers) if t["agent"] == self.actor.id and t["ready"]), None)
            if not ready:
                return None
            task = self._find(ready["id"], ledgers)
            self._check_contract(task)
            task["status"] = "running"
            task["started_at"] = datetime.now(UTC).isoformat()
            record_event(task, "working", "Harness Agent claimed the task.")
            self._commit({self.actor.id: ledgers[self.actor.id]})
            return task

    def _check_contract(self, task: dict[str, Any]) -> None:
        if task["contract_digest"] != contract_digest(self.project, self.project.agent(task["agent"])):
            raise ConfigError(
                "task contract changed; have the ledger's maintainer revise the assignment before continuing"
            )

    def _progress(self, identity: str, stage: str, message: str) -> dict[str, Any]:
        with locked(self.lock):
            ledgers = self._all()
            task = self._find(identity, ledgers)
            if task["agent"] != self.actor.id or task["status"] != "running":
                raise ConfigError("a worker can report progress only for its own running task")
            record_event(task, stage, message)
            self._commit({self.actor.id: ledgers[self.actor.id]})
            return task

    def progress(self, identity: str, message: str) -> dict[str, Any]:
        _nonempty_string(message, "progress message")
        with locked(self.runtime / f"{self.actor.local_id}.execution.lock"):
            return self._progress(identity, "working", message)

    def complete(self, identity: str) -> dict[str, Any]:
        # Serialize this worker's completion/block operations, while leaving Pod
        # reads, assignments, and other workers' validation free to proceed.
        with locked(self.runtime / f"{self.actor.local_id}.execution.lock"):
            with locked(self.lock):
                ledgers = self._all()
                task = self._find(identity, ledgers)
                if task["agent"] != self.actor.id or task["status"] != "running":
                    raise ConfigError("a worker can complete only its own running task")
                self._check_contract(task)
            try:
                root = workspace_path(self.project, self.actor)
                workspace = Workspace(
                    root, workspace_branch(self.project, self.actor) if self.project.execution == "git" else ""
                )
                violations = ownership_violations(workspace, self.actor)
                if violations:
                    raise ConfigError(f"ownership violations: {', '.join(violations)}")
                before = file_manifest(root)
                self._progress(identity, "validating", "Checking deliverables and declared contracts.")
                artifacts = verify_agent(self.project, self.actor, root)
                if file_manifest(root) != before:
                    raise ConfigError("workspace changed during validation; complete again after it is stable")
                from autodev.integrate import integrate

                self._progress(
                    identity, "publishing", "Validating the combined workspace and publishing owned outputs."
                )
                integrate(self.project, self.actor)
            except Exception as exc:
                self._progress(identity, "working", f"Completion failed: {str(exc)[:1000]}")
                raise
            delivery = {
                "task": identity,
                "agent": self.actor.id,
                "contract_digest": task["contract_digest"],
                "artifacts": [
                    dict(a, path=str(self.project.root / Path(a["path"]).relative_to(root))) for a in artifacts
                ],
                "workspace_digest": hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest(),
                "verified_at": datetime.now(UTC).isoformat(),
            }
            with locked(self.lock):
                # Reload to preserve assignments added during validation.
                ledgers = self._all()
                task = self._find(identity, ledgers)
                self._check_contract(task)
                task.update(status="completed", delivery=delivery)
                record_event(task, "completed", "Outputs validated and published.")
                self._commit({self.actor.id: ledgers[self.actor.id]})
                return task

    def block(self, identity: str, reason: str) -> dict[str, Any]:
        _nonempty_string(reason, "blocked reason")
        with locked(self.runtime / f"{self.actor.local_id}.execution.lock"), locked(self.lock):
            ledgers = self._all()
            task = self._find(identity, ledgers)
            if task["agent"] != self.actor.id or task["status"] != "running":
                raise ConfigError("a worker can block only its own running task")
            task.update(status="blocked", reason=reason)
            record_event(task, "blocked", reason)
            self._commit({self.actor.id: ledgers[self.actor.id]})
            return task

    def revise(self, identity: str, *, instructions: str, acceptance: tuple[str, ...]) -> dict[str, Any]:
        if not acceptance or any(not item.strip() for item in acceptance):
            raise ConfigError("explicit acceptance criteria are required")
        with locked(self.lock):
            ledgers = self._all()
            task = self._find(identity, ledgers)
            agent = self.project.agent(task["agent"])
            self._check_access(agent, manage=True)
            if task["status"] not in {"queued", "blocked"}:
                raise ConfigError("only queued or blocked tasks may be revised")
            task.update(
                instructions=instructions,
                acceptance=list(acceptance),
                status="queued",
                contract_digest=contract_digest(self.project, agent),
            )
            task.pop("reason", None)
            record_event(task, "queued", "Assignment revised by its maintainer.")
            self._commit({agent.id: ledgers[agent.id]})
            return task
