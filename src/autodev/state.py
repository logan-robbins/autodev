"""Shared external state for all projects managed by one Autodev installation."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from autodev.config import ConfigError, ProjectConfig, load_project

REGISTRY_VERSION = 1


def autodev_home() -> Path:
    override = os.environ.get("AUTODEV_HOME")
    if override:
        return Path(override).expanduser().resolve()
    state_home = os.environ.get("XDG_STATE_HOME")
    if state_home:
        return (Path(state_home).expanduser() / "autodev").resolve()
    return (Path.home() / ".local" / "state" / "autodev").resolve()


@dataclass(frozen=True)
class ProjectPaths:
    home: Path
    worktrees: Path
    logs: Path
    runs: Path
    laws: Path


def project_paths(project_id: str, *, home: Path | None = None) -> ProjectPaths:
    root = (home or autodev_home()) / "projects" / project_id
    return ProjectPaths(
        home=root,
        worktrees=root / "worktrees",
        logs=root / "logs",
        runs=root / "runs",
        laws=root / "laws",
    )


def role_law_path(project_id: str, role: str, *, home: Path | None = None) -> Path:
    return project_paths(project_id, home=home).laws / f"{role}.md"


def write_role_law(project_id: str, role: str, content: str, *, home: Path | None = None) -> Path:
    """Persist one role's composed law under AUTODEV_HOME (0600), outside the worktree.

    Kept out of the managed repo so it never collides with the project's own
    CLAUDE.md and never trips the ownership check.
    """
    path = role_law_path(project_id, role, home=home)
    atomic_write_text(path, content, mode=0o600)
    return path


def read_role_law(project_id: str, role: str, *, home: Path | None = None) -> str:
    path = role_law_path(project_id, role, home=home)
    if not path.exists():
        raise ConfigError(f"no composed law for role {role!r} at {path}")
    return path.read_text(encoding="utf-8")


def atomic_write_text(path: Path, content: str, *, mode: int | None = None) -> None:
    """Write ``content`` to ``path`` atomically (temp file, fsync, replace).

    The same durable-replace pattern the registry uses, exposed for the typed
    product-tree writes and the composed-law file. Parent directories are created.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if mode is not None:
            temp_path.chmod(mode)
        temp_path.replace(path)
    finally:
        temp_path.unlink(missing_ok=True)


class Registry:
    def __init__(self, *, home: Path | None = None) -> None:
        self.home = (home or autodev_home()).resolve()
        self.path = self.home / "registry.json"

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": REGISTRY_VERSION, "projects": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigError(f"cannot read Autodev registry {self.path}: {exc}") from exc
        if data.get("version") != REGISTRY_VERSION or not isinstance(data.get("projects"), dict):
            raise ConfigError(f"unsupported or malformed Autodev registry: {self.path}")
        return data

    def _write(self, data: dict[str, Any]) -> None:
        self.home.mkdir(parents=True, exist_ok=True)
        descriptor = json.dumps(data, indent=2, sort_keys=True) + "\n"
        handle, temp_name = tempfile.mkstemp(prefix="registry-", suffix=".json", dir=self.home)
        temp_path = Path(temp_name)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(descriptor)
                stream.flush()
                os.fsync(stream.fileno())
            temp_path.replace(self.path)
        finally:
            temp_path.unlink(missing_ok=True)

    def register(self, project: ProjectConfig) -> None:
        data = self._read()
        data["projects"][project.id] = str(project.descriptor)
        self._write(data)

    def unregister(self, project_id: str) -> None:
        data = self._read()
        if project_id not in data["projects"]:
            raise ConfigError(f"project is not registered: {project_id}")
        del data["projects"][project_id]
        self._write(data)

    def entries(self) -> dict[str, Path]:
        data = self._read()
        return {key: Path(value) for key, value in sorted(data["projects"].items())}

    def resolve(self, project_id: str) -> ProjectConfig:
        try:
            path = self.entries()[project_id]
        except KeyError as exc:
            raise ConfigError(f"project is not registered: {project_id}") from exc
        return load_project(path)
