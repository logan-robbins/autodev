from __future__ import annotations

import json
from pathlib import Path

import pytest

from autodev import trace
from autodev.trace import TraceError, new_event, read_events, validate_event


def _run_started(**overrides) -> dict:
    fields = {
        "run_id": "2026-08-24-book-7",
        "role": "product-manager",
        "node_ref": {"level": "pillar", "pillar": "replay-engine"},
        "goal": "Expand the replay-engine pillar.",
    }
    fields.update(overrides)
    return new_event("run_started", **fields)


def test_new_event_stamps_ts_and_validates() -> None:
    event = _run_started()
    assert event["type"] == "run_started"
    assert isinstance(event["ts"], str) and event["ts"]
    assert event["role"] == "product-manager"


def test_new_event_allows_own_kind_field() -> None:
    event = new_event(
        "step_declared",
        step_id="s1",
        parent=None,
        kind="search",
        objective="find facts",
        inputs=[],
        expects="facts",
        done_when="ranked",
        agent="pm",
    )
    assert event["kind"] == "search"


def test_phase_changed_accepts_from_keyword_via_unpacking() -> None:
    event = new_event(
        "phase_changed",
        node_ref={"level": "feature", "pillar": "p", "feature": "f"},
        reason="pm done",
        **{"from": "product-manager", "to": "project-manager"},
    )
    assert event["from"] == "product-manager"
    assert event["to"] == "project-manager"


def test_validate_event_rejects_unknown_type() -> None:
    with pytest.raises(TraceError, match="event.type must be one of"):
        validate_event({"type": "nope", "ts": "t"})


def test_validate_event_rejects_unknown_field() -> None:
    with pytest.raises(TraceError, match="unknown field"):
        _run_started(bogus=1)


def test_validate_event_rejects_missing_required_field() -> None:
    with pytest.raises(TraceError, match="missing field"):
        new_event("run_started", run_id="r", role="x", node_ref={"level": "pillar"})


def test_validate_event_rejects_bad_node_ref_level() -> None:
    with pytest.raises(TraceError, match="node_ref.level"):
        _run_started(node_ref={"level": "galaxy"})


def test_validate_event_rejects_bad_step_kind() -> None:
    with pytest.raises(TraceError, match="step_declared.kind"):
        new_event(
            "step_declared",
            step_id="s1",
            parent=None,
            kind="frobnicate",
            objective="o",
            inputs=[],
            expects="e",
            done_when="d",
            agent="a",
        )


def test_read_events_loads_handwritten_fixture(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "r1"
    run_dir.mkdir(parents=True)
    lines = [
        json.dumps(_run_started(seq=1)),
        "",  # blank lines tolerated
        json.dumps(
            new_event(
                "step_finished",
                seq=2,
                step_id="s1",
                status="done",
                output_artifacts=["a1"],
                tokens=42,
            )
        ),
    ]
    (run_dir / trace.EVENTS_FILENAME).write_text("\n".join(lines) + "\n", encoding="utf-8")

    events = read_events(run_dir)
    assert [e["type"] for e in events] == ["run_started", "step_finished"]
    assert events[1]["tokens"] == 42


def test_read_events_since_cursor(tmp_path: Path) -> None:
    run_dir = tmp_path / "r"
    run_dir.mkdir()
    lines = [
        json.dumps(_run_started(seq=1)),
        json.dumps(new_event("run_finished", seq=2, status="done")),
    ]
    (run_dir / trace.EVENTS_FILENAME).write_text("\n".join(lines) + "\n", encoding="utf-8")

    tail = read_events(run_dir, since=1)
    assert [e["seq"] for e in tail] == [2]


def test_read_events_missing_dir_is_empty(tmp_path: Path) -> None:
    assert read_events(tmp_path / "absent") == []


def test_emit_assigns_monotonic_seq(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "r1"
    first = trace.emit(run_dir, _run_started())
    second = trace.emit(run_dir, new_event("run_finished", status="done"))
    assert (first, second) == (1, 2)

    lines = (run_dir / trace.EVENTS_FILENAME).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_emit_round_trips_through_read_events(tmp_path: Path) -> None:
    run_dir = tmp_path / "r"
    trace.emit(run_dir, _run_started())
    trace.emit(
        run_dir,
        new_event("step_finished", step_id="s1", status="green", output_artifacts=[], tokens=10),
    )
    events = read_events(run_dir)
    assert [e["seq"] for e in events] == [1, 2]
    assert events[0]["type"] == "run_started"
    assert events[1]["tokens"] == 10


def test_emit_continues_seq_after_reload(tmp_path: Path) -> None:
    run_dir = tmp_path / "r"
    trace.emit(run_dir, _run_started())
    # A fresh call (as a new process would) keeps the sequence monotonic.
    assert trace.emit(run_dir, new_event("run_finished", status="done")) == 2
