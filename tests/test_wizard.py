from __future__ import annotations

import subprocess
from pathlib import Path

from autodev.config import load_project
from autodev.wizard import run_setup_wizard


def test_wizard_writes_complete_descriptor_without_launching(
    project_repo: Path,
    monkeypatch,
) -> None:
    (project_repo / "autodev.toml").unlink()
    subprocess.run(
        ["git", "add", "autodev.toml"],
        cwd=project_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Remove prior descriptor"],
        cwd=project_repo,
        check=True,
        capture_output=True,
    )
    answers = iter(
        [
            "wizard-project",
            "Wizard Project",
            "main",
            "Honor the project architecture.",
            "README.md",
            "uv run pytest",
            "team_{provider}_{project}_{agent}",
            "8877",
            "backend",
            "codex",
            "Own the backend.",
            "Complete one verified backend task.",
            "src/backend/",
            "README.md",
            "",
            "codex",
            "",
            "",
            "",
            "",
            "n",
            "n",
        ]
    )
    output: list[str] = []
    monkeypatch.setenv("AUTODEV_HOME", str(project_repo.parent / "autodev-state"))

    result = run_setup_wizard(
        str(project_repo),
        input_fn=lambda _prompt: next(answers),
        output=output.append,
    )

    assert result.commit is True
    assert result.launch is False
    assert result.yolo is False
    assert result.start_ui is False
    assert result.project.id == "wizard-project"
    assert result.project.session_pattern == "team_{provider}_{project}_{agent}"
    assert result.project.ui_port == 8877
    assert result.project.providers["codex"].command == "codex"
    assert load_project(project_repo) == result.project
    assert any("Descriptor preview" in line for line in output)
