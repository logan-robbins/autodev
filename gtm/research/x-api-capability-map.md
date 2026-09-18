# X API capability map — `@LoganRobbinsAI` growth OS

**Updated:** 2026-09-13  
**Connector:** MCP `user-X` / server `user-X--loganrobbinsai` (account `loganrobbinsai`)  
**Credits (live):** free_balance **$49.83** (expires ~2027-09-13) · prepaid $0  
**Rule:** Prefer X API over browser / fxtwitter for every **read**.  
**Gate:** Do **not** conflate X Developer API with Cursor’s X MCP. MCP = read surface only. Platform write is real — pick a write backend (see matrix). Keep **approve gate**; no unsupervised farms.

---

## Live proof (this pass)

| Call | Result |
|---|---|
| `get_posts_by_id` `2093861750416265686` | views **516,521** · likes 2,691 · BM **6,424** · RTs 245 · video **3,389,516 ms (~56.5m)** · video views **149,881** · QT Article `2090102148344262659` at **1,464,573** impressions |
| `get_users_by_username` `0xCarnagee` | 2,731 followers · pinned = Article · bio `@zscdao` |
| `search_posts_all` `("SpaceXAI engineer" OR "worth more than a $500")` | **Factory live** — clones/RTs from `@kingwilliam_`, `@0xCodez`, `@0xMorlex`, `@Mahaximus_`, `@sheemamoto`, `@TSRviral` in last hours |
| `get_posts_liking_users` on hero | empty (ACL / age) — still use on **our** posts for farm checks |
| `has:quotes` operator | **blocked** on current product packaging — use text + `referenced_tweets` instead |

---

## What we have (32 tools) — use these

### Watch / discovery (must-use)
| Tool | Growth-OS job |
|---|---|
| `search_posts_all` | Primary watch. Full-archive. `sort_order=recency` or `relevancy`. Dedup by id. |
| `get_posts_counts_recent` | Volume spikes on watch queries (7d window) |
| `get_trends_by_woeid` | Topic heat (US=2459115) |
| `search_news` / `get_news` | News hooks adjacent to CoS / agents |
| `search_users` | Find clone-network accounts |

### Score / anatomy
| Tool | Growth-OS job |
|---|---|
| `get_posts_by_id` / `get_posts_by_ids` | Exact public_metrics + note_tweet + media duration |
| `get_posts_quoted_posts` | QT graph / Article flywheel |
| `get_posts_reposted_by` | RT network sample |
| `get_posts_liking_users` | Liker graph (own posts; others may ACL) |
| `get_users_by_username` / `by_usernames` / `by_id` | Follower base, bio, pin |
| `get_users_posts` / `get_users_timeline` | Author cadence / template reuse |
| `get_users_mentions` | Inbound for approve-gated reply drafts |
| `get_users_me` | Own baseline |

### Bookmarks (steal their save signal)
| Tool | Growth-OS job |
|---|---|
| `create_users_bookmark` / `delete_users_bookmark` | Park comps in folder for Demand review |
| `create_users_bookmark_folder` · `get_users_bookmark_folders` · `get_users_bookmarks*` | Folder = `viral-comps` |

### Real-time (fair-shot vs factories)
| Tool | Growth-OS job |
|---|---|
| `create_webhooks` · `get_webhooks` · `delete_webhooks` | Event sink for Growth OS / CoS |
| `create_activity_subscription` · `get_*` · `update_*` · `delete_*` | Mentions/follows/Spaces — not unsupervised replies |

### Ops
| Tool | Growth-OS job |
|---|---|
| `get_usage_credits` | Guard spend before heavy `search_posts_all` pages |

---

## MCP ≠ platform ceiling

| Layer | What it is |
|---|---|
| **X Developer API** | Full platform: read + **write** (`POST /2/tweets`, reply via `in_reply_to_tweet_id`, media upload, likes/RTs if scoped) |
| **Cursor X MCP** (`user-X--loganrobbinsai`) | **Read + bookmarks + webhooks** only (32 tools). Not the ceiling. |
| **Create-once → post-many** | Real industry pattern (Typefully / Hypefury-class / Buffer / Late / Publer / custom OAuth apps). Factories are **not** all hand-pasting. |

---

## Write path matrix (fair-shot)

**LOCKED 2026-09-13 — Demand:** Path **A** (own X Dev App + approve-gated `POST /2/tweets`). Decision: `gtm/demand/x-write-backend-decision.md`. Approve gate stays. Unsupervised reply farms stay killed. Path D rejected.

| Path | How | Pros | Cons | Autodev fit |
|---|---|---|---|---|
| **A. Own X Dev App** (OAuth 2.0 user context, scopes `tweet.write` · `tweet.read` · `users.read` · `media.write` as needed) | CoS/Logan app @ developer.x.com → user-auth `@LoganRobbinsAI` → `POST /2/tweets` (+ media INIT/APPEND/FINALIZE) from Growth OS after approve | Full control; same stack factories use; QT/reply/thread programmable; no third-party brand leak | App review / pay tier; secrets hygiene; ads-ineligible account still can’t buy Ads (organic write OK) | **LOCKED** (Demand) |
| **B. Create-once scheduler** (Typefully / Late / Buffer / Publer / Hypefury-class) | Draft in OS → push to scheduler API or queue → human approve in their UI → multi-post / thread / QT | Fast; calendar + A/B; factories already live here | Vendor lock; less reply/QT control; still need approve discipline | Strong interim |
| **C. Browser / manual UI** | Paste approved draft on x.com | Zero setup | Not scalable; loses fair-shot vs industrial cadence | **Fallback only**, not strategy |
| **D. Await MCP write tools** | Hope Cursor ships `create_post` | Zero work | Indefinite; confuses MCP with API | **Rejected** as strategy |

**Hard rules**
- Approve (Logan or delegated CoS) **before** any write fires — path A/B still gated.
- No engagement pods / unsupervised reply scripts / fake pedigree.
- `@AutodevTeam` stays dark / no RT / no Ads until clean entity.
- Read stays on MCP; write uses A or B (not “UI forever”).

---

## Remaining non-write gaps

| Capability | Status | Mitigation |
|---|---|---|
| `organic_metrics` / `non_public_metrics` on **others** | Unauthorized (expected) | `public_metrics`; organic on **self** after we post |
| `has:quotes` | Packaging blocked | Text slots + `referenced_tweets` |
| Filtered stream / firehose | Not in MCP | `@every 6h` `search_posts_all` + webhooks |

**Bottom line:** Match factories on **read** (MCP) **and** plan **write** (own app or scheduler). Do not hide behind MCP. Do not default to fxtwitter when API read works.

---

## Demand wiring (mandatory)

1. Watch = `search_posts_all` (primary). Factory handles: `0xCarnagee` / `0xCodez` / `kingwilliam_` / `0xMorlex` / `Mahaximus_` / `sheemamoto` / `TSRviral` + `"SpaceXAI engineer"`.
2. Score = `get_posts_by_id` public_metrics; BM/like; `duration_ms`; QT Article impressions.
3. **Write** = choose path A or B this week → land `gtm/demand/x-write-backend-decision.md`. Keep approve gate.
4. Instrument own posts T+1h/24h/7d via API.
5. Bookmark comps → folder `viral-comps`.
6. `get_usage_credits` before deep archive pages.

@Autodev Demand — patch `x-growth-os.md` Write stage to matrix; ship write-backend decision artifact.
