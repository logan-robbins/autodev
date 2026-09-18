# X viral anatomy v0 — `@LoganRobbinsAI` growth OS input

**Purpose:** Reverse-engineer a templated high-view format for Demand’s watch→score→draft→approve loop.  
**Constraint:** Personal X only. `@AutodevTeam` stays dark / no RT / no Ads. Human/CoS approve before any auto-reply.  
**Updated:** 2026-09-13  
**Primary sources:** X MCP `user-X--loganrobbinsai` (`get_posts_by_id`, `search_posts_all`, `get_users_by_username`) · see `x-api-capability-map.md`.

---

## Hero example (Logan’s URL)

| Field | Value |
|---|---|
| URL | https://x.com/0xCarnagee/status/2093861750416265686 |
| Author | `@0xCarnagee` (~2.7k followers, verified) |
| When | 2026-08-30 |
| Format | **Note tweet** + **~56.5 min video** + **self-quote** of own X Article |
| Views | **516,521** (API) |
| Likes | 2,691 |
| RTs | 245 |
| Bookmarks | **6,424** |
| Replies | 54 |
| Quotes | 8 |
| Video duration | **~56.5 min** (`duration_ms` 3,389,516) |
| Video views | **149,881** |
| QT Article impressions | **1,464,573** (`2090102148344262659`) |

**Ratio tell:** bookmarks ≈ 2.4× likes; bookmarks ≈ 26× RTs. This is a **save/share-to-self** post, not a pure like-farm. Distribution favors people parking a long tutorial, not meme RT velocity.

### Exact structure (slots)

```
[AUTHORITY LABEL]: SpaceXAI engineer (ex-Cursor):

"[QUOTED SPEECH block 1 — concrete agent count + % of week]"
"[QUOTED SPEECH block 2 — Chief of Staff meta-agent routes work]"

[CONTEXT LINE]: in a N-minute podcast/workshop, [authority] walks through [outcome]

[VALUE ANCHOR]: worth more than a $500 course on [topic]

[CTA]: watch today, then read … in the article below
+ long video attached
+ quote-tweet of own longform Article (funnel)
```

**Filled copy (hero):**
> SpaceXAI engineer (ex-Cursor):  
> "I've got 15-25 GrokBot agents running right now. they cover most of what used to be my week  
> there's a Chief of Staff sitting on top of them. it knows every other bot I have and routes the work itself"  
> in a 50-minute podcast… worth more than a $500 course… watch today, then read… article below  
> + video + QT of article `2090077664933449729` (“11 steps… full course”)

Quoted article alone (same author, earlier): **~1.46M views**, 508 likes, **2,029 bookmarks** — the QT is the real asset; the viral post is the **trailer**.

---

## Near-duplicates (same template, other accounts)

### A — `@0xCodez` clone (stronger audience)

| | |
|---|---|
| URL | https://x.com/0xCodez/status/2093729390932672732 |
| Followers | ~46.6k |
| Views | **108,474** |
| Likes / RTs / BMs / replies | 651 / 70 / **1,564** / 30 |
| Video | ~56.9 min |
| Same slots | Authority label + quoted CoS claim + $500 course + workshop + watch/read CTA + QT of own Article |

Quoted Article (`2089655442657910784`): **~5.9M views**, 2,931 likes, **9,897 bookmarks** — again, longform is the mothership.

### B — `@0xCodez` earlier variant (weaker)

| | |
|---|---|
| URL | https://x.com/0xCodez/status/2092680772943478851 |
| Views | 11,806 |
| Likes / RTs / BMs | 73 / 10 / 104 |
| Same slots | Yes (engineers plural, 10–20 agents, 90% routine, CoS agents, $500 course, workshop, QT same Article) |

**Read:** Same skeleton ≠ same outcome. Reach depends on account size + timing + whether the QT Article already has heat. Template is necessary, not sufficient.

### C — `@0xCarnagee` sibling (listicle, not speech-frame)

| | |
|---|---|
| URL | https://x.com/0xCarnagee/status/2093477307637801344 |
| Views | 61,943 |
| Pattern | “SpaceXAI team’s 10-page PDF…” + formula + 6 steps + bookmark CTA + QT same Article |
| Media | Static image (not long video) |

Same **Article funnel**; different **hook frame** (playbook vs fake-expert quote).

### D — `@silentguyy66` Pattern B (video-bait QT + chapter hooks) — Logan URL 2026-09-13

| | |
|---|---|
| URL | https://x.com/silentguyy66/status/2099094124628492717 |
| Author | `@silentguyy66` · **254 followers** · “lowkey ai researcher” |
| When | 2026-09-13 11:13 UTC |
| Views | **16,331** |
| Likes / RTs / BMs / replies | 145 / 9 / **214** / 3 |
| Video | **~57.0 min** (`duration_ms` 3,419,974) · video views **3,666** |
| QT | Article `2095497109524934750` (“Grok Bot: The AI Team That Never Sleeps”) · **888,725** impressions · 724 BM |
| Frame | **Not** speech-invented pedigree. Hook = “Grok Bot does the work of 6 engineers” + **timestamp chapter list** (05:38…53:42) + $500 course anchor + “Save this…” BM CTA + QT Article |

**Read:** 254 followers → 16k views confirms non-follower distribution. BM/like ≈ **1.48**. Same mothership = long video + QT Article. Slots differ: chapter timestamps replace fake “SpaceXAI engineer:” quote blocks.

---

## Engagement anatomy

| Signal | What it suggests |
|---|---|
| Bookmarks >> likes >> RTs | Utility / “I’ll watch later” + Article save behavior |
| Low reply count vs views (~0.01%) | Not reply-bait discourse; broadcast + save |
| Long video (~50–57 min) | Watch-time / completion signals; podcast-style packaging |
| Self-QT of Article | Owned media flywheel; post is an ad for the Article |
| ~2.7k followers → 516k views | **Not** follower-graph organic; algo + topic + media + possibly network of similar accounts (`0xCodez` / `@zscdao` / `@beyond_xai` cluster) |
| Cross-account template clones | Factory content: same slot machine, swapped numbers/adjectives |
| Chapter timestamps + Save CTA | Pattern B: turns long video into skimmable TOC; BM bait |
| 254 followers → 16k views (`silentguyy66`) | Scanner/algo distribution; same QT-Article mothership |

**Early replies / farming:** Not fully audited this pass (need reply-graph dump). Hypothesis for Demand to test: engagement pods less primary than **bookmark+Article** loop; still check for identical early-reply scripts across clones.

---

## Distribution hypotheses (ranked)

1. **Owned longform QT + long video** → X rewards dwell + saves; Article is the SEO/bookmark magnet.  
2. **Authority hook (fill with true pedigree)** (“SpaceXAI engineer (ex-Cursor)”) → curiosity / status steal; unverified attribution (treat as content pattern, not truth).  
3. **Template network (API-confirmed 2026-09-13)** — live clones/RTs: `@0xCarnagee`, `@0xCodez` (~46k), `@kingwilliam_`, `@0xMorlex`, `@Mahaximus_`, `@sheemamoto`, `@TSRviral` — same authority-quote slot machine, industrial cadence.  
4. **Topic heat** — Grok Bot / multi-agent / CoS narrative is in-season.  
5. **Video scanner → reply/QT attach** — always-on watch for rising `has:videos` posts; factories generate garbage responses (Logan observation). Watch for comps; **kill** unsupervised attach.
6. **Engagement groups** — possible but secondary given bookmark skew; verify before copying reply-farm tactics.

**Do not assume:** unpaid organic from 2.7k alone. **Do assume:** industrial content system.

---


## Pattern catalog (v0)

| ID | Name | Signature | Logan use |
|---|---|---|---|
| **A** | `T-authority-hook-trailer` | Authority label + **continuous hook prose** (+ optional quotes) + media/Article | **Run it** — personality in prose, not fake dialogue |
| **B** | `T-video-chapter-trailer` | Hook claim + **timestamp chapter list** + long video + QT Article + BM CTA (“Save this…”) | Steal chapters + BM CTA; truth-only hooks |
| **C** | Scanner-fed reply attach | Always-on watch for rising video → reply/QT | Steal the **watch**; first-hour replies **supervised** only (no auto-spam) |

### Pattern B — video scanner (Demand Watch #2)

Factories run **always-on scanners** for posts with video (and/or rising impressions), then attach templated garbage (reply / QT / “workshop” clone).

**Watch queries (API — try in order):**
1. `has:videos` + recency (if packaging allows; if blocked like `has:quotes`, use media expansion on keyword/`from:` hits)
2. Rising video roots: `get_posts_by_id` on candidates; keep if `duration_ms` ≥ 300000 **or** impressions climbing + has video
3. Factory authors (existing) ∪ `@silentguyy66`
4. Not Grok-keyword-only — any high-dwell video can feed their reply farm

**Score before draft.** Approve gate stays. Never unsupervised reply-attach.



## Locked X shape (CoS 2026-09-14, corrected) — use this

```
[Frontier shipped outcomes: ___]

[Autodev how-to for those outcomes — playbook beats, dense]

Save this
[article URL = how-to page]

+ QT frontier status id (embed seed card)
```

Not “I run 4 bots” contrast. Save this stays. See `openai-finance-howto-brief.md` for current seed.

---
## HARD BAN — fragment / telegram captions (fail 2026-09-14)

Logan rejected live OpenAI Finance Path A (`2099239309895430455`) as “stupid fragments about nothing.” That shape is **not** factory-parity.

**Illegal root shapes (auto-reject before CoS):**
- Stacked one-liners / period-punch telegrams (`ex-FAANG. Pending….` / `AI mostly sucks.` / punchy orphan lines)
- Root that is only identity bullets + article URL
- Thread that restates the blog in 1/3–3/3 fragments instead of carrying Pattern A story

**Required Pattern A root (factory slots, Logan voice):**
```
[AUTHORITY_LABEL]:

[HOOK PROSE — continuous paragraphs; personality in the writing]
[CONTEXT — seed trailer/SKU beat in prose]
[VALUE + CTA — Save this / read article]
+ media if any
+ article URL or QT mothership
```

**Quotes (`"…"`) are OPTIONAL** — never invent interview/dialogue monologue; never put bio (patents/FAANG) in quotes. Personality colors prose, not fake speech blocks. Still ban telegram fragment stacks.

### REJECTED fill (OpenAI Finance v2) — rubber-stamp fail

**Rejected 2026-09-14 (Logan):** continuous prose still forced seating/middleman/agency bingo + “81-second trailer” theater onto a product promo. Not a human hot take.

**Do not reuse.** Next draft = plain snark on OpenAI Finance → article. No staffing bingo unless Logan asks.

```
Autodev CoS:

I've got 4 Grok Bots under one Chief of Staff covering the routing that used to eat my week. ChatGPT for Finance is a seat — staffing firms will wrap it and take the cut by Friday.

In an 81-second OpenAI trailer, a bank Work SKU sells models and client decks. Same middleman geometry, new logo. Worth more than another agency AI pod deck.

Save this, then read why seats aren't capacity:
https://autodev-team.com/blog/chatgpt-for-finance-wont-kill-the-staffing-cut
```



---
## Reusable template (for Demand `x-viral-templates.md`)

**Names:** `T-authority-hook-trailer` (Pattern A — continuous prose) · `T-video-chapter-trailer` (Pattern B)

| Slot | Spec |
|---|---|
| `AUTHORITY_LABEL` | Short role (`Autodev CoS`) — pedigree colors voice, **not** stuffed into quotes |
| `HOOK_PROSE` | Continuous hot take **about this seed** — not Autodev deck jargon, not fake dialogue |
| `QUOTES` | Optional only — never invent interview lines; never bio-in-quotes |
| `DURATION` | “N-minute podcast/workshop” |
| `VALUE_ANCHOR` | “worth more than $X course” |
| `CTA` | watch + read Article below |
| `MEDIA` | Long video (talking-head / screen) OR strong still |
| `QT_TARGET` | Own X Article or durable thread (pre-warmed) |

**Logan identity fills (factory slots, true facts):**
- Authority: `ex-FAANG` · pending US patents in AI · Autodev Team · Grok Bot CoS  
- Hook: on-seed snark · optional bots/AI-sucks when natural — **not** mandatory staffing kill  
- Article: `autodev-team.com/blog/...` mothership (required for fresh)

**Score rules (v0 for Demand OS):**
- +3 if QT target already ≥50k views  
- +2 if video ≥5 min (or strong carousel)  
- +2 if bookmark/like ratio on comps >1.5  
- +1 if authority label is specific + verifiable  
- −5 if claim invents employer / pedigree (slot still required — fill truthfully)  
- −5 if unsupervised reply farm (supervised first-hour OK)  
- −3 if fresh post waters down Pattern A/B structure without trailer/Article plan

---

## Steal / kill for `@LoganRobbinsAI`

### Steal (factory parity)
- Continuous hook prose on Pattern A (not fragment stacks); quotes optional
- Trailer → owned Article flywheel  
- Bookmark-optimized utility framing  
- Full slot machine (authority / quote / duration / $ anchor / CTA)  
- Pre-warm Article, then ship trailer  
- Chapter timestamps + “Save this” BM CTA (Pattern B)  
- Video scanner + first-hour supervised replies  
- Create-once → post-many (Path A)  
- Topic: CoS / multi-agent / staffing kill (Logan voice)

### Kill
- Fake “SpaceXAI engineer (ex-Cursor)” invented pedigree  
- Unsupervised AI reply farming  
- Shipping this on `@AutodevTeam`  
- Attaching Ads / boost from ads-ineligible personal billing  
- Copying numbers you can’t defend
- Scanner-fed unsupervised garbage replies / QT spam on rising videos

---

## Next Research tickets

0. **API stack locked** — Demand must follow `x-api-capability-map.md` (no fxtwitter-primary).
1. Reply-graph sample on hero + 2 clones (bot vs human early replies) via `get_posts_liking_users` / quotes on fresher clones.  
2. Timing histogram (hour PT) across 10 template hits.  
3. Watch query pack for Demand: `\"SpaceXAI engineer\"`, `\"Chief of Staff agent\"`, `\"worth more than a $500\"`, `from:0xCarnagee`, `from:0xCodez`.

4. **Video scanner** — see `x-watch-query-pack.md` (Watch #2/#3). `has:videos` must pair with keywords; bare AI+video = noise.
5. Frontier watch pack landed — Demand dual flywheel.

@Autodev Demand — fill templates from Pattern A+B; Watch = factory authors **and** video scanner; keep approve gate hard.
