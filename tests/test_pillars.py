import shutil
from pathlib import Path

import pytest

from autodev.config import ConfigError, load_project
from autodev.pillars import containing_pillar
from autodev.scaffold import create_pillar


def edit(root: Path, old: str, new: str):
    path = root / "backend/pillar.toml"
    path.write_text(path.read_text().replace(old, new))


def test_arbitrary_depth_inside_pillar_has_one_boundary(file_project: Path):
    path = file_project / "backend/a/b/c/d/result.json"
    assert containing_pillar(file_project, path) == file_project / "backend"


@pytest.mark.parametrize("destination", ["department/backend", "frontend/nested"])
def test_rejects_intermediate_and_nested_pillars(file_project: Path, destination: str):
    target = file_project / destination
    target.parent.mkdir(exist_ok=True)
    shutil.move(str(file_project / "backend"), str(target))
    with pytest.raises(ConfigError, match="direct children"):
        load_project(file_project)


def test_invalid_descriptor_keeps_declared_boundary(file_project: Path):
    (file_project / "backend/pillar.toml").write_text("invalid = [")
    assert containing_pillar(file_project, file_project / "backend/src/app.py") == file_project / "backend"
    with pytest.raises(ConfigError):
        load_project(file_project)


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ('slug = "backend"', 'slug = "other"', "must match"),
        ('template = "engineer"', 'template = "missing"', "cannot read"),
        ('provider = "codex"', 'provider = "unconfigured"', "provider"),
        ('schema = "schemas/result.schema.json"', 'schema = "../frontend/schemas/result.schema.json"', "relative path"),
        ("dependencies = []", 'dependencies = ["missing"]', "requires missing Pillar"),
        ("dependencies = []", 'dependencies = ["backend"]', "cannot depend on itself"),
        ("dependencies = []", 'dependencies = ["frontend", "frontend"]', "only once"),
        ('checks = ["{python} interface.py --check"]', "checks = []", "at least one"),
        ('write_roots = ["output/worker/", "src/"]', 'write_roots = ["../frontend/"]', "relative path"),
        ('write_roots = ["output/worker/", "src/"]', 'write_roots = ["output/worker/", "schemas/"]', "protected"),
    ],
)
def test_minimum_contract_is_enforced(file_project, old, new, message):
    edit(file_project, old, new)
    with pytest.raises(ConfigError, match=message):
        load_project(file_project)


def test_minimum_one_agent_without_pm(file_project: Path):
    path = file_project / "backend/pillar.toml"
    path.write_text(path.read_text().split("[[agents]]")[0])
    with pytest.raises(ConfigError, match="at least one Harness Agent"):
        load_project(file_project)


def test_pod_can_contain_multiple_template_instances(file_project: Path):
    path = file_project / "backend/pillar.toml"
    path.write_text(path.read_text() + '\n[[agents]]\nid = "reviewer"\ntemplate = "researcher"\nprovider = "claude"\n')
    pillar = load_project(file_project).pillar("backend")
    assert len(pillar.pod) == 2
    assert {a.template for a in pillar.pod} == {"engineer", "researcher"}


def test_agent_roots_cannot_overlap(file_project: Path):
    path = file_project / "backend/pillar.toml"
    path.write_text(
        path.read_text()
        + '\n[[agents]]\nid = "reviewer"\ntemplate = "researcher"\nprovider = "claude"\nwrite_roots = ["output/"]\n'
    )
    with pytest.raises(ConfigError, match="overlap"):
        load_project(file_project)


def test_symlink_cannot_move_a_boundary(file_project: Path, tmp_path: Path):
    shutil.move(str(file_project / "backend"), str(tmp_path / "outside"))
    (file_project / "backend").symlink_to(tmp_path / "outside", target_is_directory=True)
    with pytest.raises(ConfigError, match="symlink"):
        load_project(file_project)


def test_templates_and_schemas_stay_inside_pillar(file_project: Path):
    pillar = create_pillar(file_project, "planning", summary="Produce task plans.", template="project-manager")
    assert pillar == file_project / "planning/pillar.toml"
    assert (pillar.parent / "schemas/task-plan.schema.json").exists()
    assert load_project(file_project).pillar("planning").agents[0].deliverables[0].id == "task-plan"


def test_dependency_consumes_current_peer_output(file_project: Path):
    from autodev.workspaces import ensure_workspace

    edit(file_project, "dependencies = []", 'dependencies = ["frontend"]')
    output = file_project / "frontend/output/worker/result.json"
    output.parent.mkdir(parents=True)
    output.write_text('{"status": "completed", "summary": "Current output", "evidence": [], "artifacts": []}')
    project = load_project(file_project)
    consumer = project.agent("backend--worker")
    assert project.pillar("backend").dependencies == ("frontend",)
    workspace = ensure_workspace(project, consumer)
    consumed = workspace.path / "frontend/output/worker/result.json"
    assert consumed.read_text() == output.read_text()
    output.write_text('{"status": "completed", "summary": "Updated output", "evidence": [], "artifacts": []}')
    ensure_workspace(project, consumer)
    assert consumed.read_text() == output.read_text()
