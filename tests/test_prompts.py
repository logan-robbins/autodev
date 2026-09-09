from pathlib import Path

from autodev.config import load_project
from autodev.prompts import render_goal


def test_goal_is_generic_but_enforces_project_ownership(project_repo: Path) -> None:
    project = load_project(project_repo)
    prompt = render_goal(project, project.agent("backend--worker"))

    assert "Sample Project" in prompt
    assert "backend/src/" in prompt
    assert "Modify only the owned write roots" in prompt
    assert "Build and verify the interface first" in prompt
    assert "Treat raw source data as immutable" in prompt
    assert "Commit verified owned changes" in prompt
    assert "Spymaster" not in prompt
