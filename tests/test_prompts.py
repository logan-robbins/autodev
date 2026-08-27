from pathlib import Path

from autodev.config import AgentConfig, LoopConfig, RoleConfig, load_project
from autodev.prompts import compose_law, render_goal, render_identity


def test_goal_is_generic_but_enforces_project_ownership(project_repo: Path) -> None:
    project = load_project(project_repo)
    prompt = render_goal(project, project.agent("backend"))

    assert "Sample Project" in prompt
    assert "src/backend/" in prompt
    assert "Modify only the owned write roots" in prompt
    assert "one canonical production path" in prompt
    assert "Treat raw source data as immutable" in prompt
    assert "Commit the verified work" in prompt
    assert "Spymaster" not in prompt


# --- B2: law composer + role/shape-aware goal --------------------------------

_PM = RoleConfig(id="product-manager", shape="research", charter="Own a Pillar; emit Features.")
_ENG = RoleConfig(id="engineering", shape="contract-first", charter="Own a Leaf; red tests first.")
_PJM = RoleConfig(id="project-manager", shape="reconcile", charter="Own a Feature; split into leaves.")
_TW = RoleConfig(id="technical-writer", shape="document", charter="Own the docs; run last.")
_LOOP = LoopConfig(
    sequence=("project-manager", "engineering"),
    reenter_product_manager_when=("new-requirement",),
    max_concurrent=4,
)


def test_compose_law_research_shape_frames_fan_in() -> None:
    law = compose_law(_LOOP, _PM)
    assert "fan out" in law and "fan the facts back in" in law
    assert "Own a Pillar" in law


def test_compose_law_contract_first_shape_puts_red_tests_first() -> None:
    law = compose_law(_LOOP, _ENG)
    assert "red" in law and "tests before any internals" in law


def test_compose_law_carries_typed_write_and_approval_rules() -> None:
    law = compose_law(_LOOP, _PJM)
    assert "autodev product" in law
    assert "proposed" in law
    assert "project-manager -> engineering" in law


def test_render_goal_without_role_is_the_generic_goal(project_repo: Path) -> None:
    project = load_project(project_repo)
    prompt = render_goal(project, project.agent("backend"))
    assert "Role law:" not in prompt


def test_render_goal_for_engineering_includes_its_charter(project_repo: Path) -> None:
    project = load_project(project_repo)
    prompt = render_goal(project, project.agent("backend"), role=_ENG)
    assert "Role law:" in prompt
    assert "Own a Leaf; red tests first." in prompt
    assert "contract-first" in prompt


# --- H1: the document shape (technical-writer) -------------------------------


def test_compose_law_document_shape_is_data_flow_first() -> None:
    law = compose_law(_LOOP, _TW)
    assert "data-flow-first" in law
    assert "a -> b -> c" in law
    assert "Never edit source" in law


def test_render_goal_for_technical_writer_includes_document_framing(project_repo: Path) -> None:
    project = load_project(project_repo)
    prompt = render_goal(project, project.agent("backend"), role=_TW)
    assert "data-flow-first" in prompt


# --- H2: shared operator law + pod-memory rule -------------------------------


def test_compose_law_embeds_the_shared_operator_law() -> None:
    law = compose_law(_LOOP, _ENG)
    assert "input -> output -> unit test -> integration test" in law
    assert "written last" in law
    assert "red before green" in law


def test_compose_law_carries_the_pod_memory_rule() -> None:
    law = compose_law(_LOOP, _PJM)
    assert "autodev pod remember" in law
    assert "read it before acting" in law


def test_engineering_law_has_contract_first_and_operator_law() -> None:
    law = compose_law(_LOOP, _ENG)
    assert "tests before any internals" in law  # contract-first shape persona
    assert "One canonical path" in law  # operator law


# --- Unit 4a: the fixed per-agent identity block -----------------------------

_ENG_AGENT = AgentConfig(
    id="eng-replay-engine",
    provider="claude",
    purpose="p",
    goal="g",
    write_roots=("src/impl/replay-engine/", "tests/replay-engine/"),
    read_roots=("contracts/", "product/pillars/replay-engine/features/"),
    pod="replay-engine",
)


def test_render_identity_names_who_and_where() -> None:
    text = render_identity(
        agent=_ENG_AGENT,
        role="engineering",
        project_id="acme",
        session_name="autodev-acme-eng-replay-engine",
        worktree="/state/acme/worktrees/eng-replay-engine",
        pod_memory_path="/state/acme/pods/replay-engine/memory.jsonl",
    )
    assert "eng-replay-engine" in text  # agent id
    assert "engineering" in text  # role
    assert "provider: claude" in text  # provider
    assert "autodev-acme-eng-replay-engine" in text  # session name
    assert "/state/acme/worktrees/eng-replay-engine" in text  # worktree = only writable checkout
    assert "src/impl/replay-engine/" in text  # a write root
    assert "contracts/" in text  # shared contracts pointer
    assert "/state/acme/pods/replay-engine/memory.jsonl" in text  # pod-memory pointer
    assert "fixed for this session" in text  # identity is stable
    assert "re-injected" in text  # notes the charter rides the hook


def test_render_identity_is_deterministic() -> None:
    kwargs = dict(
        agent=_ENG_AGENT,
        role="engineering",
        project_id="acme",
        session_name="s",
        worktree="/w",
        pod_memory_path="/m",
    )
    assert render_identity(**kwargs) == render_identity(**kwargs)


def test_render_identity_omits_pod_memory_when_product_level() -> None:
    pm = AgentConfig(
        id="pm",
        provider="claude",
        purpose="p",
        goal="g",
        write_roots=(),
        read_roots=("product/",),
        pod=None,
    )
    text = render_identity(
        agent=pm,
        role="product-manager",
        project_id="acme",
        session_name="autodev-acme-pm",
        worktree="/w",
        pod_memory_path=None,
    )
    assert "pod remember" not in text  # no pod-memory line for a product-level agent
    assert "product-level" in text
    assert "verb-only" in text  # no write roots -> verb-only note
