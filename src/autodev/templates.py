"""Generate the only file a managed repository needs to add."""

from __future__ import annotations

import json
from dataclasses import dataclass

from autodev.config import SCHEMA_VERSION


@dataclass(frozen=True)
class DescriptorAgent:
    id: str
    provider: str
    purpose: str
    goal: str
    write_roots: tuple[str, ...]
    read_roots: tuple[str, ...] = ()
    pod: str | None = None


@dataclass(frozen=True)
class DescriptorRole:
    id: str
    shape: str
    charter: str


@dataclass(frozen=True)
class DescriptorLoop:
    sequence: tuple[str, ...]
    reenter_product_manager_when: tuple[str, ...] = ()
    max_concurrent: int = 4


@dataclass(frozen=True)
class DescriptorPodMember:
    role: str
    provider: str
    model: str | None = None
    effort: str | None = None


@dataclass(frozen=True)
class DescriptorPods:
    members: tuple[DescriptorPodMember, ...]


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _toml_array(values: tuple[str, ...]) -> str:
    return "[" + ", ".join(_toml_string(value) for value in values) + "]"


def render_full_descriptor(
    *,
    project_id: str,
    name: str,
    base_branch: str,
    instructions: str,
    context_roots: tuple[str, ...],
    verify_commands: tuple[str, ...],
    session_pattern: str,
    ui_port: int,
    bypass_permissions: bool,
    agents: tuple[DescriptorAgent, ...],
    provider_settings: dict[str, dict[str, str | None]] | None = None,
    loop: DescriptorLoop | None = None,
    roles: tuple[DescriptorRole, ...] = (),
    pods: DescriptorPods | None = None,
) -> str:
    lines = [
        f"schema_version = {SCHEMA_VERSION}",
        "",
        "[project]",
        f"id = {_toml_string(project_id)}",
        f"name = {_toml_string(name)}",
        f"base_branch = {_toml_string(base_branch)}",
        f"instructions = {_toml_string(instructions)}",
        f"context_roots = {_toml_array(context_roots)}",
        f"verify_commands = {_toml_array(verify_commands)}",
        "",
        "[runtime]",
        f"session_pattern = {_toml_string(session_pattern)}",
        f"ui_port = {ui_port}",
        f"bypass_permissions = {'true' if bypass_permissions else 'false'}",
    ]
    if loop is not None:
        lines.extend(
            [
                "",
                "[loop]",
                f"sequence = {_toml_array(loop.sequence)}",
                f"reenter_product_manager_when = {_toml_array(loop.reenter_product_manager_when)}",
                f"max_concurrent = {loop.max_concurrent}",
            ]
        )
    for role in roles:
        lines.extend(
            [
                "",
                f"[roles.{role.id}]",
                f"shape = {_toml_string(role.shape)}",
                f"charter = {_toml_string(role.charter)}",
            ]
        )
    if pods is not None:
        lines.extend(["", "[pods]"])
        for member in pods.members:
            lines.extend(["", f"[pods.members.{member.role}]", f"provider = {_toml_string(member.provider)}"])
            if member.model:
                lines.append(f"model = {_toml_string(member.model)}")
            if member.effort:
                lines.append(f"effort = {_toml_string(member.effort)}")
    for provider in sorted(provider_settings or {}):
        settings = provider_settings[provider]
        if not any(settings.values()):
            continue
        lines.extend(["", f"[providers.{provider}]"])
        for key in ("command", "model", "effort"):
            value = settings.get(key)
            if value:
                lines.append(f"{key} = {_toml_string(value)}")
    for agent in agents:
        lines.extend(
            [
                "",
                "[[agents]]",
                f"id = {_toml_string(agent.id)}",
                f"provider = {_toml_string(agent.provider)}",
            ]
        )
        if agent.pod is not None:
            lines.append(f"pod = {_toml_string(agent.pod)}")
        lines.extend(
            [
                f"purpose = {_toml_string(agent.purpose)}",
                f"goal = {_toml_string(agent.goal)}",
                f"write_roots = {_toml_array(agent.write_roots)}",
                f"read_roots = {_toml_array(agent.read_roots)}",
            ]
        )
    return "\n".join(lines) + "\n"


# --- K4: the default company scaffold ----------------------------------------

_COMPANY_ROLES = (
    DescriptorRole(
        id="product-manager",
        shape="research",
        charter=(
            "Own the Pillar tier. Bootstrap pillars from product.json; expand an approved pillar into "
            "proposed Features. Everything you emit is proposed until the operator approves."
        ),
    ),
    DescriptorRole(
        id="project-manager",
        shape="reconcile",
        charter=(
            "Own the Feature shape and the backlog. Split into contract-anchored leaves + depends_on edges; "
            "never approve a leaf whose gate needs another pod's unmerged work; clean proven-done leaves "
            "after validation."
        ),
    ),
    DescriptorRole(
        id="engineering",
        shape="contract-first",
        charter=(
            "Own the Task/leaf. Interfaces + RED tests before internals; implement your slice only; verify "
            "green; commit per unit."
        ),
    ),
    DescriptorRole(
        id="technical-writer",
        shape="document",
        charter=(
            "Own the pillar docs. Run only after every leaf verifies. Produce a condensed, data-flow-first "
            "README + TECHNICAL map stamped to the verified sha. Never edit source."
        ),
    ),
)

_COMPANY_PODS = DescriptorPods(
    members=(
        DescriptorPodMember(role="product-manager", provider="claude"),
        DescriptorPodMember(role="project-manager", provider="claude"),
        DescriptorPodMember(role="engineering", provider="claude"),
        DescriptorPodMember(role="technical-writer", provider="claude"),
    )
)


def default_company_descriptor(*, project_id: str = "acme", name: str = "Acme") -> str:
    """Emit the schema-3 company scaffold: four roles, the feature loop, and a full
    pod template with no static ``[[agents]]`` (pods are derived per pillar)."""
    return render_full_descriptor(
        project_id=project_id,
        name=name,
        base_branch="main",
        instructions=(
            "One canonical path, fail fast, uv for Python. The product tree is authored only through autodev verbs."
        ),
        context_roots=("contracts/", "product/product.json"),
        verify_commands=("uv run pytest",),
        session_pattern="autodev-{project}-{agent}",
        ui_port=8765,
        bypass_permissions=True,
        agents=(),
        loop=DescriptorLoop(
            sequence=("project-manager", "engineering", "project-manager"),
            reenter_product_manager_when=("new-requirement", "queues-exhausted", "roadmap-contradiction"),
            max_concurrent=4,
        ),
        roles=_COMPANY_ROLES,
        pods=_COMPANY_PODS,
    )


def default_product_json(vision: str) -> str:
    """Emit the cold-start ``product/product.json`` vision seed."""
    return json.dumps({"vision": vision, "constraints": []}, indent=2) + "\n"
