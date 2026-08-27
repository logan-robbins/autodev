# Project Descriptor Contract

Create `autodev.toml` at the managed repository's Git root. Schema 3 requires every field shown here. Provider tables are optional; each omitted provider setting uses that installed CLI's local default. The `[loop]`, `[roles.*]`, and agent `pod` tables are optional and additive — a descriptor with none of them still loads.

```toml
schema_version = 3

[project]
id = "project-id"
name = "Project Name"
base_branch = "main"
instructions = "Repository-wide implementation and operating constraints."
context_roots = ["docs/", "pyproject.toml", "uv.lock"]
verify_commands = ["uv run pytest"]

[runtime]
session_pattern = "autodev-{project}-{agent}"
ui_port = 8765
bypass_permissions = false

[providers.codex]
command = "codex"
model = "gpt-5.6-terra"
effort = "high"

[providers.claude]
command = "claude"
model = "sonnet"
effort = "high"

[[agents]]
id = "backend"
provider = "codex"
pod = "backend"
purpose = "Own the backend service and its tests."
goal = "Take the highest-priority actionable backend task and complete one verified vertical change."
write_roots = ["src/backend/", "tests/backend/"]
read_roots = ["src/shared/"]
```

## Optional schema-3 tables

```toml
[loop]
sequence = ["project-manager", "engineering", "project-manager"]
reenter_product_manager_when = ["new-requirement", "queues-exhausted", "roadmap-contradiction"]
max_concurrent = 4

[roles.product-manager]
shape = "research"
charter = "Own the Pillar tier. Bootstrap pillars from product.json; expand an approved pillar into proposed Features."

[roles.project-manager]
shape = "reconcile"
charter = "Own the Feature backlog. Split into contract-anchored leaves + depends_on edges; clean proven-done leaves."

[roles.engineering]
shape = "contract-first"
charter = "Own the Task/leaf. Interfaces + red tests before internals; implement your slice only; verify green."

[roles.technical-writer]
shape = "document"
charter = "Own the pillar docs. Run last, after every leaf verifies; produce a data-flow-first README + TECHNICAL map."

[pods]
[pods.members.product-manager]
provider = "claude"
[pods.members.project-manager]
provider = "claude"
[pods.members.engineering]
provider = "codex"
[pods.members.technical-writer]
provider = "claude"
```

- `[roles.<id>].shape` is one of `research`, `contract-first`, `reconcile`, `document`; `charter` is non-empty. The `technical-writer` role uses shape `document` and runs docs-last.
- Every `[loop].sequence` entry must name a configured `[roles.*]`. The feature loop is `project-manager → engineering → project-manager`; the Product Manager (pillar-level) and Technical Writer (docs-last) are **not** feature-loop entries. `max_concurrent` is a positive integer.
- `[pods]` declares the **team shape**, not the teams: `[pods.members.<role>]` names a configured `[roles.*]` and binds it to a `provider` (`model`/`effort` optional). One pod is derived per pillar — `pm-<pillar>`, `pjm-<pillar>`, `eng-<pillar>`, `tw-<pillar>`, plus a product-level `pm` bootstrap — with disjoint write roots. The descriptor is never auto-mutated; pods appear as `pillar.json` files appear in the tree.
- A descriptor must declare at least one `[[agents]]` table **or** a `[pods]` template. A verb-only role (PM/PjM) may have empty `write_roots`, since it authors only the tree through verbs.
- Agent `pod` (on a static `[[agents]]`) groups agents for role assignment; it uses the same id rules as agent ids.

## The product tree

Durable product intent lives in JSON files authored **only** through `autodev product` verbs (never hand-edited):

```jsonc
// product/product.json — the cold-start vision seed (operator-authored at setup)
{ "vision": "what we are building and for whom", "constraints": ["optional hard constraints"] }
```

```jsonc
// product/pillars/<pillar>/pillar.json — a major product area (PM-owned, operator-gated)
{
  "id": "replay-engine",   // lowercase id, starts with a letter, <= 28 chars
  "name": "Replay Engine",
  "why": "the problem this area exists to solve",
  "value": "the value proposition delivered",
  "goal": "the observable outcome that means this pillar is done",
  "approval": "proposed",  // proposed | approved  — the operator gate
  "docs": "pending"        // pending | active | done — the docs-last checkpoint (optional)
}
```

- A pillar id is capped at 28 characters so stamped pod ids (`pjm-<pillar>` / `eng-<pillar>`) stay within the 32-character id form.
- Under a pillar, `features/<feature>/feature.json` is the enumeration unit and `features/<feature>/leaves/<leaf>/leaf.json` is the Task (an "Epic" is an optional `epic` label on sibling leaves, not a file tier).
- The orchestrator gates on `approval` (pillar and feature) and drives docs-last from `docs`; nothing downstream of a pillar runs until it is approved.

## Constraints

- `project.id` and every agent ID use lowercase letters, digits, and hyphens, start with a letter, and contain at most 32 characters.
- `project.base_branch` must resolve to a local commit.
- `runtime.session_pattern` contains `{project}` and `{agent}` exactly once. `{provider}` is optional. Rendered names allow only letters, numbers, underscores, and hyphens and have a 100-character limit.
- `runtime.ui_port` is a dedicated, unused localhost port from 1024 through 65535.
- `runtime.bypass_permissions` is a required boolean and applies to all workers launched for this project.
- Every agent has at least one relative `write_roots` entry. Write roots cannot overlap, escape the repository, or include `autodev.toml`.
- Use `context_roots` and `read_roots` for shared context. Do not grant write ownership merely to make a file visible.

## Command Sequence

Append the project path or registered ID after the command prefix returned by `scripts/runtime.py`:

1. `autodev validate <project> --json`
2. `autodev register <project>`
3. `autodev doctor <project> --json`
4. Commit `autodev.toml` on `project.base_branch`.
5. `autodev ensure <project> --no-start`
6. `autodev ensure <project> --send-goal`
7. `autodev status <project> --json`
8. `autodev ui <project>`
