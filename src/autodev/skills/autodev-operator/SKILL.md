---
name: autodev-operator
description: Configure and operate the repository-owned Autodev runtime for an existing Git repository. Use when the user asks to set up Autodev for a repo, define its Codex or Claude worker pods, configure tmux names or a project UI port, launch or supervise workers, check pod status, send standing goals, or integrate completed worker branches.
---

# Autodev Operator

Act as the operator from the user's current Codex or Claude session. Do not launch a separate operator agent. Autodev tmux sessions are workers; this session configures, supervises, and integrates them.

## Resolve Autodev

Run `uv run <skill-directory>/scripts/runtime.py` and use the returned `command` prefix for every Autodev invocation. In Claude Code, the skill directory is `${CLAUDE_SKILL_DIR}`. In Codex, use the directory containing this `SKILL.md` from the discovered skill path.

Fail immediately if the script cannot resolve a valid Autodev checkout. Do not install, wrap, or replace the user's `codex` or `claude` executable.

## Set Up a Repository

1. Resolve the repository's Git root. Require an initial commit and a clean integration checkout before creating `autodev.toml`.
2. Discover before designing: inspect the repository structure, tracked instructions, verification commands, task or backlog conventions, and existing ownership boundaries.
3. Read [references/descriptor.md](references/descriptor.md) before authoring the descriptor.
4. Define the smallest complete set of workers with non-overlapping write roots. Give each worker one provider, purpose, and standing goal. Prefer existing architectural or pod boundaries over invented ones.
5. Choose a collision-safe `runtime.session_pattern` and an unused localhost `runtime.ui_port`.
6. Set `runtime.bypass_permissions` explicitly. Ask the user if their request does not settle the choice. This setting applies only to Autodev-managed workers. Never edit global Codex or Claude permission configuration.
7. Create exactly one project adapter at the Git root: `autodev.toml`. Do not copy this skill or generate agent wrappers inside the managed repository.
8. Run `autodev validate`, `autodev register`, and `autodev doctor` through the resolved command prefix. Correct every failure.
9. Commit `autodev.toml` on the configured base branch before creating worktrees. Do not stage or commit unrelated user changes.
10. Run `autodev ensure <project> --no-start`, then `autodev ensure <project> --send-goal`. Confirm all configured sessions are running with `autodev status <project> --json`.
11. Start the bound UI with `autodev ui <project>` when the user wants it running. Otherwise provide its exact command and `http://127.0.0.1:<ui_port>/`.

Use `autodev setup` when the user explicitly wants the human interactive wizard. When operating autonomously, author the same descriptor directly from repository evidence and validate it.

## Supervise Workers

- Treat `autodev status <project> --json` as the primary runtime view. Use the configured tmux session names and persistent worker logs for diagnosis.
- Send the standing goal with `autodev goal <project> <agent>` when a running worker is idle or needs another pass.
- Keep the operator role separate from implementation. Do not directly perform work assigned to a worker while supervising the pod.
- Stop workers with `autodev stop`; this preserves their branches and worktrees.
- Integrate with `autodev merge <project> <agent>` only after the worker has committed its work, the worktree is clean, verification has passed, and ownership checks are clean.
- Never bypass a failed ownership, Git, configuration, or verification guard. Surface the exact failure and resolve it in the responsible worker.

## Operating Boundary

The committed project descriptor is authoritative for worker count, providers, tmux naming, UI port, ownership, goals, and permission bypass. The UI edits that same file. Review and commit UI changes before launching new worktrees.

Do not weaken machine-wide safety configuration. When `runtime.bypass_permissions = true`, Autodev passes each provider's documented bypass flag only to workers launched for that project.
