# Working on Autodev

Read `README.md`, `docs/ontology.md`, and `docs/contracts.md` before changing the
runtime. The ontology is a product contract; preserve its terms and boundaries.

## Architecture

Autodev runs full native Harness Agents (currently Codex and Claude Code) in
separate tmux sessions. The native harness supplies reasoning, tools, credentials,
and user settings. Autodev supplies scoped workspaces, operating contracts,
interface validation, task ledgers, and publication. Keep runtime dependencies
empty and provider selection explicit; do not introduce an API-based agent loop.

A managed project can be any ordinary workspace; Git is an optional execution
profile. The workspace root contains schema-1 `autodev.toml`. Each Pillar is a
peer direct-child directory with schema-1 `pillar.toml` at its root. All content
under that directory belongs to its boundary, at any depth. Do not introduce
departments, nested Pillars, a separate contracts root, or a duplicate registry
of Pillar paths. Discover descriptors and reject invalid boundaries explicitly.

A Pillar contract includes a short structured natural-language introduction,
input/output descriptions, deterministic artifact paths and formats, schemas,
fixtures, dependencies, and executable checks. Interfaces and fixtures
exist first. Keep `interface-ready` distinct from `implementation-ready`; fixture
responses must not masquerade as completed functionality. Publication checks the
combined workspace, including declared consumer checks.

Each Pillar has exactly one implicit Pod with at least one template-based Harness
Agent. A Project Manager is optional, with at most one per Pod. Each Harness Agent
has its own canonical ledger at `<pillar>/tasks/<agent>/ledger.json`. Workers read
and claim their own tasks, deliver outputs, and record completion or blockage.
The PM normally creates/revises assignments and is the only Harness Agent role
with a view across that Pod's ledgers. Without a PM, workers can tend their own
assignments. There is no central Orchestrator task queue or separate acceptance
loop. Cross-Pod coordination uses public contracts. These role/context boundaries
are not an OS sandbox for native harnesses with host access.

Memory is explicitly deferred. Do not implement file-backed memory, Dreamweaver
integration, or memory commands until the user asks.

## Code map

- `config.py`, `pillars.py`: configuration, discovery, validation, ownership.
- `scaffold.py`, `wizard.py`: generic workspace and interface-first Pillar setup.
- `agent_templates/`: packaged role templates and deterministic deliverables.
- `contracts.py`: strict schema vocabulary and executable artifact checks.
- `tasks.py`, `task_plans.py`, `storage.py`: scoped ledgers, dependency readiness,
  PM plan import, atomic updates, locks, and interrupted-write recovery.
- `workspaces.py`, `integrate.py`: isolated filesystem copies or sparse Git
  worktrees, ownership/conflict checks, verified publication.
- `providers.py`, `sessions.py`, `prompts.py`: native CLI arguments, tmux lifecycle,
  actor bindings, and role-scoped operating contracts.
- `operations.py`, `cli.py`, `service.py`: shared operations, CLI, local project UI.
- `fleet.py`, `web/`: cached operator telemetry, Pillar overview, Pillar agent graph,
  task boards, agent drill-down, and local frontend assets. The human operator
  may observe all Pods; this must not widen worker ledger access. Keep demo data
  visibly separate from live observations and runtime mutations disabled in demo.
  UI navigation follows Workspace → Pillar → Harness Agent. Keep Pod as an
  internal grouping; avoid duplicate scorecards above the Pillar cards.
- `state.py`: external runtime paths and project registry.
- `skills/autodev-operator/`, `skill_install.py`: canonical packaged operator
  skill and symlink installation. Preserve the runtime resolver's location logic.

Authored contracts and task ledgers belong in their Pillars. Execution copies,
logs, locks, recovery journals, registry, and UI tokens belong under `AUTODEV_HOME`,
then `$XDG_STATE_HOME/autodev`, then `~/.local/state/autodev`. Temporary Pillar
scaffolds may be staged under excluded `.autodev/` before an atomic rename.

## Development

Use Python 3.12 and uv. Keep typed functions, pathlib paths, explicit UTF-8,
domain exceptions, and subprocess argument arrays. Use shlex quoting when a
native tool requires shell text. Do not edit the lockfile by hand.

```sh
uv sync --locked --python 3.12
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run autodev --help
uv build
```

Run focused tests during iteration and the complete checks for runtime changes.
Documentation-only changes need command/link and diff review. Use disposable
filesystem/Git projects and isolated `AUTODEV_HOME` in tests. Real tmux tests use
fake harness executables, skip if tmux is unavailable, and clean up their sessions;
they must never use real provider accounts. Report failed or skipped checks.

## Change invariants

- Keep schemas, templates, scaffolds, prompts, examples, docs, and the operator
  skill consistent. This is the first product implementation: maintain one canonical
  v1 design. Do not add historical schemas, compatibility adapters, migration
  workflows, or per-Pillar version negotiation. Dependencies name current Pillars.
- Write ownership cannot overlap or include contracts, schemas, templates, or
  ledgers. Visibility does not grant ownership. Check the complete Git branch
  diff as well as uncommitted files. Verify outputs before recording completion.
- Preserve isolated worker progress, stable output checks, conflict detection,
  clean Git integration, and rollback/merge-abort behavior. Serialize shared
  publication and ledger mutations, not independent harness execution. Expensive
  validation must not hold the Pod ledger lock.
- Bind each launched session to its actor and canonical project. Worker task
  commands cannot select other identities or expose other workers' ledgers.
- `runtime.bypass_permissions` controls per-session bypass flags only. Do not
  rewrite global provider settings or silently substitute providers/models.
- Keep the UI bound to one project on `127.0.0.1`; mutations require its token
  (mode 0600), bounded requests, and validation before atomic config replacement.
  UI saves are ordinary local edits. Preserve project identity when editing.
- Do not stage/commit unrelated user changes, install provider authentication,
  replace incompatible skill links, or erase preserved worker workspaces.
