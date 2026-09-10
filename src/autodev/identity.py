"""Individual standing identity, separate from compactable task conversation."""

import shlex
from pathlib import Path

from autodev.config import AgentConfig, ProjectConfig
from autodev.state import project_paths


def identity_text(project: ProjectConfig, agent: AgentConfig) -> str:
    command = shlex.join(["uv", "run", "--project", str(Path(__file__).resolve().parents[2]), "autodev"])
    skill = Path(__file__).parent / "skills/autodev-gm/SKILL.md"
    outputs = "\n".join(
        f"- {agent.pillar}/{item.path}: {item.format}; schema={item.schema or 'none'}; {item.description}"
        for item in agent.deliverables
    )
    return f"""\n\n<!-- AUTODEV HARNESS IDENTITY -->
# Your Autodev Harness Agent identity

You are `{agent.id}`, a native {agent.provider} Harness Agent in the `{agent.pillar}` Pillar.
Role: {agent.role}. Purpose: {agent.purpose}
Standing goal: {agent.goal}
Canonical project: `{project.descriptor}`.
Your individual template is `{agent.template}`, selected by your entry in
`{project.root / agent.pillar / "pillar.toml"}`. That authored contract remains the
source of truth; reload it at startup, after compaction and when recovering work.
Use your session's AUTODEV_AGENT_ID and AUTODEV_PROJECT_DESCRIPTOR bindings;
do not change actor, claim another identity or infer it from a stale message.
Your write roots: {", ".join(agent.write_roots)}.
Your read context: {", ".join((*project.context_roots, *agent.read_roots)) or "none"}.
Your canonical task ledger: `{project.root / agent.pillar / "tasks" / agent.local_id / "ledger.json"}`.

## Your individually authored instructions

{agent.instructions}

## Your required deliverables

{outputs}

## Recover your work

Native command prefix: `{command}`.
After compaction, recover your own current task/progress and the declared notes
in your individual template. Preserve original dates in remembered findings.
Do not restart completed research or treat a prior observation as current.
{"Read the GM skill at `" + str(skill) + "`. You coordinate only this Pod; the user-facing GM chat is available through native chat commands. Your individually authored prompt defines the domain and decision boundaries." if agent.role == "project-manager" else "You execute your own assignments and read only your own ledger. A Project Manager, if assigned, coordinates this Pod. You do not receive GM chat or employee-configuration authority."}
<!-- END AUTODEV HARNESS IDENTITY -->
"""


def save_session_identity(project: ProjectConfig, agent: AgentConfig) -> Path:
    """Keep launch identity outside both Git and filesystem publication roots."""
    folder = project_paths(project.id).home / "identities" / agent.id
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = folder / "AGENTS.md"
    path.write_text(identity_text(project, agent), encoding="utf-8")
    path.chmod(0o600)
    return path


def write_identity(project: ProjectConfig, agent: AgentConfig, target: Path) -> None:
    # Source files are copied first. The generated identity is protected by the
    # filesystem snapshot; it is never part of a worker's owned publication.
    for name in ("AGENTS.md", "CLAUDE.md", "AGENTS.override.md"):
        source = project.root / name
        if name == "AGENTS.override.md" and not source.exists():
            continue
        original = source.read_text(encoding="utf-8") if source.exists() else ""
        (target / name).write_text(identity_text(project, agent) + "\n" + original, encoding="utf-8")
