"""Append-only run trace: event schema, writer, and deterministic reducer.

A *run* is one agent's pass over a single tree node. Its events live in
``AUTODEV_HOME/projects/<id>/runs/<run_id>/events.jsonl`` as append-only JSONL.
The schema is frozen here (contract C-1); every downstream view — the reducer
that folds events into a per-run DAG (``to_dag``), the ``?since`` cursor, and the
hook-config that makes workers emit — reads this one shape.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
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


def _next_seq(run_dir: Path) -> int:
    highest = 0
    for event in read_events(run_dir):
        highest = max(highest, int(event.get("seq", 0)))
    return highest + 1


def emit(run_dir: Path, event: Mapping[str, Any]) -> int:
    """Append one validated event line and return its monotonic ``seq``.

    A run has a single writer (one agent's pass), so the sequence is assigned by
    reading the current maximum and incrementing — no lock is needed. The line
    is flushed and fsync'd so a crash cannot leave a torn trace.
    """
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    seq = _next_seq(run_dir)
    stamped = validate_event({**event, "seq": seq})
    line = json.dumps(stamped, ensure_ascii=False) + "\n"
    path = run_dir / EVENTS_FILENAME
    with open(path, "a", encoding="utf-8") as stream:
        stream.write(line)
        stream.flush()
        os.fsync(stream.fileno())
    return seq


@dataclass(frozen=True)
class StageNode:
    step_id: str
    kind: str
    status: str  # declared | running | done | failed  (verify -> red | green)
    parent: str | None
    inputs: tuple[str, ...]  # -> edges; fan-in when more than one resolves
    agent: str | None
    agent_type: str | None
    tokens: int | None
    gloss: str | None
    artifacts: tuple[str, ...]


@dataclass(frozen=True)
class RunView:
    run_id: str
    role: str
    node_ref: dict
    status: str  # running | done | failed
    nodes: tuple[StageNode, ...]  # topologically ordered
    edges: tuple[tuple[str, str], ...]
    metrics: dict
    active_step_id: str | None


@dataclass
class _WorkingNode:
    step_id: str
    kind: str
    status: str
    parent: str | None
    inputs: tuple[str, ...]
    agent: str | None = None
    agent_type: str | None = None
    tokens: int | None = None
    gloss: str | None = None
    artifacts: list[str] = field(default_factory=list)


def _topo_order(step_ids: list[str], edges: list[tuple[str, str]]) -> list[str]:
    """Kahn's algorithm; declaration order breaks ties and survives cycles."""
    position = {step_id: index for index, step_id in enumerate(step_ids)}
    indegree = {step_id: 0 for step_id in step_ids}
    successors: dict[str, list[str]] = {step_id: [] for step_id in step_ids}
    for src, dst in edges:
        if src in indegree and dst in indegree:
            successors[src].append(dst)
            indegree[dst] += 1
    ready = sorted((s for s in step_ids if indegree[s] == 0), key=position.get)
    ordered: list[str] = []
    while ready:
        current = ready.pop(0)
        ordered.append(current)
        for successor in successors[current]:
            indegree[successor] -= 1
            if indegree[successor] == 0:
                ready.append(successor)
        ready.sort(key=position.get)
    if len(ordered) != len(step_ids):  # cycle: keep the rest in declaration order
        ordered.extend(s for s in step_ids if s not in set(ordered))
    return ordered


def to_dag(events: Iterable[Mapping[str, Any]]) -> RunView:
    """Fold a run's events into a ``RunView`` (Layer 1: pure, replay-stable).

    Stage steps (``kind`` != ``tool``) become nodes; every ``tool`` step folds
    into ``metrics.tool_calls`` only. Edges derive from each step's ``inputs``,
    resolved against prior step ids and artifact ids — more than one resolved
    input is a fan-in, one source feeding several is a fan-out.
    """
    ordered_events = sorted(events, key=lambda e: int(e.get("seq", 0)))
    run_id = ""
    role = ""
    node_ref: dict = {}
    run_status = "running"
    metrics = {"tool_calls": 0, "tokens": 0}

    nodes: dict[str, _WorkingNode] = {}
    tool_steps: set[str] = set()
    artifact_producer: dict[str, str] = {}
    started_order: list[str] = []

    for event in ordered_events:
        kind = event.get("type")
        if kind == "run_started":
            run_id = event["run_id"]
            role = event["role"]
            node_ref = dict(event["node_ref"])
        elif kind == "run_finished":
            run_status = event["status"]
        elif kind == "step_declared":
            step_id = event["step_id"]
            if event["kind"] == "tool":
                tool_steps.add(step_id)
                metrics["tool_calls"] += 1
                continue
            nodes[step_id] = _WorkingNode(
                step_id=step_id,
                kind=event["kind"],
                status="declared",
                parent=event.get("parent"),
                inputs=tuple(event["inputs"]),
                agent=event.get("agent"),
            )
        elif kind == "step_started":
            step_id = event["step_id"]
            if step_id in nodes:
                node = nodes[step_id]
                node.status = "running"
                node.agent = event.get("agent", node.agent)
                node.agent_type = event.get("agent_type", node.agent_type)
                started_order.append(step_id)
        elif kind == "artifact_written":
            artifact_id = event["artifact_id"]
            artifact_producer.setdefault(artifact_id, event["step_id"])
            node = nodes.get(event["step_id"])
            if node is not None:
                node.artifacts.append(artifact_id)
        elif kind == "step_finished":
            step_id = event["step_id"]
            tokens = event.get("tokens")
            if isinstance(tokens, int) and not isinstance(tokens, bool):
                metrics["tokens"] += tokens
            for artifact_id in event.get("output_artifacts", []):
                artifact_producer.setdefault(artifact_id, step_id)
            if step_id in tool_steps:
                continue
            node = nodes.get(step_id)
            if node is not None:
                node.status = event["status"]
                node.tokens = tokens
                node.gloss = event.get("gloss")
                node.artifacts.extend(a for a in event.get("output_artifacts", []) if a not in node.artifacts)

    edges: list[tuple[str, str]] = []
    seen_edges: set[tuple[str, str]] = set()
    for node in nodes.values():
        for source in node.inputs:
            src_step = source if source in nodes else artifact_producer.get(source)
            if src_step is None or src_step == node.step_id or src_step not in nodes:
                continue
            edge = (src_step, node.step_id)
            if edge not in seen_edges:
                seen_edges.add(edge)
                edges.append(edge)

    order = _topo_order(list(nodes), edges)
    frozen_nodes = tuple(
        StageNode(
            step_id=n.step_id,
            kind=n.kind,
            status=n.status,
            parent=n.parent,
            inputs=n.inputs,
            agent=n.agent,
            agent_type=n.agent_type,
            tokens=n.tokens,
            gloss=n.gloss,
            artifacts=tuple(n.artifacts),
        )
        for n in (nodes[step_id] for step_id in order)
    )

    running = [step_id for step_id in started_order if nodes[step_id].status == "running"]
    active_step_id = running[-1] if running else None

    return RunView(
        run_id=run_id,
        role=role,
        node_ref=node_ref,
        status=run_status,
        nodes=frozen_nodes,
        edges=tuple(edges),
        metrics=metrics,
        active_step_id=active_step_id,
    )


# --- A5a: provider-agnostic hook spec -----------------------------------------

# Which autodev verb each hook event routes to. trace emit folds the firehose;
# policy check is the PreToolUse gate; charter digest re-injects the durable law.
HOOK_VERBS: dict[str, tuple[str, ...]] = {
    "PreToolUse": ("policy", "check"),
    "PostToolUse": ("trace", "emit"),
    "SubagentStart": ("trace", "emit"),
    "SubagentStop": ("trace", "emit"),
    "Stop": ("trace", "emit"),
    "SessionStart": ("charter", "digest"),
    "UserPromptSubmit": ("charter", "digest"),
}


def hook_config(run_id: str, autodev_cmd: Sequence[str]) -> dict[str, list[str]]:
    """Map each hook event to the ``autodev`` argv the worker must run for it.

    Provider-agnostic: :func:`autodev.providers.launch_command` renders this into
    a Claude ``--settings`` blob or Codex ``-c hooks.*`` overrides (A5b). Every
    verb carries ``--run <run_id>`` so a fired hook resolves back to its run.
    """
    if not run_id:
        raise TraceError("hook_config requires a run id")
    base = list(autodev_cmd)
    if not base:
        raise TraceError("hook_config requires a non-empty autodev command")
    return {event: [*base, *verb, "--run", run_id] for event, verb in HOOK_VERBS.items()}


# --- A6: hook payload -> event mapping ----------------------------------------

# SubagentStart's agent_type names the stage; anything unrecognised is tool noise.
_AGENT_TYPE_KIND = {
    "plan": "plan",
    "search": "search",
    "research": "search",
    "contract": "contract",
    "implement": "implement",
    "integrate": "integrate",
    "reconcile": "reconcile",
}

_CORRELATION_KEYS = ("turn_id", "agent_id", "agent_type", "tool_use_id")


def _correlation(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {key: payload[key] for key in _CORRELATION_KEYS if payload.get(key)}


def _hook_step_id(payload: Mapping[str, Any]) -> str:
    return str(payload.get("tool_use_id") or payload.get("agent_id") or payload.get("tool_name") or "step")


def _is_verify_command(tool_input: Mapping[str, Any], verify_commands: Sequence[str]) -> bool:
    command = str(tool_input.get("command", ""))
    return any(verify and verify in command for verify in verify_commands)


def _tool_errored(payload: Mapping[str, Any]) -> bool:
    if payload.get("tool_output_is_error"):
        return True
    response = payload.get("tool_response")
    return isinstance(response, Mapping) and bool(response.get("is_error"))


def event_from_hook(payload: Mapping[str, Any], *, verify_commands: Sequence[str] = ()) -> dict[str, Any] | None:
    """Deterministically fold one hook payload into one trace event (or ``None``).

    This is the Layer-1 stage-detection rule set (pure, no model): a subagent is
    a stage keyed by its ``agent_type``; a Bash run of a verify command is a
    verify stage that finishes red/green; every other tool call is fold-to-noise
    (``kind == "tool"``). Events routed elsewhere (PreToolUse -> policy check,
    SessionStart/UserPromptSubmit -> charter digest) map to ``None`` here.
    """
    name = payload.get("hook_event_name")
    correlation = _correlation(payload)
    step_id = _hook_step_id(payload)

    if name == "SubagentStart":
        agent_type = str(payload.get("agent_type") or "tool")
        return new_event(
            "step_declared",
            step_id=step_id,
            parent=payload.get("parent"),
            kind=_AGENT_TYPE_KIND.get(agent_type, "tool"),
            objective=f"{agent_type} subagent",
            inputs=list(payload.get("inputs", [])),
            expects=payload.get("expects", ""),
            done_when=payload.get("done_when", ""),
            agent=str(payload.get("agent_id") or agent_type),
            **correlation,
        )
    if name == "SubagentStop":
        return new_event(
            "step_finished",
            step_id=step_id,
            status="done",
            output_artifacts=list(payload.get("output_artifacts", [])),
            tokens=int(payload.get("tokens", 0) or 0),
            **correlation,
        )
    if name == "Stop":
        return new_event("run_finished", status="done", **correlation)
    if name == "PostToolUse":
        tool_input = payload.get("tool_input") or {}
        if payload.get("tool_name") == "Bash" and _is_verify_command(tool_input, verify_commands):
            return new_event(
                "step_finished",
                step_id=step_id,
                status="red" if _tool_errored(payload) else "green",
                output_artifacts=[],
                tokens=int(payload.get("tokens", 0) or 0),
                **correlation,
            )
        return new_event(
            "step_declared",
            step_id=step_id,
            parent=None,
            kind="tool",
            objective=str(payload.get("tool_name") or "tool"),
            inputs=[],
            expects="",
            done_when="",
            agent=str(payload.get("agent_id") or "worker"),
            **correlation,
        )
    return None
