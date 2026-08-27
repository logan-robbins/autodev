"""Materialise the pod template over the pillars that exist.

A ``[pods]`` template declares the *team shape* (which roles a pillar gets, each
bound to a provider). The effective agent set is **derived** from that template
crossed with the ``pillar.json`` files on disk — the descriptor is never mutated
(rejected alternative: writing ``[[agents]]`` back into ``autodev.toml``). As a
pillar appears in the git-reviewed tree, its pod appears in the runtime.

This module is a pure function of ``(descriptor template, pillars on disk)`` — it
never launches anything, so it replays and tests with a fake tree. The write-root
partition (C-P5) is verified disjoint by reusing ``config._validate_ownership``.
"""

from __future__ import annotations

import json

from autodev import product
from autodev.config import _ID_RE, AgentConfig, ProjectConfig, _validate_ownership

# role -> the short prefix used in a stamped pod agent id.
_ABBREV = {
    "product-manager": "pm",
    "project-manager": "pjm",
    "engineering": "eng",
    "technical-writer": "tw",
}

# Derived per-role purpose/goal for a stamped agent ({pillar} filled in).
_PURPOSE = {
    "product-manager": "Own the {pillar} pillar's intent: its pillar.json and its Features while proposed.",
    "project-manager": "Own the {pillar} pillar's Feature backlog: leaf decomposition and depends_on edges.",
    "engineering": "Own the {pillar} pillar's Tasks: contract, tests, and implementation under src/impl/{pillar}.",
    "technical-writer": "Own the {pillar} pillar's docs: README.md and TECHNICAL.md, produced last.",
}
_GOAL = {
    "product-manager": "Expand the approved {pillar} pillar into proposed Features via autodev product verbs.",
    "project-manager": "Split each approved {pillar} Feature into contract-anchored leaves; clean proven-done leaves.",
    "engineering": "Take one executable {pillar} leaf and complete a verified contract-first slice.",
    "technical-writer": "Document the shipped {pillar} pillar, data-flow-first, stamped to the verified sha.",
}

_BOOTSTRAP_PURPOSE = "Bootstrap the product: turn product.json's vision into the first proposed pillars."
_BOOTSTRAP_GOAL = (
    "When the tree has no pillars, create the first ones from the product vision via `autodev product add-pillars`."
)


class PodError(ValueError):
    """Raised when the pod template cannot be materialised over the pillars."""


def pod_agent_id(role: str, pillar: str | None) -> str:
    """Return the stamped agent id: ``pm`` (product-level) or ``<abbrev>-<pillar>``."""
    abbrev = _ABBREV.get(role)
    if abbrev is None:
        raise PodError(f"role {role!r} has no pod abbreviation")
    return abbrev if pillar is None else f"{abbrev}-{pillar}"


def _pod_roots(role: str, pillar: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The (write_roots, read_roots) partition for one pillar-scoped role (C-P5)."""
    if role == "product-manager":
        return (), (f"product/pillars/{pillar}/",)
    if role == "project-manager":
        return (), (f"product/pillars/{pillar}/features/", "contracts/")
    if role == "engineering":
        return (f"src/impl/{pillar}/", f"tests/{pillar}/"), ("contracts/", f"product/pillars/{pillar}/features/")
    if role == "technical-writer":
        return (
            (f"product/pillars/{pillar}/README.md", f"product/pillars/{pillar}/TECHNICAL.md"),
            (f"src/impl/{pillar}/", f"product/pillars/{pillar}/"),
        )
    raise PodError(f"no write/read-root partition defined for role {role!r}")


def _stamped_id(role: str, pillar: str) -> str:
    agent_id = pod_agent_id(role, pillar)
    if not _ID_RE.fullmatch(agent_id):
        raise PodError(f"stamped pod id {agent_id!r} exceeds the {_ID_RE.pattern!r} id form")
    return agent_id


def _pillar_ids(project: ProjectConfig) -> list[str]:
    root = product.product_root(project)
    if not root.exists():
        return []
    ids: list[str] = []
    for path in sorted(root.glob("*/pillar.json")):
        pillar = product.validate_pillar(json.loads(path.read_text(encoding="utf-8")))
        ids.append(pillar["id"])
    return ids


def materialize(project: ProjectConfig) -> tuple[AgentConfig, ...]:
    """Static ``[[agents]]`` ∪ the product-level ``pm`` ∪ one pod per pillar.

    Deterministic given the descriptor and the pillars on disk. Reuses
    ``_validate_ownership`` on the union so any accidental write-root overlap
    (within a pod or across pillars) still fails fast.
    """
    agents: list[AgentConfig] = list(project.agents)
    template = project.pods
    if template is None:
        return tuple(agents)

    bootstrap = template.members.get("product-manager")
    if bootstrap is not None:
        agents.append(
            AgentConfig(
                id="pm",
                provider=bootstrap.provider,
                purpose=_BOOTSTRAP_PURPOSE,
                goal=_BOOTSTRAP_GOAL,
                write_roots=(),
                read_roots=("product/",),
                pod=None,
            )
        )

    for pillar in _pillar_ids(project):
        for role, member in template.members.items():
            write_roots, read_roots = _pod_roots(role, pillar)
            agents.append(
                AgentConfig(
                    id=_stamped_id(role, pillar),
                    provider=member.provider,
                    purpose=_PURPOSE[role].format(pillar=pillar),
                    goal=_GOAL[role].format(pillar=pillar),
                    write_roots=write_roots,
                    read_roots=read_roots,
                    pod=pillar,
                )
            )

    result = tuple(agents)
    _validate_ownership(result)
    return result


def select_member(project: ProjectConfig, role: str, pillar: str | None) -> str:
    """The deterministic agent id the orchestrator schedules for (role, pillar)."""
    template = project.pods
    if template is None or role not in template.members:
        raise PodError(f"no pod member configured for role {role!r}")
    return pod_agent_id(role, pillar)
