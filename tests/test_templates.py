from __future__ import annotations

from pathlib import Path

from autodev.config import DEFAULT_SESSION_PATTERN, SCHEMA_VERSION, load_project
from autodev.templates import (
    DescriptorAgent,
    DescriptorLoop,
    DescriptorPodMember,
    DescriptorPods,
    DescriptorRole,
    default_company_descriptor,
    default_product_json,
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


def test_render_emits_pods_template(project_repo: Path) -> None:
    descriptor = _render(
        agents=(),
        roles=(DescriptorRole(id="engineering", shape="contract-first", charter="Own a Leaf."),),
        pods=DescriptorPods(members=(DescriptorPodMember(role="engineering", provider="codex"),)),
    )
    (project_repo / "autodev.toml").write_text(descriptor, encoding="utf-8")
    project = load_project(project_repo)
    assert project.agents == ()
    assert project.pods is not None
    assert project.pods.members["engineering"].provider == "codex"


# --- K4: the default company scaffold ----------------------------------------


def test_default_company_descriptor_loads_as_schema_3(project_repo: Path) -> None:
    (project_repo / "autodev.toml").write_text(default_company_descriptor(), encoding="utf-8")
    project = load_project(project_repo)
    assert f"schema_version = {SCHEMA_VERSION}" in default_company_descriptor()
    assert project.agents == ()  # template-only: pods are derived per pillar
    assert set(project.roles) == {"product-manager", "project-manager", "engineering", "technical-writer"}
    assert project.pods is not None
    assert set(project.pods.members) == {"product-manager", "project-manager", "engineering", "technical-writer"}
    assert project.pods.members["engineering"].provider == "codex"
    assert project.loop is not None
    assert project.loop.sequence == ("project-manager", "engineering", "project-manager")


def test_default_product_json_validates() -> None:
    import json

    from autodev.product import validate_product

    data = json.loads(default_product_json("build a deterministic replay engine"))
    assert validate_product(data)["vision"] == "build a deterministic replay engine"


# --- K5: examples/autodev.toml is the schema-3 company scaffold ---------------


def test_examples_autodev_toml_is_the_company_scaffold(project_repo: Path) -> None:
    # examples/autodev.toml lives one level up from tests/; it is the canonical
    # schema-3 company scaffold emitted by default_company_descriptor().
    example = Path(__file__).resolve().parents[1] / "examples" / "autodev.toml"
    content = example.read_text(encoding="utf-8")
    assert "schema_version = 3" in content
    assert content == default_company_descriptor()
    # a descriptor must load from a git worktree root, so load a copy at one.
    (project_repo / "autodev.toml").write_text(content, encoding="utf-8")
    project = load_project(project_repo)
    assert set(project.roles) == {"product-manager", "project-manager", "engineering", "technical-writer"}
    assert project.pods is not None and len(project.pods.members) == 4


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
