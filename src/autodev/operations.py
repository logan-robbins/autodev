"""Shared operations used by the CLI and local control-plane API."""

from __future__ import annotations

from autodev.config import AgentConfig, ConfigError, ProjectConfig
from autodev.pods import materialize
from autodev.sessions import (
    AgentStatus,
    agent_status,
    send_goal,
    start_session,
    stop_session,
)
from autodev.workspaces import ensure_workspace


def select_agents(project: ProjectConfig, ids: list[str] | tuple[str, ...]) -> tuple[AgentConfig, ...]:
    """Resolve agent ids against the one derived roster (``pods.materialize``).

    The effective worker set is a pure function of the pillars on disk, so
    ``ensure``/``status``/the UI all see exactly what the loop launches — never a
    stale static ``[[agents]]`` list. Launching stays the loop's job
    (``orchestrate``), where the ``max_concurrent`` cap lives.
    """
    roster = materialize(project)
    if not ids:
        return roster
    known_ids = {agent.id for agent in roster}
    unknown = sorted(set(ids) - known_ids)
    if unknown:
        known = ", ".join(agent.id for agent in roster) or "(none materialized yet)"
        raise ConfigError(f"unknown agent(s): {', '.join(unknown)}; available agents: {known}")
    requested = set(ids)
    return tuple(agent for agent in roster if agent.id in requested)


def ensure_agents(
    project: ProjectConfig,
    agents: tuple[AgentConfig, ...],
    *,
    base_ref: str | None,
    start: bool,
    send_initial_goal: bool,
) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for agent in agents:
        workspace = ensure_workspace(project, agent, base_ref=base_ref)
        started = False
        goal_sent = False
        if start:
            started = start_session(
                project,
                agent,
                workspace,
                send_initial_goal=send_initial_goal,
            )
            if send_initial_goal:
                if started:
                    goal_sent = True
                else:
                    send_goal(project, agent)
                    goal_sent = True
        results.append(
            {
                "agent": agent.id,
                "worktree": str(workspace.path),
                "branch": workspace.branch,
                "session_started": started,
                "goal_sent": goal_sent,
            }
        )
    return results


def statuses(project: ProjectConfig, agents: tuple[AgentConfig, ...]) -> list[AgentStatus]:
    return [agent_status(project, agent) for agent in agents]


def stop_agents(project: ProjectConfig, agents: tuple[AgentConfig, ...]) -> list[dict[str, object]]:
    return [{"agent": agent.id, "stopped": stop_session(project, agent)} for agent in agents]
