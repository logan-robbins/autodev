from __future__ import annotations

import json
from pathlib import Path

import pytest

from autodev.config import load_project
from autodev.product import (
    ProductError,
    enumerate_tree,
    load_leaf,
    validate_feature,
    validate_leaf,
)


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
