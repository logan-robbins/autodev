"""Import the Project Manager template's plan into its Pod's individual ledgers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from autodev.config import AgentConfig, ConfigError, ProjectConfig
from autodev.contracts import load_schema, read_json, validate_value
from autodev.pillars import TEMPLATE_ROOT
from autodev.storage import locked
from autodev.tasks import TaskStore


def import_plan(project: ProjectConfig, actor: AgentConfig, path: Path) -> list[dict[str, Any]]:
    store = TaskStore(project, actor)
    if not store.manager:
        raise ConfigError("only a Project Manager Harness Agent can import a Pod task plan")
    plan = read_json(path)
    validate_value(plan, load_schema(TEMPLATE_ROOT / "schemas/task-plan.schema.json"), "task plan")
    if plan["status"] != "planned" or not plan["tasks"]:
        raise ConfigError("only a planned, nonempty task plan can be imported")
    by_key = {}
    for entry in plan["tasks"]:
        key = entry["key"]
        if key in by_key:
            raise ConfigError(f"duplicate task key: {key}")
        target = project.agent(entry["agent"])
        store._check_access(target, manage=True)
        by_key[key] = entry
    ordered, visiting, visited = [], set(), set()

    def visit(key):
        if key not in by_key:
            raise ConfigError(f"unknown dependency key: {key}")
        if key in visiting:
            raise ConfigError(f"task dependency cycle at {key}")
        if key in visited:
            return
        visiting.add(key)
        for dependency in by_key[key]["dependencies"]:
            visit(dependency)
        visiting.remove(key)
        visited.add(key)
        ordered.append(key)

    for key in by_key:
        visit(key)
    digest = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    with locked(store.lock):
        ledgers = store._all()
        existing = [t for tasks in ledgers.values() for t in tasks if t.get("plan_digest") == digest]
        if existing:
            return existing
        records = {}
        for key in ordered:
            entry = by_key[key]
            agent = project.agent(entry["agent"])
            task = store._new(
                agent,
                entry["title"],
                entry["instructions"],
                tuple(records[d]["id"] for d in entry["dependencies"]),
                tuple(entry["acceptance"]),
            )
            task.update(plan_digest=digest, plan_key=key)
            ledgers[agent.id].append(task)
            records[key] = task
        store._commit(ledgers)
        return list(records.values())
