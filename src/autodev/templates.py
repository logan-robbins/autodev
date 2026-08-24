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
