"""Adapters for user-installed coding-agent command line interfaces."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from autodev.config import ProviderConfig


class ProviderError(RuntimeError):
    """Raised when a configured host CLI cannot be launched."""


def executable_path(command: str) -> str:
    if os.sep in command:
        path = Path(command).expanduser().resolve()
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    else:
        found = shutil.which(command)
        if found:
            return found
    raise ProviderError(f"required coding-agent executable {command!r} is not installed or not on PATH")


def version(provider: ProviderConfig) -> str:
    executable = executable_path(provider.command)
    result = subprocess.run(
        [executable, "--version"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    output = result.stdout.strip()
    if result.returncode:
        raise ProviderError(
            f"{provider.name} executable failed its version check with exit code "
            f"{result.returncode}: {output or 'no output'}"
        )
    return output


def launch_command(
    provider: ProviderConfig,
    worktree: Path,
    *,
    yolo: bool,
    initial_prompt: str | None,
) -> list[str]:
    """Build one interactive host-CLI command without installing or wrapping it."""
    executable = executable_path(provider.command)
    if provider.name == "codex":
        command = [executable, "--cd", str(worktree), "--no-alt-screen"]
        if provider.model:
            command.extend(["--model", provider.model])
        if provider.effort:
            command.extend(["--config", f"model_reasoning_effort={json.dumps(provider.effort)}"])
        if yolo:
            command.append("--dangerously-bypass-approvals-and-sandbox")
    elif provider.name == "claude":
        command = [executable]
        if provider.model:
            command.extend(["--model", provider.model])
        if provider.effort:
            command.extend(["--effort", provider.effort])
        if yolo:
            command.append("--dangerously-skip-permissions")
    else:  # Config validation should make this unreachable.
        raise ProviderError(f"unsupported provider: {provider.name}")

    if initial_prompt:
        command.append(initial_prompt)
    return command
