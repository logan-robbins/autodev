# Workspace and Pillar contracts

Workspace `autodev.toml` uses schema 1. It contains `[project]` with `id`, `name`,
`instructions`, `execution` (`filesystem` by default, or `git`), optional
`context_roots` and `verify_commands`, and `base_branch` for Git. `[runtime]`
requires `ui_port` (1024–65535) and `bypass_permissions`; `session_pattern`
defaults to `autodev-{project}-{agent}`. Optional `[providers.codex]` and
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

Paths are Pillar-relative. Checks run from its root; `{python}` resolves to the
runtime interpreter. Supported formats: JSON, plain text, Markdown, binary, and
directory. JSON requires a schema. The strict schema subset accepts explicit
single types, properties, required, boolean additionalProperties, items, enum,
const, length/item/numeric bounds, description, and title. Unsupported keywords
fail; use executable checks for richer validation.

Built-in templates: generalist, researcher, engineer, analyst, project-manager.
Custom template TOML files live inside the Pillar. They declare schema_version=1,
purpose, instructions, goal, optional role, and nonempty deliverables. The PM
requires its `schemas/task-plan.schema.json`; copy the packaged schema into the
Pillar when adding this template manually. No PM is required.

## Commands

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
```

Per-agent ledgers are `<pillar>/tasks/<agent>/ledger.json`; use task commands for
atomic updates. A PM plan is JSON with `status: planned`, summary, and tasks
containing key, title, full agent ID, instructions, acceptance strings, and
dependency keys. Import with `task import PROJECT PLAN --actor PILLAR--MANAGER`.
Dependencies must form a DAG in the same Pod. Workers use list/claim/complete/block
with their own bound actor. Contract changes require the maintainer to revise
queued/blocked assignments. A running worker can block first.
