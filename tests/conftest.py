from __future__ import annotations

import json
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
            bypass_permissions=False,
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


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


@pytest.fixture
def product_tree(project_repo: Path) -> Path:
    """Seed a durable product tree under ``project_repo`` (intent only, no runs).

    A ``product/product.json`` vision seed and one **approved** pillar
    ``replay-engine`` (``pillar.json``) with two features:

    - ``certified-l3-book`` — approved, engineering active, two leaves whose
      ``store`` depends on an as-yet-unverified ``bucket`` (an unmet edge).
    - ``fast-ingest`` — proposed (the orchestrator must not schedule downstream
      roles on it), no leaves yet.
    """
    _write_json(
        project_repo / "product" / "product.json",
        {"vision": "Deterministic replay for market data.", "constraints": ["uv for Python"]},
    )
    pillars = project_repo / "product" / "pillars"
    _write_json(
        pillars / "replay-engine" / "pillar.json",
        {
            "id": "replay-engine",
            "name": "Replay Engine",
            "why": "Operators cannot reproduce a trading session deterministically.",
            "value": "Byte-exact replay of any historical session.",
            "goal": "A session replays to the same state every time.",
            "approval": "approved",
            "docs": "pending",
        },
    )
    features = pillars / "replay-engine" / "features"
    book = features / "certified-l3-book"
    _write_json(
        book / "feature.json",
        {
            "id": "certified-l3-book",
            "pillar": "replay-engine",
            "name": "Certified L3 book",
            "approval": "approved",
            "loop": [
                {"role": "product-manager", "s": "done"},
                {"role": "project-manager", "s": "done"},
                {"role": "engineering", "s": "active"},
            ],
            "run_ref": "runs/book-7",
            "leaves": [
                {"ref": "leaves/bucket/leaf.json", "id": "bucket"},
                {"ref": "leaves/store/leaf.json", "id": "store"},
            ],
        },
    )
    _write_json(
        book / "leaves" / "bucket" / "leaf.json",
        {
            "id": "bucket",
            "feature": "certified-l3-book",
            "status": "in_progress",
            "pod": "book",
            "contract_ref": "contracts/rate_limit.pyi",
            "depends_on": [],
            "run_ref": "runs/book-7",
        },
    )
    _write_json(
        book / "leaves" / "store" / "leaf.json",
        {
            "id": "store",
            "feature": "certified-l3-book",
            "status": "pending",
            "pod": "book",
            "contract_ref": "contracts/store.pyi",
            "depends_on": ["bucket"],
            "run_ref": None,
        },
    )
    _write_json(
        features / "fast-ingest" / "feature.json",
        {
            "id": "fast-ingest",
            "pillar": "replay-engine",
            "name": "Fast ingest",
            "approval": "proposed",
            "loop": [
                {"role": "product-manager", "s": "done"},
                {"role": "project-manager", "s": "pending"},
                {"role": "engineering", "s": "pending"},
            ],
            "run_ref": None,
            "leaves": [],
        },
    )
    return project_repo
