"""Pod-scoped shared memory: an append-only typed envelope per pillar.

Each pod (one team per pillar) shares a durable handoff log at
``AUTODEV_HOME/projects/<id>/pods/<pillar>/memory.jsonl`` (contract C-P6). The
*record* is typed — a schema-validated envelope with a monotonic ``seq`` — while
the ``text`` body is the model's own prose, honouring the ethos "data is the
source". A pod pass has a single writer, so ``seq`` is assigned by reading the
current maximum and incrementing — no lock, the same argument as ``trace.emit``.

Reading is made automatic elsewhere (the charter digest prepends recent memory);
writing is one typed verb (``autodev pod remember``).
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from autodev.state import pod_memory_path

KINDS = frozenset({"fact", "decision", "handoff"})
_ENVELOPE_KEYS = ("seq", "ts", "pillar", "role", "agent", "run_id", "kind", "text")


class PodMemoryError(ValueError):
    """Raised when a pod-memory envelope violates the frozen schema."""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _read_raw(path: Path) -> list[Any]:
    if not path.exists():
        return []
    records: list[Any] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            records.append(json.loads(stripped))
        except json.JSONDecodeError as exc:
            raise PodMemoryError(f"{path}:{number} is not valid JSON: {exc}") from exc
    return records


def _next_seq(path: Path) -> int:
    highest = 0
    for record in _read_raw(path):
        if isinstance(record, Mapping):
            highest = max(highest, int(record.get("seq", 0)))
    return highest + 1


def _validate_envelope(record: Mapping[str, Any], path: Path) -> dict[str, Any]:
    unknown = sorted(set(record) - set(_ENVELOPE_KEYS))
    if unknown:
        raise PodMemoryError(f"{path}: pod-memory entry has unknown field(s): {', '.join(unknown)}")
    missing = sorted(set(_ENVELOPE_KEYS) - set(record))
    if missing:
        raise PodMemoryError(f"{path}: pod-memory entry is missing field(s): {', '.join(missing)}")
    if record["kind"] not in KINDS:
        raise PodMemoryError(f"{path}: pod-memory kind must be one of {sorted(KINDS)}; got {record['kind']!r}")
    return dict(record)


def append_pod_memory(
    project_id: str,
    pillar: str,
    *,
    role: str,
    agent: str,
    run_id: str,
    kind: str,
    text: str,
    home: Path | None = None,
) -> int:
    """Append one typed pod-memory envelope and return its monotonic ``seq``."""
    if kind not in KINDS:
        raise PodMemoryError(f"kind must be one of {sorted(KINDS)}; got {kind!r}")
    for label, value in (("pillar", pillar), ("role", role), ("agent", agent), ("run_id", run_id), ("text", text)):
        if not isinstance(value, str) or not value.strip():
            raise PodMemoryError(f"pod-memory {label} must be a non-empty string")
    path = pod_memory_path(project_id, pillar, home=home)
    path.parent.mkdir(parents=True, exist_ok=True)
    seq = _next_seq(path)
    envelope = {
        "seq": seq,
        "ts": _utc_now(),
        "pillar": pillar,
        "role": role,
        "agent": agent,
        "run_id": run_id,
        "kind": kind,
        "text": text,
    }
    line = json.dumps(envelope, ensure_ascii=False) + "\n"
    with open(path, "a", encoding="utf-8") as stream:
        stream.write(line)
        stream.flush()
        os.fsync(stream.fileno())
    return seq


def read_pod_memory(
    project_id: str,
    pillar: str,
    *,
    kinds: Iterable[str] | None = None,
    since: int = 0,
    home: Path | None = None,
) -> list[dict[str, Any]]:
    """Return the pod's memory (validated), keeping ``seq > since`` and, when
    ``kinds`` is given, only those kinds — ordered by ``seq``."""
    allowed = frozenset(kinds) if kinds is not None else None
    if allowed is not None:
        unknown = sorted(allowed - KINDS)
        if unknown:
            raise PodMemoryError(f"unknown kind filter: {unknown}")
    path = pod_memory_path(project_id, pillar, home=home)
    result: list[dict[str, Any]] = []
    for record in _read_raw(path):
        if not isinstance(record, Mapping):
            continue
        entry = _validate_envelope(record, path)
        if int(entry.get("seq", 0)) <= since:
            continue
        if allowed is not None and entry["kind"] not in allowed:
            continue
        result.append(entry)
    result.sort(key=lambda entry: int(entry["seq"]))
    return result
