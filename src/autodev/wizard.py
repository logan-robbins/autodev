"""Interactive creation of a generic workspace and its first peer Pillar."""

from __future__ import annotations

import socket
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from autodev.config import DEFAULT_UI_PORT, ConfigError, ProjectConfig, load_project
from autodev.scaffold import create_pillar, create_workspace
from autodev.state import Registry

Input = Callable[[str], str]
Output = Callable[[str], None]


@dataclass(frozen=True)
class WizardResult:
    project: ProjectConfig
    commit: bool
    launch: bool
    start_ui: bool


def _ask(label: str, *, input_fn: Input, default: str | None = None, output: Output = print) -> str:
    while True:
        try:
            value = input_fn(f"{label}{' [' + default + ']' if default is not None else ''}: ").strip()
        except (EOFError, KeyboardInterrupt) as exc:
            raise ConfigError("interactive setup cancelled") from exc
        if value or default:
            return value or default
        output(f"{label} is required.")


def _yes_no(label: str, *, input_fn: Input, default: bool, output: Output) -> bool:
    while True:
        value = _ask(label, input_fn=input_fn, default="no" if not default else "yes", output=output).lower()
        if value in {"yes", "y", "no", "n"}:
            return value in {"yes", "y"}
        output("Enter yes or no.")


def _suggest_ui_port() -> int:
    used = set()
    registry = Registry()
    for identity in registry.entries():
        try:
            used.add(registry.resolve(identity).ui_port)
        except ConfigError:
            continue
    for port in range(DEFAULT_UI_PORT, DEFAULT_UI_PORT + 1000):
        if port in used:
            continue
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
        return port
    raise ConfigError("no available project UI port from 8765 through 9764")


def run_setup_wizard(value: str | None, *, input_fn: Input = input, output: Output = print) -> WizardResult:
    root = Path(value or _ask("Workspace directory", input_fn=input_fn)).expanduser().resolve()
    if not (root / "autodev.toml").exists():
        identity = _ask("Project ID", input_fn=input_fn, default=root.name)
        name = _ask("Project name", input_fn=input_fn, default=identity)
        execution = _ask("Execution mode (filesystem or git)", input_fn=input_fn, default="filesystem")
        create_workspace(root, project_id=identity, name=name, execution=execution, ui_port=_suggest_ui_port())
    project = load_project(root)
    if not project.pillars:
        slug = _ask("First Pillar slug", input_fn=input_fn)
        summary = _ask("Pillar summary / responsibility", input_fn=input_fn)
        template = _ask("Harness Agent template", input_fn=input_fn, default="generalist")
        provider = _ask("Harness provider", input_fn=input_fn, default="codex")
        create_pillar(root, slug, summary=summary, template=template, provider=provider)
        project = load_project(root)
    output(f"Workspace: {project.root}")
    for pillar in project.pillars:
        output(f"{pillar.slug}: {pillar.summary} ({len(pillar.pod)} Harness Agent(s))")
    commit = project.execution == "git" and _yes_no(
        "Commit workspace and Pillar configuration", input_fn=input_fn, default=False, output=output
    )
    launch = _yes_no(
        "Launch Harness Agents with their operating contracts", input_fn=input_fn, default=False, output=output
    )
    start_ui = _yes_no("Start the project UI", input_fn=input_fn, default=False, output=output)
    return WizardResult(project, commit, launch, start_ui)
