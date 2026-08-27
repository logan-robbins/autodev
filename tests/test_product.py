from __future__ import annotations

import json
from pathlib import Path

import pytest

from autodev import trace
from autodev.config import load_project
from autodev.product import (
    ProductError,
    add_features,
    add_pillars,
    decompose_feature,
    derive_phase,
    enumerate_tree,
    join_run,
    load_leaf,
    load_product_vision,
    product_json_path,
    set_approval,
    set_leaf_status,
    set_loop_state,
    set_run_ref,
    validate_feature,
    validate_leaf,
    validate_pillar,
    validate_product,
)
from autodev.state import project_paths
from autodev.trace import new_event


def _feature(**overrides) -> dict:
    base = {
        "id": "certified-l3-book",
        "pillar": "replay-engine",
        "name": "Certified L3 book",
        "approval": "approved",
        "loop": [
            {"role": "product-manager", "s": "done"},
            {"role": "engineering", "s": "active"},
        ],
        "run_ref": "runs/book-7",
        "leaves": [{"ref": "leaves/bucket/leaf.json", "id": "bucket"}],
    }
    base.update(overrides)
    return base


def _leaf(**overrides) -> dict:
    base = {
        "id": "store",
        "feature": "certified-l3-book",
        "status": "in_progress",
        "pod": "book",
        "contract_ref": "contracts/store.pyi",
        "depends_on": ["bucket"],
        "run_ref": None,
    }
    base.update(overrides)
    return base


def test_validate_feature_normalises_valid() -> None:
    result = validate_feature(_feature())
    assert result["id"] == "certified-l3-book"
    assert result["loop"][1] == {"role": "engineering", "s": "active"}
    assert result["leaves"][0]["ref"] == "leaves/bucket/leaf.json"


def test_validate_feature_allows_null_run_ref() -> None:
    assert validate_feature(_feature(run_ref=None))["run_ref"] is None


def test_validate_feature_rejects_unknown_key() -> None:
    with pytest.raises(ProductError, match="unknown field"):
        validate_feature(_feature(phase="engineering"))


def test_validate_feature_rejects_unconfigured_role() -> None:
    with pytest.raises(ProductError, match="not a configured role"):
        validate_feature(_feature(loop=[{"role": "designer", "s": "active"}]))


def test_validate_feature_rejects_bad_loop_state() -> None:
    with pytest.raises(ProductError, match="feature.loop\\[0\\].s"):
        validate_feature(_feature(loop=[{"role": "engineering", "s": "cooking"}]))


def test_validate_feature_rejects_bad_approval() -> None:
    with pytest.raises(ProductError, match="feature.approval"):
        validate_feature(_feature(approval="maybe"))


def test_validate_feature_rejects_absolute_leaf_ref() -> None:
    with pytest.raises(ProductError, match="relative path"):
        validate_feature(_feature(leaves=[{"ref": "/etc/passwd", "id": "bucket"}]))


def test_validate_feature_rejects_leaf_ref_escape() -> None:
    with pytest.raises(ProductError, match="below the feature directory"):
        validate_feature(_feature(leaves=[{"ref": "../../other/leaf.json", "id": "bucket"}]))


def test_validate_feature_rejects_ref_not_leaf_json() -> None:
    with pytest.raises(ProductError, match="must point at leaf.json"):
        validate_feature(_feature(leaves=[{"ref": "leaves/bucket/config.json", "id": "bucket"}]))


def test_validate_feature_rejects_duplicate_leaf_id() -> None:
    with pytest.raises(ProductError, match="duplicate id"):
        validate_feature(
            _feature(
                leaves=[
                    {"ref": "leaves/a/leaf.json", "id": "bucket"},
                    {"ref": "leaves/b/leaf.json", "id": "bucket"},
                ]
            )
        )


def test_validate_leaf_normalises_valid() -> None:
    result = validate_leaf(_leaf())
    assert result["depends_on"] == ["bucket"]
    assert result["status"] == "in_progress"


def test_validate_leaf_rejects_bad_status() -> None:
    with pytest.raises(ProductError, match="leaf.status"):
        validate_leaf(_leaf(status="cooking"))


def test_validate_leaf_rejects_bad_depends_on_entry() -> None:
    with pytest.raises(ProductError, match="leaf.depends_on"):
        validate_leaf(_leaf(depends_on=["Bad Id!"]))


def test_validate_leaf_rejects_self_dependency() -> None:
    with pytest.raises(ProductError, match="cannot depend on itself"):
        validate_leaf(_leaf(depends_on=["store"]))


def test_validate_leaf_rejects_unknown_key() -> None:
    with pytest.raises(ProductError, match="unknown field"):
        validate_leaf(_leaf(priority="high"))


# --- D0: pillar.json schema --------------------------------------------------


def _pillar(**overrides) -> dict:
    base = {
        "id": "replay-engine",
        "name": "Replay Engine",
        "why": "the problem",
        "value": "the value",
        "goal": "the outcome",
        "approval": "proposed",
    }
    base.update(overrides)
    return base


def test_validate_pillar_normalises_valid_and_defaults_docs() -> None:
    result = validate_pillar(_pillar())
    assert result["id"] == "replay-engine"
    assert result["approval"] == "proposed"
    assert result["docs"] == "pending"  # optional, defaults pending


def test_validate_pillar_rejects_unknown_key() -> None:
    with pytest.raises(ProductError, match="unknown field"):
        validate_pillar(_pillar(owner="pm"))


def test_validate_pillar_rejects_bad_approval() -> None:
    with pytest.raises(ProductError, match="pillar.approval"):
        validate_pillar(_pillar(approval="maybe"))


def test_validate_pillar_rejects_bad_docs() -> None:
    with pytest.raises(ProductError, match="pillar.docs"):
        validate_pillar(_pillar(docs="written"))


def test_validate_pillar_rejects_missing_required() -> None:
    payload = _pillar()
    del payload["goal"]
    with pytest.raises(ProductError, match="missing field"):
        validate_pillar(payload)


def test_validate_pillar_rejects_id_over_28_chars() -> None:
    # 29 chars — one over the cap that keeps stamped pod ids within _ID_RE's 32.
    with pytest.raises(ProductError, match="pillar.id"):
        validate_pillar(_pillar(id="a" + "b" * 28))


def test_validate_pillar_accepts_id_at_28_chars() -> None:
    assert validate_pillar(_pillar(id="a" + "b" * 27))["id"] == "a" + "b" * 27


def test_seeded_pillar_json_validates(product_tree: Path) -> None:
    path = product_tree / "product" / "pillars" / "replay-engine" / "pillar.json"
    pillar = validate_pillar(json.loads(path.read_text(encoding="utf-8")))
    assert pillar["id"] == "replay-engine"
    assert pillar["approval"] == "approved"


# --- D0b: product.json vision seed -------------------------------------------


def test_validate_product_normalises_valid() -> None:
    result = validate_product({"vision": "build X for Y", "constraints": ["stdlib only"]})
    assert result == {"vision": "build X for Y", "constraints": ["stdlib only"]}


def test_validate_product_defaults_constraints_to_empty() -> None:
    assert validate_product({"vision": "build X"})["constraints"] == []


def test_validate_product_rejects_missing_vision() -> None:
    with pytest.raises(ProductError, match="missing field"):
        validate_product({"constraints": []})


def test_validate_product_rejects_unknown_key() -> None:
    with pytest.raises(ProductError, match="unknown field"):
        validate_product({"vision": "x", "roadmap": []})


def test_load_product_vision_reads_the_seed(product_tree: Path) -> None:
    project = load_project(product_tree)
    vision = load_product_vision(project)
    assert vision is not None
    assert vision["vision"].startswith("Deterministic replay")
    assert product_json_path(project).is_file()


def test_load_product_vision_is_none_when_absent(project_repo: Path) -> None:
    assert load_product_vision(load_project(project_repo)) is None


def test_seeded_product_tree_validates_end_to_end(product_tree: Path) -> None:
    feature_files = sorted((product_tree / "product").rglob("feature.json"))
    assert len(feature_files) == 2
    for path in feature_files:
        feature = validate_feature(json.loads(path.read_text(encoding="utf-8")))
        for link in feature["leaves"]:
            leaf_path = path.parent / link["ref"]
            validate_leaf(json.loads(leaf_path.read_text(encoding="utf-8")))


# --- A1: enumeration ----------------------------------------------------------


def test_enumerate_groups_features_by_pillar(product_tree: Path) -> None:
    tree = enumerate_tree(load_project(product_tree))
    assert [p.id for p in tree.pillars] == ["replay-engine"]
    feature_ids = [f["id"] for f in tree.pillars[0].features]
    assert feature_ids == ["certified-l3-book", "fast-ingest"]  # sorted by id


def test_enumerate_resolves_feature_dir_for_drill_down(product_tree: Path) -> None:
    tree = enumerate_tree(load_project(product_tree))
    directory = tree.feature_dir("certified-l3-book")
    assert (directory / "feature.json").is_file()
    assert tree.feature("certified-l3-book")["approval"] == "approved"


def test_enumerate_as_dict_is_json_serialisable(product_tree: Path) -> None:
    payload = enumerate_tree(load_project(product_tree)).as_dict()
    json.dumps(payload)  # must not raise
    assert payload["pillars"][0]["features"][0]["loop"][0]["role"] == "product-manager"


def test_enumerate_fails_fast_on_missing_leaf_ref(product_tree: Path) -> None:
    book = product_tree / "product" / "pillars" / "replay-engine" / "features" / "certified-l3-book"
    (book / "leaves" / "store" / "leaf.json").unlink()
    with pytest.raises(ProductError, match="missing leaf"):
        enumerate_tree(load_project(product_tree))


def test_enumerate_fails_fast_on_pillar_dir_mismatch(product_tree: Path) -> None:
    book = product_tree / "product" / "pillars" / "replay-engine" / "features" / "certified-l3-book"
    feature = json.loads((book / "feature.json").read_text(encoding="utf-8"))
    feature["pillar"] = "some-other-pillar"
    (book / "feature.json").write_text(json.dumps(feature), encoding="utf-8")
    with pytest.raises(ProductError, match="does not match directory"):
        enumerate_tree(load_project(product_tree))


def test_load_leaf_follows_ref_lazily(product_tree: Path) -> None:
    project = load_project(product_tree)
    leaf = load_leaf(project, "certified-l3-book", "leaves/store/leaf.json")
    assert leaf["id"] == "store"
    assert leaf["depends_on"] == ["bucket"]


# --- A8: derive phase + join run ---------------------------------------------


def test_derive_phase_is_the_active_role() -> None:
    feature = {
        "loop": [
            {"role": "product-manager", "s": "done"},
            {"role": "project-manager", "s": "done"},
            {"role": "engineering", "s": "active"},
        ]
    }
    assert derive_phase(feature) == ("engineering", "engineering")


def test_derive_phase_shipped_when_all_done() -> None:
    feature = {"loop": [{"role": "product-manager", "s": "done"}, {"role": "engineering", "s": "done"}]}
    assert derive_phase(feature) == ("shipped", "engineering")


def test_derive_phase_frontier_when_none_active() -> None:
    feature = {
        "loop": [
            {"role": "product-manager", "s": "done"},
            {"role": "project-manager", "s": "pending"},
            {"role": "engineering", "s": "pending"},
        ]
    }
    assert derive_phase(feature) == ("project-manager", "project-manager")


def test_join_run_without_run_ref_derives_phase_only(product_tree: Path) -> None:
    project = load_project(product_tree)
    feature = enumerate_tree(project).feature("fast-ingest")
    view = join_run(project, feature)
    assert view.phase == "project-manager"  # pm done, pjm pending
    assert view.run is None


def test_join_run_embeds_live_run_and_unmet_edges(product_tree: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AUTODEV_HOME", str(tmp_path / "state"))
    project = load_project(product_tree)
    # Seed the run the feature points at (feature.run_ref == "runs/book-7").
    run_dir = project_paths(project.id).runs / "book-7"
    trace.emit(
        run_dir,
        new_event(
            "run_started",
            run_id="book-7",
            role="engineering",
            node_ref={"level": "feature", "pillar": "replay-engine", "feature": "certified-l3-book"},
            goal="build",
        ),
    )
    trace.emit(
        run_dir,
        new_event(
            "step_declared",
            step_id="impl",
            parent=None,
            kind="implement",
            objective="build store",
            inputs=[],
            expects="",
            done_when="",
            agent="book",
        ),
    )
    trace.emit(
        run_dir, new_event("step_started", step_id="impl", agent="book", agent_type="implement", provider="claude")
    )

    feature = enumerate_tree(project).feature("certified-l3-book")
    view = join_run(project, feature)

    assert view.phase == "engineering"
    assert view.run is not None
    assert view.run.active_step_id == "impl"
    # store depends on bucket, which is not verified -> an unmet edge.
    assert ("store", "bucket") in view.unmet_depends_on
    # the whole view serialises for the API.
    import json as _json

    _json.dumps(view.as_dict())


# --- E1: add_pillars ---------------------------------------------------------


def test_add_pillars_writes_valid_pillar_json(product_tree: Path) -> None:
    project = load_project(product_tree)
    paths = add_pillars(
        project,
        [
            {
                "id": "fast-lane",
                "name": "Fast Lane",
                "why": "ingest is too slow",
                "value": "sub-second ingest",
                "goal": "p99 ingest under 1s",
                "approval": "proposed",
            }
        ],
    )
    assert paths[0].is_file()
    written = validate_pillar(json.loads(paths[0].read_text(encoding="utf-8")))
    assert written["id"] == "fast-lane"
    assert written["approval"] == "proposed"
    assert written["docs"] == "pending"


def test_add_pillars_writes_nothing_on_invalid_payload(product_tree: Path) -> None:
    project = load_project(product_tree)
    good = {
        "id": "good-pillar",
        "name": "Good",
        "why": "w",
        "value": "v",
        "goal": "g",
        "approval": "proposed",
    }
    bad = {**good, "id": "bad-pillar", "approval": "maybe"}
    with pytest.raises(ProductError):
        add_pillars(project, [good, bad])
    assert not (product_tree / "product" / "pillars" / "good-pillar").exists()


# --- B4: typed state-mutation actions ----------------------------------------


def _new_feature(feature_id: str, *, approval: str = "proposed") -> dict:
    return {
        "id": feature_id,
        "pillar": "replay-engine",
        "name": feature_id.replace("-", " ").title(),
        "approval": approval,
        "loop": [
            {"role": "product-manager", "s": "done"},
            {"role": "project-manager", "s": "pending"},
            {"role": "engineering", "s": "pending"},
        ],
        "run_ref": None,
        "leaves": [],
    }


def test_add_features_writes_valid_feature_json(product_tree: Path) -> None:
    project = load_project(product_tree)
    paths = add_features(project, "replay-engine", [_new_feature("cold-storage")])

    assert paths[0].is_file()
    tree = enumerate_tree(project)
    assert tree.feature("cold-storage")["approval"] == "proposed"


def test_add_features_rejects_invalid_payload_before_writing(product_tree: Path) -> None:
    project = load_project(product_tree)
    bad = _new_feature("bad-one")
    bad["approval"] = "maybe"
    with pytest.raises(ProductError):
        add_features(project, "replay-engine", [_new_feature("good-one"), bad])
    features = product_tree / "product" / "pillars" / "replay-engine" / "features"
    assert not (features / "good-one").exists()  # nothing written on a bad batch


def test_decompose_feature_writes_leaves_and_links_them(product_tree: Path) -> None:
    project = load_project(product_tree)
    add_features(project, "replay-engine", [_new_feature("cold-storage")])
    leaves = [
        {"id": "index", "feature": "cold-storage", "status": "pending", "depends_on": []},
        {"id": "writer", "feature": "cold-storage", "status": "pending", "depends_on": ["index"]},
    ]
    decompose_feature(project, "cold-storage", leaves)

    feature = enumerate_tree(project).feature("cold-storage")
    assert [link["id"] for link in feature["leaves"]] == ["index", "writer"]
    assert load_leaf(project, "cold-storage", "leaves/writer/leaf.json")["depends_on"] == ["index"]


def test_decompose_rejects_dependency_on_non_sibling(product_tree: Path) -> None:
    project = load_project(product_tree)
    add_features(project, "replay-engine", [_new_feature("cold-storage")])
    with pytest.raises(ProductError, match="not a sibling leaf"):
        decompose_feature(
            project,
            "cold-storage",
            [{"id": "writer", "feature": "cold-storage", "status": "pending", "depends_on": ["ghost"]}],
        )


def test_set_leaf_status_updates_atomically(product_tree: Path) -> None:
    project = load_project(product_tree)
    set_leaf_status(project, "certified-l3-book", "bucket", "verified")
    assert load_leaf(project, "certified-l3-book", "leaves/bucket/leaf.json")["status"] == "verified"


def test_set_run_ref_and_approval_and_loop_state(product_tree: Path) -> None:
    project = load_project(product_tree)
    set_run_ref(project, "fast-ingest", "ingest-3")
    set_approval(project, "fast-ingest", "approved")
    set_loop_state(project, "fast-ingest", "project-manager", "active")

    feature = enumerate_tree(project).feature("fast-ingest")
    assert feature["run_ref"] == "runs/ingest-3"
    assert feature["approval"] == "approved"
    assert derive_phase(feature) == ("project-manager", "project-manager")


def test_set_loop_state_rejects_unknown_role(product_tree: Path) -> None:
    project = load_project(product_tree)
    with pytest.raises(ProductError, match="no role"):
        set_loop_state(project, "fast-ingest", "designer", "active")
