from pathlib import Path

from autodev.wizard import run_setup_wizard


def test_wizard_creates_non_git_project_with_optional_task_manager(tmp_path: Path):
    answers = iter(
        [
            "research-project",
            "Research Project",
            "filesystem",
            "planning",
            "Plan research delivery.",
            "project-manager",
            "codex",
            "no",
            "no",
        ]
    )
    result = run_setup_wizard(
        str(tmp_path / "project"), input_fn=lambda prompt: next(answers), output=lambda line: None
    )
    assert result.project.execution == "filesystem"
    assert result.project.agent("planning--worker").template == "project-manager"
    assert not result.commit and not result.launch and not result.start_ui
