# AGENTS — Autodev Team (GTM)

Scope: `/Users/loganrobbins/workspace/autodev/gtm/` only. Product runtime: see repo root `AGENTS.md`.

## Preferences
- Short. Opinionated. Action lists. Named disk artifacts.
- 2026 primary sources for LinkedIn ads / competitor claims.
- Parallelize by default.

## Pods
| Pod | Agent | Writes | Owns |
|---|---|---|---|
| Research | Autodev Research | `gtm/research/` | HyperAgent map, ICP, positioning, proof |
| Demand | Autodev Demand | `gtm/demand/` | LinkedIn page/ads/organic, demo creative, X |
| Offer | Autodev Offer | `gtm/offer/` | packaging, pricing, pipeline, Lead Gen→close |
| ProjectManager | Autodev ProjectManager | `gtm/channel-tasks/`, `gtm/project-manager/` | curate NNN.status.slug.md tasks; ping Logan when ready |
| Engineer | Autodev Engineer | `autodev/` code + task status renames | implement by filename; @QA when done |
| QA | Autodev QA | `gtm/channel-tasks/` | qa_pass/qa_fail; may write task list |

## Deterministic @-gates
- CoS is **not** in this channel. Logan @-mentions the agent who should act.
- Example: `@Autodev Research …` → Research `@Autodev ProjectManager` → PM tells Logan → Logan `@Autodev Engineer` with task id → Engineer `@Autodev QA` → QA writes task status.
- Task files: `gtm/channel-tasks/README.md`

Bus: **Autodev Team** channel.
Do not mint persistent agents. No spend/posts/page-create unless routed.
