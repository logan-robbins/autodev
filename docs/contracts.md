# Descriptor and ledger contracts

## Workspace: autodev.toml, schema 1

`[project]` requires `id`, `name`, and `instructions`. `execution` is `filesystem`
(default) or `git`; `base_branch` defaults to `main` for Git. `context_roots` and
`verify_commands` are optional arrays. `[[agents]]` and a Pillar registry are not
allowed here: discovery uses `<workspace>/<slug>/pillar.toml`.

`[runtime]` requires `ui_port` (1024–65535) and boolean `bypass_permissions`.
`session_pattern` defaults to `autodev-{project}-{agent}`; both placeholders must
occur exactly once. `{provider}` is optional. Rendered names contain only letters,
numbers, underscores, and hyphens and are limited to 100 characters.

Optional `[providers.codex]` and `[providers.claude]` tables accept `command`,
`model`, and `effort`. Unspecified settings use the native harness defaults.

## Pillar: pillar.toml, schema 1

- `[pillar]`: `slug` must match its directory; `summary` and `responsibility` are
  required natural-language strings.
- `[interface]`: `state` is `interface-ready` or
  `implementation-ready`; `consumption` and `constraints` are required strings.
  `checks` is a nonempty command list. `dependencies` lists peer slugs, for example
  `["research"]`; use `[]` for none. Consumers use each Pillar's current canonical
  contract. `inputs` may be an empty array.
- `[[interface.outputs]]`: at least one public output is required. Each input,
  output, and agent deliverable declares `id`, `path`, `format`, and `description`.
  JSON artifacts require `schema`. Every public output requires a `fixture`.
- `[[agents]]`: at least one assignment with local `id`, `template`, and `provider`.
  Optional `purpose` and `goal` override the template. `write_roots` defaults to
  `output/<agent>/`; `read_roots` defaults to empty. `deliverables` can override
  the template's declarations. All paths are relative to this Pillar.

Supported formats: `application/json`, `text/plain`, `text/markdown`,
`application/octet-stream`, and `directory`. Text must be nonempty UTF-8;
binary and directory artifacts require the declared file/directory to exist.
Use checks for substantive content validation. Output files may be absent before
implementation, while schema and fixture references must resolve immediately.

Keep the descriptive introduction short, approximately 150–300 words. Descriptions
explain meaning; fields and schemas establish deterministic access and validation.

## Templates: schema 1

A template TOML requires `purpose`, `instructions`, `goal`, and nonempty
`[[deliverables]]`. An optional `role` is `worker` (default) or `project-manager`.
A built-in name resolves inside the Autodev package. A relative TOML path resolves
inside the Pillar. `{agent}` in template deliverable strings resolves to the
instance's local ID. The instance must own every required deliverable destination.

Each Pod can have zero or one Project Manager. To add one to an existing Pillar,
copy the packaged `task-plan.schema.json` into that Pillar's `schemas/` and add:

```toml
[[agents]]
id = "manager"
template = "project-manager"
provider = "codex"
```

It owns `output/manager/` by default and delivers `task-plan.json`. See the example
workspace for a PM and two workers in the same Pod.

## Strict schema vocabulary

Artifact schemas use an explicit subset of JSON Schema syntax. They are not a
claim of full JSON Schema draft support. Every schema object requires `type`:
`object`, `array`, `string`, `integer`, `number`, `boolean`, or `null`.

Supported keywords are `properties`, `required`, boolean `additionalProperties`,
`items`, `enum`, `const`, `minLength`, `maxLength`, `minimum`, `maximum`, `minItems`,
`maxItems`, `description`, and `title`. Nested properties/items use the same
vocabulary. Unknown keywords—including `$ref`, `$schema`, and `pattern`—are
rejected. No Python dependency or network schema resolver is required. Use
Pillar checks for a richer schema validator or domain-specific assertions.

## Task plans and ledgers

The Project Manager's task plan has `status = "planned"`, a `summary`, and
nonempty `tasks`. Each task declares a unique local `key`, `title`, full assigned
`agent` ID, `instructions`, nonempty `acceptance` strings, and `dependencies` by
local key. References may be forward references but must form a DAG. Assignments
must remain inside that PM's Pod. Identical imports do not duplicate tasks.

Every worker has its own ledger. Runtime transitions are:

```text
queued → running → completed
            ↓
          blocked → queued (maintainer revises the assignment)
```

`task claim` atomically selects the worker's next ready task. Dependencies must
be `completed`; the worker sees readiness without receiving another worker's
ledger contents. There is at most one running task per worker. A task is pinned
to its configuration/template/schema digest; changed contracts require revision.

`task complete` is performed by the executing worker. It validates deliverables
and checks, publishes owned changes, and stores a delivery record. Blocked or
unavailable result envelopes cannot complete a task. A failed validation or
publication leaves the task running. `task block` records the worker's reason.
The maintainer can use `task revise` for queued/blocked work. A Pod without a PM
permits workers to tend their own assignments.

The runtime serializes ledger writes and recovers interrupted multi-ledger
transactions. Git profiles add a local Git exclude for the Pod's task directory;
ledgers persist in the canonical Pillar without contaminating worker commits.

## Observable execution

Task records include `stage`, `progress`, `updated_at`, and timestamped `events`.
The worker's `task progress --message` records a meaningful work step while the
task is running. Runtime completion records `validating`, then `publishing`, then
`completed`; a failed check returns the visible stage to `working` with the error.
These stages provide observation inside the existing task lifecycle. They do not
create a separate approval queue. The ledger retains the most recent 100 events
per task, and the UI activity feed shows the most recent 100 across the workspace.

The operator's authenticated fleet endpoint observes current Pod ledgers and
session presence. A session being online is not proof the harness is making
progress; the UI shows the latest reported task step and its timestamp. A running
task whose session is offline is marked interrupted. Dependency graph edges come
from actual task references; PM assignment-scope lines are visually distinct.
