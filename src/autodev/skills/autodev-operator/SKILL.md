---
name: autodev-operator
description: Configure and operate Autodev workspaces, Pillar contracts, and native Codex or Claude Code harness sessions. Use for Autodev setup, template assignments, scoped task-ledger operation, session supervision, or verified publication.
---

# Autodev Operator

The user's current conversation is the Orchestrator. Autodev launches full native
harnesses in individual tmux sessions. Each Pillar has one implicit Pod; an
optional Project Manager Harness Agent tends its Pod's individual task ledgers.
Workers read their own tasks, deliver outputs, and update their own completion or
blocked state. Preserve that division of responsibility while operating the system.

## Resolve the runtime

Run `uv run <skill-directory>/scripts/runtime.py` and use its returned `command`
prefix. In Claude Code the skill directory is `${CLAUDE_SKILL_DIR}`; in Codex it
is the directory containing this discovered skill. If resolution fails, report
the failure. Do not replace or wrap the user's provider executables.

## Configure a workspace

Inspect the user's project and existing boundaries before authoring configuration.
Read [references/descriptor.md](references/descriptor.md) for descriptor rules and
commands. The default execution profile is an ordinary filesystem; use Git when
requested or appropriate to the existing project.

Create `autodev.toml` at the workspace root and peer `<slug>/pillar.toml` boundaries.
Keep each Pillar's descriptions, interfaces, schemas, fixtures, templates, and
outputs in that Pillar. Do not add departments, nested Pillars, or a contracts
root. A valid Pillar needs at least one template-based Harness Agent; do not
manufacture a mandatory manager. Memory is deferred.

Use `init` and `pillar create` for new directories. To adopt existing content,
author the descriptor and interface files without replacing user material.
Define deterministic deliverables and nonoverlapping write roots. Keep runnable
fixtures and honest unavailable responses before building functionality. Validate
the descriptors and each interface, then register the workspace and check `doctor`.
Use the human-interactive `setup` wizard only when that interaction is wanted.

Preserve explicit provider/model choices and native defaults when unspecified.
`runtime.bypass_permissions = false` is the scaffold default; enable bypass only
when the user's authorization supports it. Never change global harness settings.
For Git execution, ensure all authored contracts and needed source are committed
on the configured base before launching worktrees. Do not commit unrelated work.

## Operate the Pod

Use `ensure --no-start` to prepare copies, `ensure --send-goal` to launch harnesses
with their operating contracts, and `status --json` to inspect sessions. Startup
does not invent or claim tasks. Existing sessions are reused; `stop` preserves
workspaces and ledgers.

The PM uses `task create`, `task import`, and `task revise` to tend assignments,
then `task dispatch` to start/nudge workers with ready tasks. Scope these commands
to the PM's Pod. The worker uses `task list`, `task claim`, `task complete`, and
`task block` for its own work. Without a PM, a worker can tend its own assignments.
Outside a launched session, task commands require `--actor PILLAR--AGENT`.

A worker's `task complete` validates and publishes owned outputs before recording
completion. It commits its verified changes first under the Git profile. A failed
check leaves the task running; resolve the failure rather than bypassing the
contract. Use `goal` or PM `dispatch` to nudge idle sessions after new assignments.
There is no background polling scheduler or separate Orchestrator acceptance queue.

Use public Pillar outputs for cross-Pod coordination. The local CLI/UI are trusted
operator tools; role scoping is not an OS security boundary. Open the project UI
with `ui PROJECT` when requested. Configuration saves modify the same authored
files; revalidate changed contracts before subsequent work.
