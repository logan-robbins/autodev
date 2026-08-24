"""Append-only run trace: event schema, writer, and deterministic reducer.

A *run* is one agent's pass over a single tree node. Its events live in
``AUTODEV_HOME/projects/<id>/runs/<run_id>/events.jsonl`` as append-only JSONL.
The schema is frozen here (contract C-1); every downstream view — the reducer
that folds events into a per-run DAG (``to_dag``), the ``?since`` cursor, and the
hook-config that makes workers emit — reads this one shape.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EVENTS_FILENAME = "events.jsonl"

EVENT_TYPES = frozenset(
    {
        "run_started",
        "step_declared",
        "step_started",
        "artifact_written",
        "step_finished",
        "run_finished",
        "phase_changed",
    }
)

# A step's shape. ``tool`` is the fold-to-noise kind: such steps never become
# DAG nodes, they only increment ``metrics.tool_calls`` (contract C-3, Layer 1).
STEP_KINDS = frozenset({"plan", "search", "contract", "implement", "integrate", "reconcile", "tool"})

_NODE_LEVELS = frozenset({"pillar", "feature", "leaf"})

# Correlation keys allowed on any event (present only when the source has them).
_COMMON_OPTIONAL = frozenset({"seq", "turn_id", "agent_id", "agent_type", "tool_use_id"})

# Required fields per event type, beyond the universal ``type`` and ``ts``.
_REQUIRED: dict[str, frozenset[str]] = {
    "run_started": frozenset({"run_id", "role", "node_ref", "goal"}),
    "step_declared": frozenset({"step_id", "parent", "kind", "objective", "inputs", "expects", "done_when", "agent"}),
    "step_started": frozenset({"step_id", "agent", "agent_type", "provider"}),
    "artifact_written": frozenset({"step_id", "artifact_id", "path", "sha", "kind", "meta"}),
    "step_finished": frozenset({"step_id", "status", "output_artifacts", "tokens"}),
    "run_finished": frozenset({"status"}),
    "phase_changed": frozenset({"node_ref", "from", "to", "reason"}),
}

# Optional fields per event type, beyond the common correlation keys.
_OPTIONAL: dict[str, frozenset[str]] = {
    "run_started": frozenset(),
    "step_declared": frozenset(),
    "step_started": frozenset(),
    "artifact_written": frozenset(),
    "step_finished": frozenset({"gloss"}),
    "run_finished": frozenset({"output_artifact"}),
    "phase_changed": frozenset(),
}


class TraceError(ValueError):
    """Raised when an event violates the frozen trace schema."""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _validate_node_ref(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TraceError(f"{label} must be an object with a level")
    level = value.get("level")
    if level not in _NODE_LEVELS:
        raise TraceError(f"{label}.level must be one of {sorted(_NODE_LEVELS)}; got {level!r}")
    return dict(value)


def validate_event(obj: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of ``obj`` if it satisfies the schema, else raise ``TraceError``.

    Rejects unknown top-level keys (fail-fast, mirroring ``config.py``) so a typo
    in an emitter cannot silently produce an event the reducer will ignore.
    """
    if not isinstance(obj, Mapping):
        raise TraceError("event must be an object")
    event_type = obj.get("type")
    if event_type not in EVENT_TYPES:
        raise TraceError(f"event.type must be one of {sorted(EVENT_TYPES)}; got {event_type!r}")
    if not isinstance(obj.get("ts"), str) or not obj["ts"]:
        raise TraceError(f"{event_type} event requires a non-empty ts")

    allowed = {"type", "ts"} | _COMMON_OPTIONAL | _REQUIRED[event_type] | _OPTIONAL[event_type]
    unknown = sorted(set(obj) - allowed)
    if unknown:
        raise TraceError(f"{event_type} event has unknown field(s): {', '.join(unknown)}")
    missing = sorted(_REQUIRED[event_type] - set(obj))
    if missing:
        raise TraceError(f"{event_type} event is missing field(s): {', '.join(missing)}")

    if "seq" in obj and (not isinstance(obj["seq"], int) or isinstance(obj["seq"], bool)):
        raise TraceError("event.seq must be an integer")
    if "node_ref" in obj:
        _validate_node_ref(obj["node_ref"], f"{event_type}.node_ref")
    if event_type == "step_declared":
        if obj["kind"] not in STEP_KINDS:
            raise TraceError(f"step_declared.kind must be one of {sorted(STEP_KINDS)}; got {obj['kind']!r}")
        if not isinstance(obj["inputs"], (list, tuple)):
            raise TraceError("step_declared.inputs must be a list")
    if event_type == "step_finished" and not isinstance(obj["output_artifacts"], (list, tuple)):
        raise TraceError("step_finished.output_artifacts must be a list")
    return dict(obj)


def new_event(event_type: str, /, **fields: Any) -> dict[str, Any]:
    """Build a validated event dict, stamping ``ts`` when the caller omits it.

    ``event_type`` is positional-only so an event may still carry its own
    ``kind`` field (e.g. ``new_event("step_declared", kind="plan", ...)``). The
    ``seq`` is assigned later by :func:`emit`, which owns the per-run counter.
    """
    fields.setdefault("ts", _utc_now())
    return validate_event({"type": event_type, **fields})


def read_events(run_dir: Path, *, since: int = 0) -> list[dict[str, Any]]:
    """Return the run's events (validated), keeping only ``seq > since``."""
    path = Path(run_dir) / EVENTS_FILENAME
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise TraceError(f"{path}:{number} is not valid JSON: {exc}") from exc
        event = validate_event(obj)
        if int(event.get("seq", 0)) > since:
            events.append(event)
    return events
