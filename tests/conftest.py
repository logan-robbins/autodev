from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from autodev.scaffold import create_pillar, create_workspace


def git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, check=True)


def populate(root: Path, *, execution: str) -> None:
    create_workspace(root, project_id="sample-project", name="Sample Project", execution=execution)
    (root / "README.md").write_text("# Sample\n", encoding="utf-8")
    for slug in ("backend", "frontend"):
        create_pillar(root, slug, summary=f"Own {slug} functionality.", template="engineer")
        descriptor = root / slug / "pillar.toml"
        descriptor.write_text(
            descriptor.read_text().replace(
                'write_roots = ["output/worker/"]', 'write_roots = ["output/worker/", "src/"]'
            )
        )
        (root / slug / "src").mkdir()
    (root / "backend/src/app.py").write_text("VALUE = 1\n")
    (root / "frontend/src/app.js").write_text("export const value = 1;\n")


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AUTODEV_HOME", str(tmp_path / "runtime"))


@pytest.fixture
def project_repo(tmp_path: Path) -> Path:
    root = tmp_path / "sample-project"
    root.mkdir()
    git(root, "init", "-b", "main")
    git(root, "config", "user.name", "Autodev Tests")
    git(root, "config", "user.email", "autodev@example.invalid")
    populate(root, execution="git")
    git(root, "add", ".")
    git(root, "commit", "-m", "Initial project")
    return root


@pytest.fixture
def file_project(tmp_path: Path) -> Path:
    root = tmp_path / "plain-project"
    populate(root, execution="filesystem")
    return root
