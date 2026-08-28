"""Schedule role-instances across the deterministic company tree; never implement.

``tick`` reads the tree joined with its live trace and advances it one step, in
this deterministic order:

    0. cold-start  — empty tree + a product.json vision → a product-level PM pass
    1. pillars     — an approved, feature-less pillar → a pillar PM (pm-<P>) pass
                     (a proposed pillar is gated: nothing downstream runs)
    2. features    — each approved feature's loop (PjM -> Eng -> PjM), one pass
    3. docs-last   — a pillar whose every feature shipped and every leaf verified
                     → a Technical Writer (tw-<P>) pass, flipping pillar docs
                     pending -> active -> done

Agent selection is deterministic via :func:`autodev.pods.select_member`; the
descriptor is never mutated (pods are derived from the pillars). The launch is a
seam (``launch``) so the scheduler is testable with a fake, and the orchestrator
only composes ``ensure_workspace``/``start_session`` — it never edits pod source.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from autodev import pods, product, trace
from autodev.config import ConfigError, LoopConfig, ProjectConfig
from autodev.prompts import compose_law, render_identity
from autodev.sessions import RunContext, session_name, start_session
from autodev.state import pod_memory_path, project_paths, write_brief, write_identity, write_role_law
from autodev.workspaces import ensure_workspace

# role -> the step kind its pass declares (feeds AUTODEV_KIND / policy).
_ROLE_KIND = {
    "product-manager": "search",
    "project-manager": "reconcile",
    "engineering": "implement",
    "technical-writer": "document",
}


@dataclass(frozen=True)
class ScheduleDecision:
    level: str  # "product" | "pillar" | "feature"
    node_id: str
    role: str
    run_id: str
    action: str  # scheduled | advanced | gated | at-capacity | running | shipped | blocked
    agent: str | None = None


Launcher = Callable[[ProjectConfig, ScheduleDecision], None]


def _run_dir(project: ProjectConfig, run_id: str):
    return project_paths(project.id).runs / run_id


def _new_run_id(project: ProjectConfig, node_id: str, role: str) -> str:
    runs = project_paths(project.id).runs
    base = f"{node_id}-{role}"
    candidate = base
    counter = 1
    while (runs / candidate).exists():
        counter += 1
        candidate = f"{base}-{counter}"
    return candidate


def _tw_run_id(pillar_id: str) -> str:
    """A deterministic docs run id so an in-flight TW pass is found next tick."""
    return f"{pillar_id}-technical-writer"


def _emit_schedule(project: ProjectConfig, run_id: str, role: str, node_ref: dict, goal: str, prev: str | None) -> None:
    run_dir = _run_dir(project, run_id)
    trace.emit(run_dir, trace.new_event("run_started", run_id=run_id, role=role, node_ref=node_ref, goal=goal))
    trace.emit(
        run_dir,
        trace.new_event("phase_changed", node_ref=node_ref, reason="scheduled", **{"from": prev or "none", "to": role}),
    )


def _active_role(feature: dict) -> str | None:
    for entry in feature["loop"]:
        if entry["s"] == "active":
            return entry["role"]
    return None


def _frontier_role(feature: dict) -> str | None:
    for entry in feature["loop"]:
        if entry["s"] == "pending":
            return entry["role"]
    return None


def _blocked_role(feature: dict) -> str | None:
    for entry in feature["loop"]:
        if entry["s"] == "blocked":
            return entry["role"]
    return None


def _next_after(feature: dict, role: str) -> str | None:
    seen = False
    for entry in feature["loop"]:
        if seen and entry["s"] != "done":
            return entry["role"]
        if entry["role"] == role:
            seen = True
    return None


def _prev_done(feature: dict, role: str) -> str | None:
    previous = None
    for entry in feature["loop"]:
        if entry["role"] == role:
            return previous
        if entry["s"] == "done":
            previous = entry["role"]
    return previous


def _read_run(project: ProjectConfig, run_id: str) -> trace.RunView | None:
    events = trace.read_events(_run_dir(project, run_id))
    if not events:
        return None
    return trace.to_dag(events)


def failed_pass_count(project: ProjectConfig, feature_id: str) -> int:
    """Count the feature's runs whose derived verdict is ``failed`` (U4).

    The self-retry budget is spent against this count. It is *derived* from the
    append-only trace — the durable store — never from a stored counter that
    could drift from history. Each run is attributed by its
    ``run_started.node_ref.feature`` (surfaced as ``RunView.node_ref``), so a run
    belonging to another feature or a non-feature node is ignored. O(runs) per
    call, the same fold-each-run shape as :func:`_count_running`.
    """
    runs_dir = project_paths(project.id).runs
    if not runs_dir.is_dir():
        return 0
    count = 0
    for run_dir in sorted(runs_dir.iterdir()):
        if not run_dir.is_dir():
            continue
        events = trace.read_events(run_dir)
        if not events:
            continue
        view = trace.to_dag(events)
        if view.node_ref.get("feature") == feature_id and view.status == "failed":
            count += 1
    return count


def _materialized_agent(project: ProjectConfig, agent_id: str):
    for agent in pods.materialize(project):
        if agent.id == agent_id:
            return agent
    raise ConfigError(f"no materialised agent {agent_id!r} for project {project.id!r}")


def _default_launch(project: ProjectConfig, decision: ScheduleDecision) -> None:
    """Start one role-instance session with its run env, hooks, and durable brief.

    The launch brief is the fixed per-agent identity (who/where) composed with the
    per-role charter law, written to ``briefs/<agent>.md`` and appended via the
    single ``--append-system-prompt-file`` Claude accepts. The per-role law is also
    written to ``laws/<role>.md`` and the identity to ``identities/<agent>.md`` so
    the ``charter digest`` hook can re-inject both from disk after every compaction.
    """
    if decision.agent is None:
        return
    agent = _materialized_agent(project, decision.agent)
    kind = _ROLE_KIND.get(decision.role)
    workspace = ensure_workspace(project, agent, kind=kind)

    memory_path = str(pod_memory_path(project.id, agent.pod)) if agent.pod else None
    identity = render_identity(
        agent=agent,
        role=decision.role,
        project_id=project.id,
        session_name=session_name(project, agent),
        worktree=str(workspace.path),
        pod_memory_path=memory_path,
    )
    write_identity(project.id, agent.id, identity)

    role_config = project.roles.get(decision.role)
    law = compose_law(project.loop, role_config) if role_config is not None else ""
    if role_config is not None:
        write_role_law(project.id, decision.role, law)  # digest law source, unchanged
    brief = identity + (f"\n\n{law}" if law else "")
    law_file = write_brief(project.id, agent.id, brief)

    start_session(
        project,
        agent,
        workspace,
        send_initial_goal=True,
        run=RunContext(
            run_id=decision.run_id,
            role=decision.role,
            kind=kind or "tool",
            provider=agent.provider,
            agent=agent.id,
        ),
        law_file=law_file,
    )


def _pillar_ready_for_docs(project: ProjectConfig, pillar: product.PillarView) -> bool:
    """True when every feature is shipped (loop all done) and every leaf verified."""
    if not pillar.features:
        return False
    for feature in pillar.features:
        if not all(entry["s"] == "done" for entry in feature["loop"]):
            return False
        for link in feature["leaves"]:
            if product.load_leaf(project, feature["id"], link["ref"])["status"] != "verified":
                return False
    return True


def _count_running(project: ProjectConfig) -> int:
    running = 0
    for pillar in product.enumerate_tree(project).pillars:
        for feature in pillar.features:
            if _active_role(feature) is None:
                continue
            view = product.join_run(project, feature)
            if view.run is None or view.run.status == "running":
                running += 1
        if pillar.pillar["docs"] == "active":
            run = _read_run(project, _tw_run_id(pillar.id))
            if run is None or run.status == "running":
                running += 1
    return running


def _drive_feature(
    project: ProjectConfig,
    feature: dict,
    limits: LoopConfig,
    running: int,
    launch: Launcher,
) -> tuple[list[ScheduleDecision], int]:
    decisions: list[ScheduleDecision] = []
    feature_id = feature["id"]
    node_ref = {"level": "feature", "pillar": feature["pillar"], "feature": feature_id}
    active = _active_role(feature)

    if active is not None:
        view = product.join_run(project, feature)
        run_id = view.run.run_id if view.run else ""
        status = view.run.status if view.run is not None else None
        if status == "done":
            product.set_loop_state(project, feature_id, active, "done")
            nxt = _next_after(feature, active)
            trace.emit(
                _run_dir(project, run_id),
                trace.new_event(
                    "phase_changed",
                    node_ref=node_ref,
                    reason="pass complete",
                    **{"from": active, "to": nxt or "shipped"},
                ),
            )
            decisions.append(ScheduleDecision("feature", feature_id, active, run_id, "advanced"))
        elif status == "failed":
            # A failed pass is visibly blocked, never silently advanced or shipped.
            product.set_loop_state(project, feature_id, active, "blocked")
            trace.emit(
                _run_dir(project, run_id),
                trace.new_event(
                    "phase_changed",
                    node_ref=node_ref,
                    reason="failed",
                    **{"from": active, "to": "blocked"},
                ),
            )
            decisions.append(ScheduleDecision("feature", feature_id, active, run_id, "blocked"))
        else:
            decisions.append(ScheduleDecision("feature", feature_id, active, run_id, "running"))
        return decisions, running

    if feature["approval"] == "proposed":
        decisions.append(ScheduleDecision("feature", feature_id, _frontier_role(feature) or "", "", "gated"))
        return decisions, running

    frontier = _frontier_role(feature)
    if frontier is None:
        # No active or pending role: only an all-done loop is shipped; a blocked
        # entry keeps the feature visibly blocked so it is never mislabeled shipped.
        blocked = _blocked_role(feature)
        if blocked is not None:
            decisions.append(ScheduleDecision("feature", feature_id, blocked, "", "blocked"))
        else:
            decisions.append(ScheduleDecision("feature", feature_id, "", "", "shipped"))
        return decisions, running
    if running >= limits.max_concurrent:
        decisions.append(ScheduleDecision("feature", feature_id, frontier, "", "at-capacity"))
        return decisions, running

    run_id = _new_run_id(project, feature_id, frontier)
    product.set_loop_state(project, feature_id, frontier, "active")
    product.set_run_ref(project, feature_id, run_id)
    prev = _prev_done(feature, frontier)
    _emit_schedule(project, run_id, frontier, node_ref, f"Run {frontier} on feature {feature_id}.", prev)
    decision = ScheduleDecision(
        "feature", feature_id, frontier, run_id, "scheduled", pods.select_member(project, frontier, feature["pillar"])
    )
    launch(project, decision)
    return [*decisions, decision], running + 1


def _drive_docs(
    project: ProjectConfig,
    pillar: product.PillarView,
    limits: LoopConfig,
    running: int,
    launch: Launcher,
) -> tuple[list[ScheduleDecision], int]:
    docs = pillar.pillar["docs"]
    if docs == "done":
        return [], running
    node_ref = {"level": "pillar", "pillar": pillar.id}
    tw_run_id = _tw_run_id(pillar.id)

    if docs == "active":
        run = _read_run(project, tw_run_id)
        if run is not None and run.status in {"done", "failed"}:
            product.set_pillar_docs(project, pillar.id, "done")
            trace.emit(
                _run_dir(project, tw_run_id),
                trace.new_event(
                    "phase_changed",
                    node_ref=node_ref,
                    reason="docs complete",
                    **{"from": "technical-writer", "to": "documented"},
                ),
            )
            return [ScheduleDecision("pillar", pillar.id, "technical-writer", tw_run_id, "advanced")], running
        return [ScheduleDecision("pillar", pillar.id, "technical-writer", tw_run_id, "running")], running

    # docs == "pending"
    if not _pillar_ready_for_docs(project, pillar):
        return [ScheduleDecision("pillar", pillar.id, "technical-writer", "", "gated")], running
    if running >= limits.max_concurrent:
        return [ScheduleDecision("pillar", pillar.id, "technical-writer", "", "at-capacity")], running

    product.set_pillar_docs(project, pillar.id, "active")
    _emit_schedule(project, tw_run_id, "technical-writer", node_ref, f"Document pillar {pillar.id}.", None)
    decision = ScheduleDecision(
        "pillar",
        pillar.id,
        "technical-writer",
        tw_run_id,
        "scheduled",
        pods.select_member(project, "technical-writer", pillar.id),
    )
    launch(project, decision)
    return [decision], running + 1


def tick(project: ProjectConfig, *, limits: LoopConfig, launch: Launcher | None = None) -> list[ScheduleDecision]:
    """Advance the tree one step and return every scheduling decision made."""
    launch = launch or _default_launch
    decisions: list[ScheduleDecision] = []
    running = _count_running(project)
    tree = product.enumerate_tree(project)

    # Step 0: cold-start — an empty tree plus a product vision bootstraps pillars.
    if not tree.pillars:
        if product.load_product_vision(project) is None:
            return decisions
        agent = pods.select_member(project, "product-manager", None)
        if running >= limits.max_concurrent:
            return [ScheduleDecision("product", project.id, "product-manager", "", "at-capacity", agent)]
        run_id = _new_run_id(project, "product", "product-manager")
        _emit_schedule(
            project, run_id, "product-manager", {"level": "product"}, "Bootstrap pillars from the product vision.", None
        )
        decision = ScheduleDecision("product", project.id, "product-manager", run_id, "scheduled", agent)
        launch(project, decision)
        return [decision]

    for pillar in tree.pillars:
        node_ref = {"level": "pillar", "pillar": pillar.id}
        if pillar.pillar["approval"] == "proposed":
            decisions.append(ScheduleDecision("pillar", pillar.id, "product-manager", "", "gated"))
            continue

        # Step 1: an approved, feature-less pillar → schedule pm-<P> to expand it.
        if not pillar.features:
            agent = pods.select_member(project, "product-manager", pillar.id)
            if running >= limits.max_concurrent:
                decisions.append(ScheduleDecision("pillar", pillar.id, "product-manager", "", "at-capacity", agent))
                continue
            run_id = _new_run_id(project, pillar.id, "product-manager")
            _emit_schedule(
                project, run_id, "product-manager", node_ref, f"Expand pillar {pillar.id} into features.", None
            )
            decision = ScheduleDecision("pillar", pillar.id, "product-manager", run_id, "scheduled", agent)
            launch(project, decision)
            running += 1
            decisions.append(decision)
            continue

        # Step 2: drive each feature's loop.
        for feature in pillar.features:
            feature_decisions, running = _drive_feature(project, feature, limits, running, launch)
            decisions.extend(feature_decisions)

        # Step 3: docs-last gate.
        docs_decisions, running = _drive_docs(project, pillar, limits, running, launch)
        decisions.extend(docs_decisions)

    return decisions
