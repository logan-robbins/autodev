---
name: autodev-operator
description: Configure and operate the repository-owned Autodev runtime for a Git repository. Use to set up Autodev, start a new product from a vision (deterministic company scaffold), run and supervise the loop, approve pillars/features, reset a product, inspect status, or integrate completed worker branches.
---

# Autodev Operator

You (this Codex/Claude session) plus the user **are the Operator**. There is no separate boss process — this session configures, supervises, approves, and integrates. Autodev tmux sessions are the **workers**. Never do a worker's implementation yourself while supervising.

## Resolve Autodev

Run `uv run <skill-directory>/scripts/runtime.py` and use the returned `command` prefix for every Autodev invocation. In Claude Code the skill directory is `${CLAUDE_SKILL_DIR}`; in Codex use the directory holding this `SKILL.md`. Fail immediately if it can't resolve a valid Autodev checkout. Never install, wrap, or replace the user's `codex`/`claude`.

## How Autodev works (the model you supervise)

Deterministic company over a git-reviewed product tree:

```
Product → Pillar (Product Manager)  → Feature (the pillar's Pod) → Epic/Task = leaf (Engineers + Project Manager) → Docs (Technical Writer, LAST)
  product.json      pillar.json           feature.json                 leaf.json                                     README/TECHNICAL.md
```

- **State is data, never scraped.** The tree is JSON (`product/pillars/**`); live activity is the append-only trace under `AUTODEV_HOME`. Read those (and the UI) — do not infer from prose.
- **Pods are derived, per pillar.** A `[pods]` template in `autodev.toml` declares the team *shape* `{product-manager, project-manager, engineering, technical-writer}`. The effective worker set = **`pods.materialize` = template × the `pillar.json` files on disk**, plus a product-level `pm` bootstrap. So the number/identity of tmux sessions is **not chosen** — it's a function of the pillars that exist. Cold-start (no pillars) = one bootstrap `pm`; each new pillar adds its 4-member pod.
- **Cold-start.** Empty tree + a `product.json` vision → the loop schedules the bootstrap `pm`, which proposes the first pillars. Nothing downstream runs until pillars exist.
- **The approval gate is your seat.** Pillars/features are emitted `proposed`; the loop will not schedule downstream roles until you approve. That is the one seat the loop never auto-advances past.
- **Pod memory** (`AUTODEV_HOME/projects/<id>/pods/<pillar>/memory.jsonl`) is shared by a pillar's pod and replayed into each worker.
- **Honest scope:** the *graph/scheduler, ownership (sparse checkout), schema validation, and the PreToolUse exit-2 policy* are hard-wired/enforced. The *personas doing contract-first/TDD/docs-last* are charter-prompted (best-effort) with those few hard gates. Supervise accordingly — you are the quality gate on top of prompted workers.

## Start a repository

When the repo has no `autodev.toml`, first ask: **continue an existing product** (a repo with code/history) or **start a new product** (grow from a vision)?

**Continue existing** — design the smallest set of non-overlapping static `[[agents]]` from the code that exists (read [references/descriptor.md](references/descriptor.md) first), set `runtime.bypass_permissions` explicitly, `autodev validate` → `register` → `doctor` (fix every failure), commit `autodev.toml` on the base branch, then launch those static workers with `autodev ensure <project> --send-goal`.

**Start new — the deterministic company scaffold:**
1. Ask **"What do you want to build?"** — capture as the vision.
2. Write the default schema-3 company `autodev.toml` (four roles, the feature `[loop]`, a `[pods]` template) — see [references/descriptor.md](references/descriptor.md). It declares the team shape, not the teams.
3. Write the vision to `product/product.json` (`{ "vision": "…", "constraints": [ … ] }`).
4. Commit **both** on the base branch before launching.
5. `autodev register` → `autodev doctor` (fix every failure).
6. **Run the loop with `autodev orchestrate <project>`** (add `--watch` to keep ticking).
7. Approve at the boundaries (below).

## Running the loop — `orchestrate` vs `ensure` (know which launches what)

- **`autodev orchestrate <project>`** advances the tree one tick: it schedules and launches the **derived per-pillar pods** (`pods.materialize`) and the bootstrap PM. **This is how a company-scaffold product runs.** Use `--watch` to keep ticking.
- **`autodev ensure <project>`** launches only the **static `[[agents]]`** declared in `autodev.toml` — the continue-existing path. It does **not** launch the derived pods.
- To answer *"how many / which sessions should be running?"* read the derived set — `autodev status <project> --json` and the UI list it (both fold `pods.materialize`). Never eyeball it; it changes as pillars are approved.

## Approve, supervise, integrate

- **Approve intent:** `autodev product set-pillar-approval <project> --pillar <p> --approval approved`; `autodev product set-approval <project> --feature <f> --approval approved`. Downstream of an approved node runs autonomously; a `proposed` node blocks.
- **Status:** `autodev status <project> --json` is the primary runtime view; `autodev ui <project>` serves the dashboard on `runtime.ui_port`.
- **Nudge:** `autodev goal <project> <agent>` re-sends the standing goal to an idle worker.
- **Stop:** `autodev stop <project>` (preserves branches/worktrees).
- **Integrate:** `autodev merge <project> <agent>` only after the worker committed, its worktree is clean, verification passed, and ownership is clean. Never bypass a failed ownership/Git/verify guard — surface it and fix it in the responsible worker.

## Author the tree (typed verbs only — never hand-edit JSON)

Pillars/features/leaves and their states are written **only** through `autodev product …`: `add-pillars`, `add-features`, `decompose-feature`, `set-leaf-status`, `set-approval`, `set-pillar-approval`, `reset`. They validate the schema and write into the integration checkout as ordinary Git modifications — review and commit them like any change. Pod-shared notes: `autodev pod remember`. (`trace emit`, `charter digest`, `policy check` are hook-internal — workers' hooks call them; you do not.)

## Reset / start over

`autodev product reset <project>` **clears the product, keeps the company.** A bare call previews (exit 1); `--yes` applies. It deletes `product/product.json` + `product/pillars/**` (left as uncommitted deletions to review), `runs/**` and `pods/**` under `AUTODEV_HOME`, and the dynamic per-pillar pod worktrees/branches. It **never** touches `autodev.toml` (roles/personas, `[loop]`, the `[pods]` template, providers), this skill, or static `[[agents]]`. After a reset, give the PM a new `product.json` vision and cold-start again.

## Operating boundary

The committed `autodev.toml` is authoritative for roles, the pod template, providers, tmux naming, UI port, ownership, and permission bypass; the UI edits that same file (review/commit before launching new worktrees). When `runtime.bypass_permissions = true`, Autodev passes each provider's documented bypass flag only to that project's workers — never weaken machine-wide config.
