from __future__ import annotations

from pathlib import Path

from autodev.config import DEFAULT_SESSION_PATTERN, SCHEMA_VERSION, load_project
from autodev.templates import (
    DescriptorAgent,
    DescriptorLoop,
    DescriptorRole,
    render_full_descriptor,
)


def _render(**overrides) -> str:
    kwargs = dict(
        project_id="sample-project",
        name="Sample Project",
        base_branch="main",
        instructions="Follow the repository architecture.",
        context_roots=(),
        verify_commands=("uv run pytest",),
        session_pattern=DEFAULT_SESSION_PATTERN,
        ui_port=8765,
        bypass_permissions=False,
        agents=(
            DescriptorAgent(
                id="backend",
                provider="codex",
                pod="backend",
                purpose="Own backend changes.",
                goal="Complete one verified backend task.",
                write_roots=("src/backend/",),
            ),
        ),
    )
    kwargs.update(overrides)
    return render_full_descriptor(**kwargs)


def test_render_emits_current_schema_version() -> None:
    assert f"schema_version = {SCHEMA_VERSION}" in _render()


def test_render_emits_agent_pod() -> None:
    assert 'pod = "backend"' in _render()


def test_render_loop_and_roles_round_trip_through_load(project_repo: Path) -> None:
    descriptor = _render(
        loop=DescriptorLoop(
            sequence=("project-manager", "engineering", "project-manager"),
            reenter_product_manager_when=("new-requirement",),
            max_concurrent=2,
        ),
        roles=(
            DescriptorRole(id="product-manager", shape="research", charter="Own a Pillar."),
            DescriptorRole(id="project-manager", shape="reconcile", charter="Own a Feature."),
            DescriptorRole(id="engineering", shape="contract-first", charter="Own a Leaf."),
        ),
    )
    (project_repo / "autodev.toml").write_text(descriptor, encoding="utf-8")

    project = load_project(project_repo)
    assert project.loop is not None
    assert project.loop.sequence == ("project-manager", "engineering", "project-manager")
    assert project.loop.max_concurrent == 2
    assert project.roles["engineering"].shape == "contract-first"
    assert project.agent("backend").pod == "backend"


def test_render_without_optional_tables_still_loads(project_repo: Path) -> None:
    (project_repo / "autodev.toml").write_text(
        _render(
            agents=(
                DescriptorAgent(
                    id="backend",
                    provider="codex",
                    purpose="Own backend changes.",
                    goal="Complete one verified backend task.",
                    write_roots=("src/backend/",),
                ),
            )
        ),
        encoding="utf-8",
    )
    project = load_project(project_repo)
    assert project.loop is None
    assert project.roles == {}
    assert project.agent("backend").pod is None
