"""Interactive setup wizard for one complete Autodev project descriptor."""

from __future__ import annotations

import socket
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from autodev.config import (
    DEFAULT_SESSION_PATTERN,
    DEFAULT_UI_PORT,
    DESCRIPTOR_NAME,
    ConfigError,
    ProjectConfig,
    load_project,
)
from autodev.state import Registry, autodev_home
from autodev.templates import DescriptorAgent, render_full_descriptor

Input = Callable[[str], str]
Output = Callable[[str], None]


@dataclass(frozen=True)
class WizardResult:
    project: ProjectConfig
    commit: bool
    launch: bool
    start_ui: bool


def _ask(
    label: str,
    *,
    input_fn: Input,
    default: str | None = None,
    required: bool = True,
    output: Output = print,
) -> str:
    suffix = f" [{default}]" if default is not None else ""
    while True:
        try:
            answer = input_fn(f"{label}{suffix}: ").strip()
        except (EOFError, KeyboardInterrupt) as exc:
            raise ConfigError("interactive setup cancelled") from exc
        value = answer or default or ""
        if value or not required:
            return value
        output(f"{label} is required.")


def _yes_no(label: str, *, input_fn: Input, default: bool, output: Output) -> bool:
    marker = "Y/n" if default else "y/N"
    while True:
        answer = _ask(
            f"{label} [{marker}]",
            input_fn=input_fn,
            required=False,
            output=output,
        ).lower()
        if not answer:
            return default
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        output("Enter yes or no.")


def _csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _commands(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(";") if item.strip())


def _suggest_ui_port() -> int:
    used: set[int] = set()
    registry = Registry()
    for project_id in registry.entries():
        try:
            used.add(registry.resolve(project_id).ui_port)
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
    raise ConfigError("no available Autodev UI port from 8765 through 9764")


def _ask_ui_port(*, input_fn: Input, output: Output) -> int:
    default = _suggest_ui_port()
    while True:
        raw = _ask("Local project UI port", input_fn=input_fn, default=str(default), output=output)
        try:
            port = int(raw)
        except ValueError:
            output("UI port must be an integer from 1024 through 65535.")
            continue
        if 1024 <= port <= 65535:
            return port
        output("UI port must be an integer from 1024 through 65535.")


def _git_root(path: Path) -> tuple[Path, str]:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=path,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise ConfigError(f"setup requires an existing Git repository: {path}")
    root = Path(result.stdout.strip()).resolve()
    if root != path.resolve():
        raise ConfigError(f"select the Git repository root {root}, not nested directory {path}")
    head = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD^{commit}"],
        cwd=root,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        check=False,
    )
    if head.returncode:
        raise ConfigError(f"setup requires an existing initial commit in {root}")
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    if status:
        raise ConfigError(
            "setup requires a clean project checkout before creating autodev.toml; "
            f"commit or stash these changes first:\n{status}"
        )
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    return root, branch or "main"


def run_setup_wizard(
    initial_project: str | None = None,
    *,
    input_fn: Input = input,
    output: Output = print,
) -> WizardResult:
    output("Autodev interactive project setup")
    output(f"Shared runtime state: {autodev_home()}")
    selected = initial_project or _ask(
        "Existing Git project directory",
        input_fn=input_fn,
        default=str(Path.cwd()),
        output=output,
    )
    root, current_branch = _git_root(Path(selected).expanduser().resolve())
    descriptor = root / DESCRIPTOR_NAME
    if descriptor.exists():
        raise ConfigError(f"refusing to overwrite existing descriptor: {descriptor}")

    default_id = root.name.lower().replace("_", "-").replace(" ", "-")
    project_id = _ask("Project ID", input_fn=input_fn, default=default_id, output=output)
    name = _ask("Project display name", input_fn=input_fn, default=root.name, output=output)
    base_branch = _ask("Integration branch", input_fn=input_fn, default=current_branch, output=output)
    instructions = _ask(
        "Project-wide instructions",
        input_fn=input_fn,
        default="Follow the repository's existing architecture, task state, and contribution rules.",
        output=output,
    )
    context_roots = _csv(
        _ask(
            "Shared read-only context paths (comma-separated, blank allowed)",
            input_fn=input_fn,
            default="",
            required=False,
            output=output,
        )
    )
    verify_commands = _commands(
        _ask(
            "Verification commands (semicolon-separated, blank allowed)",
            input_fn=input_fn,
            default="",
            required=False,
            output=output,
        )
    )
    session_pattern = _ask(
        "tmux session pattern ({project}, {agent}, optional {provider})",
        input_fn=input_fn,
        default=DEFAULT_SESSION_PATTERN,
        output=output,
    )
    ui_port = _ask_ui_port(input_fn=input_fn, output=output)
    bypass_permissions = _yes_no(
        "Bypass permission controls for every Autodev-managed worker?",
        input_fn=input_fn,
        default=False,
        output=output,
    )

    agents: list[DescriptorAgent] = []
    while True:
        number = len(agents) + 1
        agent_id = _ask(
            f"Agent {number} ID",
            input_fn=input_fn,
            default="engineering" if number == 1 else f"agent-{number}",
            output=output,
        )
        provider = _ask(
            f"Agent {agent_id} provider (codex/claude)",
            input_fn=input_fn,
            default="codex",
            output=output,
        )
        purpose = _ask(
            f"Agent {agent_id} purpose",
            input_fn=input_fn,
            default=f"Own and deliver complete changes in the {agent_id} boundary.",
            output=output,
        )
        goal = _ask(
            f"Agent {agent_id} standing goal",
            input_fn=input_fn,
            default=(
                "Inspect current project state, select the highest-priority actionable work item "
                "in your ownership, and complete exactly one verified vertical change."
            ),
            output=output,
        )
        write_roots = _csv(
            _ask(
                f"Agent {agent_id} write roots (comma-separated)",
                input_fn=input_fn,
                output=output,
            )
        )
        if not write_roots:
            raise ConfigError(f"agent {agent_id} requires at least one write root")
        read_roots = _csv(
            _ask(
                f"Agent {agent_id} additional read roots (comma-separated, blank allowed)",
                input_fn=input_fn,
                default="",
                required=False,
                output=output,
            )
        )
        agents.append(
            DescriptorAgent(
                id=agent_id,
                provider=provider,
                purpose=purpose,
                goal=goal,
                write_roots=write_roots,
                read_roots=read_roots,
            )
        )
        if not _yes_no("Add another agent?", input_fn=input_fn, default=False, output=output):
            break

    provider_settings: dict[str, dict[str, str | None]] = {}
    for provider in sorted({agent.provider for agent in agents}):
        output(f"Configure installed {provider} CLI (blank model/effort keeps its local default).")
        provider_settings[provider] = {
            "command": _ask(
                f"{provider} executable",
                input_fn=input_fn,
                default=provider,
                output=output,
            ),
            "model": _ask(
                f"{provider} model",
                input_fn=input_fn,
                default="",
                required=False,
                output=output,
            )
            or None,
            "effort": _ask(
                f"{provider} effort",
                input_fn=input_fn,
                default="",
                required=False,
                output=output,
            )
            or None,
        }

    text = render_full_descriptor(
        project_id=project_id,
        name=name,
        base_branch=base_branch,
        instructions=instructions,
        context_roots=context_roots,
        verify_commands=verify_commands,
        session_pattern=session_pattern,
        ui_port=ui_port,
        bypass_permissions=bypass_permissions,
        agents=tuple(agents),
        provider_settings=provider_settings,
    )
    output("\nDescriptor preview:\n")
    output(text)
    if not _yes_no(f"Write {descriptor}?", input_fn=input_fn, default=True, output=output):
        raise ConfigError("interactive setup cancelled before writing")

    descriptor.write_text(text, encoding="utf-8")
    try:
        project = load_project(descriptor)
    except Exception:
        descriptor.unlink(missing_ok=True)
        raise
    commit = _yes_no(
        f"Commit {DESCRIPTOR_NAME} to {project.base_branch}?",
        input_fn=input_fn,
        default=True,
        output=output,
    )
    launch = False
    if commit:
        launch = _yes_no(
            "Create worktrees, start agents, and send goals now?",
            input_fn=input_fn,
            default=True,
            output=output,
        )
    else:
        output("Immediate launch is disabled until autodev.toml is committed.")
    start_ui = _yes_no(
        f"Start the project UI at http://127.0.0.1:{project.ui_port}/ now?",
        input_fn=input_fn,
        default=True,
        output=output,
    )
    return WizardResult(project=project, commit=commit, launch=launch, start_ui=start_ui)
