# Autodev

This is the canonical Autodev v1 design. All authored descriptors use
`schema_version = 1`.

Autodev runs full native coding harnesses—currently Codex and Claude Code—in
separate tmux sessions, with owned workspaces, executable output contracts, and
individual task ledgers. Projects can produce software, research, analysis,
documents, or other artifacts. Git is an optional execution profile.

Autodev launches the user's installed harness and inherits its authentication,
tools, extensions, and defaults. It does not implement an LLM reasoning loop or
install or authenticate providers. Python 3.12, uv, and tmux are required for
execution; Git is required only for the Git profile. There are no Python runtime
dependencies.

## Pillars are capability boundaries

```text
workspace/
├── autodev.toml
├── frontend/
│   ├── pillar.toml
│   ├── src/
│   ├── schemas/
│   └── tasks/
│       ├── builder/ledger.json
│       └── manager/ledger.json
└── research/
    ├── pillar.toml
    ├── fixtures/
    └── output/
```

Every Pillar is a direct child of the workspace root, identified by its slug.
Its required descriptor is always `<slug>/pillar.toml`. All directories beneath
it belong to that boundary, however deep. Pillars are peers: intermediate
organizational directories and nested Pillars are rejected. Invalid descriptors
remain declared boundaries and produce validation errors.

The workspace manifest does not duplicate a list of Pillars. Autodev discovers
root descriptors, excluding `.git`, `.venv`, `node_modules`, `__pycache__`, and
`.autodev`. Discovery rejects misplaced descriptors outside those excluded
runtime/dependency directories. Symlinks cannot relocate boundaries or declared
artifact paths.

Each Pillar has one implicit **Pod**, with at least one **Harness Agent** based
on a template. There is no Pod declaration and no required manager. An optional
`project-manager` template gives one Harness Agent the ability to read and tend
the individual ledgers across its own Pod. Each worker reads its own tasks,
delivers its outputs, and updates its own ledger.

See [the ontology](docs/ontology.md) for the exact terms and
[the contract reference](docs/contracts.md) for descriptor fields.

## Create a workspace and its first interface

From the shared Autodev checkout:

```sh
uv sync --locked --python 3.12
uv run autodev init /path/to/workspace --id my-project --name "My Project"
uv run autodev pillar create /path/to/workspace research \
  --summary "Produce research reports with traceable evidence." \
  --template researcher --agent researcher
uv run autodev validate /path/to/workspace --json
uv run autodev pillar verify /path/to/workspace research --interface
uv run autodev register /path/to/workspace
```

Use `uv run --project /path/to/autodev autodev ...` from elsewhere. The
interactive alternative is `uv run autodev setup /path/to/workspace`.

`pillar create` writes a complete, validated interface: `pillar.toml`, schemas,
fixtures, and a runnable `interface.py` that returns an explicit unavailable
response. It refuses to replace an existing directory. To adopt existing
content, author `pillar.toml` and its referenced files in that directory, then
validate. The files in [the example workspace](examples/research-project) show
this structure, including an optional Project Manager and multiple workers.

A newly created Pillar is `interface-ready`. Consumers can develop against its
fixtures while implementation proceeds. To declare `implementation-ready`,
provide the real declared outputs, replace or extend the checks with meaningful
implementation and consumer checks, and update the descriptor. `pillar verify`
without `--interface` requires implementation readiness and real outputs.

## Agent-native contracts

`pillar.toml` combines machine-readable declarations with a short natural-language
introduction: summary, responsibility, consumption instructions, constraints,
and descriptions of each input and output. A consumer can find and understand
the interface without exploring the implementation.

Output paths, schema paths, fixture paths, and agent ownership paths are
relative to the Pillar root. Workspace context paths are relative to the
workspace root. Every JSON artifact requires a schema; every public output
requires a fixture. Interface checks are explicit commands, run from the Pillar
root. `{python}` expands to Autodev's interpreter.

Dependencies name peer slugs and consume their current canonical contracts. Publication checks
all Pillar interfaces and all implementation-ready outputs, including consumer
checks declared by peers. These are executable gates over declared behavior;
Autodev cannot prove behavior omitted from those checks.

Schemas use the strict vocabulary documented in [docs/contracts.md](docs/contracts.md).
Unsupported keywords fail validation rather than being silently ignored. External
formats and richer behavior can be checked with the declared commands.

## Templates and individual task ledgers

List shipped templates:

```sh
uv run autodev templates
```

Available templates are `generalist`, `researcher`, `engineer`, `analyst`, and
`project-manager`. Templates specify purpose, instructions, standing goal, and
deterministic deliverables. An instance selects a provider, local ID, and owned
paths. Custom templates can live inside their Pillar and be referenced by a
relative TOML path. Runtime identities use `<pillar>--<agent>`; `--` is reserved
and cannot occur within a slug or local ID.

Each agent's canonical ledger lives at `<pillar>/tasks/<agent>/ledger.json`.
Ledgers are accessed through atomic runtime operations and excluded from execution
copies and Git worktree changes. Only a Project Manager has a Pod-wide ledger
view. Workers receive their own view; other Pods' internal ledgers are outside
both roles' scope. The local CLI and UI are trusted operator tools: role scopes
are workflow boundaries, not an OS sandbox for a harness with host access.

A Project Manager creates tasks, imports plans, revises queued or blocked work,
and reads completion evidence. A Pod without a manager permits agents to tend
their own assignments. No manager is manufactured for a single-agent Pillar.

For the example workspace's research Pod:

```sh
# PM imports a structured plan into each worker's own ledger.
uv run autodev task import /path/to/workspace \
  /path/to/workspace/research/fixtures/work-plan.json --actor research--manager

# PM inspects the Pod and starts/nudges workers with ready tasks.
uv run autodev task list /path/to/workspace --actor research--manager
uv run autodev task dispatch /path/to/workspace --actor research--manager

# These operations are performed by the worker itself.
uv run autodev task list /path/to/workspace --actor research--researcher
uv run autodev task claim /path/to/workspace --actor research--researcher
uv run autodev task complete /path/to/workspace TASK_ID --actor research--researcher
uv run autodev task block /path/to/workspace TASK_ID \
  --actor research--researcher --reason "The requested source is unavailable."
```

The session binds its own actor identity, so `--actor` may be omitted inside the
harness. Outside a session it is required. A session cannot select another actor
or another project's ledger through the task CLI.

Task plans require unique local keys, existing agents in the manager's Pod,
instructions, acceptance criteria, and acyclic dependencies. Imports resolve
forward references and are idempotent. Updates to multiple ledgers use a recovery
journal so an interrupted import is completed before the next ledger access.

Workers claim at most one task at a time. Independent tasks can run concurrently;
dependencies become ready when their producing workers record completion.
`task complete` validates the required artifacts, runs checks, publishes owned
changes, and records delivery evidence in the worker's ledger. Failures leave the
task running for correction. Workers use `task block` to record an impediment;
the PM uses `task revise` to update instructions and acceptance criteria and
return queued/blocked work to the queue. There is no Orchestrator acceptance
queue. The harness reads its ledger again after completion and continues with
its next ready task. `goal` or PM `dispatch` can nudge an idle session after new
assignments arrive; Autodev does not run a background polling scheduler.

The Project Manager template is in
[src/autodev/agent_templates/project-manager.toml](src/autodev/agent_templates/project-manager.toml).
It maintains ledgers and produces `task-plan.json`; it does not do its workers'
implementation or mark their tasks complete. Cross-Pod coordination uses public
Pillar contracts and outputs.

## Harness execution and publication

```sh
uv run autodev doctor /path/to/workspace --json
uv run autodev ensure /path/to/workspace --no-start
uv run autodev ensure /path/to/workspace --send-goal
uv run autodev status /path/to/workspace --json
uv run autodev goal /path/to/workspace research--researcher
uv run autodev stop /path/to/workspace
```

`ensure --send-goal` supplies the worker's operating contract and scoped ledger
view. The worker claims its own task; startup does not invent an assignment.
Existing sessions are reused. Stopping preserves workspaces and ledgers.

The default `filesystem` profile creates a separate execution copy for each
Harness Agent containing its owned paths, explicit read context, and public
contracts. Publication detects edits outside ownership and conflicts with
changes in the canonical workspace. It verifies a combined candidate against
all Pillar checks before replacing owned files, with rollback on write errors.
Runtime publications serialize; arbitrary external readers of a multi-file
output should use its completed delivery record as the readiness signal.

The `git` profile uses sparse Git worktrees and dedicated branches. Set
`project.execution = "git"` and `project.base_branch` to an existing local
branch. The workspace must be the repository root. Commit the workspace manifest
and every Pillar's descriptors, schemas, fixtures, and relevant source before
launching. Workers commit their own verified changes before `task complete`.
Integration requires clean source and base worktrees, owned branch changes,
whitespace checks, and contract checks on the combined result. Failed integration
is aborted. A successful merge refreshes the worker branch.

`runtime.bypass_permissions` is a required boolean. False preserves the native
harness's configured behavior. True passes that provider's explicit bypass flag
to its managed sessions. Autodev never changes global provider settings.

Runtime copies, Git worktrees, session logs, registry, and transaction locks live
under `AUTODEV_HOME`, otherwise `$XDG_STATE_HOME/autodev`, otherwise
`~/.local/state/autodev`. Authored contracts and per-agent ledgers belong to their
Pillar workspaces. Memory implementation is deliberately deferred.

## Local UI and operator skill

`uv run autodev ui PROJECT` serves one project at `127.0.0.1` on its configured
port. The main page shows Pillar cards with their work and session status, without
repeating the same counts in scorecards. Navigation follows Workspace → Pillar →
Harness Agent: selecting a Pillar expands its agents in the sidebar and opens its
graph. Task board, agent list, and contract are views within that Pillar. Agent
details show the current assignment, execution stages, dependencies, delivery
evidence, and on-demand session output. Workspace-wide tasks and activity remain
secondary views. Pod is an internal grouping, not a user-facing navigation level.

The trusted human operator can observe all Pods. This does not broaden a Harness
Agent's scoped ledger API. Fleet observation refreshes every two seconds, using
one tmux session query and one ledger read per Pod per snapshot. Unchanged views
retain their state; failed refreshes show an explicit disconnected warning.
A claimed task with an offline session is marked interrupted. The UI reports
recorded work stages, not inferred model thoughts or completion percentages.

Workers can report meaningful steps with `task progress PROJECT TASK_ID --actor
PILLAR--AGENT --message "Current step and outcome"`. Completion automatically
records validation, publication, and delivery events. The worker still controls
its task state; moving cards manually cannot bypass contract checks.

The clearly labeled 60-agent demonstration runs a finite browser-only scenario:
six distinct Pillars and 180 assignments, with dependency-aware claims, validation,
publication, blockers, recovery, and downstream handoffs. Pause, step, change speed,
or restart playback. The session transcript is explicitly simulated. Runtime
controls stay disabled: no real tasks, files, or harness sessions are created.
A `?demo=1` link preserves demo mode on reload; exiting returns to live observations.
Run `node --test tests/web/demo.test.cjs` to verify the scenario's invariants.

Configuration edits target `autodev.toml` or a Pillar descriptor, with validation
before replacement. Fleet telemetry, session output, and mutations require the
project token, stored with mode `0600` in external runtime state. All frontend
assets are packaged locally; no web CDN or frontend build is required.

`uv run autodev skill install` links the canonical operator skill into the user's
Codex and Claude skill directories. It refuses to replace existing incompatible
paths. The user's current conversation is the Orchestrator; it coordinates
Pillars and interfaces, while PM harnesses tend their Pod's individual ledgers.

Each Pillar with a PM also has a **GM chat** tab for direct operator questions and
explicitly requested employee changes within that Pillar. Install the scoped GM
skill with `uv run autodev skill install --gm`. Filesystem execution copies retain
each agent's identity in native `AGENTS.md`/`CLAUDE.md` entrypoints. See
[GM chat and persistent identity](docs/gm-chat.md) for delivery, edit boundaries
and compaction recovery behavior.

## Development

```sh
uv sync --locked --python 3.12
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run autodev --help
uv build
```

Tests use disposable directories and Git repositories. Native-session tests run
fake harness executables inside real tmux sessions and never contact AI services.
The license is MIT.

## Agency website

`website/` contains the Next.js agency website, its Request a Quote flow, and
the self-contained fleet demo. Vercel uses `website` as the project root. See
[website/README.md](website/README.md) for development and email delivery setup.
