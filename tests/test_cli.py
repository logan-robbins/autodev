from __future__ import annotations

import subprocess
from pathlib import Path

from autodev.cli import build_parser, main
from autodev.config import load_project
from autodev.wizard import WizardResult


def test_validate_prints_machine_readable_contract(project_repo: Path, capsys) -> None:
    assert main(["validate", str(project_repo), "--json"]) == 0
    output = capsys.readouterr().out
    assert '"id": "sample-project"' in output
    assert '"provider": "codex"' in output


def test_invalid_flag_combination_fails_fast(project_repo: Path, capsys) -> None:
    assert main(["ensure", str(project_repo), "--no-start", "--send-goal"]) == 1
    assert "cannot be combined" in capsys.readouterr().err


def test_setup_command_accepts_optional_project_path() -> None:
    args = build_parser().parse_args(["setup", "/tmp/example"])

    assert args.command == "setup"
    assert args.project == "/tmp/example"


def test_setup_registers_wizard_project_without_launching(
    project_repo: Path, tmp_path: Path, monkeypatch, capsys
) -> None:
    project = load_project(project_repo)
    state = tmp_path / "state"
    monkeypatch.setenv("AUTODEV_HOME", str(state))
    monkeypatch.setattr(
        "autodev.cli.run_setup_wizard",
        lambda selected: WizardResult(project=project, commit=False, launch=False, yolo=False, start_ui=False),
    )

    assert main(["setup", str(project_repo)]) == 0

    assert str(project.descriptor) in (state / "registry.json").read_text(encoding="utf-8")
    output = capsys.readouterr().out
    assert "registered sample-project" in output
    assert "launch later" in output


def test_setup_launches_all_agents_and_sends_goals(project_repo: Path, tmp_path: Path, monkeypatch, capsys) -> None:
    project = load_project(project_repo)
    monkeypatch.setenv("AUTODEV_HOME", str(tmp_path / "state"))
    monkeypatch.setattr(
        "autodev.cli.run_setup_wizard",
        lambda selected: WizardResult(project=project, commit=False, launch=True, yolo=True, start_ui=False),
    )
    captured: dict[str, object] = {}

    def fake_ensure(project_arg, agents, **options):
        captured.update(project=project_arg, agents=agents, options=options)
        return [
            {
                "agent": "backend",
                "worktree": "/tmp/backend",
                "branch": "autodev/sample-project/backend",
                "session_started": True,
                "goal_sent": True,
            }
        ]

    monkeypatch.setattr("autodev.cli.ensure_agents", fake_ensure)

    assert main(["setup", str(project_repo)]) == 0

    assert captured == {
        "project": project,
        "agents": project.agents,
        "options": {
            "base_ref": None,
            "start": True,
            "send_initial_goal": True,
            "yolo": True,
        },
    }
    assert "backend: started, goal sent" in capsys.readouterr().out


def test_setup_commits_new_descriptor_before_registration(project_repo: Path, tmp_path: Path, monkeypatch) -> None:
    descriptor = project_repo / "autodev.toml"
    descriptor.write_text(descriptor.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    project = load_project(project_repo)
    monkeypatch.setenv("AUTODEV_HOME", str(tmp_path / "state"))
    monkeypatch.setattr(
        "autodev.cli.run_setup_wizard",
        lambda selected: WizardResult(project=project, commit=True, launch=False, yolo=False, start_ui=False),
    )

    assert main(["setup", str(project_repo)]) == 0

    subject = subprocess.run(
        ["git", "log", "-1", "--format=%s"],
        cwd=project_repo,
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=project_repo,
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    ).stdout.strip()
    assert subject == "Configure Autodev"
    assert status == ""


def test_setup_starts_the_bound_project_ui(project_repo: Path, tmp_path: Path, monkeypatch) -> None:
    project = load_project(project_repo)
    monkeypatch.setenv("AUTODEV_HOME", str(tmp_path / "state"))
    monkeypatch.setattr(
        "autodev.cli.run_setup_wizard",
        lambda selected: WizardResult(project=project, commit=False, launch=False, yolo=False, start_ui=True),
    )
    served: list[object] = []
    monkeypatch.setattr("autodev.cli.serve_project", served.append)

    assert main(["setup", str(project_repo)]) == 0

    assert served == [project]
