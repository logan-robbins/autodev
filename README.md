# Autodev

Autodev is a shared local runtime for autonomous engineering agents. One
Autodev checkout can operate any number of Git repositories elsewhere on the
machine. A managed repository adds exactly one file, `autodev.toml`; Autodev
keeps its worktrees, registry, logs, and runtime state outside that repository.

Autodev does not install, embed, proxy, or authenticate an AI runtime. It starts
the user's existing `codex` or `claude` executable and inherits that CLI's local
account, settings, plugins, skills, MCP servers, and model defaults. The launch
adapters follow the documented [Codex CLI](https://learn.chatgpt.com/docs/developer-commands?surface=cli)
and [Claude Code CLI](https://code.claude.com/docs/en/cli-usage) interfaces.

## Architecture

```text
one Autodev checkout
├── Python orchestration and prompt templates
├── shared project registry
├── one localhost UI process and port per active project
└── AUTODEV_HOME/
    └── projects/
        ├── project-a/{worktrees,logs,ui-token}
        └── project-b/{worktrees,logs,ui-token}

external project-a/                 external project-b/
└── autodev.toml                     └── autodev.toml
```

The project checkout remains the integration worktree. Every configured agent
gets a dedicated branch, sparse worktree, and namespaced tmux session. With the
default session pattern, project `acme` and agent `backend` use:

- Branch: `autodev/acme/backend`
- Session: `autodev-acme-backend`
- Worktree: `$AUTODEV_HOME/projects/acme/worktrees/backend`

The default state root is `~/.local/state/autodev`. Set `AUTODEV_HOME` to move
all generated runtime state. Nothing from the Autodev source checkout is copied
into managed projects.

## Requirements

- Python 3.12
- `uv`
- Git
- tmux
- An installed and authenticated `codex` or `claude` CLI

Only the providers named by a project's agents are required. Autodev has no
runtime Python dependencies.

## Quick start

Clone and prepare the single shared checkout:

```sh
git clone https://github.com/logan-robbins/autodev.git /path/to/autodev
cd /path/to/autodev
uv sync --locked --python 3.12
```

Run the guided setup from any directory. It asks for the existing project root,
integration branch, project instructions, verification commands, agent
ownership, installed CLI settings, tmux session naming, and a dedicated UI
port. After a descriptor preview, it can register the project, launch every
agent, and start that project's editable UI:

```sh
uv run --project /path/to/autodev autodev setup /path/to/project
```

Omit `/path/to/project` to choose it in the wizard. After setup, validate the
descriptor and host tools at any time:

```sh
uv run --project /path/to/autodev autodev validate /path/to/project
uv run --project /path/to/autodev autodev doctor /path/to/project
```

Create all worktrees, start their installed CLIs, and submit each standing
goal:

```sh
uv run --project /path/to/autodev autodev ensure /path/to/project --send-goal
uv run --project /path/to/autodev autodev status /path/to/project
```

`ensure` automatically registers the project with the shared runtime.
It reuses existing worktrees and tmux sessions; it never replaces live agents.
The guided setup requires a clean repository with an initial commit. It offers
to commit `autodev.toml` to the configured integration branch before immediate
launch so every new agent worktree starts with the same project contract.

## The project descriptor

`autodev.toml` is the complete project adapter. There are no project-local
Autodev templates, generated capsules, launch scripts, or copied skills.

```toml
schema_version = 1

[project]
id = "acme-app"
name = "Acme App"
base_branch = "main"
instructions = "Use uv for Python and preserve the public HTTP contract."
context_roots = ["docs/", "contracts/", "pyproject.toml", "uv.lock"]
verify_commands = ["uv run pytest"]

[runtime]
session_pattern = "autodev-{project}-{agent}"
ui_port = 8765

[providers.codex]
model = "gpt-5.6-terra"
effort = "high"

[providers.claude]
model = "sonnet"
effort = "high"

[[agents]]
id = "backend"
provider = "codex"
purpose = "Own the backend service and its tests."
goal = "Take the highest-priority actionable backend task and complete one verified vertical change."
write_roots = ["src/backend/", "tests/backend/"]
read_roots = ["src/shared/"]

[[agents]]
id = "frontend"
provider = "claude"
purpose = "Own the browser application and its tests."
goal = "Take the highest-priority actionable frontend task and complete one verified vertical change."
write_roots = ["src/frontend/", "tests/frontend/"]
read_roots = ["src/shared/"]
```

A complete two-provider example is available at
[`examples/autodev.toml`](examples/autodev.toml).

### Project fields

- `id`: Stable lowercase identifier used in branches, sessions, and state.
- `name`: Human-readable display name.
- `base_branch`: Local integration branch. It must already resolve to a commit.
- `instructions`: Project-wide architecture and operating law included in every
  agent goal.
- `context_roots`: Shared read-only paths added to every sparse worktree.
- `verify_commands`: Canonical commands agents are instructed to run.

### Runtime fields

- `session_pattern`: tmux name template. It must contain `{project}` and
  `{agent}` exactly once; `{provider}` is optional. The rendered name may use
  letters, numbers, underscores, and hyphens, with a 100-character limit.
- `ui_port`: Dedicated localhost port for this project's UI, from 1024 through
  65535. The setup wizard selects the first available, unregistered port at or
  above 8765.

The default is `autodev-{project}-{agent}`. For example,
`team_{provider}_{project}_{agent}` renders as
`team_codex_acme-app_backend`.

Autodev automatically includes common root context when it exists:
`README.md`, `AGENTS.md`, `AGENTS.override.md`, `CLAUDE.md`, `.agents/skills/`,
`.codex/`, `.claude/`, `.gitignore`, and `autodev.toml`.

### Provider fields

Provider tables are optional. When a field is omitted, the installed CLI uses
its own local default.

- `command`: Executable name or absolute path. Defaults to `codex` or `claude`.
- `model`: Optional model alias or identifier passed directly to the CLI.
- `effort`: Optional reasoning/effort value passed directly to the CLI.

There is no provider fallback. If the selected executable or configuration is
unavailable, startup fails with a specific error.

### Agent fields

- `id`: Stable lowercase agent identifier.
- `provider`: Exactly `codex` or `claude`.
- `purpose`: The mechanism this agent owns.
- `goal`: The standing task-selection contract for each pass.
- `write_roots`: Non-empty, relative ownership paths.
- `read_roots`: Additional context paths this agent may inspect but not modify.

Write roots cannot be absolute, escape the repository, own `autodev.toml`, or
overlap another agent's roots. Sparse checkout limits visible source, while
`status` and `merge` independently reject edits outside declared ownership.

## Operating commands

All commands accept a repository directory, an `autodev.toml` path, or a
registered project ID. When run inside a managed repository, read-only commands
can discover the nearest descriptor automatically.

```sh
# Walk through configuration, registration, and optional launch.
uv run --project /path/to/autodev autodev setup /path/to/project

# Start this project's UI on runtime.ui_port.
uv run --project /path/to/autodev autodev ui my-project

# Prepare worktrees without starting agents.
uv run --project /path/to/autodev autodev ensure /path/to/project --no-start

# Start or reuse selected agents and send their goals.
uv run --project /path/to/autodev autodev ensure my-project backend frontend --send-goal

# Print a goal without sending it, then send it to a live session.
uv run --project /path/to/autodev autodev goal my-project backend --dry-run
uv run --project /path/to/autodev autodev goal my-project backend

# Inspect machine-readable runtime, Git, and ownership state.
uv run --project /path/to/autodev autodev status my-project --json

# Stop sessions without deleting their branches or worktrees.
uv run --project /path/to/autodev autodev stop my-project

# Merge one clean, committed, ownership-valid agent branch into the base.
uv run --project /path/to/autodev autodev merge my-project backend
```

By default, each CLI retains its configured permission behavior. `ensure
--yolo` maps to that provider's documented permission-bypass flag and should be
used only when the operator intentionally authorizes unrestricted execution in
an appropriately isolated environment.

`merge` fails unless the agent worktree is clean, its complete branch diff is
inside its write roots, the integration checkout is clean and on
`project.base_branch`, and Git's whitespace check passes. Merge conflicts stay
on the agent branch for explicit resolution and re-verification.

## Per-project UI

Register projects explicitly when they have not been started yet:

```sh
uv run --project /path/to/autodev autodev register /path/to/project-a
uv run --project /path/to/autodev autodev register /path/to/project-b
uv run --project /path/to/autodev autodev projects
```

Each project starts an independent UI bound to `127.0.0.1` on its configured
`runtime.ui_port`. The page exposes only that project, including agent launch,
goal, stop, Git state, ownership state, and an editor for the complete
`autodev.toml`.

Run one UI in the foreground:

```sh
uv run --project /path/to/autodev autodev ui my-project
```

Or keep it running as a logged background process using the default state root:

```sh
mkdir -p ~/.local/state/autodev/projects/my-project/logs
nohup uv run --project /path/to/autodev autodev ui my-project \
  >~/.local/state/autodev/projects/my-project/logs/ui.log 2>&1 &
```

Start another project's UI with `autodev ui other-project`; its descriptor
selects a different port. Configuration saves are parsed and fully validated
before an atomic replacement. The running UI refuses a `project.id` change,
and a changed `ui_port` takes effect after restarting that UI. Saved changes
remain visible as an ordinary Git modification and must be reviewed and
committed normally.

Mutating API requests require the project-scoped bearer token stored with mode
`0600` at `$AUTODEV_HOME/projects/<project-id>/ui-token`. The token is embedded
only into that project's localhost page. This is a local operator boundary,
not a hosted multi-user service.

## Updating the shared runtime

Pull once in the Autodev checkout; no managed project changes are needed:

```sh
git -C /path/to/autodev pull --ff-only
uv sync --project /path/to/autodev --locked --python 3.12
```

Every subsequent `uv run --project /path/to/autodev autodev ...` invocation
uses the updated core. Existing agent worktrees and sessions remain under
`AUTODEV_HOME`.

## Debugging

```sh
# Check exact host tool and selected provider versions.
uv run --project /path/to/autodev autodev doctor my-project --json

# Inspect sessions and attach using the rendered session name.
tmux list-sessions
tmux attach-session -t autodev-my-project-backend

# Inspect one agent's persistent pane log.
tail -n 200 "$AUTODEV_HOME/projects/my-project/logs/backend.log"

# Inspect all Git worktrees owned by the managed repository.
git -C /path/to/project worktree list --porcelain
```

If startup reports a missing provider, install and authenticate that CLI
outside Autodev, verify `codex --version` or `claude --version`, then retry.
Autodev never repairs or replaces a user's agent installation.

## Development

```sh
uv sync --locked --python 3.12
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run autodev --help
```

Tests use disposable Git repositories. The tmux integration test substitutes a
test-only executable and never contacts an AI provider.

## License

MIT
