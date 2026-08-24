from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path

from autodev.cli import build_parser, main
from autodev.config import load_project
from autodev.state import Registry, project_paths, write_role_law
from autodev.trace import emit, new_event, read_events
from autodev.wizard import WizardResult


def test_validate_prints_machine_readable_contract(project_repo: Path, capsys) -> None:
    assert main(["validate", str(project_repo), "--json"]) == 0
    output = capsys.readouterr().out
    assert '"id": "sample-project"' in output
    assert '"provider": "codex"' in output


def test_invalid_flag_combination_fails_fast(project_repo: Path, capsys) -> None:
    assert main(["ensure", str(project_repo), "--no-start", "--send-goal"]) == 1
    assert "cannot be combined" in capsys.readouterr().err


def test_trace_emit_appends_one_event_from_stdin(project_repo: Path, tmp_path: Path, monkeypatch) -> None:
    state = tmp_path / "state"
    monkeypatch.setenv("AUTODEV_HOME", str(state))
    project = load_project(project_repo)
    Registry(home=state).register(project)
    monkeypatch.setenv("AUTODEV_PROJECT", project.id)
    payload = {"hook_event_name": "PostToolUse", "tool_name": "Read", "tool_use_id": "t1", "agent_id": "backend"}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

    assert main(["trace", "emit", "--run", "book-7"]) == 0

    run_dir = project_paths(project.id, home=state).runs / "book-7"
    events = read_events(run_dir)
    assert len(events) == 1
    assert events[0]["type"] == "step_declared"
    assert events[0]["kind"] == "tool"


def test_trace_emit_enriches_tokens_from_transcript(project_repo: Path, tmp_path: Path, monkeypatch) -> None:
    state = tmp_path / "state"
    monkeypatch.setenv("AUTODEV_HOME", str(state))
    project = load_project(project_repo)
    Registry(home=state).register(project)
    monkeypatch.setenv("AUTODEV_PROJECT", project.id)
    monkeypatch.setenv("AUTODEV_PROVIDER", "claude")
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(
        json.dumps({"message": {"usage": {"input_tokens": 200, "output_tokens": 15}}}) + "\n",
        encoding="utf-8",
    )
    payload = {"hook_event_name": "SubagentStop", "tool_use_id": "impl", "transcript_path": str(transcript)}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

    assert main(["trace", "emit", "--run", "book-7"]) == 0

    events = read_events(project_paths(project.id, home=state).runs / "book-7")
    assert events[0]["type"] == "step_finished"
    assert events[0]["tokens"] == 215


def test_trace_emit_ignores_routed_event_without_writing(project_repo: Path, tmp_path: Path, monkeypatch) -> None:
    state = tmp_path / "state"
    monkeypatch.setenv("AUTODEV_HOME", str(state))
    monkeypatch.setenv("AUTODEV_PROJECT", "sample-project")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Write"})))

    assert main(["trace", "emit", "--run", "book-7"]) == 0
    assert read_events(project_paths("sample-project", home=state).runs / "book-7") == []


def test_charter_digest_injects_role_law_as_additional_context(tmp_path: Path, monkeypatch, capsys) -> None:
    state = tmp_path / "state"
    monkeypatch.setenv("AUTODEV_HOME", str(state))
    monkeypatch.setenv("AUTODEV_PROJECT", "sample-project")
    monkeypatch.setenv("AUTODEV_ROLE", "engineering")
    write_role_law("sample-project", "engineering", "CHARTER: red tests before internals.", home=state)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"hook_event_name": "SessionStart"})))

    assert main(["charter", "digest", "--run", "book-7"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "red tests before internals" in payload["hookSpecificOutput"]["additionalContext"]


def test_charter_survives_a_forced_compaction(tmp_path: Path, monkeypatch, capsys) -> None:
    # Independent of E-1: SessionStart re-fires after compaction and the digest
    # re-reads the law from disk, so the charter is present both times.
    state = tmp_path / "state"
    monkeypatch.setenv("AUTODEV_HOME", str(state))
    monkeypatch.setenv("AUTODEV_PROJECT", "sample-project")
    monkeypatch.setenv("AUTODEV_ROLE", "engineering")
    write_role_law("sample-project", "engineering", "CHARTER-LAW: own a leaf.", home=state)

    def digest_once(event: str) -> str:
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"hook_event_name": event})))
        assert main(["charter", "digest", "--run", "r"]) == 0
        return json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]

    assert "CHARTER-LAW" in digest_once("SessionStart")  # initial session
    assert "CHARTER-LAW" in digest_once("SessionStart")  # after a forced compaction


def test_charter_digest_without_role_env_is_silent(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("AUTODEV_HOME", str(tmp_path / "state"))
    monkeypatch.delenv("AUTODEV_PROJECT", raising=False)
    monkeypatch.delenv("AUTODEV_ROLE", raising=False)
    monkeypatch.setattr("sys.stdin", io.StringIO("{}"))
    assert main(["charter", "digest", "--run", "r"]) == 0
    assert capsys.readouterr().out.strip() == ""


def _policy_env(monkeypatch, tmp_path: Path, *, role: str, kind: str) -> Path:
    state = tmp_path / "state"
    monkeypatch.setenv("AUTODEV_HOME", str(state))
    monkeypatch.setenv("AUTODEV_PROJECT", "sample-project")
    monkeypatch.setenv("AUTODEV_ROLE", role)
    monkeypatch.setenv("AUTODEV_KIND", kind)
    return state


def test_policy_check_blocks_implement_write_before_red_test(tmp_path: Path, monkeypatch, capsys) -> None:
    _policy_env(monkeypatch, tmp_path, role="engineering", kind="implement")
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": "/repo/src/impl/book/store.py"},
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

    assert main(["policy", "check", "--run", "book-7"]) == 2  # exit 2 = hard block
    assert "TDD gate" in capsys.readouterr().err


def test_policy_check_allows_write_after_a_red_test(tmp_path: Path, monkeypatch) -> None:
    state = _policy_env(monkeypatch, tmp_path, role="engineering", kind="implement")
    run_dir = project_paths("sample-project", home=state).runs / "book-7"
    emit(run_dir, new_event("step_finished", step_id="verify", status="red", output_artifacts=[], tokens=0))
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": "/repo/src/impl/book/store.py"},
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

    assert main(["policy", "check", "--run", "book-7"]) == 0  # red test recorded -> allowed


def test_policy_check_without_role_env_does_not_block(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AUTODEV_HOME", str(tmp_path / "state"))
    monkeypatch.delenv("AUTODEV_ROLE", raising=False)
    monkeypatch.delenv("AUTODEV_KIND", raising=False)
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Write", "tool_input": {"file_path": "/repo/src/x.py"}}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    assert main(["policy", "check", "--run", "r"]) == 0


def test_setup_command_accepts_optional_project_path() -> None:
    args = build_parser().parse_args(["setup", "/tmp/example"])

    assert args.command == "setup"
    assert args.project == "/tmp/example"


def test_setup_registers_wizard_project_without_launching(
    project_repo: Path, tmp_path: Path, monkeypatch, capsys
) -> None:
    project = load_project(project_repo)
    state = tmp_path / "state"
    monkeypatch.setenv("AUTODEV_HOME", str(state))
    monkeypatch.setattr(
        "autodev.cli.run_setup_wizard",
        lambda selected: WizardResult(project=project, commit=False, launch=False, start_ui=False),
    )

    assert main(["setup", str(project_repo)]) == 0

    assert str(project.descriptor) in (state / "registry.json").read_text(encoding="utf-8")
    output = capsys.readouterr().out
    assert "registered sample-project" in output
    assert "launch later" in output


def test_setup_launches_all_agents_and_sends_goals(project_repo: Path, tmp_path: Path, monkeypatch, capsys) -> None:
    project = load_project(project_repo)
    monkeypatch.setenv("AUTODEV_HOME", str(tmp_path / "state"))
    monkeypatch.setattr(
        "autodev.cli.run_setup_wizard",
        lambda selected: WizardResult(project=project, commit=False, launch=True, start_ui=False),
    )
    captured: dict[str, object] = {}

    def fake_ensure(project_arg, agents, **options):
        captured.update(project=project_arg, agents=agents, options=options)
        return [
            {
                "agent": "backend",
                "worktree": "/tmp/backend",
                "branch": "autodev/sample-project/backend",
                "session_started": True,
                "goal_sent": True,
            }
        ]

    monkeypatch.setattr("autodev.cli.ensure_agents", fake_ensure)

    assert main(["setup", str(project_repo)]) == 0

    assert captured == {
        "project": project,
        "agents": project.agents,
        "options": {
            "base_ref": None,
            "start": True,
            "send_initial_goal": True,
        },
    }
    assert "backend: started, goal sent" in capsys.readouterr().out


def test_setup_commits_new_descriptor_before_registration(project_repo: Path, tmp_path: Path, monkeypatch) -> None:
    descriptor = project_repo / "autodev.toml"
    descriptor.write_text(descriptor.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    project = load_project(project_repo)
    monkeypatch.setenv("AUTODEV_HOME", str(tmp_path / "state"))
    monkeypatch.setattr(
        "autodev.cli.run_setup_wizard",
        lambda selected: WizardResult(project=project, commit=True, launch=False, start_ui=False),
    )

    assert main(["setup", str(project_repo)]) == 0

    subject = subprocess.run(
        ["git", "log", "-1", "--format=%s"],
        cwd=project_repo,
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=project_repo,
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    ).stdout.strip()
    assert subject == "Configure Autodev"
    assert status == ""


def test_setup_starts_the_bound_project_ui(project_repo: Path, tmp_path: Path, monkeypatch) -> None:
    project = load_project(project_repo)
    monkeypatch.setenv("AUTODEV_HOME", str(tmp_path / "state"))
    monkeypatch.setattr(
        "autodev.cli.run_setup_wizard",
        lambda selected: WizardResult(project=project, commit=False, launch=False, start_ui=True),
    )
    served: list[object] = []
    monkeypatch.setattr("autodev.cli.serve_project", served.append)

    assert main(["setup", str(project_repo)]) == 0

    assert served == [project]
