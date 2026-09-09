"""Discover peer capability boundaries and resolve their agent-native contracts."""

from __future__ import annotations

import os
import tomllib
from dataclasses import asdict
from pathlib import Path
from typing import Any

from autodev.config import (
    SUPPORTED_PROVIDERS,
    AgentConfig,
    ArtifactSpec,
    ConfigError,
    PillarConfig,
    _id,
    _nonempty_string,
    _root,
    _roots_overlap,
    _string_list,
    _table,
)

PILLAR_DESCRIPTOR = "pillar.toml"
EXCLUDED_DIRECTORIES = frozenset({".git", ".venv", "node_modules", "__pycache__", ".autodev"})
TEMPLATE_ROOT = Path(__file__).parent / "agent_templates"


def local_path(root: Path, value: str, label: str = "path") -> Path:
    root = root.resolve()
    relative = _root(value, label)
    candidate = root / relative
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise ConfigError(f"{label} escapes its Pillar/workspace: {value!r}")
    # A declared boundary cannot change meaning through a symlink, even internally.
    if any(path.is_symlink() for path in (candidate, *candidate.parents) if path.is_relative_to(root)):
        raise ConfigError(f"{label} cannot traverse a symlink: {value!r}")
    return candidate


def read_toml(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc


def agent_template(reference: str, root: Path) -> dict[str, Any]:
    if "/" in reference or reference.endswith(".toml"):
        path = local_path(root, reference, "agent template")
    else:
        path = TEMPLATE_ROOT / f"{_id(reference, 'template')}.toml"
    data = read_toml(path)
    if data.get("schema_version") != 1:
        raise ConfigError(f"{path}: agent template schema_version must be 1")
    for key in ("purpose", "instructions", "goal"):
        _nonempty_string(data.get(key), f"{path}:{key}")
    if data.get("role", "worker") not in {"worker", "project-manager"}:
        raise ConfigError(f"{path}: role must be worker or project-manager")
    return data


def artifacts(raw: Any, root: Path, label: str, *, allow_empty: bool = False) -> tuple[ArtifactSpec, ...]:
    if not isinstance(raw, list) or (not raw and not allow_empty):
        raise ConfigError(f"{label} must be {'a' if allow_empty else 'a nonempty'} list of artifact declarations")
    results = []
    seen: set[str] = set()
    for item in raw:
        item = _table(item, label)
        identity = _id(item.get("id"), f"{label}.id")
        if identity in seen:
            raise ConfigError(f"duplicate {label} id: {identity}")
        seen.add(identity)
        path = _root(_nonempty_string(item.get("path"), f"{label}.path"), f"{label}.path")
        local_path(root, path, label)
        media = _nonempty_string(item.get("format"), f"{label}.format")
        if media not in {"application/json", "text/plain", "text/markdown", "application/octet-stream", "directory"}:
            raise ConfigError(f"unsupported artifact format {media!r} in {label}")
        schema = item.get("schema")
        if media == "application/json" and schema is None:
            raise ConfigError(f"{label}: application/json requires a schema")
        if schema is not None:
            schema = _root(_nonempty_string(schema, f"{label}.schema"), f"{label}.schema")
            from autodev.contracts import load_schema

            load_schema(local_path(root, schema, f"{label}.schema"))
        fixture = item.get("fixture")
        if fixture is not None:
            fixture = _root(_nonempty_string(fixture, "fixture"), "fixture")
            if not local_path(root, fixture, "fixture").exists():
                raise ConfigError(f"missing interface fixture: {fixture}")
        if label == "interface.outputs" and fixture is None:
            raise ConfigError("interface.outputs require a fixture for consumers before implementation")
        results.append(
            ArtifactSpec(identity, path, media, _nonempty_string(item.get("description"), label), schema, fixture)
        )
    return tuple(results)


def load_pillar(root: Path, *, content: str | None = None) -> PillarConfig:
    try:
        data = read_toml(root / PILLAR_DESCRIPTOR) if content is None else tomllib.loads(content)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid Pillar TOML: {exc}") from exc
    if data.get("schema_version") != 1:
        raise ConfigError(f"{root}/pillar.toml: schema_version must be 1")
    if "pod" in data or "pm" in data:
        raise ConfigError("a Pillar has one implicit Pod; do not declare a pod or required PM")
    meta = _table(data.get("pillar"), "pillar")
    slug = _id(meta.get("slug"), "pillar.slug")
    if slug != root.name:
        raise ConfigError(f"pillar.slug {slug!r} must match directory name {root.name!r}")
    interface = _table(data.get("interface"), "interface")
    state = interface.get("state")
    if state not in {"interface-ready", "implementation-ready"}:
        raise ConfigError("interface.state must be interface-ready or implementation-ready")
    outputs = artifacts(interface.get("outputs"), root, "interface.outputs")
    inputs = artifacts(interface.get("inputs"), root, "interface.inputs", allow_empty=True)
    checks = _string_list(interface.get("checks"), "interface.checks", allow_empty=False)
    dependencies = _string_list(interface.get("dependencies"), "interface.dependencies")
    if len(set(dependencies)) != len(dependencies):
        raise ConfigError("interface.dependencies must name each Pillar only once")
    for dependency in dependencies:
        _id(dependency, "dependency")
        if dependency == slug:
            raise ConfigError("a Pillar cannot depend on itself")
    raw_agents = data.get("agents")
    if not isinstance(raw_agents, list) or not raw_agents:
        raise ConfigError(f"{slug}: at least one Harness Agent must be assigned to its Pod")
    agents = []
    identities = set()
    protected = ["pillar.toml", "memory/", "tasks/", *[a.schema for a in (*inputs, *outputs) if a.schema]]
    for raw in raw_agents:
        raw = _table(raw, "agent")
        identity = _id(raw.get("id"), "agent.id")
        if identity in identities:
            raise ConfigError(f"duplicate agent id {identity!r} in {slug}")
        identities.add(identity)
        reference = _nonempty_string(raw.get("template"), "agent.template")
        template = agent_template(reference, root)
        if "/" in reference or reference.endswith(".toml"):
            protected.append(reference)
        provider = raw.get("provider")
        if provider not in SUPPORTED_PROVIDERS:
            raise ConfigError(f"agent.provider must be one of {', '.join(sorted(SUPPORTED_PROVIDERS))}")
        write_roots = _string_list(raw.get("write_roots", [f"output/{identity}/"]), "write_roots", allow_empty=False)
        reads = _string_list(raw.get("read_roots", []), "read_roots")
        if any(Path(path).parts[0] == "tasks" for path in reads):
            raise ConfigError("read task ledgers through the scoped ledger API, not read_roots")
        for path in (*write_roots, *reads):
            local_path(root, path)
        delivery = raw.get("deliverables", template.get("deliverables"))
        if isinstance(delivery, list):
            delivery = [
                {k: v.replace("{agent}", identity) if isinstance(v, str) else v for k, v in d.items()}
                for d in delivery
                if isinstance(d, dict)
            ]
        deliverables = artifacts(delivery, root, "agent.deliverables")
        protected.extend(a.schema for a in deliverables if a.schema)
        for output in deliverables:
            if not any(
                output.path == w.rstrip("/") or output.path.startswith(w.rstrip("/") + "/") for w in write_roots
            ):
                raise ConfigError(f"deliverable {output.path} is outside {identity}'s write roots")
        agents.append(
            AgentConfig(
                id=f"{slug}--{identity}",
                local_id=identity,
                pillar=slug,
                template=reference,
                provider=provider,
                purpose=_nonempty_string(raw.get("purpose", template["purpose"]), "purpose"),
                goal=_nonempty_string(raw.get("goal", template["goal"]), "goal"),
                instructions=template["instructions"],
                write_roots=tuple(f"{slug}/{_root(p, 'write_roots')}" for p in write_roots),
                read_roots=tuple(f"{slug}/{_root(p, 'read_roots')}" for p in reads),
                deliverables=deliverables,
                role=template.get("role", "worker"),
            )
        )
    if sum(agent.role == "project-manager" for agent in agents) > 1:
        raise ConfigError("a Pod may have at most one Project Manager Harness Agent")
    for agent in agents:
        for owned in agent.write_roots:
            if any(_roots_overlap(owned, f"{slug}/{reserved}") for reserved in protected):
                raise ConfigError(
                    f"write root {owned!r} overlaps a protected contract, template, schema, or memory path"
                )
    return PillarConfig(
        slug=slug,
        root=root,
        summary=_nonempty_string(meta.get("summary"), "pillar.summary"),
        responsibility=_nonempty_string(meta.get("responsibility"), "pillar.responsibility"),
        state=state,
        consumption=_nonempty_string(interface.get("consumption"), "interface.consumption"),
        constraints=_nonempty_string(interface.get("constraints"), "interface.constraints"),
        inputs=inputs,
        outputs=outputs,
        dependencies=dependencies,
        checks=checks,
        agents=tuple(agents),
    )


def discover_pillars(workspace: Path, *, overrides: dict[str, str] | None = None) -> tuple[PillarConfig, ...]:
    """Reject misplaced boundaries, including invalid descriptors; never absorb them."""
    roots = []
    for current, dirs, files in os.walk(workspace, followlinks=False):
        directory = Path(current)
        for name in dirs:
            child = directory / name
            if child.is_symlink() and (child / PILLAR_DESCRIPTOR).exists():
                raise ConfigError(f"Pillar boundary cannot be a symlink: {child}")
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED_DIRECTORIES and not (directory / d).is_symlink())
        if PILLAR_DESCRIPTOR in files:
            if directory.parent != workspace:
                raise ConfigError(
                    f"Pillars must be direct children of workspace {workspace}; misplaced {directory}/pillar.toml"
                )
            roots.append(directory)
    pillars = tuple(load_pillar(root, content=(overrides or {}).get(root.name)) for root in sorted(roots))
    slugs = {pillar.slug for pillar in pillars}
    for pillar in pillars:
        for dependency in pillar.dependencies:
            if dependency not in slugs:
                raise ConfigError(f"{pillar.slug} requires missing Pillar {dependency}")
    return pillars


def containing_pillar(workspace: Path, path: Path) -> Path:
    """Ownership is based on the direct child, even when its descriptor is invalid."""
    workspace, path = workspace.resolve(), path.resolve()
    if not path.is_relative_to(workspace) or path == workspace:
        raise ConfigError(f"path is outside a Pillar: {path}")
    root = workspace / path.relative_to(workspace).parts[0]
    if not (root / PILLAR_DESCRIPTOR).is_file():
        raise ConfigError(f"no Pillar boundary for {path}")
    return root


def pillar_payload(pillar: PillarConfig) -> dict[str, Any]:
    result = asdict(pillar)
    result["root"] = str(pillar.root)
    result["descriptor"] = str(pillar.descriptor)
    return result
