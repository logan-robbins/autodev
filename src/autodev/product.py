"""The product tree: schema, enumeration, and typed mutation.

Durable project intent is a tree of small JSON files inside the owning role's
write-roots:

    product/pillars/<pillar>/features/<feature>/feature.json   (enumerated)
      └─ leaves/<leaf>/leaf.json                                (drilled into)

``feature.json`` stores only ``loop[]`` checkpoints; ``phase`` and ``owner_role``
are *derived* (contract C-2, ethos "derive, don't store, what can drift"), joined
with the live run trace on drill-down. Every write goes through the typed actions
here so the schema is validated at the boundary, the way ``config.py`` validates
``autodev.toml``.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from pathlib import PurePosixPath
from typing import Any

from autodev.config import _ID_RE

# The three standard roles; loop[].role must be one of the configured roles, and
# these are the fallback when a descriptor declares none (pre-schema-3).
DEFAULT_ROLES = ("product-manager", "project-manager", "engineering")

APPROVALS = frozenset({"proposed", "approved"})
LOOP_STATES = frozenset({"pending", "active", "done", "blocked"})
LEAF_STATUSES = frozenset({"pending", "in_progress", "verified", "blocked"})

_FEATURE_KEYS = frozenset({"id", "pillar", "name", "approval", "loop", "run_ref", "leaves"})
_FEATURE_REQUIRED = frozenset({"id", "pillar", "name", "approval", "loop", "leaves"})
_LEAF_KEYS = frozenset({"id", "feature", "status", "pod", "contract_ref", "depends_on", "run_ref"})
_LEAF_REQUIRED = frozenset({"id", "feature", "status"})


class ProductError(ValueError):
    """Raised when a feature.json / leaf.json violates the tree schema."""


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ProductError(f"{label} must be an object")
    return dict(value)


def _reject_unknown(obj: Mapping[str, Any], allowed: Collection[str], label: str) -> None:
    unknown = sorted(set(obj) - set(allowed))
    if unknown:
        raise ProductError(f"{label} has unknown field(s): {', '.join(unknown)}")


def _require(obj: Mapping[str, Any], required: Collection[str], label: str) -> None:
    missing = sorted(set(required) - set(obj))
    if missing:
        raise ProductError(f"{label} is missing field(s): {', '.join(missing)}")


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise ProductError(f"{label} must match {_ID_RE.pattern!r}; got {value!r}")
    return value


def _nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProductError(f"{label} must be a non-empty string")
    return value


def _relative_ref(value: Any, label: str, *, suffix: str | None = None) -> str:
    if not isinstance(value, str) or not value:
        raise ProductError(f"{label} must be a relative path string")
    if "\\" in value:
        raise ProductError(f"{label} must use forward slashes: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or any(part in {"", "."} for part in path.parts):
        raise ProductError(f"{label} must be a relative path below the feature directory: {value!r}")
    if suffix and path.name != suffix:
        raise ProductError(f"{label} must point at {suffix}: {value!r}")
    return value


def _enum(value: Any, allowed: frozenset[str], label: str) -> str:
    if value not in allowed:
        raise ProductError(f"{label} must be one of {sorted(allowed)}; got {value!r}")
    return value


def validate_feature(obj: Mapping[str, Any], *, roles: Collection[str] = DEFAULT_ROLES) -> dict[str, Any]:
    """Return a normalised feature dict or raise ``ProductError`` (fail-fast)."""
    feature = _mapping(obj, "feature")
    _reject_unknown(feature, _FEATURE_KEYS, "feature")
    _require(feature, _FEATURE_REQUIRED, "feature")

    feature_id = _identifier(feature["id"], "feature.id")
    pillar = _identifier(feature["pillar"], "feature.pillar")
    name = _nonempty(feature["name"], "feature.name")
    approval = _enum(feature["approval"], APPROVALS, "feature.approval")

    raw_loop = feature["loop"]
    if not isinstance(raw_loop, (list, tuple)) or not raw_loop:
        raise ProductError("feature.loop must be a non-empty list of {role, s} checkpoints")
    role_set = set(roles)
    loop: list[dict[str, str]] = []
    for index, entry in enumerate(raw_loop):
        step = _mapping(entry, f"feature.loop[{index}]")
        _reject_unknown(step, {"role", "s"}, f"feature.loop[{index}]")
        _require(step, {"role", "s"}, f"feature.loop[{index}]")
        role = step["role"]
        if role not in role_set:
            raise ProductError(f"feature.loop[{index}].role {role!r} is not a configured role: {sorted(role_set)}")
        loop.append({"role": role, "s": _enum(step["s"], LOOP_STATES, f"feature.loop[{index}].s")})

    run_ref = feature.get("run_ref")
    if run_ref is not None:
        run_ref = _relative_ref(run_ref, "feature.run_ref")

    leaves: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, entry in enumerate(feature.get("leaves", [])):
        link = _mapping(entry, f"feature.leaves[{index}]")
        _reject_unknown(link, {"ref", "id"}, f"feature.leaves[{index}]")
        _require(link, {"ref", "id"}, f"feature.leaves[{index}]")
        leaf_id = _identifier(link["id"], f"feature.leaves[{index}].id")
        if leaf_id in seen:
            raise ProductError(f"feature.leaves has duplicate id {leaf_id!r}")
        seen.add(leaf_id)
        ref = _relative_ref(link["ref"], f"feature.leaves[{index}].ref", suffix="leaf.json")
        leaves.append({"ref": ref, "id": leaf_id})

    return {
        "id": feature_id,
        "pillar": pillar,
        "name": name,
        "approval": approval,
        "loop": loop,
        "run_ref": run_ref,
        "leaves": leaves,
    }


def validate_leaf(obj: Mapping[str, Any]) -> dict[str, Any]:
    """Return a normalised leaf dict or raise ``ProductError`` (fail-fast)."""
    leaf = _mapping(obj, "leaf")
    _reject_unknown(leaf, _LEAF_KEYS, "leaf")
    _require(leaf, _LEAF_REQUIRED, "leaf")

    leaf_id = _identifier(leaf["id"], "leaf.id")
    feature = _identifier(leaf["feature"], "leaf.feature")
    status = _enum(leaf["status"], LEAF_STATUSES, "leaf.status")

    pod = leaf.get("pod")
    if pod is not None:
        pod = _identifier(pod, "leaf.pod")
    contract_ref = leaf.get("contract_ref")
    if contract_ref is not None:
        contract_ref = _relative_ref(contract_ref, "leaf.contract_ref")
    run_ref = leaf.get("run_ref")
    if run_ref is not None:
        run_ref = _relative_ref(run_ref, "leaf.run_ref")

    raw_depends = leaf.get("depends_on", [])
    if not isinstance(raw_depends, (list, tuple)):
        raise ProductError("leaf.depends_on must be a list of sibling leaf ids")
    depends_on: list[str] = []
    for index, target in enumerate(raw_depends):
        dep = _identifier(target, f"leaf.depends_on[{index}]")
        if dep == leaf_id:
            raise ProductError(f"leaf {leaf_id!r} cannot depend on itself")
        depends_on.append(dep)

    return {
        "id": leaf_id,
        "feature": feature,
        "status": status,
        "pod": pod,
        "contract_ref": contract_ref,
        "depends_on": depends_on,
        "run_ref": run_ref,
    }
