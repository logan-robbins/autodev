from pathlib import Path

import pytest

from autodev import providers
from autodev.config import ProviderConfig
from autodev.providers import ProviderError, launch_command


def test_codex_launch_uses_installed_cli_and_local_defaults(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(providers, "executable_path", lambda _command: "/usr/local/bin/codex")
    config = ProviderConfig(name="codex", command="codex")

    command = launch_command(config, tmp_path, bypass_permissions=False, initial_prompt="Do the work")

    assert command == [
        "/usr/local/bin/codex",
        "--cd",
        str(tmp_path),
        "--no-alt-screen",
        "Do the work",
    ]


def test_codex_launch_maps_explicit_model_effort_and_permission_bypass(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(providers, "executable_path", lambda _command: "/bin/codex")
    config = ProviderConfig(name="codex", command="codex", model="gpt-test", effort="high")
    command = launch_command(config, tmp_path, bypass_permissions=True, initial_prompt=None)

    assert command == [
        "/bin/codex",
        "--cd",
        str(tmp_path),
        "--no-alt-screen",
        "--model",
        "gpt-test",
        "--config",
        'model_reasoning_effort="high"',
        "--dangerously-bypass-approvals-and-sandbox",
    ]


def test_claude_launch_maps_installed_cli_flags(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(providers, "executable_path", lambda _command: "/bin/claude")
    config = ProviderConfig(name="claude", command="claude", model="sonnet", effort="xhigh")
    command = launch_command(config, tmp_path, bypass_permissions=True, initial_prompt="Ship it")

    assert command == [
        "/bin/claude",
        "--model",
        "sonnet",
        "--effort",
        "xhigh",
        "--dangerously-skip-permissions",
        "Ship it",
    ]


def test_missing_provider_fails_fast(monkeypatch) -> None:
    monkeypatch.setattr(providers.shutil, "which", lambda _command: None)
    with pytest.raises(ProviderError, match="not installed or not on PATH"):
        providers.executable_path("codex")
