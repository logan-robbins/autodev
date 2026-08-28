"""select_agents resolves against the one derived roster (pods.materialize)."""

from __future__ import annotations

from pathlib import Path

import pytest

from autodev.config import ConfigError, load_project
from autodev.operations import select_agents
from autodev.pods import materialize

# Template-only company descriptor: four roles, a full pod, no static [[agents]].
_TEMPLATE_ONLY = """schema_version = 3

[project]
id = "sample-project"
name = "Sample Project"
base_branch = "main"
instructions = "One canonical path."
context_roots = []
verify_commands = []

[runtime]
session_pattern = "autodev-{project}-{agent}"
ui_port = 8765
bypass_permissions = true

[loop]
sequence = ["project-manager", "engineering", "project-manager"]
reenter_product_manager_when = []
max_concurrent = 4

[roles.product-manager]
shape = "research"
charter = "Own the Pillar tier."
[roles.project-manager]
shape = "reconcile"
charter = "Own the Feature backlog."
[roles.engineering]
shape = "contract-first"
charter = "Own the Task."
[roles.technical-writer]
shape = "document"
charter = "Own the docs; run last."

[pods]
[pods.members.product-manager]
provider = "claude"
[pods.members.project-manager]
provider = "claude"
[pods.members.engineering]
provider = "claude"
[pods.members.technical-writer]
provider = "claude"
"""


def _template_project(product_tree: Path):
    (product_tree / "autodev.toml").write_text(_TEMPLATE_ONLY, encoding="utf-8")
    return load_project(product_tree)


def test_select_agents_returns_the_materialized_roster(product_tree: Path) -> None:
    """No ids → exactly the derived set (bootstrap pm + the pillar's pod), not static agents."""
    project = _template_project(product_tree)
    assert select_agents(project, []) == materialize(project)
    ids = {agent.id for agent in select_agents(project, [])}
    assert "pm" in ids  # the product-level bootstrap PM
    assert any("-" in agent_id for agent_id in ids)  # at least one stamped per-pillar pod member


def test_select_agents_filters_to_a_derived_pod_member(product_tree: Path) -> None:
    project = _template_project(product_tree)
    stamped = next(agent.id for agent in materialize(project) if "-" in agent.id)
    assert [agent.id for agent in select_agents(project, [stamped])] == [stamped]


def test_select_agents_rejects_unknown_against_the_derived_roster(product_tree: Path) -> None:
    project = _template_project(product_tree)
    with pytest.raises(ConfigError):
        select_agents(project, ["definitely-not-an-agent"])
