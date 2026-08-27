from __future__ import annotations

from pathlib import Path

import pytest

from autodev.config import load_project
from autodev.pods import PodError, materialize, pod_agent_id, select_member
from autodev.product import add_pillars

# A template-only company descriptor: four roles, a full pod, no [[agents]].
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
bypass_permissions = false

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
provider = "codex"
[pods.members.technical-writer]
provider = "claude"
"""


def _two_pillar_project(product_tree: Path):
    """product_tree already has pillar replay-engine; add a second, cold-store."""
    (product_tree / "autodev.toml").write_text(_TEMPLATE_ONLY, encoding="utf-8")
    project = load_project(product_tree)
    add_pillars(
        project,
        [
            {
                "id": "cold-store",
                "name": "Cold Store",
                "why": "w",
                "value": "v",
                "goal": "g",
                "approval": "proposed",
            }
        ],
    )
    return load_project(product_tree)


def test_materialize_stamps_bootstrap_pm_plus_one_pod_per_pillar(product_tree: Path) -> None:
    project = _two_pillar_project(product_tree)
    agents = materialize(project)
    ids = {a.id for a in agents}
    # product-level pm + {pm,pjm,eng,tw} per pillar (2 pillars) = 1 + 8.
    assert len(agents) == 9
    assert ids == {
        "pm",
        "pm-replay-engine",
        "pjm-replay-engine",
        "eng-replay-engine",
        "tw-replay-engine",
        "pm-cold-store",
        "pjm-cold-store",
        "eng-cold-store",
        "tw-cold-store",
    }


def test_materialize_derives_the_c_p5_roots(product_tree: Path) -> None:
    project = _two_pillar_project(product_tree)
    by_id = {a.id: a for a in materialize(project)}

    assert by_id["pm"].write_roots == ()
    assert by_id["pm"].read_roots == ("product/",)
    assert by_id["pm-replay-engine"].write_roots == ()  # verb-only
    assert by_id["pjm-replay-engine"].write_roots == ()  # verb-only
    assert by_id["eng-replay-engine"].write_roots == ("src/impl/replay-engine/", "tests/replay-engine/")
    assert by_id["tw-replay-engine"].write_roots == (
        "product/pillars/replay-engine/README.md",
        "product/pillars/replay-engine/TECHNICAL.md",
    )
    # provider comes from the pod member.
    assert by_id["eng-replay-engine"].provider == "codex"
    assert by_id["pm-replay-engine"].provider == "claude"


def test_materialize_write_roots_are_disjoint(product_tree: Path) -> None:
    # materialize runs _validate_ownership on the union; overlap would raise.
    project = _two_pillar_project(product_tree)
    write_roots = [root for a in materialize(project) for root in a.write_roots]
    assert len(write_roots) == len(set(write_roots))  # no duplicate ownership
    # cross-pillar impl roots are distinct.
    assert "src/impl/replay-engine/" in write_roots
    assert "src/impl/cold-store/" in write_roots


def test_materialize_without_pods_returns_static_agents(project_repo: Path) -> None:
    project = load_project(project_repo)  # only [[agents]] backend, no [pods]
    assert {a.id for a in materialize(project)} == {"backend"}


def test_select_member_and_pod_agent_id(product_tree: Path) -> None:
    project = _two_pillar_project(product_tree)
    assert select_member(project, "product-manager", None) == "pm"
    assert select_member(project, "project-manager", "replay-engine") == "pjm-replay-engine"
    assert select_member(project, "engineering", "cold-store") == "eng-cold-store"
    assert pod_agent_id("technical-writer", "replay-engine") == "tw-replay-engine"


def test_select_member_rejects_role_absent_from_template(product_tree: Path) -> None:
    project = _two_pillar_project(product_tree)
    with pytest.raises(PodError, match="no pod member"):
        select_member(project, "designer", "replay-engine")


def test_pod_agent_id_rejects_unknown_role() -> None:
    with pytest.raises(PodError, match="no pod abbreviation"):
        pod_agent_id("designer", "replay-engine")


def test_stamped_id_stays_within_the_id_form(product_tree: Path) -> None:
    # A 28-char pillar id yields eng-<28> = 32 chars, the boundary that fits _ID_RE.
    (product_tree / "autodev.toml").write_text(_TEMPLATE_ONLY, encoding="utf-8")
    project = load_project(product_tree)
    long_id = "a" + "b" * 27  # 28 chars
    add_pillars(
        project,
        [{"id": long_id, "name": "L", "why": "w", "value": "v", "goal": "g", "approval": "proposed"}],
    )
    ids = {a.id for a in materialize(load_project(product_tree))}
    assert f"eng-{long_id}" in ids
    assert len(f"eng-{long_id}") == 32
