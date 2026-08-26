"""Schedule role-instances across the product tree; never implement.

``tick`` reads the tree joined with its live trace and decides which nodes may
advance: it expands pillars (Product Manager), then drives each approved
feature's loop (Project Manager -> Engineering) under a concurrency limit. It
honours the approval gate (decision #4) — a ``proposed`` feature is never
scheduled downstream — and it emits ``phase_changed`` for every transition. The
actual session launch is a seam (``launch``) so the scheduler is testable with
``operations``/``sessions`` swapped for a fake; the orchestrator itself only
composes them and never edits pod source.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from autodev import product, trace
from autodev.config import LoopConfig, ProjectConfig
from autodev.prompts import compose_law
from autodev.sessions import RunContext, start_session
from autodev.state import project_paths, write_role_law
from autodev.workspaces import ensure_workspace

# role -> the step kind its pass declares (feeds AUTODEV_KIND / policy).
_ROLE_KIND = {
    "product-manager": "search",
    "project-manager": "reconcile",
    "engineering": "implement",
}


@dataclass(frozen=True)
class ScheduleDecision:
    level: str  # "pillar" | "feature"
    node_id: str
    role: str
    run_id: str
    action: str  # scheduled | advanced | gated | at-capacity | running | shipped
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


def _emit_schedule(project: ProjectConfig, run_id: str, role: str, node_ref: dict, goal: str, prev: str | None) -> None:
    run_dir = _run_dir(project, run_id)
    trace.emit(run_dir, trace.new_event("run_started", run_id=run_id, role=role, node_ref=node_ref, goal=goal))
    trace.emit(
        run_dir,
        trace.new_event("phase_changed", node_ref=node_ref, reason="scheduled", **{"from": prev or "none", "to": role}),
    )


def _pillar_dirs(project: ProjectConfig) -> list[str]:
    root = product.product_root(project)
    if not root.exists():
        return []
    return sorted(child.name for child in root.iterdir() if child.is_dir())


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


def _next_after(feature: dict, role: str) -> str | None:
    seen = False
    for entry in feature["loop"]:
        if seen and entry["s"] != "done":
            return entry["role"]
        if entry["role"] == role:
            seen = True
    return None


def _select_agent(project: ProjectConfig, feature: dict | None) -> str | None:
    """Pick the worker for a role-instance: pod match on the feature's pillar, else first.

    The full role->agent assignment policy is a product decision beyond this build;
    this default is deterministic and is exercised only through the launch seam.
    """
    if feature is not None:
        for agent in project.agents:
            if agent.pod and agent.pod == feature.get("pillar"):
                return agent.id
    return project.agents[0].id if project.agents else None


def _default_launch(project: ProjectConfig, decision: ScheduleDecision) -> None:
    """Start one role-instance session with its run env, hooks, and durable law."""
    if decision.agent is None:
        return
    agent = project.agent(decision.agent)
    workspace = ensure_workspace(project, agent, kind=_ROLE_KIND.get(decision.role))
    law_file = None
    role_config = project.roles.get(decision.role)
    if role_config is not None:
        law_file = write_role_law(project.id, decision.role, compose_law(project.loop, role_config))
    start_session(
        project,
        agent,
        workspace,
        send_initial_goal=True,
        run=RunContext(
            run_id=decision.run_id,
            role=decision.role,
            kind=_ROLE_KIND.get(decision.role, "tool"),
            provider=agent.provider,
        ),
        law_file=law_file,
    )


def _count_running(project: ProjectConfig) -> int:
    running = 0
    for pillar in product.enumerate_tree(project).pillars:
        for feature in pillar.features:
            active = _active_role(feature)
            if active is None:
                continue
            view = product.join_run(project, feature)
            if view.run is None or view.run.status == "running":
                running += 1
    return running


def tick(project: ProjectConfig, *, limits: LoopConfig, launch: Launcher | None = None) -> list[ScheduleDecision]:
    """Advance the tree one step and return every scheduling decision made."""
    launch = launch or _default_launch
    decisions: list[ScheduleDecision] = []
    running = _count_running(project)

    tree = product.enumerate_tree(project)
    pillars_with_features = {pillar.id for pillar in tree.pillars}

    # 1. Pillar-level: schedule a Product-Manager pass to expand an empty pillar.
    for pillar in _pillar_dirs(project):
        if pillar in pillars_with_features:
            continue
        if running >= limits.max_concurrent:
            decisions.append(ScheduleDecision("pillar", pillar, "product-manager", "", "at-capacity"))
            continue
        run_id = _new_run_id(project, pillar, "product-manager")
        node_ref = {"level": "pillar", "pillar": pillar}
        _emit_schedule(project, run_id, "product-manager", node_ref, f"Expand pillar {pillar} into features.", None)
        decision = ScheduleDecision(
            "pillar", pillar, "product-manager", run_id, "scheduled", _select_agent(project, None)
        )
        launch(project, decision)
        running += 1
        decisions.append(decision)

    # 2. Feature-level: drive each approved feature's loop.
    for pillar in tree.pillars:
        for feature in pillar.features:
            feature_id = feature["id"]
            node_ref = {"level": "feature", "pillar": feature["pillar"], "feature": feature_id}
            active = _active_role(feature)

            if active is not None:
                view = product.join_run(project, feature)
                run_id = view.run.run_id if view.run else ""
                if view.run is not None and view.run.status in {"done", "failed"}:
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
                else:
                    decisions.append(ScheduleDecision("feature", feature_id, active, run_id, "running"))
                continue

            if feature["approval"] == "proposed":
                decisions.append(ScheduleDecision("feature", feature_id, _frontier_role(feature) or "", "", "gated"))
                continue

            frontier = _frontier_role(feature)
            if frontier is None:
                decisions.append(ScheduleDecision("feature", feature_id, "", "", "shipped"))
                continue
            if running >= limits.max_concurrent:
                decisions.append(ScheduleDecision("feature", feature_id, frontier, "", "at-capacity"))
                continue

            run_id = _new_run_id(project, feature_id, frontier)
            product.set_loop_state(project, feature_id, frontier, "active")
            product.set_run_ref(project, feature_id, run_id)
            prev = _prev_done(feature, frontier)
            _emit_schedule(project, run_id, frontier, node_ref, f"Run {frontier} on feature {feature_id}.", prev)
            decision = ScheduleDecision(
                "feature", feature_id, frontier, run_id, "scheduled", _select_agent(project, feature)
            )
            launch(project, decision)
            running += 1
            decisions.append(decision)

    return decisions


def _prev_done(feature: dict, role: str) -> str | None:
    previous = None
    for entry in feature["loop"]:
        if entry["role"] == role:
            return previous
        if entry["s"] == "done":
            previous = entry["role"]
    return previous
