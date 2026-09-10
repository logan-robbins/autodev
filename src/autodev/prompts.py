"""Role-scoped contracts for native harnesses that work from their own task ledgers."""

from __future__ import annotations

import json
import shlex
from pathlib import Path

from autodev.config import AgentConfig, ProjectConfig
from autodev.tasks import TaskStore


def render_goal(project: ProjectConfig, agent: AgentConfig) -> str:
    pillar = project.pillar(agent.pillar)
    store = TaskStore(project, agent)
    checkout = Path(__file__).resolve().parents[2]
    command = shlex.join(["uv", "run", "--project", str(checkout), "autodev"])
    selected = shlex.quote(str(project.descriptor))
    actor = shlex.quote(agent.id)
    outputs = "\n".join(
        f"- {pillar.slug}/{item.path}: {item.format}; schema={item.schema or 'none'}; {item.description}"
        for item in agent.deliverables
    )
    dependencies = (
        "\n".join(f"- {slug}/pillar.toml: {project.pillar(slug).summary}" for slug in pillar.dependencies) or "- none"
    )
    completion = (
        "Commit verified owned changes on this dedicated branch before completing the task."
        if project.execution == "git"
        else "Leave verified artifacts in this isolated workspace for publication by task complete."
    )
    role = (
        "You are this Pod's Project Manager Harness Agent. You may read and tend every Harness Agent ledger in this Pod. "
        "Use task create, task revise, or task import to assign work; use task dispatch to nudge ready workers. "
        "Workers own execution and update their own completion or blocked state. Do not complete their tasks. "
        "Other Pods' internal ledgers are outside your scope."
        if store.manager
        else "Read only your own task ledger. Your Pod's Project Manager, when assigned, tends your task assignments. "
        "You are responsible for reading your tasks, delivering the declared outputs, and updating your own task state."
    )
    if store.manager:
        role += (
            "\nAt startup and after compaction, read the GM skill: "
            + str(Path(__file__).parent / "skills/autodev-gm/SKILL.md")
            + ". Its runtime procedures supplement your individually configured template."
        )
    tasks = [t for t in store.list() if t["status"] != "completed"]
    # A small initial view; agents use ledger commands to retrieve additional tasks.
    preview = json.dumps(tasks[:8], ensure_ascii=False)
    return f"""You are Harness Agent `{agent.id}` instantiated from `{agent.template}` in the `{pillar.slug}` Pillar's single Pod.
Your full native coding harness supplies your tools and reasoning. You run in your own tmux session.

Project: {project.name}
Project instructions: {project.instructions}
Role: {agent.purpose}
Template instructions: {agent.instructions}
Standing goal: {agent.goal}
{role}

Pillar boundary: {pillar.slug}/pillar.toml
Summary: {pillar.summary}
Responsibility: {pillar.responsibility}
Interface state: {pillar.state}
Consumption: {pillar.consumption}
Constraints: {pillar.constraints}
Declared dependencies:
{dependencies}

Owned write roots:
{chr(10).join("- " + path for path in agent.write_roots)}
Additional read-only context:
{chr(10).join("- " + path for path in (*project.context_roots, *agent.read_roots)) or "- none"}
Required deterministic deliverables, relative to workspace root:
{outputs}

Your canonical ledger: {project.root / pillar.slug / "tasks" / agent.local_id / "ledger.json"}
Ledger view (first 8 unfinished tasks visible to your role, {len(tasks)} total):
{preview}

Worker loop:
1. Read your tasks: {command} task list {selected} --actor {actor}
2. Claim your next ready task: {command} task claim {selected} --actor {actor}
   Read its instructions and acceptance criteria. If no task is ready, report that you are idle or blocked; do not invent an assignment.
3. Discover the current workspace and public interfaces. Modify only the owned write roots. Treat raw source data as immutable unless your task explicitly authorizes changes.
4. Build and verify the interface first. Fixtures and unavailable responses support interface development; never present them as completed business functionality.
   Report meaningful work steps with: {command} task progress {selected} TASK_ID --actor {actor} --message "Current step and outcome"
5. Deliver the exact required artifacts and verify the task's acceptance criteria. {completion}
6. Update your ledger by running: {command} task complete {selected} TASK_ID --actor {actor}
   This validates and publishes your output, then records completion and delivery evidence in your ledger. A failed check leaves the task running for you to fix.
7. If blocked: {command} task block {selected} TASK_ID --actor {actor} --reason REASON
   Your Project Manager can read the reason and revise the task.
8. Read your ledger again and continue with the next ready task. {"Review your Pod's ledgers to coordinate assignments and dependencies." if store.manager else "Keep other workers' ledgers out of your context."}

Use ledger commands for atomic updates; never edit ledger storage directly. Contract and template files are maintained separately from task execution.
Memory implementation is deferred.
"""
