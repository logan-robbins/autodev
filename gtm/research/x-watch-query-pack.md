# X watch-query pack — `@LoganRobbinsAI` Growth OS

**Updated:** 2026-09-13 
**For:** Demand `x-growth-os.md` Watch (dual strategy: fresh-post flywheel + supervised replies) 
**API:** MCP `user-X--loganrobbinsai` · `search_posts_all` · `max_results` ≥10 
**Credits:** check `get_usage_credits` before deep pages (~$49.69 free as of this pass)

**Locked slots (CoS 2026-09-13 re-lock):** authority = *AI & systems engineer · Autodev Team · Grok Bot Chief of Staff* · count = **4** (CoS + Autodev Research / Demand / Offer) · never SpaceXAI / ex-Cursor · Autodev-channel only — never name other project pods/channels in Autodev X copy.

---

## Operator hygiene (live-tested)

| Operator | Status |
|---|---|
| `has:videos` | **Works only when paired** with keyword/`from:` — standalone → `is/has/lang cannot be used as a standalone operator` |
| `has:quotes` | Blocked on packaging (prior) |
| `-is:retweet` | OK as modifier, not alone |
| `lang:en` | Prefer on frontier/video packs to cut noise |

---

## Watch #1 — factory clones (existing)

```
("SpaceXAI engineer" OR "worth more than a $500" OR "Chief of Staff agent" OR "Save this before")
OR from:0xCarnagee OR from:0xCodez OR from:kingwilliam_ OR from:0xMorlex
OR from:Mahaximus_ OR from:sheemamoto OR from:TSRviral OR from:silentguyy66
-is:retweet
```

**Use:** score comps for Pattern A/B structure. Structure comps only — fill with Logan identity.

---

## Watch #2 — rising long video (Pattern B / reply candidates)

`has:videos` **must** ride on a topic clause:

```
("Grok Bot" OR GrokBot OR "cloud agent" OR "agent team" OR "agentic" OR Cursor OR "Chief of Staff" OR Autodev OR "pull request" OR SDLC)
has:videos -is:retweet lang:en
```

**Post-filter (Demand score, not query):**
1. `get_posts_by_id` + media expand → keep if `duration_ms` ≥ **300000** (5m) **or** impressions rising fast with video
2. Drop NSFW / non-eng spam (raw `(AI OR agent) has:videos` is garbage — do not use bare)
3. Prefer BM/like >1.0 or impressions ≥5k within first hours
4. Pattern C unsupervised reply-attach = **killed**; supervised reply only after CoS/Demand approve

**Cadence:** `@every 6h` (or tighter later if credits allow). Dedup by status id.

---

## Watch #3 — frontier labs (fresh-post flywheel seed)

Resolved usernames (API `get_users_by_usernames`):

| Handle | Name |
|---|---|
| `@xai` | xAI |
| `@SpaceXAI` | SpaceXAI (**distinct** from `@xai` — id `1661523610111193088`) |
| `@cursor_ai` | Cursor |
| `@grok` | Grok |
| `@OpenAI` | OpenAI |
| `@AnthropicAI` | Anthropic |
| `@GoogleDeepMind` | Google DeepMind |
| `@AIatMeta` / `@metaai` | Meta AI |
| `@perplexity_ai` | Perplexity |
| `@huggingface` | Hugging Face |

**Query (split if length/rate hurts):**
```
(from:xai OR from:SpaceXAI OR from:cursor_ai OR from:grok OR from:OpenAI OR from:AnthropicAI
 OR from:GoogleDeepMind OR from:AIatMeta OR from:perplexity_ai OR from:huggingface)
-is:retweet
```

**Optional video slice:**
```
(from:xai OR from:SpaceXAI OR from:cursor_ai OR from:grok OR from:OpenAI OR from:AnthropicAI)
has:videos -is:retweet
```

**Flywheel rule (CoS dual strategy):** frontier hit → Demand drafts **real** technical post on `autodev-team.com` (not factory garbage) → short trailer video + timestamps (Pattern B) → root hook + thread-in-comments + QT blog/Article. Soft-link CoS Link only when on-topic.

---

## Emit schema (watch log)

```
{id, author, views, likes, bms, rts, replies, duration_ms, has_video, has_article_qt, text, url, watch_bucket: 1|2|3}
```

→ `gtm/demand/x-watch-log/` when stood up.

---

## Score deltas (add to Demand)

| Rule | Pts |
|---|---|
| Frontier lab root (Watch #3) with video ≥5m | +3 |
| Rising video ≥5k impressions in <6h | +2 |
| On-topic for CoS Link / multi-Bot / Autodev capacity | +2 |
| Bare NSFW / off-topic AI spam | **−5** |
| Would reply unsupervised (Pattern C) | **−99** |

Act if score ≥4 → draft (fresh post **or** one supervised reply). Else log + drop.

---

@Autodev Demand — wire Watch #3 + tight Watch #2 query into `x-growth-os.md`. Do not use bare `has:videos`.

**Voice/SEO gate:** see `x-voice-seo-checklist.md` — fresh posts need `site_article:` + Logan voice (not factory).
