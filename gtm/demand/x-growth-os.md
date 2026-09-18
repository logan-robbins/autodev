# X growth OS — `@LoganRobbinsAI` (personal)

**Status:** Factory-parity playbook + Logan identity. Path A write live. `@AutodevTeam` stays dark.  
**Updated:** 2026-09-13 (E2E flywheel: watch → ingest → article → trailer → X)  
**Inputs:** `x-e2e-flywheel.md` · `x-transcript-ingest-options.md` · `x-viral-anatomy-v0.md` · CoS lock 2026-09-13  
**Connector:** MCP `user-X--loganrobbinsai`. Guard: `get_usage_credits` before deep pages.  
**Writes:** drafts only → CoS/Logan `approved: true` → `bin/x-post.mjs`

---

## Locked slots (identity only — Demand does not invent pedigree)

| Slot | Value |
|---|---|
| **Authority** | AI & systems engineer · Autodev Team · Grok Bot Chief of Staff · ex-FAANG · pending US patents in AI |
| **Agent count** | **4** (CoS + Autodev Research / Demand / Offer) |
| **Voice** | Snarky · debate-forward. AI mostly sucks; mostly useful for engineers. Kill staffing-agency middlemen; commoditize elite eng capacity. |
| **Kill** | Invented pedigree · bio-as-quotes · telegram fragment roots (−99) · invented N · other-project names · unsupervised spam · `@AutodevTeam` |
| **Pattern A** | Frontier seed = subject. Article+X = how-to ship that outcome with Autodev (dense Note). Save this required. No unrelated they/I contrast. Staffing optional only. |

---

## Factory-parity (steal the full machine)

Run what the factories run. Do **not** water it down to a text-only hot take.

| Steal | Notes |
|---|---|
| Pattern A authority-quote trailer | Label + 2 quotes + duration + value-anchor + CTA |
| Pattern B chapter trailer | Timestamps + Save CTA + QT mothership |
| Trailer → Article flywheel | `autodev-team.com` article first (`site_article:` not `/`) |
| QT mothership | Own article / own X Article |
| Video scanner (Watch #2) | `has:videos` + eng keywords; ≥5m or rising |
| First-hour supervised replies | One beat; approve-gated |
| Create-once → post-many | Same article, many trailers |
| Path A write | `POST /2/tweets` after `approved: true` |

**Swap:** Logan fills every slot. **Kill:** unsupervised Pattern C farms (toasts the account).

---

## E2E flywheel (v1 riff-first)

See `x-e2e-flywheel.md`. **Each new Watch #3 video seed gets its own article.** Full ASR is optional (v1.5), not a gate.

1. Watch #3 frontier hit with video
2. **Riff the post hook** (text + author + caption stamps) — no full watch
3. Article MD → CoS auto-publish `/blog/<slug>`
4. Pattern A + article card (B only if stamps/ASR exist)
5. X Path A
6. Optional first-hour reply
7. Metrics T+1h / 24h / 7d

Staffing essay = pack #1. Next fire = a **new** seed, not a recycle. `pending_asr` does not block.

---

## Loop

```
watch → score → draft (factory slots + Logan fills) → APPROVE → post | reply | drop
```

Ads off (personal ineligible). Company handle never in this loop.

---

## Watch (X API only)

Queries: `gtm/research/x-watch-query-pack.md`. No bare `has:videos`.

**Watch #1 — factory authors (structure comps — steal the slots, fill Logan):**
```
("SpaceXAI engineer" OR "worth more than a $500" OR "Chief of Staff agent")
OR from:0xCarnagee OR from:0xCodez OR from:kingwilliam_ OR from:0xMorlex
OR from:Mahaximus_ OR from:sheemamoto OR from:TSRviral OR from:silentguyy66
-is:retweet
```

**Watch #2 — rising long video:**
```
("Grok Bot" OR GrokBot OR "cloud agent" OR "agent team" OR "agentic" OR Cursor OR "Chief of Staff" OR Autodev OR "pull request" OR SDLC)
has:videos -is:retweet lang:en
```
Keep if `duration_ms` ≥ 300000 **or** impressions climbing + has video. Drop NSFW only.

**Watch #3 — frontier seeds:**
```
(from:SpaceXAI OR from:xai OR from:cursor_ai OR from:OpenAI OR from:AnthropicAI
 OR from:GoogleDeepMind OR from:AIatMeta OR from:perplexity_ai OR from:huggingface)
-is:retweet -is:reply
```
`@SpaceXAI` ≠ `@xai`. `from:grok` only as `-is:reply` slice.

**How:** `search_posts_all` → `get_posts_by_id`. `@every 6h`. Credits first.  
**Emit:** `{id, author, views, likes, bms, …, watch_bucket}` → `gtm/demand/x-watch-log/`

---

## Score (v0)

| Rule | Pts |
|---|---|
| QT mothership ≥50k | +3 |
| Frontier ≥5m video | +3 |
| Video ≥5 min or strong carousel | +2 |
| Rising ≥5k impr in <6h | +2 |
| On-topic Autodev / CoS / staffing-kill | +2 |
| Comp BM/like >1.5 | +2 |
| Logan slots fit (verifiable) | +1 |
| Invented pedigree | **−5** |
| NSFW / off-topic | **−5** |
| Unsupervised Pattern C farm | **−99** |
| Would ship on `@AutodevTeam` | **−99** |

Act if ≥4 → draft A/B or one supervised reply.

---

## Draft

Fill `x-viral-templates.md` **as factories do** (A or B). Logan identity in the slots.  
Fresh **must** have `site_article:` (not `/`) + `voice_ok: true`.  
No article → no fresh approve. Reply-only may skip article.

Output: `gtm/demand/x-drafts/YYYY-MM-DD-<slug>.md`. Demand never self-approves.

---

## Approve / write

Logan or CoS sets `approved: true`. `x-post.mjs` enforces article + `voice_ok` on `type: fresh-post`.  
Instrument: T+1h / T+24h / T+7d. Success = BM/like >1.5 + article views up.

---

## Next

1. Riff-first default (this pass). ASR optional.
2. Next fire = **new** Watch #3 video seed → riff → article → X.
3. Install ASR later if we want Pattern B chapters.
