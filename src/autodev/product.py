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

import json
import re
import shutil
from collections.abc import Collection, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from autodev import trace
from autodev.config import _ID_RE, AgentConfig, ProjectConfig
from autodev.state import atomic_write_text, project_paths

PRODUCT_ROOT = ("product", "pillars")
# The cold-start vision seed sits beside the pillars directory.
PRODUCT_JSON = ("product", "product.json")

# The three standard roles; loop[].role must be one of the configured roles, and
# these are the fallback when a descriptor declares none (pre-schema-3).
DEFAULT_ROLES = ("product-manager", "project-manager", "engineering")

APPROVALS = frozenset({"proposed", "approved"})
LOOP_STATES = frozenset({"pending", "active", "done", "blocked"})
LEAF_STATUSES = frozenset({"pending", "in_progress", "verified", "blocked"})
PILLAR_DOCS = frozenset({"pending", "active", "done"})

# A pillar id is capped at 28 chars so a stamped pod id (``pjm-<pillar>`` /
# ``eng-<pillar>``, a 4-char prefix) still fits the shared _ID_RE 32-char limit.
_PILLAR_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,27}$")

_PILLAR_KEYS = frozenset({"id", "name", "why", "value", "goal", "approval", "docs"})
_PILLAR_REQUIRED = frozenset({"id", "name", "why", "value", "goal", "approval"})
_PRODUCT_KEYS = frozenset({"vision", "constraints"})
_PRODUCT_REQUIRED = frozenset({"vision"})

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


def _pillar_identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _PILLAR_ID_RE.fullmatch(value):
        raise ProductError(f"{label} must match {_PILLAR_ID_RE.pattern!r}; got {value!r}")
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


def validate_pillar(obj: Mapping[str, Any]) -> dict[str, Any]:
    """Return a normalised pillar dict or raise ``ProductError`` (fail-fast).

    ``pillar.json`` is the PM-owned artifact and the operator gate (contract
    C-P1): ``why``/``value``/``goal`` describe the area, ``approval`` is the
    human gate, and ``docs`` is the docs-last checkpoint. ``docs`` is optional
    and defaults to ``pending``.
    """
    pillar = _mapping(obj, "pillar")
    _reject_unknown(pillar, _PILLAR_KEYS, "pillar")
    _require(pillar, _PILLAR_REQUIRED, "pillar")
    return {
        "id": _pillar_identifier(pillar["id"], "pillar.id"),
        "name": _nonempty(pillar["name"], "pillar.name"),
        "why": _nonempty(pillar["why"], "pillar.why"),
        "value": _nonempty(pillar["value"], "pillar.value"),
        "goal": _nonempty(pillar["goal"], "pillar.goal"),
        "approval": _enum(pillar["approval"], APPROVALS, "pillar.approval"),
        "docs": _enum(pillar.get("docs", "pending"), PILLAR_DOCS, "pillar.docs"),
    }


def validate_product(obj: Mapping[str, Any]) -> dict[str, Any]:
    """Return a normalised product-vision dict or raise ``ProductError``.

    ``product/product.json`` (contract C-P2) is the cold-start seed the Product
    Manager reads to bootstrap the first pillars. It is operator-authored and
    read-only intent thereafter — no agent rewrites it.
    """
    data = _mapping(obj, "product")
    _reject_unknown(data, _PRODUCT_KEYS, "product")
    _require(data, _PRODUCT_REQUIRED, "product")
    vision = _nonempty(data["vision"], "product.vision")
    raw = data.get("constraints", [])
    if not isinstance(raw, (list, tuple)):
        raise ProductError("product.constraints must be a list of strings")
    constraints = [_nonempty(item, f"product.constraints[{index}]") for index, item in enumerate(raw)]
    return {"vision": vision, "constraints": constraints}


def product_json_path(project: ProjectConfig) -> Path:
    return project.root.joinpath(*PRODUCT_JSON)


def load_product_vision(project: ProjectConfig) -> dict[str, Any] | None:
    """Load and validate ``product/product.json``, or ``None`` when it is absent.

    Absence is a valid state (nothing to bootstrap yet); a present-but-malformed
    seed fails fast so a typo cannot silently disable cold-start.
    """
    path = product_json_path(project)
    if not path.is_file():
        return None
    return validate_product(json.loads(path.read_text(encoding="utf-8")))


# --- A1: enumeration ----------------------------------------------------------


@dataclass(frozen=True)
class PillarView:
    id: str
    pillar: dict  # the validated pillar.json (why/value/goal/approval/docs)
    features: tuple[dict, ...]


@dataclass(frozen=True)
class ProductTree:
    pillars: tuple[PillarView, ...]
    directories: dict[str, Path]

    def feature_dir(self, feature_id: str) -> Path:
        try:
            return self.directories[feature_id]
        except KeyError as exc:
            raise ProductError(f"unknown feature {feature_id!r}") from exc

    def feature(self, feature_id: str) -> dict:
        for pillar in self.pillars:
            for feature in pillar.features:
                if feature["id"] == feature_id:
                    return feature
        raise ProductError(f"unknown feature {feature_id!r}")

    def pillar(self, pillar_id: str) -> PillarView:
        for pillar in self.pillars:
            if pillar.id == pillar_id:
                return pillar
        raise ProductError(f"unknown pillar {pillar_id!r}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "pillars": [
                {"id": pillar.id, "pillar": pillar.pillar, "features": list(pillar.features)} for pillar in self.pillars
            ]
        }


def _roles_for(project: ProjectConfig) -> tuple[str, ...]:
    roles = getattr(project, "roles", None)
    if roles:
        return tuple(roles)
    return DEFAULT_ROLES


def product_root(project: ProjectConfig) -> Path:
    return project.root.joinpath(*PRODUCT_ROOT)


def enumerate_tree(project: ProjectConfig) -> ProductTree:
    """Discover pillars from ``pillar.json``, then nest their ``feature.json`` files.

    A pillar is the enumeration key (contract C-P1): globbing ``pillar.json``
    means a **feature-less pillar is still visible** — required for cold-start,
    where the Product Manager creates a pillar before any feature exists. Leaves
    are linked, not inlined (loaded on drill-down via :func:`load_leaf`).

    Fails fast on a broken tree: a pillar whose ``id`` disagrees with its
    directory, a duplicate pillar id, a feature under a directory with no
    ``pillar.json``, a feature whose ``pillar`` disagrees with its directory, a
    duplicate feature id, or a dangling/duplicated leaf ref.
    """
    roles = _roles_for(project)
    root = product_root(project)

    pillars_meta: dict[str, dict] = {}
    for pillar_path in sorted(root.glob("*/pillar.json")):
        pillar_dir = pillar_path.parent.name
        pillar = validate_pillar(json.loads(pillar_path.read_text(encoding="utf-8")))
        if pillar["id"] != pillar_dir:
            raise ProductError(f"{pillar_path}: pillar.id {pillar['id']!r} does not match directory {pillar_dir!r}")
        if pillar["id"] in pillars_meta:
            raise ProductError(f"duplicate pillar id {pillar['id']!r} in the product tree")
        pillars_meta[pillar["id"]] = pillar

    grouped: dict[str, list[dict]] = {pillar_id: [] for pillar_id in pillars_meta}
    directories: dict[str, Path] = {}
    for feature_path in sorted(root.glob("*/features/*/feature.json")):
        pillar_dir = feature_path.parents[2].name
        if pillar_dir not in pillars_meta:
            raise ProductError(f"{feature_path}: feature under pillar {pillar_dir!r} which has no pillar.json")
        feature = validate_feature(json.loads(feature_path.read_text(encoding="utf-8")), roles=roles)
        if feature["pillar"] != pillar_dir:
            raise ProductError(
                f"{feature_path}: feature.pillar {feature['pillar']!r} does not match directory {pillar_dir!r}"
            )
        feature_id = feature["id"]
        if feature_id in directories:
            raise ProductError(f"duplicate feature id {feature_id!r} in the product tree")
        directories[feature_id] = feature_path.parent
        for link in feature["leaves"]:
            if not (feature_path.parent / link["ref"]).is_file():
                raise ProductError(f"feature {feature_id!r} references missing leaf {link['ref']!r}")
        grouped[pillar_dir].append(feature)

    pillars = tuple(
        PillarView(
            id=pillar_id,
            pillar=pillars_meta[pillar_id],
            features=tuple(sorted(grouped[pillar_id], key=lambda f: f["id"])),
        )
        for pillar_id in sorted(pillars_meta)
    )
    return ProductTree(pillars=pillars, directories=directories)


def load_leaf(project: ProjectConfig, feature_id: str, ref: str) -> dict[str, Any]:
    """Follow one ``leaves[].ref`` and return the validated leaf (drill-down)."""
    directory = enumerate_tree(project).feature_dir(feature_id)
    checked = _relative_ref(ref, "leaf ref", suffix="leaf.json")
    path = directory / checked
    if not path.is_file():
        raise ProductError(f"feature {feature_id!r} has no leaf at {ref!r}")
    return validate_leaf(json.loads(path.read_text(encoding="utf-8")))


# --- A8: derive phase + join the live run -------------------------------------


@dataclass(frozen=True)
class FeatureView:
    feature: dict
    phase: str
    owner_role: str
    run: trace.RunView | None
    leaves: tuple[dict, ...]
    unmet_depends_on: tuple[tuple[str, str], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.feature,
            "phase": self.phase,
            "owner_role": self.owner_role,
            "run": asdict(self.run) if self.run is not None else None,
            "leaves": list(self.leaves),
            "unmet_depends_on": [list(edge) for edge in self.unmet_depends_on],
        }


def derive_phase(feature: Mapping[str, Any]) -> tuple[str, str]:
    """Derive (phase, owner_role) from ``loop[]`` — never stored (ethos 0.4).

    The active checkpoint is the phase; with none active the frontier is the
    first blocked-or-pending role, and an all-done loop is ``shipped``.
    """
    loop = feature["loop"]
    for entry in loop:
        if entry["s"] == "active":
            return entry["role"], entry["role"]
    if all(entry["s"] == "done" for entry in loop):
        return "shipped", loop[-1]["role"]
    for state in ("blocked", "pending"):
        for entry in loop:
            if entry["s"] == state:
                phase = "blocked" if state == "blocked" else entry["role"]
                return phase, entry["role"]
    return "shipped", loop[-1]["role"]


def _run_dir(project: ProjectConfig, run_ref: str) -> Path:
    return project_paths(project.id).home / run_ref


def join_run(project: ProjectConfig, feature: Mapping[str, Any]) -> FeatureView:
    """Join a feature with its live trace: derived phase + embedded RunView + leaves."""
    normalised = validate_feature(feature, roles=_roles_for(project))
    phase, owner_role = derive_phase(normalised)

    run = None
    if normalised["run_ref"]:
        run = trace.to_dag(trace.read_events(_run_dir(project, normalised["run_ref"])))

    leaves = tuple(load_leaf(project, normalised["id"], link["ref"]) for link in normalised["leaves"])
    verified = {leaf["id"] for leaf in leaves if leaf["status"] == "verified"}
    unmet = tuple((leaf["id"], dep) for leaf in leaves for dep in leaf["depends_on"] if dep not in verified)
    return FeatureView(
        feature=normalised,
        phase=phase,
        owner_role=owner_role,
        run=run,
        leaves=leaves,
        unmet_depends_on=unmet,
    )


# --- B4: typed state-mutation actions -----------------------------------------
# The only sanctioned way to change the tree (decision #3). Each validates
# against the C-2 schema and writes atomically, so a malformed payload raises
# before any file is touched.


def _write_json(path: Path, obj: Mapping[str, Any]) -> None:
    atomic_write_text(path, json.dumps(obj, indent=2) + "\n")


def _leaf_ref(leaf_id: str) -> str:
    return f"leaves/{leaf_id}/leaf.json"


def add_pillars(project: ProjectConfig, pillars: Sequence[Mapping[str, Any]]) -> list[Path]:
    """Create one ``pillar.json`` per spec (validate all, then write atomically).

    A bad payload anywhere in the batch raises before any file is written, so an
    invalid id (>28 chars) or missing field never leaves a half-written tree.
    """
    validated = [validate_pillar(spec) for spec in pillars]
    root = product_root(project)
    paths = []
    for pillar in validated:
        path = root / pillar["id"] / "pillar.json"
        _write_json(path, pillar)
        paths.append(path)
    return paths


def _default_feature_loop(project: ProjectConfig) -> list[dict[str, str]] | None:
    """The FEATURE loop a PM-emitted feature gets when the spec omits one.

    Stamped from ``[loop].sequence`` (PjM -> Eng -> PjM); the Product Manager
    and Technical Writer are pillar-level steps and are never feature-loop
    entries. ``None`` when no sequence is configured to default from.
    """
    if project.loop is None or not project.loop.sequence:
        return None
    return [{"role": role, "s": "pending"} for role in project.loop.sequence]


def add_features(project: ProjectConfig, pillar: str, features: Sequence[Mapping[str, Any]]) -> list[Path]:
    """Create one feature.json per spec under ``pillar`` (validate all, then write).

    When a spec omits ``loop``, it defaults to the feature loop stamped from
    ``[loop].sequence`` so a PM never has to hand-write the loop.
    """
    pillar = _identifier(pillar, "pillar")
    roles = _roles_for(project)
    default_loop = _default_feature_loop(project)
    validated = []
    for raw_spec in features:
        spec = dict(raw_spec)
        if spec.get("loop") is None:
            if default_loop is None:
                raise ProductError("feature spec omits loop and no [loop].sequence is configured to default from")
            spec["loop"] = [dict(entry) for entry in default_loop]
        feature = validate_feature(spec, roles=roles)
        if feature["pillar"] != pillar:
            raise ProductError(f"feature.pillar {feature['pillar']!r} does not match target pillar {pillar!r}")
        validated.append(feature)
    base = product_root(project) / pillar / "features"
    paths = []
    for feature in validated:
        path = base / feature["id"] / "feature.json"
        _write_json(path, feature)
        paths.append(path)
    return paths


def decompose_feature(project: ProjectConfig, feature_id: str, leaves: Sequence[Mapping[str, Any]]) -> list[Path]:
    """Write leaf.json files for ``feature_id`` and link them into its feature.json."""
    tree = enumerate_tree(project)
    directory = tree.feature_dir(feature_id)
    feature = tree.feature(feature_id)

    validated = []
    for spec in leaves:
        leaf = validate_leaf(spec)
        if leaf["feature"] != feature_id:
            raise ProductError(f"leaf.feature {leaf['feature']!r} does not match {feature_id!r}")
        validated.append(leaf)

    links = list(feature["leaves"])
    known = {link["id"] for link in links}
    for leaf in validated:
        if leaf["id"] not in known:
            links.append({"ref": _leaf_ref(leaf["id"]), "id": leaf["id"]})
            known.add(leaf["id"])
    for leaf in validated:
        for dep in leaf["depends_on"]:
            if dep not in known:
                raise ProductError(f"leaf {leaf['id']!r} depends_on {dep!r}, which is not a sibling leaf")

    updated_feature = validate_feature({**feature, "leaves": links}, roles=_roles_for(project))
    paths = []
    for leaf in validated:
        path = directory / _leaf_ref(leaf["id"])
        _write_json(path, leaf)
        paths.append(path)
    feature_path = directory / "feature.json"
    _write_json(feature_path, updated_feature)
    paths.append(feature_path)
    return paths


def set_leaf_status(project: ProjectConfig, feature_id: str, leaf_id: str, status: str) -> Path:
    """Set one leaf's status (validated, atomic)."""
    _enum(status, LEAF_STATUSES, "status")
    directory = enumerate_tree(project).feature_dir(feature_id)
    path = directory / _leaf_ref(leaf_id)
    if not path.is_file():
        raise ProductError(f"feature {feature_id!r} has no leaf {leaf_id!r}")
    leaf = validate_leaf(json.loads(path.read_text(encoding="utf-8")))
    _write_json(path, validate_leaf({**leaf, "status": status}))
    return path


def _rewrite_feature(project: ProjectConfig, feature_id: str, changes: Mapping[str, Any]) -> Path:
    directory = enumerate_tree(project).feature_dir(feature_id)
    path = directory / "feature.json"
    feature = validate_feature(json.loads(path.read_text(encoding="utf-8")), roles=_roles_for(project))
    _write_json(path, validate_feature({**feature, **changes}, roles=_roles_for(project)))
    return path


def set_run_ref(project: ProjectConfig, feature_id: str, run_id: str) -> Path:
    """Point a feature at its current run (``runs/<run_id>``)."""
    return _rewrite_feature(project, feature_id, {"run_ref": f"runs/{run_id}"})


def set_approval(project: ProjectConfig, feature_id: str, approval: str) -> Path:
    """Flip a feature's approval gate (the human control plane, decision #4)."""
    _enum(approval, APPROVALS, "approval")
    return _rewrite_feature(project, feature_id, {"approval": approval})


def _pillar_path(project: ProjectConfig, pillar: str) -> Path:
    return product_root(project) / pillar / "pillar.json"


def _rewrite_pillar(project: ProjectConfig, pillar: str, changes: Mapping[str, Any]) -> Path:
    path = _pillar_path(project, pillar)
    if not path.is_file():
        raise ProductError(f"unknown pillar {pillar!r}")
    current = validate_pillar(json.loads(path.read_text(encoding="utf-8")))
    _write_json(path, validate_pillar({**current, **changes}))
    return path


def set_pillar_approval(project: ProjectConfig, pillar: str, approval: str) -> Path:
    """Flip a pillar's approval gate (the operator control plane, contract C-P1)."""
    _enum(approval, APPROVALS, "pillar approval")
    return _rewrite_pillar(project, pillar, {"approval": approval})


def set_pillar_docs(project: ProjectConfig, pillar: str, state: str) -> Path:
    """Advance a pillar's docs-last checkpoint (pending -> active -> done)."""
    _enum(state, PILLAR_DOCS, "pillar docs state")
    return _rewrite_pillar(project, pillar, {"docs": state})


def set_loop_state(project: ProjectConfig, feature_id: str, role: str, state: str) -> Path:
    """Advance one role's loop checkpoint for a feature."""
    _enum(state, LOOP_STATES, "loop state")
    directory = enumerate_tree(project).feature_dir(feature_id)
    path = directory / "feature.json"
    feature = validate_feature(json.loads(path.read_text(encoding="utf-8")), roles=_roles_for(project))
    loop = feature["loop"]
    if not any(entry["role"] == role for entry in loop):
        raise ProductError(f"feature {feature_id!r} loop has no role {role!r}")
    new_loop = [{"role": e["role"], "s": state if e["role"] == role else e["s"]} for e in loop]
    _write_json(path, validate_feature({**feature, "loop": new_loop}, roles=_roles_for(project)))
    return path


# --- reset: clear the product, keep the company ------------------------------
# "Fire the staff and clear the product; keep the operating manual." The reset
# removes only Autodev's product tree and pod runtime state — it never touches
# ``autodev.toml`` (roles/personas, [loop], the [pods] template, providers), the
# operator skill, static [[agents]], or any other repository content.


@dataclass(frozen=True)
class ResetPlan:
    """What a product reset would clear (also the summary of what it cleared).

    ``repo_files`` are tracked files removed from the project working tree (left
    as ordinary uncommitted deletions for the operator to review — never
    auto-committed). ``runtime_dirs`` live under ``AUTODEV_HOME``. ``pod_worktrees``
    and ``pod_branches`` are the dynamically-materialised per-pillar pods
    (``<pm|pjm|eng|tw>-<pillar>``); static ``[[agents]]`` and the product-level
    ``pm`` bootstrap pod are never in this set.
    """

    repo_files: tuple[Path, ...]
    runtime_dirs: tuple[Path, ...]
    pod_worktrees: tuple[Path, ...]
    pod_branches: tuple[str, ...]

    @property
    def is_empty(self) -> bool:
        return not (self.repo_files or self.runtime_dirs or self.pod_worktrees or self.pod_branches)

    def as_dict(self) -> dict[str, Any]:
        return {
            "repo_files": [str(path) for path in self.repo_files],
            "runtime_dirs": [str(path) for path in self.runtime_dirs],
            "pod_worktrees": [str(path) for path in self.pod_worktrees],
            "pod_branches": list(self.pod_branches),
        }


def _dynamic_pods(project: ProjectConfig) -> list[AgentConfig]:
    """The per-pillar pods materialised over the pillars on disk (never static agents).

    ``pods.materialize`` is a pure function of ``(descriptor template, pillars on
    disk)``; a per-pillar pod is exactly one whose ``pod`` is set and whose id is
    not a declared static ``[[agents]]``. This excludes both static agents and the
    product-level ``pm`` bootstrap (``pod is None``).
    """
    from autodev import pods

    static_ids = {agent.id for agent in project.agents}
    return [agent for agent in pods.materialize(project) if agent.pod is not None and agent.id not in static_ids]


def plan_reset(project: ProjectConfig, *, home: Path | None = None) -> ResetPlan:
    """Compute what :func:`reset_product` would clear, without deleting anything."""
    from autodev import workspaces

    repo_files: list[Path] = []
    product_json = product_json_path(project)
    if product_json.is_file():
        repo_files.append(product_json)
    pillars_root = product_root(project)
    if pillars_root.exists():
        repo_files.extend(sorted(path for path in pillars_root.rglob("*") if path.is_file()))

    paths = project_paths(project.id, home=home)
    runtime_dirs = tuple(directory for directory in (paths.runs, paths.pods) if directory.exists())

    pod_worktrees: list[Path] = []
    pod_branches: list[str] = []
    for agent in _dynamic_pods(project):
        destination = workspaces.workspace_path(project, agent, home=home)
        branch = workspaces.workspace_branch(project, agent)
        if destination.exists():
            pod_worktrees.append(destination)
        if workspaces.branch_exists(project.root, branch):
            pod_branches.append(branch)

    return ResetPlan(
        repo_files=tuple(repo_files),
        runtime_dirs=runtime_dirs,
        pod_worktrees=tuple(pod_worktrees),
        pod_branches=tuple(pod_branches),
    )


def reset_product(project: ProjectConfig, *, home: Path | None = None) -> ResetPlan:
    """Clear the product tree and pod runtime state; keep the company (contract C-R1).

    Deletes, in order that keeps Git consistent:

    1. the dynamic per-pillar pod worktrees and branches (computed while the
       pillars still exist on disk),
    2. ``product/pillars/**`` and ``product/product.json`` from the working tree,
    3. ``runs/**`` and ``pods/**`` under ``AUTODEV_HOME``.

    Returns the plan captured *before* deletion (== what was cleared). Never
    touches ``autodev.toml``, the operator skill, static ``[[agents]]``, or any
    other repository content.
    """
    from autodev import workspaces

    plan = plan_reset(project, home=home)

    # Pods first: materialisation reads the pillars, so tear them down before the
    # tree is removed. Force-remove discards any unmerged pod work by design.
    for agent in _dynamic_pods(project):
        workspaces.remove_workspace(project, agent, home=home)

    pillars_root = product_root(project)
    if pillars_root.exists():
        shutil.rmtree(pillars_root)
    product_json_path(project).unlink(missing_ok=True)
    product_dir = project.root / PRODUCT_ROOT[0]
    if product_dir.is_dir() and not any(product_dir.iterdir()):
        product_dir.rmdir()

    paths = project_paths(project.id, home=home)
    for directory in (paths.runs, paths.pods):
        if directory.exists():
            shutil.rmtree(directory)

    return plan
