# Task and fleet operations

Commands below are arguments after the resolver's `command` prefix. `PROJECT`
means the canonical workspace, its `autodev.toml`, or a registered project ID;
agent identities are full `pillar--agent` IDs. Use `--help` for the installed
command before relying on an option not shown here.

## Prepare and start useful work

```sh
validate PROJECT --json
pillar verify PROJECT research --interface
doctor PROJECT --json
ensure PROJECT research--researcher --no-start
prompt PROJECT research--researcher
ensure PROJECT research--researcher --send-goal
status PROJECT research--researcher --json
```

Use the project's real IDs, not these examples. Verify each relevant Pillar's
interface. `validate` checks configuration and the Git base, not all executable
checks. `prompt` previews the operating contract and up to eight unfinished tasks;
the harness must read its ledger for the full current view. `doctor` can report a
missing tool without exiting unsuccessfully; inspect its returned values. Git
is needed only for Git execution. Never start real harnesses as a smoke test.

No agent IDs on `ensure`, `status`, `goal`, or `stop` selects **all** project agents.
Prepare contract changes before launch. For Git, commit the manifest, referenced
Pillar contracts, schemas, fixtures, and required source on the configured base;
`--base-ref` only controls creation of new worktrees, not existing ones.

Native sessions retain the user's installed tools and authentication. Use the
runtime's launch/prompt transport rather than hand-built tmux shell commands.
A process that has exhausted quota, awaits authentication, or is sitting at a
shell is not useful capacity. Inspect session output before nudging it.

## Plan tasks without taking over worker execution

The PM may create/import/revise tasks in its own Pod and dispatch ready agents.
Without a PM, a worker may create and revise its own tasks; `task import` and
`task dispatch` still require a PM. To begin from an empty fleet, bootstrap a
bounded planning assignment for the PM or an execution assignment for a sole
worker. Starting the harness with its standing goal does not create that task.

Each assignment needs one configured owner, instructions, concrete acceptance
criteria, and an outcome expressible through that agent's existing deliverables.
Do not invent task-specific output paths the agent does not own. Add only real
dependencies: independent branches of work should proceed in parallel. Review,
testing, and integration agents need their own output roots and declared read
context. A PM plans implementation of already established public interfaces;
workers cannot rewrite protected contracts or fixtures as implementation work.

```sh
task create PROJECT research--researcher "Synthesize the supplied evidence" \
  --actor research--manager \
  --instructions "Use the declared sources and deliver the contracted report with source-linked findings." \
  --acceptance "Every finding cites its source; limitations and unresolved questions are explicit."
task list PROJECT --actor research--manager
task dispatch PROJECT --actor research--manager
```

For a larger plan, the PM writes JSON to its contracted plan artifact and imports
that actual file. A minimal shape, assuming both named agents already exist:

```json
{
  "status": "planned",
  "summary": "Publish a supported synthesis and independent review.",
  "tasks": [
    {
      "key": "synthesis",
      "title": "Synthesize the evidence",
      "agent": "research--researcher",
      "instructions": "Deliver the declared research artifacts from the supplied sources.",
      "acceptance": ["Each conclusion is supported by traceable source evidence."],
      "dependencies": []
    },
    {
      "key": "review",
      "title": "Review the published synthesis",
      "agent": "research--reviewer",
      "instructions": "Read the published synthesis and deliver the contracted review artifact.",
      "acceptance": ["Identify unsupported conclusions and report the checks performed."],
      "dependencies": ["synthesis"]
    }
  ]
}
```

```sh
task import PROJECT /absolute/path/to/task-plan.json --actor research--manager
```

Plan dependency keys are local to the plan; `task create --depends-on TASK_ID`
uses actual existing task IDs. Both remain within one Pod. Identical plan imports
are idempotent, but an edited plan has a different digest and creates new tasks.
Use `task revise` on existing queued/blocked work rather than re-importing a
modified plan to update it. Revision replaces instructions and acceptance;
include their complete intended values. It does not reassign ownership or edit
dependencies. Coordinate cross-Pillar readiness through published evidence.

## Worker execution

Inside the harness, the actor defaults to `AUTODEV_AGENT_ID`; its canonical
project is bound by `AUTODEV_PROJECT_DESCRIPTOR`. Do not unset these to access
another actor or project. Outside a session, supply its authorized actor explicitly.

```sh
task list PROJECT --actor research--researcher
task claim PROJECT --actor research--researcher
task show PROJECT TASK_ID --actor research--researcher
task progress PROJECT TASK_ID --actor research--researcher \
  --message "Checked source coverage; two claims still need evidence."
# Work in this agent's execution workspace and verify its exact deliverables.
# Git profile only: commit the verified owned changes on the agent branch.
task complete PROJECT TASK_ID --actor research--researcher
```

`claim` returns the already running task on a retry, otherwise the next ready
assignment, or null when none is ready. One task runs per worker. A blocked
assignment does not prevent other independent ready work from being claimed.
Report meaningful milestones and impediments using `progress`; do not fabricate
percentages, model thoughts, or a heartbeat with no new evidence.

On completion, Autodev checks ownership, deliverables, configured commands, and
the combined workspace before recording delivery. It emits `validating`,
`publishing`, and `completed` stages automatically. An error leaves the task
running and reports the failure. A JSON status of `blocked` or `unavailable`
cannot be passed off as a completed deliverable. Acceptance prose is not an
automatic proof: verify substantive criteria and use executable gates where useful.
After successful completion, read the ledger again and continue with ready work.

```sh
task block PROJECT TASK_ID --actor research--researcher --reason "Required source is inaccessible; need an accessible export."
# PM, or the same worker in a Pod without a PM:
task revise PROJECT TASK_ID --actor research--manager \
  --instructions "Use the newly supplied export and retain the declared report format." \
  --acceptance "All findings cite the supplied export and distinguish missing evidence."
```

Use ledger commands for all transitions. Do not edit `ledger.json`, its digest,
transaction journal, locks, or snapshots to force completion.

## Supervise and recover

Use `ui PROJECT` to open the local workspace view when requested. Navigate
**Workspace → Pillar → Harness Agent**; Pod is an internal grouping. Pillar views
include the handoff graph, task board, agent list, and contract. Agent details
expose current task, stages, timestamps, acceptance, delivery evidence, and session
output. Actual task dependencies and PM assignment-scope edges are different.
Use the graph to find bottlenecks, not to infer a model's private reasoning.

`status --json` reports session presence, workspace, branch, dirty state,
ownership violations, and current task ID; it is not an aggregated task-count
endpoint. The UI combines ledger state with sessions and refreshes about every
two seconds. Prefer its fleet view for large workspaces instead of repeatedly
polling each agent and dumping every ledger into the Orchestrator's context.

| Observation | Operation |
| --- | --- |
| Online but no progress | Check the last event timestamp and session output. Distinguish active work, an idle prompt, provider limits, and a shell left after harness exit. Nudge an idle harness once with `goal PROJECT AGENT`; inspect again before repeating. |
| Running task, offline session | Preserve its workspace. `ensure PROJECT AGENT --send-goal` restarts the session; the worker claims its existing running task and reconciles partial output. PM dispatch excludes already-running tasks and is not the recovery command. |
| Blocked task | Read its concrete reason. Resolve the dependency/input/decision, then have the maintainer revise queued/blocked work and dispatch or nudge its worker. |
| Contract digest changed | Have a running worker block first. The maintainer revises the task against the current contract. Revalidate the interface and refresh relevant execution context without discarding dirty work. |
| Validation failed | Read the recorded error and fix the owned artifacts or checks' legitimate prerequisites. Retry completion after a correction, not in a tight loop. Checks must not modify the candidate or Git index. |
| Filesystem publication conflict | Compare the worker's changes with the current canonical files and reconcile the affected owned paths. Keep the execution copy and snapshot; do not erase evidence or reset the baseline to bypass the conflict. |
| Git publication failed | Inspect the complete agent branch diff and both worktree states. Keep the base on its configured branch and clean; commit the agent's verified changes. For merge conflicts, merge the current base into the agent branch, resolve and verify, then retry completion. Do not stash/reset unrelated user changes. |
| Need to stop work | `stop PROJECT AGENT` stops only that session and preserves tasks/workspaces. A running task remains running and appears interrupted while offline. |

Do not use `merge PROJECT AGENT` as a replacement for `task complete`: it performs
integration without completing the ledger task. The ordinary delivery path is
worker completion. A successful Git publication refreshes the agent branch;
filesystem copies refresh at preparation/claim only when clean and without an
active task. Existing dirty copies are deliberately preserved.

If a failure requires new credentials, a changed external state, or a user
decision, state the blocker and the next action. Do not promise a retry or ongoing
monitoring after the conversation ends unless a real scheduler is configured.

## Demo and operator access

The bundled demo is a browser simulation of 60 agents, six Pillars, and 180 tasks.
It supports play/pause, step, speed, restart, graphs, and simulated transcripts.
Runtime launch/stop controls are disabled. It does not prove real sessions are
running or validate the host's providers. The public agency demo runs without a
runtime backend; use the local project UI for real operations.

Keep the live UI on loopback. Its token protects telemetry and mutations, and
configuration saves modify authored descriptors. Never expose it by publishing
the token, binding externally, or treating the demo host as a remote control plane.
Runtime state is under `AUTODEV_HOME`, then `$XDG_STATE_HOME/autodev`, then
`~/.local/state/autodev`, outside the workspace. Canonical ledgers remain under
`<pillar>/tasks/<agent>/ledger.json`; runtime logs may contain task/source content.
