# General Manager chat and persistent identity

Each Pillar's **GM chat** tab addresses its sole `project-manager` Harness Agent.
The GM remains a native Codex or Claude Code session with its configured model,
tools and individual template. Chat does not create a second reasoning agent.
A Pillar without a PM has no chat recipient. Workers have no direct chat route.

## Conversation

Run `autodev ui PROJECT` and open the Pillar's GM chat tab. The authenticated
local UI saves messages in external project state and delivers them to the GM's
native session, starting that session if needed. It waits while the GM has an
active assignment or an unanswered message. A small mailbox dispatcher supplies
transport only; it does not create periodic tasks or trading cycles.

The GM reads `chat inbox PROJECT --actor PILLAR--GM` and sends the actual visible
answer with `chat reply PROJECT MESSAGE_ID --actor PILLAR--GM --text-file FILE`.
A terminal response alone is not a chat reply. Conversations and configuration
receipts persist across UI restarts. The UI displays explicit replies, not raw
terminal output or private reasoning. Ambiguous delivery failures are not silently
resent: Resume delivery is available once the GM session is offline.

## Requested employee changes

The operator can enable **Allow agent edits for this message** when requesting a
change. The GM still needs an explicit requested edit in the message; enabling
the control does not authorize unrelated changes. Inspect the employee with
`chat agent PROJECT AGENT_ID --actor PILLAR--GM`, then apply a JSON patch using
`chat edit-agent PROJECT AGENT_ID --actor PILLAR--GM --request MESSAGE_ID
--expected-digest DIGEST --patch-file FILE`.

Only another existing employee in the same Pillar can be changed. Supported
fields are its instructions, purpose, goal, deliverables, read/write roots and
provider. Self-edits, cross-Pillar edits, protected write ownership, stale
contracts, unfinished Pod assignments, online employee sessions and dirty
employee workspaces are rejected. Unrelated individual templates are preserved.
The operation validates a new individual template before replacing the canonical
Pillar reference and records before/after configuration in the conversation.
Git projects still require the ordinary operator commit workflow for authored
configuration changes. These are workflow boundaries, not an OS sandbox.

## GM skill and agent identity

`autodev skill install --gm` links the packaged
[autodev-gm skill](../src/autodev/skills/autodev-gm/SKILL.md) into Codex and Claude
skill directories. Native PM startup and chat prompts also reference the packaged
skill directly. It covers runtime identity, Pod task coordination, operator chat,
and requested employee changes. Each agent's individual template continues to
define its domain goal, process, deliverables and decision authority.

For **filesystem execution**, workspace preparation prepends the assigned agent's
identity to `AGENTS.md` and `CLAUDE.md`, preserving authored root guidance. If an
authored `AGENTS.override.md` exists, the same identity is added there because
Codex gives it precedence. The block includes the concrete agent/Pillar identity,
role, purpose, standing goal, canonical contract location, write scope and
recovery instructions. Only PMs receive the GM skill pointer. Generated entrypoints
are part of the protected execution snapshot, not employee-owned deliverables.
Dirty execution copies are preserved; an identity refresh cannot discard work.

Recovery instructions require reloading the current individual template, task
state and declared notes after compaction, retaining original observation dates
and continuing existing work. Codex documents AGENTS discovery at session start;
this implementation does **not** assume a fresh disk read happens automatically
at every compaction. See [Codex AGENTS guidance](https://learn.chatgpt.com/docs/agent-configuration/agents-md).
The durable entrypoint and explicit recovery mandate support recovery; they do
not prove a particular model will follow every instruction after compaction.

Every native tmux launch additionally saves its full individual standing identity
to external state at `identities/AGENT_ID/AGENTS.md` and binds that path through
`AUTODEV_IDENTITY_FILE`. Codex receives it as session `developer_instructions`;
Claude receives it through `--append-system-prompt`. This applies to **all roles,
both execution profiles, and launches without an initial task prompt**. The
identity contains the full individually authored instructions and deliverables,
not just a pointer. Native session instructions remain separate from transient
task messages. Git worktrees retain authored entrypoints and stay clean because
the identity file is external. See [Harness Agent identity](harness-identity.md).

Identity tests check file persistence, complete template selection, protected
copy behavior and actual tmux argument/environment transport for both providers
and execution profiles. Chat tests use disposable projects and fake native
executables, including an actual CLI reply round trip, without provider accounts.
