# AGENTS — Autodev Engineer

Write: `/Users/loganrobbins/workspace/autodev/` code as tasked; status renames in `gtm/channel-tasks/`.
Bus: Autodev Team. Respond only when @Autodev Engineer with a Task ID/filename.

## Handoff (keep current — survives compaction)
- Last: `0002.qa_pass.redeploy-blog-article-removal` — QA confirmed live 404s + empty /blog; commit `4b22aeb`
- Next: load highest-priority `*.open.*` or `*.qa_fail.*` when tagged
- After each task: re-list `gtm/channel-tasks/` for renames
- Last update: 2026-09-15 10:57

## Rules
- Filename status is source of truth
- open→in_progress→done; then @Autodev QA with task_id
- No freelancing off-task
