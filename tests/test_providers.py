import json
from pathlib import Path

import pytest

from autodev import providers
from autodev.config import ProviderConfig
from autodev.providers import ProviderError, launch_command
from autodev.trace import hook_config


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


def test_claude_launch_injects_hooks_via_settings(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(providers, "executable_path", lambda _command: "/bin/claude")
    config = ProviderConfig(name="claude", command="claude")
    spec = hook_config("book-7", ["autodev"])

    command = launch_command(config, tmp_path, bypass_permissions=True, initial_prompt=None, hook_config=spec)

    assert "--settings" in command
    settings = json.loads(command[command.index("--settings") + 1])
    assert settings["hooks"]["PreToolUse"][0]["matcher"] == "Write|Edit"
    assert settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"] == "autodev policy check --run book-7"
    assert settings["hooks"]["PostToolUse"][0]["hooks"][0]["command"] == "autodev trace emit --run book-7"
    # PostToolUse folds every tool: no matcher narrows it.
    assert "matcher" not in settings["hooks"]["PostToolUse"][0]


def test_codex_launch_injects_hooks_via_config_overrides(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(providers, "executable_path", lambda _command: "/bin/codex")
    config = ProviderConfig(name="codex", command="codex")
    spec = hook_config("book-7", ["autodev"])

    command = launch_command(config, tmp_path, bypass_permissions=True, initial_prompt=None, hook_config=spec)

    assert "--dangerously-bypass-hook-trust" in command
    assert "features.hooks=true" in command
    pretool = next(arg for arg in command if arg.startswith("hooks.PreToolUse="))
    assert "autodev policy check --run book-7" in pretool


def test_launch_without_hook_config_is_unchanged(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(providers, "executable_path", lambda _command: "/bin/claude")
    config = ProviderConfig(name="claude", command="claude")
    command = launch_command(config, tmp_path, bypass_permissions=False, initial_prompt="go")
    assert command == ["/bin/claude", "go"]


def test_claude_appends_the_law_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(providers, "executable_path", lambda _command: "/bin/claude")
    config = ProviderConfig(name="claude", command="claude")
    law = tmp_path / "engineering.md"
    command = launch_command(config, tmp_path, bypass_permissions=False, initial_prompt=None, law_file=law)
    assert command == ["/bin/claude", "--append-system-prompt-file", str(law)]


def test_shipped_default_fires_skip_permissions(project_repo: Path, monkeypatch) -> None:
    # Unit 2: under the shipped default (bypass_permissions=true from Unit 1), a
    # Claude worker's launch command always carries --dangerously-skip-permissions.
    from autodev.config import load_project
    from autodev.templates import default_company_descriptor

    (project_repo / "autodev.toml").write_text(default_company_descriptor(), encoding="utf-8")
    project = load_project(project_repo)
    assert project.bypass_permissions is True  # Unit 1's default is wired through

    monkeypatch.setattr(providers, "executable_path", lambda _command: "/bin/claude")
    command = launch_command(
        project.providers["claude"],
        project_repo,
        bypass_permissions=project.bypass_permissions,
        initial_prompt=None,
    )
    assert "--dangerously-skip-permissions" in command


def test_codex_does_not_clobber_instructions_with_law(monkeypatch, tmp_path: Path) -> None:
    # Codex 0.147.0 has no safe append flag, so law_file must NOT add one.
    monkeypatch.setattr(providers, "executable_path", lambda _command: "/bin/codex")
    config = ProviderConfig(name="codex", command="codex")
    law = tmp_path / "engineering.md"
    command = launch_command(config, tmp_path, bypass_permissions=False, initial_prompt=None, law_file=law)
    assert command == ["/bin/codex", "--cd", str(tmp_path), "--no-alt-screen"]
    assert not any("instructions" in arg for arg in command)
