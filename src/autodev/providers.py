"""Adapters for user-installed coding-agent command line interfaces."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

from autodev.config import ProviderConfig

# PreToolUse policy only gates edits; other events fire for every tool/turn.
_CLAUDE_MATCHERS = {"PreToolUse": "Write|Edit"}


class ProviderError(RuntimeError):
    """Raised when a configured host CLI cannot be launched."""


def _claude_hook_settings(hook_config: Mapping[str, Sequence[str]]) -> dict:
    """Render the hook spec as a Claude ``settings.json`` object (A5b)."""
    hooks: dict[str, list[dict]] = {}
    for event, argv in hook_config.items():
        group: dict = {"hooks": [{"type": "command", "command": shlex.join(argv)}]}
        matcher = _CLAUDE_MATCHERS.get(event)
        if matcher:
            group["matcher"] = matcher
        hooks[event] = [group]
    return {"hooks": hooks}


def _codex_hook_overrides(hook_config: Mapping[str, Sequence[str]]) -> list[str]:
    """Render the hook spec as Codex ``-c`` overrides (A5b).

    Codex needs the hooks feature enabled and, because Autodev-generated hooks
    are untrusted, ``--dangerously-bypass-hook-trust`` for them to fire at all.
    """
    argv: list[str] = ["-c", "features.hooks=true", "--dangerously-bypass-hook-trust"]
    for event in sorted(hook_config):
        command = json.dumps(shlex.join(hook_config[event]))
        argv += ["-c", f"hooks.{event}=[{{ hooks = [{{ command = {command} }}] }}]"]
    return argv


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
    bypass_permissions: bool,
    initial_prompt: str | None,
    hook_config: Mapping[str, Sequence[str]] | None = None,
) -> list[str]:
    """Build one interactive host-CLI command without installing or wrapping it.

    Hook injection (A5b) is argv-only — Claude via ``--settings`` inline JSON,
    Codex via ``-c hooks.*`` overrides — so no hook file ever lands in the
    managed repo and the one-file invariant holds.
    """
    executable = executable_path(provider.command)
    if provider.name == "codex":
        command = [executable, "--cd", str(worktree), "--no-alt-screen"]
        if provider.model:
            command.extend(["--model", provider.model])
        if provider.effort:
            command.extend(["--config", f"model_reasoning_effort={json.dumps(provider.effort)}"])
        if bypass_permissions:
            command.append("--dangerously-bypass-approvals-and-sandbox")
        if hook_config:
            command.extend(_codex_hook_overrides(hook_config))
    elif provider.name == "claude":
        command = [executable]
        if provider.model:
            command.extend(["--model", provider.model])
        if provider.effort:
            command.extend(["--effort", provider.effort])
        if bypass_permissions:
            command.append("--dangerously-skip-permissions")
        if hook_config:
            command.extend(["--settings", json.dumps(_claude_hook_settings(hook_config))])
    else:  # Config validation should make this unreachable.
        raise ProviderError(f"unsupported provider: {provider.name}")

    if initial_prompt:
        command.append(initial_prompt)
    return command
