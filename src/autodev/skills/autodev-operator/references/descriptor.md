# Workspace and Pillar contracts

Workspace `autodev.toml` uses schema 1. It contains `[project]` with `id`, `name`,
`instructions`, `execution` (`filesystem` by default, or `git`), optional
`context_roots` and `verify_commands`, and `base_branch` for Git. `[runtime]`
requires `ui_port` (1024–65535) and `bypass_permissions`; `session_pattern`
defaults to `autodev-{project}-{agent}`. Both placeholders occur exactly once;
`{provider}` is optional. Optional `[providers.codex]` and
`[providers.claude]` tables accept command/model/effort. Omit unspecified settings.

Do not put agents or a duplicate Pillar-path registry in this manifest. Discover
peer `<workspace>/<slug>/pillar.toml` descriptors. Slugs and local agent IDs use
lowercase letters, digits, and hyphens; start with a letter; max 32 characters.
The delimiter `--` is reserved for full agent identities.

## Pillar schema 1

- `[pillar]`: `slug` matching the directory, short `summary`, `responsibility`.
- `[interface]`: `state` (`interface-ready`
  or `implementation-ready`), `consumption`, `constraints`, `inputs` (may be []),
  `dependencies` listing peer slugs (or []), nonempty command `checks`.
  Each dependency consumes its Pillar's current canonical contract.
- `[[interface.outputs]]`: nonempty list of `id`, `path`, `format`, `description`,
  `fixture`, and `schema` for JSON. Input declarations use the same artifact fields
  but do not require fixtures.
- `[[agents]]`: nonempty list of local `id`, `template`, `provider`, optional
  `write_roots` (default `output/<agent>/`), `read_roots`, purpose/goal overrides,
  and deliverable overrides.

Artifact and agent-root paths in the Pillar descriptor are Pillar-relative;
workspace `context_roots` are workspace-relative. Paths cannot escape through
`..` or symlinks. Write roots cannot overlap another agent's roots or include
contracts, templates, schemas, fixtures, or ledgers. Every agent deliverable must
be inside that agent's owned roots. Declare worker-to-worker read context
explicitly; peer Pillar dependencies supply their public output paths, not
unrestricted access to their internals.

Supported formats are `application/json`, `text/plain`, `text/markdown`,
`application/octet-stream`, and `directory`. JSON requires a schema. The strict schema subset accepts explicit
single types, properties, required, boolean additionalProperties, items, enum,
const, length/item/numeric bounds, description, and title. Unsupported keywords
fail, including `$schema`, `$ref`, and `pattern`; use executable checks for richer
validation. Nonempty text, an existing directory, or a schema-valid JSON envelope
is only a structural gate, not proof of the task outcome.

Built-in templates: generalist, researcher, engineer, analyst, project-manager.
Custom template TOML files live inside the Pillar. They declare schema_version=1,
purpose, instructions, goal, optional role, and nonempty deliverables. The PM
requires its `schemas/task-plan.schema.json`; copy the packaged schema into the
Pillar when adding this template manually. No PM is required. Built-in templates
are starting contracts: ensure their deliverables, schemas, and checks match the
actual work rather than using the same generic result envelope for every role.

## Checks and interface readiness

Keep the structured introduction short: explain responsibility, consumption,
output layout, and constraints without making a consumer read implementation.
Author the public interface and executable fixtures before workers implement it.
The scaffold's `interface.py --check` only demonstrates an honest unavailable
fixture. Replace or extend it with checks of the actual capability as work lands.

Pillar `checks` run from the Pillar root; workspace `verify_commands` run from
the execution/candidate workspace root. `{python}` resolves to the runtime
interpreter. Checks are trusted project commands with a 300-second timeout per
command. Declare any scripts and dependencies they need in the agent's readable
context. Keep them deterministic, noninteractive, and non-mutating so they can
run both before publication and against the combined candidate.

Agent checks receive runtime-owned `AUTODEV_CHECK_PROJECT` (canonical descriptor),
`AUTODEV_CHECK_AGENT_ID`, and `AUTODEV_CHECK_TASK_ID` (active task or an empty
string). When a task's outcome depends on its particular input or acceptance
criteria, use these values to check the artifact against the real assignment;
a self-reported task ID or `status: completed` is not sufficient evidence.
Do not supply these variables yourself to manufacture verification context.
Plain Pillar/interface checks remove this context and must validate the public
contract independently. The variables are not an OS security boundary.

Publication checks the producing agent and all public Pillar contracts: fixtures
for `interface-ready` Pillars and actual outputs for `implementation-ready` ones.
Consumers encode compatibility requirements in their own checks. Completion of
an agent's task does not automatically promote its Pillar's interface state.
The maintainer promotes the descriptor only after actual public outputs and
substantive checks exist, then runs `pillar verify PROJECT SLUG` without
`--interface`. A changed descriptor/schema/template also changes task digests;
revise affected queued/blocked assignments before further execution.

## Creation and discovery

Use the resolved runtime prefix, followed by these arguments:

```sh
init /path/to/workspace --id my-project --name "My Project"
pillar create /path/to/workspace research --summary "Evidence-backed research" --template researcher
validate /path/to/workspace --json
pillar verify /path/to/workspace research --interface
register /path/to/workspace
doctor /path/to/workspace --json
ensure /path/to/workspace --no-start
ensure /path/to/workspace --send-goal
status /path/to/workspace --json
pillar show /path/to/workspace research
pillar locate /path/to/workspace research/output/report.md
```

`init` creates a manifest in an existing or new workspace without replacing one;
`pillar create` refuses an existing Pillar directory. For adoption, inspect and
author the descriptor and referenced files directly. Use `setup` only when a
human-interactive wizard is appropriate. Registering associates an ID with this
workspace; it does not copy the project or launch sessions. See
[operations.md](operations.md) for task planning, publication, and recovery.
