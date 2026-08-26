from __future__ import annotations

from pathlib import Path

import pytest

from autodev import trace
from autodev.gloss import GlossError, gloss_step, should_gloss
from autodev.trace import new_event, read_events


def _fake_claude(tmp_path: Path, *, stdout: str = "Distilled 3 facts on L3 certification", exit_code: int = 0) -> Path:
    script = tmp_path / "fake-claude"
    script.write_text(
        f'#!/bin/sh\nprintf "%s\\n" "{stdout}"\nexit {exit_code}\n',
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def test_gloss_step_returns_one_line(tmp_path: Path) -> None:
    fake = _fake_claude(tmp_path)
    line = gloss_step("...transcript slice...", claude_cmd=[str(fake)])
    assert line == "Distilled 3 facts on L3 certification"


def test_gloss_step_raises_on_failure(tmp_path: Path) -> None:
    fake = _fake_claude(tmp_path, stdout="boom", exit_code=3)
    with pytest.raises(GlossError, match="exited 3"):
        gloss_step("slice", claude_cmd=[str(fake)])


def test_gloss_step_missing_executable_raises() -> None:
    with pytest.raises(GlossError, match="failed"):
        gloss_step("slice", claude_cmd=["/nonexistent/claude-xyz"])


def test_should_gloss_only_completed_uncached_nodes() -> None:
    events = [
        new_event(
            "run_started",
            run_id="r",
            role="engineering",
            node_ref={"level": "leaf", "pillar": "p", "feature": "f", "leaf": "l"},
            goal="g",
        ),
    ]
    for step_id, kind in (("done-step", "implement"), ("live-step", "integrate")):
        events.append(
            new_event(
                "step_declared",
                step_id=step_id,
                parent=None,
                kind=kind,
                objective="o",
                inputs=[],
                expects="",
                done_when="",
                agent="eng",
            )
        )
        events.append(new_event("step_started", step_id=step_id, agent="eng", agent_type=kind, provider="claude"))
    events.append(new_event("step_finished", step_id="done-step", status="done", output_artifacts=[], tokens=5))
    view = trace.to_dag(events)

    glossable = [n for n in view.nodes if should_gloss(n)]
    assert [n.step_id for n in glossable] == ["done-step"]  # not the running one


def test_fold_then_gloss_annotates_a_completed_node(tmp_path: Path) -> None:
    fake = _fake_claude(tmp_path, stdout="Published contracts and red tests")
    run_dir = tmp_path / "r"
    trace.emit(
        run_dir,
        new_event(
            "run_started",
            run_id="eng-1",
            role="engineering",
            node_ref={"level": "leaf", "pillar": "p", "feature": "f", "leaf": "store"},
            goal="g",
        ),
    )
    trace.emit(
        run_dir,
        new_event(
            "step_declared",
            step_id="contract",
            parent=None,
            kind="contract",
            objective="publish",
            inputs=[],
            expects="",
            done_when="",
            agent="eng",
        ),
    )
    trace.emit(
        run_dir, new_event("step_started", step_id="contract", agent="eng", agent_type="contract", provider="claude")
    )
    trace.emit(run_dir, new_event("step_finished", step_id="contract", status="done", output_artifacts=[], tokens=7))

    view = trace.to_dag(read_events(run_dir))
    calls = 0
    glosses: dict[str, str] = {}
    for node in view.nodes:
        if should_gloss(node):
            calls += 1
            glosses[node.step_id] = gloss_step("contract slice", claude_cmd=[str(fake)])

    assert calls == 1  # one bounded call for the one completed stage
    assert glosses["contract"] == "Published contracts and red tests"
