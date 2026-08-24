"""Load and validate the single-file Autodev project contract."""

from __future__ import annotations

import re
import string
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

DESCRIPTOR_NAME = "autodev.toml"
SCHEMA_VERSION = 2
SUPPORTED_PROVIDERS = frozenset({"codex", "claude"})
DEFAULT_SESSION_PATTERN = "autodev-{project}-{agent}"
DEFAULT_UI_PORT = 8765
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
_TMUX_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class ConfigError(ValueError):
    """Raised when a project descriptor is incomplete or unsafe."""


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    command: str
    model: str | None = None
    effort: str | None = None


@dataclass(frozen=True)
class AgentConfig:
    id: str
    provider: str
    purpose: str
    goal: str
    write_roots: tuple[str, ...]
    read_roots: tuple[str, ...]


@dataclass(frozen=True)
class ProjectConfig:
    id: str
    name: str
    root: Path
    descriptor: Path
    base_branch: str
    instructions: str
    context_roots: tuple[str, ...]
    verify_commands: tuple[str, ...]
    session_pattern: str
    ui_port: int
    bypass_permissions: bool
    providers: dict[str, ProviderConfig]
    agents: tuple[AgentConfig, ...]

    def agent(self, agent_id: str) -> AgentConfig:
        for agent in self.agents:
            if agent.id == agent_id:
                return agent
        known = ", ".join(agent.id for agent in self.agents)
        raise ConfigError(f"unknown agent {agent_id!r}; configured agents: {known}")


def _table(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{label} must be a TOML table")
    return value


def _nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{label} must be a non-empty string")
    return value.strip()


def _optional_string(value: Any, label: str) -> str | None:
    if value is None:
        return None
    return _nonempty_string(value, label)


def _ui_port(value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1024 <= value <= 65535:
        raise ConfigError("runtime.ui_port must be an integer from 1024 through 65535")
    return value


def _boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"{label} must be true or false")
    return value


def _string_list(value: Any, label: str, *, allow_empty: bool = True) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ConfigError(f"{label} must be a list of non-empty strings")
    if not allow_empty and not value:
        raise ConfigError(f"{label} must contain at least one entry")
    return tuple(item.strip() for item in value)


def _id(value: Any, label: str) -> str:
    result = _nonempty_string(value, label)
    if not _ID_RE.fullmatch(result):
        raise ConfigError(f"{label} must match {_ID_RE.pattern!r}; got {result!r}")
    return result


def _root(value: str, label: str) -> str:
    if "\\" in value:
        raise ConfigError(f"{label} must use forward slashes: {value!r}")
    trailing_slash = value.endswith("/")
    path = PurePosixPath(value.rstrip("/"))
    if path.is_absolute() or not path.parts or path.parts == (".",) or ".." in path.parts:
        raise ConfigError(f"{label} must be a relative path below the repository root: {value!r}")
    if any(part in {"", "."} for part in path.parts):
        raise ConfigError(f"{label} contains an invalid path component: {value!r}")
    normalized = path.as_posix()
    if normalized == DESCRIPTOR_NAME:
        raise ConfigError(f"{label} cannot grant an agent ownership of {DESCRIPTOR_NAME}")
    return normalized + ("/" if trailing_slash else "")


def _roots(value: Any, label: str, *, allow_empty: bool = True) -> tuple[str, ...]:
    raw = _string_list(value, label, allow_empty=allow_empty)
    normalized = tuple(_root(item, label) for item in raw)
    if len(normalized) != len(set(normalized)):
        raise ConfigError(f"{label} contains duplicate paths")
    return normalized


def _path_parts(root: str) -> tuple[str, ...]:
    return PurePosixPath(root.rstrip("/")).parts


def _roots_overlap(left: str, right: str) -> bool:
    left_parts = _path_parts(left)
    right_parts = _path_parts(right)
    shorter = min(len(left_parts), len(right_parts))
    return left_parts[:shorter] == right_parts[:shorter]


def _validate_ownership(agents: tuple[AgentConfig, ...]) -> None:
    owned: list[tuple[str, str]] = []
    for agent in agents:
        for root in agent.write_roots:
            for other_agent, other_root in owned:
                if _roots_overlap(root, other_root):
                    raise ConfigError(
                        f"write roots overlap between agents {other_agent!r} ({other_root}) and {agent.id!r} ({root})"
                    )
            owned.append((agent.id, root))


def validate_session_pattern(pattern: str) -> str:
    fields: list[str] = []
    try:
        for _literal, field, format_spec, conversion in string.Formatter().parse(pattern):
            if field is None:
                continue
            if format_spec or conversion:
                raise ConfigError("runtime.session_pattern does not support format specs or conversions")
            fields.append(field)
    except ValueError as exc:
        raise ConfigError(f"runtime.session_pattern is malformed: {exc}") from exc
    unknown = sorted(set(fields) - {"project", "agent", "provider"})
    if unknown:
        raise ConfigError(f"runtime.session_pattern has unknown fields: {', '.join(unknown)}")
    for required in ("project", "agent"):
        if fields.count(required) != 1:
            raise ConfigError(f"runtime.session_pattern must contain exactly one {{{required}}}")
    return pattern


def render_session_name(pattern: str, project_id: str, agent: AgentConfig) -> str:
    name = pattern.format(project=project_id, agent=agent.id, provider=agent.provider)
    if len(name) > 100 or not _TMUX_NAME_RE.fullmatch(name):
        raise ConfigError(
            "runtime.session_pattern must render only letters, numbers, underscores, and hyphens "
            f"with at most 100 characters; rendered {name!r}"
        )
    return name


def _git_root(descriptor: Path) -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=descriptor.parent,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        detail = result.stderr.strip() or "not a Git repository"
        raise ConfigError(f"{descriptor.parent} is not a usable Git worktree: {detail}")
    return Path(result.stdout.strip()).resolve()


def descriptor_path(value: str | Path | None = None, *, cwd: Path | None = None) -> Path:
    """Resolve a descriptor path from a file, directory, or ancestor search."""
    if value is not None:
        candidate = Path(value).expanduser().resolve()
        descriptor = candidate / DESCRIPTOR_NAME if candidate.is_dir() else candidate
        if not descriptor.is_file():
            raise ConfigError(f"project descriptor does not exist: {descriptor}")
        return descriptor

    current = (cwd or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        descriptor = directory / DESCRIPTOR_NAME
        if descriptor.is_file():
            return descriptor
    raise ConfigError(f"no {DESCRIPTOR_NAME} found at or above {current}")


def load_project(value: str | Path | None = None, *, cwd: Path | None = None) -> ProjectConfig:
    descriptor = descriptor_path(value, cwd=cwd)
    try:
        data = tomllib.loads(descriptor.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"cannot read {descriptor}: {exc}") from exc

    if data.get("schema_version") != SCHEMA_VERSION:
        raise ConfigError(f"schema_version must be {SCHEMA_VERSION}")

    project_data = _table(data.get("project"), "[project]")
    project_id = _id(project_data.get("id"), "project.id")
    name = _nonempty_string(project_data.get("name"), "project.name")
    base_branch = _nonempty_string(project_data.get("base_branch"), "project.base_branch")
    instructions = _nonempty_string(project_data.get("instructions"), "project.instructions")
    context_roots = _roots(project_data.get("context_roots", []), "project.context_roots")
    verify_commands = _string_list(project_data.get("verify_commands", []), "project.verify_commands")
    runtime_data = _table(data.get("runtime", {}), "[runtime]")
    session_pattern = validate_session_pattern(
        _nonempty_string(
            runtime_data.get("session_pattern", DEFAULT_SESSION_PATTERN),
            "runtime.session_pattern",
        )
    )
    ui_port = _ui_port(runtime_data.get("ui_port"))
    bypass_permissions = _boolean(runtime_data.get("bypass_permissions"), "runtime.bypass_permissions")

    repo_root = _git_root(descriptor)
    if repo_root != descriptor.parent.resolve():
        raise ConfigError(f"{DESCRIPTOR_NAME} must be at the Git worktree root {repo_root}; found {descriptor}")

    provider_data = _table(data.get("providers", {}), "[providers]")
    unknown_providers = sorted(set(provider_data) - SUPPORTED_PROVIDERS)
    if unknown_providers:
        raise ConfigError(f"unsupported provider configuration: {', '.join(unknown_providers)}")
    providers: dict[str, ProviderConfig] = {}
    for provider_name in SUPPORTED_PROVIDERS:
        raw = _table(provider_data.get(provider_name, {}), f"[providers.{provider_name}]")
        providers[provider_name] = ProviderConfig(
            name=provider_name,
            command=_nonempty_string(raw.get("command", provider_name), f"providers.{provider_name}.command"),
            model=_optional_string(raw.get("model"), f"providers.{provider_name}.model"),
            effort=_optional_string(raw.get("effort"), f"providers.{provider_name}.effort"),
        )

    raw_agents = data.get("agents")
    if not isinstance(raw_agents, list) or not raw_agents:
        raise ConfigError("at least one [[agents]] table is required")
    agents: list[AgentConfig] = []
    seen_ids: set[str] = set()
    for index, value in enumerate(raw_agents):
        raw = _table(value, f"agents[{index}]")
        agent_id = _id(raw.get("id"), f"agents[{index}].id")
        if agent_id in seen_ids:
            raise ConfigError(f"duplicate agent id: {agent_id}")
        seen_ids.add(agent_id)
        provider = _nonempty_string(raw.get("provider"), f"agents[{index}].provider")
        if provider not in SUPPORTED_PROVIDERS:
            raise ConfigError(f"agents[{index}].provider must be one of {', '.join(sorted(SUPPORTED_PROVIDERS))}")
        agents.append(
            AgentConfig(
                id=agent_id,
                provider=provider,
                purpose=_nonempty_string(raw.get("purpose"), f"agents[{index}].purpose"),
                goal=_nonempty_string(raw.get("goal"), f"agents[{index}].goal"),
                write_roots=_roots(raw.get("write_roots"), f"agents[{index}].write_roots", allow_empty=False),
                read_roots=_roots(raw.get("read_roots", []), f"agents[{index}].read_roots"),
            )
        )

    result_agents = tuple(agents)
    _validate_ownership(result_agents)
    for agent in result_agents:
        render_session_name(session_pattern, project_id, agent)
    return ProjectConfig(
        id=project_id,
        name=name,
        root=repo_root,
        descriptor=descriptor,
        base_branch=base_branch,
        instructions=instructions,
        context_roots=context_roots,
        verify_commands=verify_commands,
        session_pattern=session_pattern,
        ui_port=ui_port,
        bypass_permissions=bypass_permissions,
        providers=providers,
        agents=result_agents,
    )
