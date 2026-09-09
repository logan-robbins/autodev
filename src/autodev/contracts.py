"""Executable artifact contracts and a strict, documented JSON Schema vocabulary.

Unsupported schema keywords fail validation; they are never silently ignored.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from autodev.config import AgentConfig, ArtifactSpec, ConfigError, PillarConfig, ProjectConfig

KEYWORDS = frozenset(
    {
        "type",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "enum",
        "const",
        "minLength",
        "maxLength",
        "minimum",
        "maximum",
        "minItems",
        "maxItems",
        "description",
        "title",
    }
)
TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "null": type(None),
}


def check_schema(schema: Any, label: str = "schema") -> None:
    if not isinstance(schema, dict):
        raise ConfigError(f"{label} must be an object")
    unknown = set(schema) - KEYWORDS
    if unknown:
        raise ConfigError(f"{label}: unsupported schema keywords: {', '.join(sorted(unknown))}")
    if not isinstance(schema.get("type"), str) or schema["type"] not in TYPES:
        raise ConfigError(f"{label}: an explicit supported type is required")
    for key in ("minLength", "maxLength", "minItems", "maxItems"):
        if key in schema and (type(schema[key]) is not int or schema[key] < 0):
            raise ConfigError(f"{label}.{key} must be a nonnegative integer")
    for key in ("minimum", "maximum"):
        if key in schema and type(schema[key]) not in (int, float):
            raise ConfigError(f"{label}.{key} must be numeric")
    if "enum" in schema and (not isinstance(schema["enum"], list) or not schema["enum"]):
        raise ConfigError(f"{label}.enum must be a nonempty list")
    if "required" in schema and (
        not isinstance(schema["required"], list) or any(not isinstance(x, str) for x in schema["required"])
    ):
        raise ConfigError(f"{label}.required must be a list of strings")
    if "additionalProperties" in schema and type(schema["additionalProperties"]) is not bool:
        raise ConfigError(f"{label}.additionalProperties must be boolean")
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        raise ConfigError(f"{label}.properties must be an object")
    for name, child in properties.items():
        check_schema(child, f"{label}.{name}")
    if "items" in schema:
        check_schema(schema["items"], f"{label}.items")


def read_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value))
        )
    except (OSError, ValueError) as exc:
        raise ConfigError(f"cannot read JSON {path}: {exc}") from exc


def load_schema(path: Path) -> dict[str, Any]:
    schema = read_json(path)
    check_schema(schema, str(path))
    return schema


def validate_value(value: Any, schema: dict[str, Any], label: str = "artifact") -> None:
    expected = schema["type"]
    valid = isinstance(value, TYPES[expected])
    if expected in {"integer", "number"} and isinstance(value, bool):
        valid = False
    if not valid:
        raise ConfigError(f"{label}: expected {expected}")
    if "enum" in schema and not any(type(value) is type(v) and value == v for v in schema["enum"]):
        raise ConfigError(f"{label}: value is outside enum")
    if "const" in schema and (type(value) is not type(schema["const"]) or value != schema["const"]):
        raise ConfigError(f"{label}: value does not match const")
    if isinstance(value, dict):
        missing = set(schema.get("required", [])) - set(value)
        if missing:
            raise ConfigError(f"{label}: missing required fields {sorted(missing)}")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False and set(value) - set(props):
            raise ConfigError(f"{label}: unexpected fields {sorted(set(value) - set(props))}")
        for key, child in value.items():
            if key in props:
                validate_value(child, props[key], f"{label}.{key}")
    if isinstance(value, list) and "items" in schema:
        for index, child in enumerate(value):
            validate_value(child, schema["items"], f"{label}[{index}]")
    for low, high, measured in (
        ("minLength", "maxLength", len(value) if isinstance(value, str) else None),
        ("minItems", "maxItems", len(value) if isinstance(value, list) else None),
        ("minimum", "maximum", value if type(value) in (int, float) else None),
    ):
        if measured is not None and (
            (low in schema and measured < schema[low]) or (high in schema and measured > schema[high])
        ):
            raise ConfigError(f"{label}: outside {low}/{high} bounds")


def verify_artifact(root: Path, artifact: ArtifactSpec, *, fixture: bool = False) -> dict[str, str]:
    from autodev.pillars import local_path

    location = artifact.fixture if fixture else artifact.path
    if location is None:
        raise ConfigError(f"artifact {artifact.id} has no fixture")
    path = local_path(root, location)
    if artifact.format == "directory":
        if not path.is_dir():
            raise ConfigError(f"missing output directory: {path}")
    elif not path.is_file():
        raise ConfigError(f"missing output file: {path}")
    elif artifact.format == "application/json":
        validate_value(read_json(path), load_schema(local_path(root, artifact.schema)), str(path))
    elif artifact.format in {"text/plain", "text/markdown"}:
        try:
            if not path.read_text(encoding="utf-8").strip():
                raise ConfigError(f"empty text output: {path}")
        except UnicodeError as exc:
            raise ConfigError(f"output must be UTF-8: {path}") from exc
    return {"id": artifact.id, "path": str(path), "format": artifact.format}


def run_checks(commands: tuple[str, ...], root: Path) -> None:
    for command in commands:
        command = command.replace("{python}", shlex.quote(sys.executable))
        try:
            result = subprocess.run(
                command, shell=True, cwd=root, text=True, capture_output=True, timeout=300, check=False
            )
        except subprocess.TimeoutExpired as exc:
            raise ConfigError(f"contract check timed out: {command}") from exc
        if result.returncode:
            raise ConfigError(
                f"contract check failed ({result.returncode}): {command}\n{result.stdout[-4000:]}{result.stderr[-4000:]}"
            )


def verify_pillar(
    pillar: PillarConfig, *, workspace: Path | None = None, interface_only: bool = False
) -> list[dict[str, str]]:
    root = workspace / pillar.slug if workspace else pillar.root
    if not interface_only and pillar.state != "implementation-ready":
        raise ConfigError(f"{pillar.slug} is interface-ready; use --interface until its implementation is ready")
    results = [verify_artifact(root, artifact, fixture=interface_only) for artifact in pillar.outputs]
    run_checks(pillar.checks, root)
    return results


def verify_agent(project: ProjectConfig, agent: AgentConfig, workspace: Path) -> list[dict[str, str]]:
    results = [verify_artifact(workspace / agent.pillar, artifact) for artifact in agent.deliverables]
    for artifact in agent.deliverables:
        if artifact.format == "application/json":
            value = read_json(workspace / agent.pillar / artifact.path)
            if isinstance(value, dict) and value.get("status") in {"blocked", "unavailable"}:
                raise ConfigError(
                    "a blocked or unavailable result cannot complete a task; update the ledger with task block"
                )
    run_checks(project.verify_commands, workspace)
    pillar = project.pillar(agent.pillar)
    run_checks(pillar.checks, workspace / pillar.slug)
    return results
