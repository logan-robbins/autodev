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

## Start a New Product

When the repository has no `autodev.toml`, first ask whether to **continue an existing product** (a repo that already has code and history) or **start a new product** (a fresh or near-empty repo that will grow from a vision).

For **continue existing**, follow *Set Up a Repository* above: design non-overlapping workers from the code that exists.

For **start new**, run the deterministic company scaffold:

1. Ask the user: **"What do you want to build?"** Capture the answer as the product vision.
2. Write the default schema-3 company descriptor to `autodev.toml` at the Git root — four roles (`product-manager`, `project-manager`, `engineering`, `technical-writer`), the feature `[loop]`, and a `[pods]` template. This is the scaffold in [references/descriptor.md](references/descriptor.md); it declares the team *shape*, not the teams — pods are derived per pillar as pillars appear.
3. Write the vision to `product/product.json` as `{ "vision": "…", "constraints": [ … ] }`.
4. Commit **both** `autodev.toml` and `product/product.json` on the base branch before launching, so every agent worktree starts from the same contract and vision.
5. Register the project (`autodev register`), then run `autodev doctor` and correct every failure.
6. Start the loop with `autodev orchestrate <project>` (add `--watch` to keep ticking). On an empty tree with a vision, the first tick schedules a product-level Product Manager that proposes the first pillars.
7. Approve intent at the boundaries: the operator approves each `pillar.json` (`autodev product set-pillar-approval <project> --pillar <p> --approval approved`) and each feature (`autodev product set-approval`). Nothing downstream of a pillar runs until it is approved; everything downstream of an approved feature runs autonomously.

The org chart is deterministic: `Product → Pillar (Product Manager) → Feature (Pod) → Epic/Task (Engineers + Project Manager) → Docs (Technical Writer, last)`. Each pillar gets its own pod with shared pod memory; the Technical Writer runs only after every leaf in the pillar verifies.

Tree mutations (`pillar.json`, `feature.json`, `leaf.json`, approval/loop/docs states) are authored **only** through the typed `autodev product` verbs, which write into the integration checkout as ordinary Git modifications. Review and commit them like any other change; never hand-edit tree JSON.

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
