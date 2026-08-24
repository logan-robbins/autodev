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
charter = "Own a Pillar. Extract facts; rank recency x relevance; emit the Pillar's Features."

[roles.project-manager]
shape = "reconcile"
charter = "Own a Feature. Split into complete leaves; emit depends_on edges."

[roles.engineering]
shape = "contract-first"
charter = "Own a Leaf. Interfaces + red tests before internals."
```

- `[roles.<id>].shape` is one of `research`, `contract-first`, `reconcile`; `charter` is non-empty.
- Every `[loop].sequence` entry must name a configured `[roles.*]`. `max_concurrent` is a positive integer.
- Agent `pod` groups agents for role assignment; it uses the same id rules as agent ids.

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
