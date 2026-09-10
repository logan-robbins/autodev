---
name: autodev-operator
description: Set up and operate Autodev workspaces, Pillar interfaces, scoped task ledgers, and native Codex or Claude Code harnesses in tmux. Use for project configuration, task planning and dispatch, fleet supervision, recovery, and verified publication—not ordinary edits to the agency website.
---

# Autodev Operator

Autodev coordinates full native **Harness Agents**, each in its own tmux session
and execution workspace. Their harness supplies tools, authentication, and
reasoning; Autodev supplies boundaries, delivery contracts, ledgers, and checked
publication. Projects may produce software, research, analysis, or other artifacts.

The user-facing conversation is the **Orchestrator**. A **Pillar** is a peer
capability boundary with one implicit **Pod** of template-based Harness Agents.
A Pod needs at least one agent and may have one Project Manager (PM). Workers
execute and update their own tasks; the PM tends individual ledgers across its
own Pod. Do not replace that model with a central task queue or a second agent loop.

## Find the runtime and current state

Run `uv run <skill-directory>/scripts/runtime.py` and use the returned `command`
array as the CLI prefix. Resolve this file through its installed symlink; in
Claude Code, `${CLAUDE_SKILL_DIR}` identifies the skill directory. Quote paths
when converting the command array to shell text. If resolution fails, report the
missing checkout; do not substitute another installation or provider wrapper.

Use an explicit project path, descriptor, or registered ID. Start with its
`autodev.toml`, `pillar list PROJECT`, and `status PROJECT --json`; use
`projects --json` when the target is not known. Inspect existing work before
scaffolding or restarting it. Preserve the user's configured providers, model,
execution profile, and authorization. Run `doctor PROJECT --json` before native
launch; it checks availability/versions, not authentication or provider quota.

Read only the reference needed for the operation:

- [Descriptor and interface design](references/descriptor.md): creation/adoption,
  ownership, templates, checks, and assignment-bound verification.
- [Task and fleet operations](references/operations.md): planning, worker loop,
  selective launch, UI observation, publication, and failure recovery.

## Establish useful boundaries

Keep `autodev.toml` at the workspace root and `<slug>/pillar.toml` directly inside
each peer Pillar. The descriptor is its discoverable contract; no departments,
nested Pillars, or central contract registry. All Pillar-authored schemas,
fixtures, custom templates, and outputs stay inside that Pillar. One canonical
schema 1 is supported; do not invent migrations or version negotiation.

Separate independently consumable capabilities, then assign agents distinct
write roots and deterministic deliverables. Size the fleet to independent ready
work, native account capacity, and host resources. The 60-agent demo is an
example, not a required team size. Avoid more agents than useful independent
ownership allows. Additional read context does not grant write permission.

Use `init` and `pillar create` for new directories. Adopt existing directories
by adding descriptors and interfaces without replacing existing content. Scaffold
fixtures and functioning interface responses first, then validate them. Keep
`interface-ready` distinct from `implementation-ready`: an unavailable fixture
is not completed functionality. Add substantive acceptance and consumer checks;
shape validation alone does not establish that an assignment was accomplished.

## Operate within the contract

Use the normal worker cycle: **read → claim → work/report progress → verify →
complete**, or **block with a reason**. Only the executing worker completes its
task. In Git execution the worker commits verified owned changes before calling
`task complete`; the command validates and integrates them, then records delivery.
In filesystem execution it publishes the owned files from the execution copy.

Task commands target the canonical project and use the session-bound actor.
Outside a session, pass `--actor PILLAR--AGENT` explicitly. The Orchestrator can
bootstrap authorized assignments using the appropriate maintainer role; it does
not impersonate a worker to claim success. Workers see their own ledgers; only
the PM has a Pod-wide ledger role. Cross-Pod work consumes public contracts and
outputs, not internal ledgers or cross-Pod task dependencies.

Prepare or launch selected agent IDs when practical. `ensure --no-start` prepares
workspaces; `ensure --send-goal` starts or reuses sessions and sends their current
contracts. Neither creates tasks. Use `goal` for a deliberate nudge of an idle
session and PM `task dispatch` for ready workers. Autodev has no background task
scheduler; do not keep resending goals to busy agents or promise unattended
follow-up without an actual scheduling mechanism.

Observe recorded task state and evidence, not just online sessions. Surface
blockers, interrupted work, stale progress, failed checks, and required operator
decisions. Completion means verified publication and a delivery record, not a
native harness saying it is done. Preserve ledgers and execution copies during
recovery; use the recovery guidance instead of deleting state or weakening checks.

## Operating limits

- `runtime.bypass_permissions = false` is the scaffold default. Enable bypass
  only within the user's authorization; never rewrite global provider settings.
- Role scopes, sparse worktrees, and execution copies are workflow isolation,
  not OS sandboxes. The agency's clean room, outbound filtering, and air-gap
  offerings are not automatically implemented by this runtime. Only `codex`
  and `claude` providers are currently supported; do not invent a Grok/local-model
  backend or infer security controls from marketing copy.
- Raw source data stays immutable unless the assignment authorizes changes.
  Give harnesses only the declared context needed for their work. Memory and
  Dreamweaver are deferred; use declared project artifacts without inventing a
  separate memory subsystem.
- The local UI observes one workspace on `127.0.0.1`. Its human operator can see
  all Pillars; this does not widen agent ledger access. Runtime tokens and logs
  remain in external state. Never publish them with project outputs.
