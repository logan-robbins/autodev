# Autodev channel tasks (Bot handoff)

Deterministic queue for Autodev Team channel. Not the product Pillar ledgers under `<pillar>/tasks/`.

## Filename (status is in the name)

```text
NNN.<status>.<slug>.md
```

- `NNN` — zero-padded sequence `0001`, `0002`, …
- `<status>` — one of: `open` | `in_progress` | `blocked` | `done` | `qa_fail` | `qa_pass`
- `<slug>` — kebab-case, stable across renames (only status segment changes)

Engineer picks work from the directory listing alone (prefer `*.open.*`, then `*.qa_fail.*`). After every task, re-list this folder — a rename may reopen work.

## File body (strict)

```markdown
# <title>

status: <same as filename status>
updated: yyyy-mm-dd HH:mm
owner: <Research|ProjectManager|Engineer|QA|Logan>
task_id: NNN

## Acceptance
- …

## Notes
- …
```

QA may rename `done` → `qa_pass` / `qa_fail` and append timestamped notes.
