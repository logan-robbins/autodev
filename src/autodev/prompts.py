"""Core project-independent prompt templates and the durable role law."""

from __future__ import annotations

from autodev.config import AgentConfig, LoopConfig, ProjectConfig, RoleConfig

# One persona per role shape (config.ROLE_SHAPES). These carry the workflow
# framing the trace expects: research fans out searches and fans facts back in;
# contract-first puts red tests before internals; reconcile splits into leaves.
SHAPE_PERSONA = {
    "research": (
        "Work as a research fan-in: plan the queries, fan out one search per query, distil each "
        "result into a fact {claim, source, date, relevance}, then fan the facts back in and "
        "synthesize — ranking recency x relevance — into the Pillar's Features."
    ),
    "contract-first": (
        "Work contract-first: publish interfaces and red (failing) tests before any internals; "
        "build each unit against its own contract slice only; integration reads eval signals, not "
        "another unit's source."
    ),
    "reconcile": (
        "Work as a reconcile pass: read the committed work and existing leaves, split the Feature "
        "into complete leaves, correct stale gates, and emit unmet depends_on edges as the next "
        "executable queue."
    ),
    "document": (
        "Work as a documentarian, last: read the verified source and the pod memory, then produce a "
        "highly condensed, data-flow-first technical map — show the flow (a -> b -> c) before any "
        "prose — stamped to the verified sha. Never edit source; if the source contradicts the "
        "intent you were asked to document, report it rather than changing it."
    ),
}


# The shared operating law embedded in every role's charter (the design's
# "shared operator law"). It is deterministic text, appended by compose_law.
OPERATOR_LAW = (
    "Operating law (shared by every role):\n"
    "- Contract-first, TDD/eval-driven: publish the interface and a red (failing) test before any "
    "internals; red before green.\n"
    "- State every unit as input -> output -> unit test -> integration test -> the one module it "
    "lives in; a unit lives in exactly one module.\n"
    "- One canonical path; fail fast on a missing prerequisite. No stub, fallback, or 'v2'.\n"
    "- Clean the backlog after validation; drop proven-done leaves.\n"
    "- Docs are written last, only after every leaf verifies."
)

# The read-before-act / write-after rule for pod-scoped shared memory.
POD_MEMORY_RULE = (
    "Pod memory: your pod's recent memory is prepended to this law (read it before acting); after "
    "acting, record durable facts, decisions, and handoffs with `autodev pod remember`."
)


def _list(values: tuple[str, ...], *, empty: str = "none") -> str:
    if not values:
        return f"- {empty}"
    return "\n".join(f"- {value}" for value in values)


def compose_law(loop: LoopConfig | None, role: RoleConfig) -> str:
    """Compose one role's durable law: charter + shape persona + loop rules.

    This is the text placed where compaction cannot erase it — appended to the
    system prompt at launch (C2) and re-injected via SessionStart/
    UserPromptSubmit (C3). It is deterministic given ``(loop, role)``.
    """
    parts = [
        f"You own the {role.id} level of the product tree.",
        f"Charter: {role.charter}",
        f"Working shape ({role.shape}): {SHAPE_PERSONA[role.shape]}",
    ]
    if loop is not None:
        parts.append("Loop law:")
        if loop.sequence:
            parts.append(f"- Execution sequence across the tree: {' -> '.join(loop.sequence)}.")
        if loop.reenter_product_manager_when:
            parts.append(
                "- Re-enter the Product Manager only on: " + ", ".join(loop.reenter_product_manager_when) + "."
            )
        parts.append(f"- At most {loop.max_concurrent} role-instances run concurrently.")
    parts.append(
        "Mutate the product tree only through the typed `autodev product` verbs (add-pillars, "
        "add-features, decompose-feature, set-leaf-status); never hand-edit pillar.json, feature.json, "
        "or leaf.json."
    )
    parts.append(
        "Pillars and Features you emit are `proposed`; the Orchestrator schedules downstream roles "
        "only after the operator approves them."
    )
    parts.append(OPERATOR_LAW)
    parts.append(POD_MEMORY_RULE)
    return "\n".join(parts)


def render_goal(project: ProjectConfig, agent: AgentConfig, role: RoleConfig | None = None) -> str:
    verification = _list(project.verify_commands, empty="use the repository's relevant local checks")
    base = f"""You are the `{agent.id}` Autodev agent for {project.name}.

Purpose:
{agent.purpose}

Project instructions:
{project.instructions}

Owned write roots:
{_list(agent.write_roots)}

Read-only context roots:
{_list(tuple(dict.fromkeys((*project.context_roots, *agent.read_roots))))}

Standing goal:
{agent.goal}

Operating contract:
1. Discover existing patterns and current Git state before changing anything.
2. Select one vertically complete, locally actionable work item. Make the task
   state explicit using the project's existing task mechanism when it has one.
3. Modify only the owned write roots listed above. Read-only context is for
   understanding and verification, never edits. If completion requires another
   agent's owned path, stop and report the exact provider change instead of
   crossing the boundary.
4. Implement one canonical production path. Do not represent a stub,
   placeholder, mock, fallback, compatibility path, or narrowed scope as
   complete. Fail fast when a real prerequisite is absent.
5. Treat raw source data as immutable unless the project instructions
   explicitly authorize a mutation.
6. Verify the full change locally. Project-declared verification commands:
{verification}
7. Update existing task state and README documentation when behavior,
   configuration, launch, or debugging instructions changed.
8. Inspect the final diff for ownership violations, dead code, secrets, and
   accidental artifacts. Commit the verified work on this dedicated branch
   with a precise message, then stop. Autodev integration is a separate gate.

Complete exactly one work item in this pass. Do not merely describe what you
would do; carry it through implementation, verification, task-state update,
and commit when its prerequisites are present."""
    if role is None:
        return base
    return f"{base}\n\nRole law:\n{compose_law(project.loop, role)}"
