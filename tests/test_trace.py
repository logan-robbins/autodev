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


# --- A3: to_dag reducer -------------------------------------------------------
# These fold tests omit seq and rely on to_dag's stable sort preserving list
# order, so causal order is exactly the list order.


def _step(step_id: str, kind: str, *, inputs=(), parent=None) -> list[dict]:
    return [
        new_event(
            "step_declared",
            step_id=step_id,
            parent=parent,
            kind=kind,
            objective=f"{kind} {step_id}",
            inputs=list(inputs),
            expects="something",
            done_when="asserted",
            agent="pm",
        ),
        new_event("step_started", step_id=step_id, agent="pm", agent_type=kind, provider="claude"),
    ]


def _finish(step_id: str, *, status="done", tokens=10, outputs=()) -> dict:
    return new_event(
        "step_finished",
        step_id=step_id,
        status=status,
        output_artifacts=list(outputs),
        tokens=tokens,
    )


def _pm_research_events() -> list[dict]:
    """plan -> {search1, search2} -> synthesize: fan-out then fan-in.

    ``synth`` is declared and started but not finished, so it is the running
    node the UI should default to.
    """
    events = [
        new_event(
            "run_started",
            run_id="pm-1",
            role="product-manager",
            node_ref={"level": "pillar", "pillar": "replay-engine"},
            goal="expand",
        )
    ]
    events += _step("plan", "plan")
    events.append(_finish("plan"))
    events += _step("search1", "search", inputs=["plan"])
    events += _step("search2", "search", inputs=["plan"])
    events.append(_finish("search1", outputs=["facts1"]))
    events.append(_finish("search2", outputs=["facts2"]))
    events += _step("synth", "reconcile", inputs=["facts1", "facts2"])
    return events


def test_to_dag_shows_fan_out_and_fan_in() -> None:
    view = trace.to_dag(_pm_research_events())
    edges = set(view.edges)
    # fan-out: plan feeds both searches.
    assert ("plan", "search1") in edges
    assert ("plan", "search2") in edges
    # fan-in: both searches (via their facts artifacts) feed synth.
    assert ("search1", "synth") in edges
    assert ("search2", "synth") in edges
    fan_in = [dst for _src, dst in view.edges].count("synth")
    fan_out = [src for src, _dst in view.edges].count("plan")
    assert fan_in == 2
    assert fan_out == 2


def test_to_dag_active_step_is_the_running_node() -> None:
    view = trace.to_dag(_pm_research_events())
    assert view.active_step_id == "synth"
    synth = next(n for n in view.nodes if n.step_id == "synth")
    assert synth.status == "running"


def test_to_dag_folds_non_stage_tools_into_tool_calls() -> None:
    events = [_run_started()]
    events += _step("impl", "implement")
    events.append(
        new_event(
            "step_declared",
            step_id="grep-1",
            parent=None,
            kind="tool",
            objective="grep",
            inputs=[],
            expects="matches",
            done_when="done",
            agent="eng",
        )
    )
    events.append(_finish("grep-1", tokens=5))
    events.append(_finish("impl", tokens=0))
    view = trace.to_dag(events)
    assert [n.step_id for n in view.nodes] == ["impl"]
    assert view.metrics["tool_calls"] == 1
    # tool tokens still count toward the run total.
    assert view.metrics["tokens"] == 5


def test_to_dag_is_deterministic_on_replay() -> None:
    events = _pm_research_events()
    first = trace.to_dag(events)
    second = trace.to_dag(list(events))
    assert first == second


def test_to_dag_engineering_contract_first_shape() -> None:
    events = [
        new_event(
            "run_started",
            run_id="eng-1",
            role="engineering",
            node_ref={"level": "leaf", "pillar": "p", "feature": "f", "leaf": "store"},
            goal="build",
        )
    ]
    events += _step("contract", "contract")
    events.append(_finish("contract", outputs=["iface"]))
    events += _step("impl-a", "implement", inputs=["iface"])
    events += _step("impl-b", "implement", inputs=["iface"])
    events.append(_finish("impl-a"))
    events.append(_finish("impl-b"))
    events += _step("integrate", "integrate", inputs=["impl-a", "impl-b"])
    events.append(_finish("integrate", status="green"))
    events.append(new_event("run_finished", status="done"))

    view = trace.to_dag(events)
    assert view.status == "done"
    assert ("contract", "impl-a") in view.edges
    assert ("contract", "impl-b") in view.edges  # fan-out
    assert ("impl-a", "integrate") in view.edges
    assert ("impl-b", "integrate") in view.edges  # fan-in
    # topological order: contract before its consumers before the integrator.
    order = [n.step_id for n in view.nodes]
    assert order.index("contract") < order.index("impl-a") < order.index("integrate")
    integrate_node = next(n for n in view.nodes if n.step_id == "integrate")
    assert integrate_node.status == "green"


def test_to_dag_folds_persisted_events_jsonl(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "pm-1"
    for event in _pm_research_events():
        trace.emit(run_dir, {k: v for k, v in event.items() if k != "seq"})
    view = trace.to_dag(read_events(run_dir))
    assert ("plan", "search1") in view.edges
    assert ("search1", "synth") in view.edges
    assert view.active_step_id == "synth"


# --- A5a: hook spec -----------------------------------------------------------


def test_hook_config_routes_events_to_verbs() -> None:
    spec = trace.hook_config("book-7", ["uv", "run", "autodev"])
    assert spec["PreToolUse"] == ["uv", "run", "autodev", "policy", "check", "--run", "book-7"]
    assert spec["PostToolUse"] == ["uv", "run", "autodev", "trace", "emit", "--run", "book-7"]
    assert spec["SessionStart"] == ["uv", "run", "autodev", "charter", "digest", "--run", "book-7"]
    assert spec["UserPromptSubmit"][-3:] == ["digest", "--run", "book-7"]
    # every provider-parity event is covered.
    assert set(spec) == {
        "PreToolUse",
        "PostToolUse",
        "SubagentStart",
        "SubagentStop",
        "Stop",
        "SessionStart",
        "UserPromptSubmit",
    }


def test_hook_config_requires_run_and_command() -> None:
    with pytest.raises(TraceError):
        trace.hook_config("", ["autodev"])
    with pytest.raises(TraceError):
        trace.hook_config("r", [])


# --- A6 (pure): hook payload -> event mapping ---------------------------------


def test_event_from_hook_folds_generic_tool_to_noise() -> None:
    event = trace.event_from_hook(
        {"hook_event_name": "PostToolUse", "tool_name": "Read", "tool_use_id": "t1", "agent_id": "eng"}
    )
    assert event["type"] == "step_declared"
    assert event["kind"] == "tool"
    assert event["step_id"] == "t1"


def test_event_from_hook_marks_verify_green_and_red() -> None:
    green = trace.event_from_hook(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_use_id": "v1",
            "tool_input": {"command": "uv run pytest -q"},
        },
        verify_commands=["uv run pytest"],
    )
    assert green["type"] == "step_finished" and green["status"] == "green"
    red = trace.event_from_hook(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_use_id": "v2",
            "tool_input": {"command": "uv run pytest -q"},
            "tool_output_is_error": True,
        },
        verify_commands=["uv run pytest"],
    )
    assert red["status"] == "red"


def test_event_from_hook_subagent_start_is_a_stage() -> None:
    event = trace.event_from_hook(
        {"hook_event_name": "SubagentStart", "agent_type": "search", "agent_id": "pm-sub", "tool_use_id": "s1"}
    )
    assert event["type"] == "step_declared"
    assert event["kind"] == "search"
    assert event["agent_type"] == "search"


def test_event_from_hook_stop_finishes_run() -> None:
    assert trace.event_from_hook({"hook_event_name": "Stop"})["type"] == "run_finished"


def test_event_from_hook_ignores_routed_events() -> None:
    assert trace.event_from_hook({"hook_event_name": "PreToolUse", "tool_name": "Write"}) is None
    assert trace.event_from_hook({"hook_event_name": "SessionStart"}) is None


def test_event_from_hook_stream_folds_into_dag(tmp_path: Path) -> None:
    payloads = [
        {"hook_event_name": "SubagentStart", "agent_type": "implement", "tool_use_id": "impl", "agent_id": "eng"},
        {"hook_event_name": "PostToolUse", "tool_name": "Read", "tool_use_id": "r1", "agent_id": "eng"},
        {"hook_event_name": "SubagentStop", "tool_use_id": "impl"},
    ]
    run_dir = tmp_path / "r"
    for payload in payloads:
        event = trace.event_from_hook(payload)
        if event is not None:
            trace.emit(run_dir, event)
    view = trace.to_dag(read_events(run_dir))
    assert [n.step_id for n in view.nodes] == ["impl"]
    assert view.metrics["tool_calls"] == 1
