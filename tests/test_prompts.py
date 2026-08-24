from pathlib import Path

from autodev.config import load_project
from autodev.prompts import render_goal


def test_goal_is_generic_but_enforces_project_ownership(project_repo: Path) -> None:
    project = load_project(project_repo)
    prompt = render_goal(project, project.agent("backend"))

    assert "Sample Project" in prompt
    assert "src/backend/" in prompt
    assert "Modify only the owned write roots" in prompt
    assert "one canonical production path" in prompt
    assert "Treat raw source data as immutable" in prompt
    assert "Commit the verified work" in prompt
    assert "Spymaster" not in prompt
