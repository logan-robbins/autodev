from __future__ import annotations

from pathlib import Path

from autodev import trace
from autodev.config import LoopConfig, load_project
from autodev.orchestrator import ScheduleDecision, tick
from autodev.product import enumerate_tree, set_approval
from autodev.state import project_paths
from autodev.trace import new_event, read_events

_LIMITS = LoopConfig(sequence=(), reenter_product_manager_when=(), max_concurrent=4)


def _no_launch(_project, _decision) -> None:
    return None


def _proposed_feature(feature_id: str, pillar: str) -> dict:
    return {
        "id": feature_id,
        "pillar": pillar,
        "name": feature_id.title(),
        "approval": "proposed",
        "loop": [
            {"role": "product-manager", "s": "done"},
            {"role": "project-manager", "s": "pending"},
            {"role": "engineering", "s": "pending"},
        ],
        "run_ref": None,
        "leaves": [],
    }


def _leaf(leaf_id: str, feature_id: str, depends_on=()) -> dict:
    return {"id": leaf_id, "feature": feature_id, "status": "pending", "depends_on": list(depends_on)}


def test_tick_gates_a_proposed_feature(product_tree: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AUTODEV_HOME", str(tmp_path / "state"))
    project = load_project(product_tree)
    decisions = tick(project, limits=_LIMITS, launch=_no_launch)
    fast = next(d for d in decisions if d.node_id == "fast-ingest")
    assert fast.action == "gated"  # proposed -> never scheduled downstream


def test_tick_advances_active_role_when_its_run_is_finished(product_tree: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AUTODEV_HOME", str(tmp_path / "state"))
    project = load_project(product_tree)
    # certified-l3-book: loop [pm done, pjm done, eng active], run_ref runs/book-7.
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
    events = read_events(run_dir)
    changed = [e for e in events if e["type"] == "phase_changed"]
    assert changed and changed[-1]["from"] == "engineering" and changed[-1]["to"] == "shipped"


def test_tick_respects_max_concurrent(product_tree: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AUTODEV_HOME", str(tmp_path / "state"))
    project = load_project(product_tree)
    # certified-l3-book has an active engineering run in flight (no run_finished),
    # so one instance is already running; a limit of 1 blocks new scheduling.
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


def test_tick_expands_pillar_into_features_then_feature_into_leaves(
    project_repo: Path, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("AUTODEV_HOME", str(tmp_path / "state"))
    (project_repo / "product" / "pillars" / "new-engine").mkdir(parents=True)

    launched: list[ScheduleDecision] = []

    def fake_launch(proj, decision: ScheduleDecision) -> None:
        launched.append(decision)
        from autodev.product import add_features, decompose_feature

        run_dir = project_paths(proj.id).runs / decision.run_id
        if decision.level == "pillar" and decision.role == "product-manager":
            add_features(proj, decision.node_id, [_proposed_feature("cold-path", "new-engine")])
            trace.emit(run_dir, new_event("run_finished", status="done"))
        elif decision.role == "project-manager":
            decompose_feature(
                proj,
                decision.node_id,
                [_leaf("index", decision.node_id), _leaf("writer", decision.node_id, ["index"])],
            )
            trace.emit(run_dir, new_event("run_finished", status="done"))

    # Tick 1: an empty pillar schedules a Product-Manager pass, which authors a feature.
    tick(load_project(project_repo), limits=_LIMITS, launch=fake_launch)
    tree = enumerate_tree(load_project(project_repo))
    assert tree.feature("cold-path")["approval"] == "proposed"

    # Tick 2: the proposed feature is gated (not decomposed) until a human approves.
    decisions = tick(load_project(project_repo), limits=_LIMITS, launch=fake_launch)
    assert next(d for d in decisions if d.node_id == "cold-path").action == "gated"

    set_approval(load_project(project_repo), "cold-path", "approved")

    # Tick 3: now a Project-Manager pass is scheduled and decomposes the feature.
    decisions = tick(load_project(project_repo), limits=_LIMITS, launch=fake_launch)
    pjm = next(d for d in decisions if d.node_id == "cold-path" and d.role == "project-manager")
    assert pjm.action == "scheduled"

    feature = enumerate_tree(load_project(project_repo)).feature("cold-path")
    assert [link["id"] for link in feature["leaves"]] == ["index", "writer"]

    events = read_events(project_paths("sample-project", home=tmp_path / "state").runs / pjm.run_id)
    assert any(e["type"] == "phase_changed" for e in events)


def test_tick_default_launch_is_used_when_none_given(product_tree: Path, tmp_path: Path, monkeypatch) -> None:
    # With everything either gated or already terminal, the default launcher is
    # never invoked, so tick must not require tmux/providers here.
    monkeypatch.setenv("AUTODEV_HOME", str(tmp_path / "state"))
    project = load_project(product_tree)
    # certified-l3-book eng active + running (no finish) -> "running", fast-ingest proposed -> gated.
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
