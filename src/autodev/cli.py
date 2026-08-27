"""Autodev command line interface."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from autodev import __version__
from autodev.config import (
    DESCRIPTOR_NAME,
    ConfigError,
    ProjectConfig,
    load_project,
)
from autodev.integrate import integrate
from autodev.operations import ensure_agents, select_agents, statuses, stop_agents
from autodev.podmemory import append_pod_memory, read_pod_memory
from autodev.pods import pod_agent_id
from autodev.policy import PolicyInput, decide
from autodev.product import (
    ProductError,
    add_features,
    decompose_feature,
    set_approval,
    set_leaf_status,
)
from autodev.prompts import render_goal
from autodev.providers import ProviderError, version
from autodev.service import serve_project
from autodev.sessions import SessionError, send_goal
from autodev.skill_install import install_operator_skill
from autodev.state import Registry, autodev_home, project_paths, read_role_law
from autodev.trace import emit, event_from_hook, read_events, read_tokens
from autodev.wizard import run_setup_wizard

CHARTER_MAX_CONTEXT = 10_000
POLICY_BLOCK_EXIT = 2
CHARTER_MEMORY_ENTRIES = 20


def _resolve_project(value: str | None, registry: Registry) -> ProjectConfig:
    if value is None:
        return load_project()
    candidate = Path(value).expanduser()
    if candidate.exists() or candidate.is_absolute() or "/" in value or "\\" in value:
        return load_project(candidate)
    try:
        return registry.resolve(value)
    except ConfigError as registry_error:
        try:
            return load_project(candidate)
        except ConfigError:
            raise registry_error from None


def _print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def _project_summary(project: ProjectConfig) -> dict[str, Any]:
    return {
        "id": project.id,
        "name": project.name,
        "root": str(project.root),
        "descriptor": str(project.descriptor),
        "base_branch": project.base_branch,
        "session_pattern": project.session_pattern,
        "ui_port": project.ui_port,
        "bypass_permissions": project.bypass_permissions,
        "agents": [
            {
                "id": agent.id,
                "provider": agent.provider,
                "write_roots": agent.write_roots,
                "read_roots": agent.read_roots,
            }
            for agent in project.agents
        ],
    }


def _validate_base(project: ProjectConfig) -> None:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", f"{project.base_branch}^{{commit}}"],
        cwd=project.root,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise ConfigError(
            f"project.base_branch {project.base_branch!r} does not resolve to a local commit: "
            f"{result.stderr.strip() or 'unknown Git error'}"
        )


def _commit_descriptor(project: ProjectConfig) -> None:
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=project.root,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    if branch != project.base_branch:
        raise ConfigError(
            f"cannot commit {DESCRIPTOR_NAME}: project checkout is on {branch!r}, "
            f"not configured base branch {project.base_branch!r}"
        )
    result = subprocess.run(
        ["git", "add", "--", DESCRIPTOR_NAME],
        cwd=project.root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise ConfigError(f"cannot stage {DESCRIPTOR_NAME}: {result.stderr.strip() or 'unknown Git error'}")
    result = subprocess.run(
        ["git", "commit", "-m", "Configure Autodev", "--", DESCRIPTOR_NAME],
        cwd=project.root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise ConfigError(f"cannot commit {DESCRIPTOR_NAME}: {result.stderr.strip() or 'unknown Git error'}")
    print(f"committed {DESCRIPTOR_NAME} to {project.base_branch}")


def _validate_descriptor_committed(project: ProjectConfig) -> None:
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", DESCRIPTOR_NAME],
        cwd=project.root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    unstaged = subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", DESCRIPTOR_NAME],
        cwd=project.root,
        check=False,
    )
    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet", "HEAD", "--", DESCRIPTOR_NAME],
        cwd=project.root,
        check=False,
    )
    if tracked.returncode or unstaged.returncode or staged.returncode:
        raise ConfigError(f"immediate launch requires {DESCRIPTOR_NAME} to be committed on {project.base_branch}")


def _command_version(command: str, flag: str = "--version") -> str:
    path = shutil.which(command)
    if not path:
        return "missing"
    result = subprocess.run(
        [path, flag],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return result.stdout.strip() or f"exit {result.returncode}"


def _hook_run_dir(run_id: str) -> Path:
    """Resolve a worker hook's run directory from its session env (A5c)."""
    project_id = os.environ.get("AUTODEV_PROJECT")
    if not project_id:
        raise ConfigError("hook verbs require AUTODEV_PROJECT in the session environment")
    return project_paths(project_id).runs / run_id


def _trace_emit(run_id: str) -> int:
    """Fold one hook payload (stdin JSON) into the run trace; never blocks a worker."""
    raw = sys.stdin.read()
    if not raw.strip():
        return 0
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        print("autodev: trace emit received non-JSON hook payload", file=sys.stderr)
        return 0
    if not isinstance(payload, dict):
        return 0
    project_id = os.environ.get("AUTODEV_PROJECT")
    if not project_id:
        print("autodev: trace emit requires AUTODEV_PROJECT", file=sys.stderr)
        return 0
    verify_commands: tuple[str, ...] = ()
    with contextlib.suppress(ConfigError):
        verify_commands = Registry().resolve(project_id).verify_commands
    provider = os.environ.get("AUTODEV_PROVIDER")
    transcript = payload.get("transcript_path")
    if provider and transcript and "tokens" not in payload:
        with contextlib.suppress(Exception):
            payload = {**payload, "tokens": read_tokens(Path(transcript), provider)}
    event = event_from_hook(payload, verify_commands=verify_commands)
    if event is None:
        return 0
    emit(_hook_run_dir(run_id), event)
    return 0


def _run_pillar(project_id: str, run_id: str) -> str | None:
    """The pillar this run belongs to, read from its run_started node_ref."""
    with contextlib.suppress(ConfigError, OSError):
        for event in read_events(project_paths(project_id).runs / run_id):
            if event.get("type") == "run_started":
                pillar = event.get("node_ref", {}).get("pillar")
                return pillar if isinstance(pillar, str) and pillar else None
    return None


def _recent_pod_memory(project_id: str, run_id: str) -> str:
    """Recent pod-memory lines for this run's pillar, to prepend to the law."""
    pillar = _run_pillar(project_id, run_id)
    if not pillar:
        return ""
    entries = read_pod_memory(project_id, pillar)[-CHARTER_MEMORY_ENTRIES:]
    if not entries:
        return ""
    lines = [f"- [{entry['kind']}] {entry['role']}: {entry['text']}" for entry in entries]
    return "Recent pod memory (read before acting):\n" + "\n".join(lines) + "\n\n"


def _charter_digest(run_id: str) -> int:
    """Print the run role's composed law as hook additionalContext (<=10k).

    Registered on SessionStart + UserPromptSubmit (A5a) so the durable law is
    re-injected from disk after every compaction and at every pass — the layer
    that survives regardless of the append-system-prompt outcome (E-1). The
    pillar's recent pod memory is prepended ahead of the law so "read before
    acting" is automatic, all within the 10k budget.
    """
    raw = sys.stdin.read()
    event_name = "SessionStart"
    if raw.strip():
        with contextlib.suppress(json.JSONDecodeError):
            payload = json.loads(raw)
            if isinstance(payload, dict):
                event_name = payload.get("hook_event_name", event_name)
    project_id = os.environ.get("AUTODEV_PROJECT")
    role = os.environ.get("AUTODEV_ROLE")
    if not project_id or not role:
        return 0
    try:
        law = read_role_law(project_id, role)
    except ConfigError:
        return 0
    context = (_recent_pod_memory(project_id, run_id) + law)[:CHARTER_MAX_CONTEXT]
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event_name, "additionalContext": context}}))
    return 0


def _pod_remember(pillar: str, kind: str) -> int:
    """Append one typed pod-memory entry from stdin (the `autodev pod remember` verb).

    Resolves the project, role, and run from the session environment; the writing
    agent id is derived deterministically from the role and pillar.
    """
    project_id = os.environ.get("AUTODEV_PROJECT")
    role = os.environ.get("AUTODEV_ROLE")
    run_id = os.environ.get("AUTODEV_RUN_ID")
    if not project_id or not role or not run_id:
        raise ConfigError(
            "`autodev pod remember` requires AUTODEV_PROJECT, AUTODEV_ROLE, and AUTODEV_RUN_ID in the session environment"
        )
    text = sys.stdin.read().strip()
    if not text:
        raise ConfigError("`autodev pod remember` requires memory text on stdin")
    seq = append_pod_memory(
        project_id,
        pillar,
        role=role,
        agent=pod_agent_id(role, pillar),
        run_id=run_id,
        kind=kind,
        text=text,
    )
    print(f"remembered {kind} #{seq} for pod {pillar}")
    return 0


def _red_test_recorded(run_id: str) -> bool:
    """True when a failing (red) verify step is already in this pass's trace."""
    try:
        events = read_events(_hook_run_dir(run_id))
    except (ConfigError, OSError):
        return False
    return any(e.get("type") == "step_finished" and e.get("status") == "red" for e in events)


def _policy_check(run_id: str) -> int:
    """PreToolUse gate: exit 2 (reason on stderr) to hard-block a denied tool call.

    Role/kind come from the session env (A5c). With none set (a non-orchestrated
    session) nothing is gated. exit 2 is the portable hard block verified on both
    providers; a denied write never runs.
    """
    raw = sys.stdin.read()
    if not raw.strip():
        return 0
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return 0
    if not isinstance(payload, dict):
        return 0
    role = os.environ.get("AUTODEV_ROLE")
    kind = os.environ.get("AUTODEV_KIND")
    if not role or not kind:
        return 0
    decision = decide(
        PolicyInput(
            role=role,
            kind=kind,
            tool_name=str(payload.get("tool_name", "")),
            tool_input=payload.get("tool_input") or {},
            red_test=_red_test_recorded(run_id),
        )
    )
    if decision.allow:
        return 0
    print(f"Blocked by Autodev policy: {decision.reason}", file=sys.stderr)
    return POLICY_BLOCK_EXIT


def _stdin_json_list(label: str) -> list:
    try:
        payload = json.loads(sys.stdin.read() or "[]")
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{label} must be a JSON array on stdin: {exc}") from exc
    if not isinstance(payload, list):
        raise ConfigError(f"{label} must be a JSON array")
    return payload


def _product_verb(project: ProjectConfig, args: argparse.Namespace) -> int:
    """Typed tree-authoring verbs (decision #3): schema-validated, atomic writes."""
    if args.product_command == "add-features":
        paths = add_features(project, args.pillar, _stdin_json_list("features"))
        print(f"wrote {len(paths)} feature file(s) under pillar {args.pillar}")
    elif args.product_command == "decompose-feature":
        paths = decompose_feature(project, args.feature, _stdin_json_list("leaves"))
        print(f"wrote {len(paths)} file(s) for feature {args.feature}")
    elif args.product_command == "set-leaf-status":
        path = set_leaf_status(project, args.feature, args.leaf, args.status)
        print(f"set {args.feature}/{args.leaf} status to {args.status} ({path})")
    elif args.product_command == "set-approval":
        path = set_approval(project, args.feature, args.approval)
        print(f"set {args.feature} approval to {args.approval} ({path})")
    else:  # argparse required=True makes this unreachable.
        raise AssertionError(f"unhandled product command: {args.product_command}")
    return 0


def _add_project_argument(parser: argparse.ArgumentParser, *, required: bool = False) -> None:
    parser.add_argument(
        "project",
        nargs=None if required else "?",
        help=f"project directory, {DESCRIPTOR_NAME} path, or registered project ID",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autodev",
        description="Operate installed Codex and Claude Code agents across isolated project worktrees.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    setup = subparsers.add_parser(
        "setup",
        help="interactively configure, register, and optionally launch a project",
    )
    setup.add_argument("project", nargs="?", help="existing Git repository root (prompted when omitted)")

    skill = subparsers.add_parser("skill", help="manage the repository-owned operator skill")
    skill_commands = skill.add_subparsers(dest="skill_command", required=True)
    skill_commands.add_parser("install", help="link the operator skill into Codex and Claude Code")

    trace = subparsers.add_parser("trace", help="record run trace events emitted by worker hooks")
    trace_commands = trace.add_subparsers(dest="trace_command", required=True)
    trace_emit = trace_commands.add_parser("emit", help="append one event from a hook payload on stdin")
    trace_emit.add_argument("--run", dest="run_id", required=True, help="run id the firing hook belongs to")

    charter = subparsers.add_parser("charter", help="inject durable role law into a worker via hooks")
    charter_commands = charter.add_subparsers(dest="charter_command", required=True)
    charter_digest = charter_commands.add_parser("digest", help="print the role law as hook additionalContext")
    charter_digest.add_argument("--run", dest="run_id", required=True, help="run id the firing hook belongs to")

    pod = subparsers.add_parser("pod", help="pod-scoped shared memory for a pillar's team")
    pod_commands = pod.add_subparsers(dest="pod_command", required=True)
    pod_remember = pod_commands.add_parser("remember", help="append one typed pod-memory entry (text on stdin)")
    pod_remember.add_argument("--pillar", required=True)
    pod_remember.add_argument("--kind", required=True, choices=["fact", "decision", "handoff"])

    policy = subparsers.add_parser("policy", help="enforce the per-role/kind PreToolUse policy")
    policy_commands = policy.add_subparsers(dest="policy_command", required=True)
    policy_check = policy_commands.add_parser("check", help="block a denied tool call (exit 2) from a hook payload")
    policy_check.add_argument("--run", dest="run_id", required=True, help="run id the firing hook belongs to")

    product = subparsers.add_parser("product", help="author the product tree through typed, validated verbs")
    product_commands = product.add_subparsers(dest="product_command", required=True)
    add_features_cmd = product_commands.add_parser(
        "add-features", help="write feature.json files (JSON array on stdin)"
    )
    _add_project_argument(add_features_cmd, required=True)
    add_features_cmd.add_argument("--pillar", required=True)
    decompose_cmd = product_commands.add_parser("decompose-feature", help="write leaf.json files (JSON array on stdin)")
    _add_project_argument(decompose_cmd, required=True)
    decompose_cmd.add_argument("--feature", required=True)
    leaf_status_cmd = product_commands.add_parser("set-leaf-status", help="update one leaf's status")
    _add_project_argument(leaf_status_cmd, required=True)
    leaf_status_cmd.add_argument("--feature", required=True)
    leaf_status_cmd.add_argument("--leaf", required=True)
    leaf_status_cmd.add_argument("--status", required=True)
    approval_cmd = product_commands.add_parser("set-approval", help="flip a feature's approval gate")
    _add_project_argument(approval_cmd, required=True)
    approval_cmd.add_argument("--feature", required=True)
    approval_cmd.add_argument("--approval", required=True, choices=["proposed", "approved"])

    validate = subparsers.add_parser("validate", help="validate a project descriptor and local base branch")
    _add_project_argument(validate)
    validate.add_argument("--json", action="store_true")

    register = subparsers.add_parser("register", help="register a project with the shared runtime")
    _add_project_argument(register, required=True)

    unregister = subparsers.add_parser("unregister", help="remove a project from the shared registry")
    unregister.add_argument("project_id")

    projects = subparsers.add_parser("projects", help="list registered projects")
    projects.add_argument("--json", action="store_true")

    doctor = subparsers.add_parser("doctor", help="check host prerequisites and configured providers")
    _add_project_argument(doctor)
    doctor.add_argument("--json", action="store_true")

    ensure = subparsers.add_parser("ensure", help="create/reuse worktrees and agent sessions")
    _add_project_argument(ensure, required=True)
    ensure.add_argument("agents", nargs="*")
    ensure.add_argument("--base-ref", help="base ref for newly created worktrees")
    ensure.add_argument("--no-start", action="store_true", help="prepare worktrees without starting agents")
    ensure.add_argument("--send-goal", action="store_true", help="start or continue the standing goal")
    ensure.add_argument("--json", action="store_true")

    goal = subparsers.add_parser("goal", help="send the standing goal to running agent sessions")
    _add_project_argument(goal, required=True)
    goal.add_argument("agents", nargs="*")
    goal.add_argument("--dry-run", action="store_true")

    prompt = subparsers.add_parser("prompt", help="render one agent's standing prompt")
    _add_project_argument(prompt, required=True)
    prompt.add_argument("agent")

    status = subparsers.add_parser("status", help="show agent, worktree, Git, and ownership status")
    _add_project_argument(status, required=True)
    status.add_argument("agents", nargs="*")
    status.add_argument("--json", action="store_true")

    stop = subparsers.add_parser("stop", help="stop running agent sessions without deleting worktrees")
    _add_project_argument(stop, required=True)
    stop.add_argument("agents", nargs="*")
    stop.add_argument("--json", action="store_true")

    merge = subparsers.add_parser("merge", help="integrate one clean, owned agent branch into the base branch")
    _add_project_argument(merge, required=True)
    merge.add_argument("agent")

    ui = subparsers.add_parser("ui", help="run one project's configuration and agent UI")
    _add_project_argument(ui, required=True)
    return parser


def run(args: argparse.Namespace, *, registry: Registry | None = None) -> int:
    active_registry = registry or Registry()
    if args.command == "skill":
        if args.skill_command != "install":
            raise AssertionError(f"unhandled skill command: {args.skill_command}")
        for link in install_operator_skill():
            state = "installed" if link.created else "already installed"
            print(f"{link.client}: {state} {link.path} -> {link.source}")
        return 0
    if args.command == "trace":
        if args.trace_command != "emit":
            raise AssertionError(f"unhandled trace command: {args.trace_command}")
        return _trace_emit(args.run_id)
    if args.command == "charter":
        if args.charter_command != "digest":
            raise AssertionError(f"unhandled charter command: {args.charter_command}")
        return _charter_digest(args.run_id)
    if args.command == "pod":
        if args.pod_command != "remember":
            raise AssertionError(f"unhandled pod command: {args.pod_command}")
        return _pod_remember(args.pillar, args.kind)
    if args.command == "policy":
        if args.policy_command != "check":
            raise AssertionError(f"unhandled policy command: {args.policy_command}")
        return _policy_check(args.run_id)
    if args.command == "setup":
        result = run_setup_wizard(args.project)
        _validate_base(result.project)
        if result.commit:
            _commit_descriptor(result.project)
        active_registry.register(result.project)
        print(f"registered {result.project.id}: {result.project.descriptor}")
        if result.launch:
            _validate_descriptor_committed(result.project)
            started = ensure_agents(
                result.project,
                result.project.agents,
                base_ref=None,
                start=True,
                send_initial_goal=True,
            )
            for item in started:
                state = "started" if item["session_started"] else "reused"
                goal_state = ", goal sent" if item["goal_sent"] else ""
                print(f"{item['agent']}: {state}{goal_state} ({item['worktree']})")
        else:
            print(f"setup complete; launch later with `autodev ensure {result.project.id} --send-goal`")
        if result.start_ui:
            serve_project(result.project)
        else:
            print(f"project UI: `autodev ui {result.project.id}` on port {result.project.ui_port}")
        return 0
    if args.command == "unregister":
        active_registry.unregister(args.project_id)
        print(f"unregistered {args.project_id}")
        return 0
    if args.command == "projects":
        entries = {key: str(value) for key, value in active_registry.entries().items()}
        if args.json:
            _print_json({"projects": entries})
        elif entries:
            for project_id, path in entries.items():
                print(f"{project_id:32} {path}")
        else:
            print("no registered projects")
        return 0
    project = _resolve_project(args.project, active_registry)
    if args.command == "product":
        return _product_verb(project, args)
    if args.command == "ui":
        serve_project(project)
        return 0
    if args.command == "validate":
        _validate_base(project)
        summary = _project_summary(project)
        if args.json:
            _print_json(summary)
        else:
            print(f"valid {project.descriptor}: {len(project.agents)} agent(s), base {project.base_branch}")
        return 0
    if args.command == "register":
        _validate_base(project)
        active_registry.register(project)
        print(f"registered {project.id}: {project.descriptor}")
        return 0
    if args.command == "doctor":
        used_providers = sorted({agent.provider for agent in project.agents})
        checks: dict[str, str] = {
            "autodev_home": str(autodev_home()),
            "git": _command_version("git"),
            "tmux": _command_version("tmux", "-V"),
            "uv": _command_version("uv"),
        }
        for provider_name in used_providers:
            checks[provider_name] = version(project.providers[provider_name])
        if args.json:
            _print_json(checks)
        else:
            for name, value in checks.items():
                print(f"{name:16} {value}")
        return 0
    if args.command == "prompt":
        print(render_goal(project, project.agent(args.agent)))
        return 0

    agents = select_agents(project, args.agents)
    if args.command == "ensure":
        if args.no_start and args.send_goal:
            raise ConfigError("--send-goal cannot be combined with --no-start")
        active_registry.register(project)
        result = ensure_agents(
            project,
            agents,
            base_ref=args.base_ref,
            start=not args.no_start,
            send_initial_goal=args.send_goal,
        )
        if args.json:
            _print_json({"project": project.id, "agents": result})
        else:
            for item in result:
                state = "started" if item["session_started"] else ("prepared" if args.no_start else "reused")
                goal_state = ", goal sent" if item["goal_sent"] else ""
                print(f"{item['agent']}: {state}{goal_state} ({item['worktree']})")
        return 0
    if args.command == "goal":
        for agent in agents:
            output = send_goal(project, agent, dry_run=args.dry_run)
            if args.dry_run:
                print(f"--- {agent.id} ---\n{output}")
            else:
                print(f"{agent.id}: goal sent")
        return 0
    if args.command == "status":
        values = statuses(project, agents)
        if args.json:
            _print_json({"project": project.id, "agents": [value.as_dict() for value in values]})
        else:
            print("agent                            provider running worktree git ownership")
            for value in values:
                git_state = "dirty" if value.git_status else "clean"
                ownership = "VIOLATION" if value.ownership_violations else "ok"
                print(
                    f"{value.agent:32} {value.provider:8} "
                    f"{'yes' if value.running else 'no':7} "
                    f"{'yes' if value.worktree_exists else 'no':8} {git_state:5} {ownership}"
                )
        return 0
    if args.command == "stop":
        result = stop_agents(project, agents)
        if args.json:
            _print_json({"project": project.id, "agents": result})
        else:
            for item in result:
                print(f"{item['agent']}: {'stopped' if item['stopped'] else 'already offline'}")
        return 0
    if args.command == "merge":
        print(integrate(project, project.agent(args.agent)))
        return 0
    raise AssertionError(f"unhandled command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (ConfigError, ProductError, ProviderError, SessionError, RuntimeError) as exc:
        print(f"autodev: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("autodev: interrupted", file=sys.stderr)
        return 130
