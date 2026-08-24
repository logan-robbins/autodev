from __future__ import annotations

import json
from pathlib import Path

import pytest

from autodev.product import ProductError, validate_feature, validate_leaf


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
