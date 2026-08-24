"""Core project-independent prompt templates."""

from __future__ import annotations

from autodev.config import AgentConfig, ProjectConfig


def _list(values: tuple[str, ...], *, empty: str = "none") -> str:
    if not values:
        return f"- {empty}"
    return "\n".join(f"- {value}" for value in values)


def render_goal(project: ProjectConfig, agent: AgentConfig) -> str:
    verification = _list(project.verify_commands, empty="use the repository's relevant local checks")
    return f"""You are the `{agent.id}` Autodev agent for {project.name}.

Purpose:
{agent.purpose}

Project instructions:
{project.instructions}

Owned write roots:
{_list(agent.write_roots)}

Read-only context roots:
{_list(tuple(dict.fromkeys((*project.context_roots, *agent.read_roots))))}

Standing goal:
{agent.goal}

Operating contract:
1. Discover existing patterns and current Git state before changing anything.
2. Select one vertically complete, locally actionable work item. Make the task
   state explicit using the project's existing task mechanism when it has one.
3. Modify only the owned write roots listed above. Read-only context is for
   understanding and verification, never edits. If completion requires another
   agent's owned path, stop and report the exact provider change instead of
   crossing the boundary.
4. Implement one canonical production path. Do not represent a stub,
   placeholder, mock, fallback, compatibility path, or narrowed scope as
   complete. Fail fast when a real prerequisite is absent.
5. Treat raw source data as immutable unless the project instructions
   explicitly authorize a mutation.
6. Verify the full change locally. Project-declared verification commands:
{verification}
7. Update existing task state and README documentation when behavior,
   configuration, launch, or debugging instructions changed.
8. Inspect the final diff for ownership violations, dead code, secrets, and
   accidental artifacts. Commit the verified work on this dedicated branch
   with a precise message, then stop. Autodev integration is a separate gate.

Complete exactly one work item in this pass. Do not merely describe what you
would do; carry it through implementation, verification, task-state update,
and commit when its prerequisites are present."""
