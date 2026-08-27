from __future__ import annotations

from pathlib import Path

from autodev import trace
from autodev.config import LoopConfig, load_project
from autodev.orchestrator import ScheduleDecision, tick
from autodev.product import (
    add_features,
    add_pillars,
    decompose_feature,
    enumerate_tree,
    set_approval,
    set_leaf_status,
    set_pillar_approval,
)
from autodev.state import project_paths
from autodev.trace import new_event, read_events

_LIMITS = LoopConfig(sequence=(), reenter_product_manager_when=(), max_concurrent=4)


def _no_launch(_project, _decision) -> None:
    return None


def _approved_pillar(pillar_id: str) -> dict:
    return {
        "id": pillar_id,
        "name": pillar_id.replace("-", " ").title(),
        "why": "w",
        "value": "v",
        "goal": "g",
        "approval": "approved",
    }


def _feature_spec(feature_id: str, pillar: str, **overrides) -> dict:
    spec = {"id": feature_id, "pillar": pillar, "name": feature_id.title(), "approval": "proposed", "leaves": []}
    spec.update(overrides)
    return spec


# --- existing feature-loop behaviour (still holds under the new orchestrator) --


def test_tick_gates_a_proposed_feature(product_tree: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AUTODEV_HOME", str(tmp_path / "state"))
    project = load_project(product_tree)
    decisions = tick(project, limits=_LIMITS, launch=_no_launch)
    fast = next(d for d in decisions if d.node_id == "fast-ingest")
    assert fast.action == "gated"  # proposed feature -> never scheduled downstream


def test_tick_advances_active_role_when_its_run_is_finished(product_tree: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AUTODEV_HOME", str(tmp_path / "state"))
    project = load_project(product_tree)
    run_dir = project_paths(project.id).runs / "book-7"
    trace.emit(
        run_dir,
        new_event(
            "run_started",
            run_id="book-7",
            role="engineering",
            node_ref={"level": "feature", "pillar": "replay-engine", "feature": "certified-l3-book"},
            goal="g",
        ),
    )
    trace.emit(run_dir, new_event("run_finished", status="done"))

    decisions = tick(project, limits=_LIMITS, launch=_no_launch)
    book = next(d for d in decisions if d.node_id == "certified-l3-book")
    assert book.action == "advanced"

    feature = enumerate_tree(load_project(product_tree)).feature("certified-l3-book")
    assert [e["s"] for e in feature["loop"]] == ["done", "done", "done"]  # engineering now done
    changed = [e for e in read_events(run_dir) if e["type"] == "phase_changed"]
    assert changed and changed[-1]["from"] == "engineering" and changed[-1]["to"] == "shipped"


def test_tick_respects_max_concurrent(product_tree: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AUTODEV_HOME", str(tmp_path / "state"))
    project = load_project(product_tree)
    run_dir = project_paths(project.id).runs / "book-7"
    trace.emit(
        run_dir,
        new_event(
            "run_started",
            run_id="book-7",
            role="engineering",
            node_ref={"level": "feature", "pillar": "replay-engine", "feature": "certified-l3-book"},
            goal="g",
        ),
    )
    set_approval(project, "fast-ingest", "approved")

    limits = LoopConfig(sequence=(), reenter_product_manager_when=(), max_concurrent=1)
    decisions = tick(load_project(product_tree), limits=limits, launch=_no_launch)
    fast = next(d for d in decisions if d.node_id == "fast-ingest")
    assert fast.action == "at-capacity"


def test_tick_default_launch_is_used_when_none_given(product_tree: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AUTODEV_HOME", str(tmp_path / "state"))
    project = load_project(product_tree)
    run_dir = project_paths(project.id).runs / "book-7"
    trace.emit(
        run_dir,
        new_event(
            "run_started",
            run_id="book-7",
            role="engineering",
            node_ref={"level": "feature", "pillar": "replay-engine", "feature": "certified-l3-book"},
            goal="g",
        ),
    )
    decisions = tick(project, limits=_LIMITS)
    assert {d.action for d in decisions} <= {"running", "gated"}


# --- I1: cold-start step-0 ----------------------------------------------------


def test_tick_cold_starts_from_the_product_vision(bootstrap_repo: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AUTODEV_HOME", str(tmp_path / "state"))
    project = load_project(bootstrap_repo)
    launched: list[ScheduleDecision] = []
    decisions = tick(project, limits=_LIMITS, launch=lambda _p, d: launched.append(d))

    assert len(decisions) == 1
    cold = decisions[0]
    assert cold.level == "product"  # node_ref.level "product"
    assert cold.role == "product-manager"
    assert cold.agent == "pm"  # the product-level bootstrap pm
    assert cold.action == "scheduled"
    assert launched == [cold]
    events = read_events(project_paths(project.id).runs / cold.run_id)
    assert any(e["type"] == "run_started" and e["node_ref"]["level"] == "product" for e in events)


def test_tick_no_cold_start_without_a_vision(bootstrap_repo: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AUTODEV_HOME", str(tmp_path / "state"))
    (bootstrap_repo / "product" / "product.json").unlink()  # remove the vision
    project = load_project(bootstrap_repo)
    assert tick(project, limits=_LIMITS, launch=_no_launch) == []


# --- I2: pillar gate + expansion ---------------------------------------------


def test_tick_gates_a_proposed_pillar(product_tree: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AUTODEV_HOME", str(tmp_path / "state"))
    set_pillar_approval(load_project(product_tree), "replay-engine", "proposed")
    decisions = tick(load_project(product_tree), limits=_LIMITS, launch=_no_launch)
    pillar_dec = next(d for d in decisions if d.level == "pillar" and d.node_id == "replay-engine")
    assert pillar_dec.action == "gated"
    assert not any(d.level == "feature" for d in decisions)  # nothing downstream runs


def test_tick_schedules_pm_for_an_approved_empty_pillar(product_tree: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AUTODEV_HOME", str(tmp_path / "state"))
    add_pillars(load_project(product_tree), [_approved_pillar("cold-store")])
    launched: list[ScheduleDecision] = []
    decisions = tick(load_project(product_tree), limits=_LIMITS, launch=lambda _p, d: launched.append(d))
    cold = next(d for d in decisions if d.node_id == "cold-store")
    assert cold.action == "scheduled"
    assert cold.role == "product-manager"
    assert cold.agent == "pm-cold-store"  # the pillar-scoped PM


def test_tick_expands_pillar_then_gates_the_proposed_feature_until_approved(
    product_tree: Path, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("AUTODEV_HOME", str(tmp_path / "state"))
    add_pillars(load_project(product_tree), [_approved_pillar("cold-store")])
    launched: list[ScheduleDecision] = []

    def fake_launch(proj, decision: ScheduleDecision) -> None:
        launched.append(decision)
        run_dir = project_paths(proj.id).runs / decision.run_id
        if decision.level == "pillar" and decision.role == "product-manager":
            add_features(proj, decision.node_id, [_feature_spec("cold-path", "cold-store")])
            trace.emit(run_dir, new_event("run_finished", status="done"))
        elif decision.role == "project-manager":
            decompose_feature(
                proj,
                decision.node_id,
                [{"id": "index", "feature": decision.node_id, "status": "pending", "depends_on": []}],
            )
            trace.emit(run_dir, new_event("run_finished", status="done"))

    # Tick 1: the approved empty pillar schedules a PM pass, which authors a feature.
    tick(load_project(product_tree), limits=_LIMITS, launch=fake_launch)
    assert enumerate_tree(load_project(product_tree)).feature("cold-path")["approval"] == "proposed"

    # Tick 2: the proposed feature is gated until the operator approves it.
    decisions = tick(load_project(product_tree), limits=_LIMITS, launch=fake_launch)
    assert next(d for d in decisions if d.node_id == "cold-path").action == "gated"

    set_approval(load_project(product_tree), "cold-path", "approved")

    # Tick 3: an approved feature schedules its project-manager (pjm-<P>) pass.
    decisions = tick(load_project(product_tree), limits=_LIMITS, launch=fake_launch)
    pjm = next(d for d in decisions if d.node_id == "cold-path" and d.role == "project-manager")
    assert pjm.action == "scheduled"
    assert pjm.agent == "pjm-cold-store"
    assert [link["id"] for link in enumerate_tree(load_project(product_tree)).feature("cold-path")["leaves"]] == [
        "index"
    ]


# --- I3: deterministic pod-member selection drives PjM -> Eng ------------------


def test_feature_loop_launches_pjm_then_eng(product_tree: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AUTODEV_HOME", str(tmp_path / "state"))
    # an approved feature whose loop defaults to PjM -> Eng -> PjM.
    add_features(
        load_project(product_tree), "replay-engine", [_feature_spec("warm-path", "replay-engine", approval="approved")]
    )
    launched: list[ScheduleDecision] = []

    def fake_launch(proj, decision: ScheduleDecision) -> None:
        launched.append(decision)
        if decision.node_id == "warm-path":
            trace.emit(project_paths(proj.id).runs / decision.run_id, new_event("run_finished", status="done"))

    for _ in range(3):
        tick(load_project(product_tree), limits=_LIMITS, launch=fake_launch)

    warm = [d.agent for d in launched if d.node_id == "warm-path"]
    assert warm == ["pjm-replay-engine", "eng-replay-engine"]


# --- I4: docs-last gate -------------------------------------------------------


def _seed_shipped_pillar(project_root: Path) -> None:
    project = load_project(project_root)
    add_pillars(project, [_approved_pillar("ship-lane")])
    add_features(
        load_project(project_root),
        "ship-lane",
        [_feature_spec("only-feature", "ship-lane", approval="approved", loop=[{"role": "engineering", "s": "done"}])],
    )
    decompose_feature(
        load_project(project_root),
        "only-feature",
        [{"id": "core", "feature": "only-feature", "status": "pending", "depends_on": []}],
    )


def test_docs_last_gate_waits_for_verified_then_schedules_tw(product_tree: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AUTODEV_HOME", str(tmp_path / "state"))
    _seed_shipped_pillar(product_tree)

    # One leaf unverified -> docs gated (no Technical Writer yet).
    decisions = tick(load_project(product_tree), limits=_LIMITS, launch=_no_launch)
    gate = next(d for d in decisions if d.node_id == "ship-lane" and d.role == "technical-writer")
    assert gate.action == "gated"

    set_leaf_status(load_project(product_tree), "only-feature", "core", "verified")
    launched: list[ScheduleDecision] = []

    def fake_launch(proj, decision: ScheduleDecision) -> None:
        launched.append(decision)
        if decision.role == "technical-writer":
            trace.emit(project_paths(proj.id).runs / decision.run_id, new_event("run_finished", status="done"))

    # Now every feature is shipped and every leaf verified -> schedule tw-<P>, docs -> active.
    decisions = tick(load_project(product_tree), limits=_LIMITS, launch=fake_launch)
    tw = next(d for d in decisions if d.node_id == "ship-lane" and d.role == "technical-writer")
    assert tw.action == "scheduled"
    assert tw.agent == "tw-ship-lane"
    assert enumerate_tree(load_project(product_tree)).pillar("ship-lane").pillar["docs"] == "active"

    # The finished docs run flips pillar docs pending -> ... -> done.
    tick(load_project(product_tree), limits=_LIMITS, launch=fake_launch)
    assert enumerate_tree(load_project(product_tree)).pillar("ship-lane").pillar["docs"] == "done"
