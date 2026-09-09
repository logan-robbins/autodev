"""Create workspace manifests and interface-first Pillars without replacing user files."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from autodev.config import ConfigError, _id, load_project
from autodev.pillars import TEMPLATE_ROOT, agent_template, load_pillar

RESULT_SCHEMA = {
    "type": "object",
    "required": ["status", "summary", "evidence", "artifacts"],
    "additionalProperties": False,
    "properties": {
        "status": {"type": "string", "enum": ["completed", "blocked", "unavailable"]},
        "summary": {"type": "string", "minLength": 1},
        "evidence": {"type": "array", "items": {"type": "string", "minLength": 1}},
        "artifacts": {"type": "array", "items": {"type": "string", "minLength": 1}},
    },
}

STUB = '''"""Runnable interface fixture. Business functionality is explicitly unavailable."""
import argparse
import json
from pathlib import Path


def deliver():
    return json.loads((Path(__file__).parent / "fixtures/result.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = deliver()
    if args.check:
        assert result["status"] == "unavailable"
        assert result["summary"]
    else:
        print(json.dumps(result, indent=2))
'''


def create_workspace(
    root: Path, *, project_id: str, name: str, execution: str = "filesystem", ui_port: int = 8765
) -> Path:
    _id(project_id, "project.id")
    if execution not in {"filesystem", "git"}:
        raise ConfigError("execution must be filesystem or git")
    root = root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    descriptor = root / "autodev.toml"
    content = f"""schema_version = 1

[project]
id = {json.dumps(project_id)}
name = {json.dumps(name)}
execution = {json.dumps(execution)}
base_branch = "main"
instructions = "Honor Pillar boundaries and publish verified deliverables through their declared interfaces."
context_roots = []
verify_commands = []

[runtime]
session_pattern = "autodev-{{project}}-{{agent}}"
ui_port = {ui_port}
bypass_permissions = false
"""
    try:
        with descriptor.open("x", encoding="utf-8") as stream:
            stream.write(content)
    except FileExistsError as exc:
        raise ConfigError(f"workspace manifest already exists: {descriptor}") from exc
    try:
        load_project(descriptor)
    except Exception:
        descriptor.unlink()
        raise
    return descriptor


def create_pillar(
    workspace: Path,
    slug: str,
    *,
    summary: str,
    template: str = "generalist",
    provider: str = "codex",
    agent_id: str = "worker",
) -> Path:
    project = load_project(workspace)
    _id(slug, "pillar.slug")
    _id(agent_id, "agent.id")
    if not summary.strip():
        raise ConfigError("Pillar summary is required")
    destination = project.root / slug
    if destination.exists() or destination.is_symlink():
        raise ConfigError(
            f"Pillar destination already exists: {destination}; add pillar.toml manually to adopt existing content"
        )
    definition = agent_template(template, destination)
    if len(definition.get("deliverables", [])) != 1:
        raise ConfigError("scaffolding requires a template with one deliverable; author multi-output Pillars directly")
    delivery = {
        key: value.replace("{agent}", agent_id) if isinstance(value, str) else value
        for key, value in definition["deliverables"][0].items()
    }
    # Stage a complete valid boundary, then expose it in one rename.
    with tempfile.TemporaryDirectory(prefix="autodev-pillar-") as temporary:
        root = Path(temporary) / slug
        root.mkdir()
        (root / "schemas").mkdir()
        (root / "fixtures").mkdir()
        (root / "schemas/result.schema.json").write_text(json.dumps(RESULT_SCHEMA, indent=2) + "\n", encoding="utf-8")
        if template == "project-manager":
            shutil.copy2(TEMPLATE_ROOT / "schemas/task-plan.schema.json", root / "schemas/task-plan.schema.json")
        (root / "fixtures/result.json").write_text(
            json.dumps(
                (
                    {
                        "status": "unavailable",
                        "summary": "Interface fixture; no task plan has been produced.",
                        "tasks": [],
                    }
                    if template == "project-manager"
                    else {
                        "status": "unavailable",
                        "summary": "Interface fixture; implementation is not yet available.",
                        "evidence": [],
                        "artifacts": [],
                    }
                ),
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (root / "interface.py").write_text(STUB, encoding="utf-8")
        descriptor = root / "pillar.toml"
        descriptor.write_text(
            f"""schema_version = 1

[pillar]
slug = {json.dumps(slug)}
summary = {json.dumps(summary.strip())}
responsibility = {json.dumps(summary.strip())}

[interface]
state = "interface-ready"
consumption = "Run interface.py for the deterministic unavailable response while developing a consumer. Read the declared output after implementation and validation."
constraints = "Fixtures support interface development. They do not indicate that business functionality is available."
inputs = []
dependencies = []
checks = ["{{python}} interface.py --check"]

[[interface.outputs]]
id = {json.dumps(delivery["id"])}
path = {json.dumps(delivery["path"])}
format = {json.dumps(delivery["format"])}
schema = {json.dumps(delivery["schema"])}
fixture = "fixtures/result.json"
description = {json.dumps(delivery["description"])}

[[agents]]
id = {json.dumps(agent_id)}
template = {json.dumps(template)}
provider = {json.dumps(provider)}
write_roots = ["output/{agent_id}/"]
read_roots = ["schemas/", "fixtures/", "interface.py"]
""",
            encoding="utf-8",
        )
        pillar = load_pillar(root)
        from autodev.contracts import verify_pillar

        verify_pillar(pillar, interface_only=True)
        # A staging directory on the destination filesystem makes rename atomic.
        staging_root = project.root / ".autodev"
        staging_root.mkdir(exist_ok=True)
        staged = Path(tempfile.mkdtemp(prefix="pillar-", dir=staging_root))
        try:
            shutil.copytree(root, staged, dirs_exist_ok=True)
            staged.rename(destination)
        finally:
            if staged.exists():
                shutil.rmtree(staged)
    return destination / "pillar.toml"
