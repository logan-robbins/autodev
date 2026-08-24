from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from autodev.config import DEFAULT_SESSION_PATTERN
from autodev.templates import DescriptorAgent, render_full_descriptor


def git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=True,
    )


@pytest.fixture
def project_repo(tmp_path: Path) -> Path:
    root = tmp_path / "sample-project"
    root.mkdir()
    git(root, "init", "-b", "main")
    git(root, "config", "user.name", "Autodev Tests")
    git(root, "config", "user.email", "autodev@example.invalid")
    (root / "README.md").write_text("# Sample\n", encoding="utf-8")
    (root / "src" / "backend").mkdir(parents=True)
    (root / "src" / "backend" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "src" / "frontend").mkdir(parents=True)
    (root / "src" / "frontend" / "app.js").write_text("export const value = 1;\n", encoding="utf-8")
    (root / "autodev.toml").write_text(
        render_full_descriptor(
            project_id="sample-project",
            name="Sample Project",
            base_branch="main",
            instructions="Follow the repository architecture.",
            context_roots=(),
            verify_commands=(),
            session_pattern=DEFAULT_SESSION_PATTERN,
            ui_port=8765,
            agents=(
                DescriptorAgent(
                    id="backend",
                    provider="codex",
                    purpose="Own backend changes.",
                    goal="Complete one verified backend task.",
                    write_roots=("src/backend/",),
                ),
            ),
        ),
        encoding="utf-8",
    )
    git(root, "add", ".")
    git(root, "commit", "-m", "Initial project")
    return root
