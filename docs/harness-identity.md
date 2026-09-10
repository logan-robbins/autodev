# Every Harness Agent has a standing identity

Identity belongs to the configured Harness Agent. It applies to every specialist,
reviewer, trader, worker and manager launched by Autodev. It is independent of
whether the session starts from `ensure`, task dispatch or GM chat.

Before starting a new tmux session, `start_session` saves the selected agent's
standing contract to external runtime state:

```
<project-state>/identities/<agent-id>/AGENTS.md
```

The file contains the concrete agent ID, Pillar, role, purpose, standing goal,
full individually authored instructions, read/write scope, deliverables and
canonical ledger/template locations. It includes recovery instructions for
current tasks and declared notes. It contains no copied task preview or stale
open-task list. `AUTODEV_IDENTITY_FILE` binds the file to the native session,
alongside the existing actor and canonical project bindings.

The native launch installs this same text separately from the task prompt:

| Harness | Standing instruction mechanism |
| --- | --- |
| Codex | Per-session `--config developer_instructions=...` |
| Claude Code | `--append-system-prompt ...`, retaining the native base prompt |

Autodev owns the managed session's developer-instruction setting. It does not
rewrite the user's global configuration or change the selected model, reasoning
effort, provider or permission mode. The agent's individual template remains the
authored source of truth; the identity file is a generated launch snapshot.

All launch paths install identity even when `send_initial_goal` is false or the
opening message is a chat request. Existing online sessions are preserved and
do not silently acquire a new identity. A new session receives the current
configuration. Updating the file alone does not hot-update a running harness's
loaded instructions; configuration changes require a deliberate new launch.

Filesystem copies also include the full identity in `AGENTS.md` and `CLAUDE.md`,
and in an authored `AGENTS.override.md` when present, ahead of preserved project
guidance. Git execution uses the external identity and native instruction channel
without modifying tracked entrypoints or introducing ownership exceptions.

This removes dependence on the opening user message retaining role instructions
through conversation compaction. After compaction, the standing instructions
direct the agent to recover its current task and declared notes while preserving
original observation times. This does not promise that all past conversation
details survive or that a model will always follow its instructions. Automatic
disk rereading on each compaction is not assumed.

Validation uses fake Codex/Claude executables in real tmux for both Git and
filesystem execution. Two different workers must receive different complete
identities with no opening task prompt, the native instruction argument must
match the durable file, the environment must bind the correct actor, workspaces
must remain clean, and identity must survive session termination. Actual model
compaction is not part of these provider-free tests.

Native configuration reference: [Codex developer instructions](https://learn.chatgpt.com/docs/config-file/config-reference).
