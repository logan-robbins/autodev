from __future__ import annotations

from pathlib import Path

import pytest

from autodev.podmemory import PodMemoryError, append_pod_memory, read_pod_memory


def _append(home: Path, **overrides) -> int:
    base = {
        "project_id": "acme",
        "pillar": "replay-engine",
        "role": "engineering",
        "agent": "eng-replay-engine",
        "run_id": "r1",
        "kind": "fact",
        "text": "the contract is frozen",
        "home": home,
    }
    base.update(overrides)
    return append_pod_memory(**base)


def test_append_assigns_monotonic_seq(tmp_path: Path) -> None:
    home = tmp_path / "state"
    assert _append(home) == 1
    assert _append(home, kind="decision", text="chose jsonl") == 2


def test_read_round_trips_what_was_written(tmp_path: Path) -> None:
    home = tmp_path / "state"
    _append(home, text="fact one")
    _append(home, kind="handoff", text="leaf ready for eng")
    entries = read_pod_memory("acme", "replay-engine", home=home)
    assert [e["seq"] for e in entries] == [1, 2]
    assert entries[0]["text"] == "fact one"
    assert entries[1]["kind"] == "handoff"
    assert entries[0]["pillar"] == "replay-engine"


def test_append_rejects_bad_kind(tmp_path: Path) -> None:
    with pytest.raises(PodMemoryError, match="kind must be one of"):
        _append(tmp_path / "state", kind="rumor")


def test_append_rejects_empty_text(tmp_path: Path) -> None:
    with pytest.raises(PodMemoryError, match="text must be a non-empty string"):
        _append(tmp_path / "state", text="   ")


def test_read_filters_by_kind_and_since(tmp_path: Path) -> None:
    home = tmp_path / "state"
    _append(home, kind="fact", text="f1")
    _append(home, kind="decision", text="d1")
    _append(home, kind="fact", text="f2")

    facts = read_pod_memory("acme", "replay-engine", kinds=["fact"], home=home)
    assert [e["text"] for e in facts] == ["f1", "f2"]

    tail = read_pod_memory("acme", "replay-engine", since=2, home=home)
    assert [e["seq"] for e in tail] == [3]


def test_read_rejects_unknown_kind_filter(tmp_path: Path) -> None:
    with pytest.raises(PodMemoryError, match="unknown kind filter"):
        read_pod_memory("acme", "replay-engine", kinds=["rumor"], home=tmp_path / "state")


def test_read_missing_log_is_empty(tmp_path: Path) -> None:
    assert read_pod_memory("acme", "nothing-here", home=tmp_path / "state") == []


def test_pods_of_different_pillars_are_separate(tmp_path: Path) -> None:
    home = tmp_path / "state"
    _append(home, pillar="replay-engine", text="re")
    _append(home, pillar="fast-lane", text="fl")
    assert read_pod_memory("acme", "replay-engine", home=home)[0]["seq"] == 1
    assert read_pod_memory("acme", "fast-lane", home=home)[0]["seq"] == 1  # per-pod counter
