# X E2E flywheel — `@LoganRobbinsAI`

**Status:** v1 riff-first. 2026-09-13.  
**Every new Watch #3 video seed gets its own article.** Staffing essay = pack #1, not the loop.

---

## Default (v1 — ship this)

You do **not** need the whole video for views. Riff the **post hook** (text + author + any caption timestamps) → exaggerate/contrast in Logan voice → blog + factory-parity X.

```
1 Watch #3 frontier hit with video (native or linked)
2 Riff    seed text + author + caption stamps — no full watch, no ASR gate
3 Article Demand drafts Logan-voice blog → CoS auto-publish /blog/<slug>
4 Trailer Pattern A + article card (default). Pattern B only if we already have stamps or ran optional ASR
5 X Path A root + comments + site_article
6 Reply   optional supervised first-hour on the seed if score ≥4
7 Metrics T+1h / T+24h / T+7d
```

`pending_asr` **must not** block blog → X.

---

## Upgrade (v1.5 — optional)

ASR / `bin/x-ingest.mjs` Path A|B **only** when we want real Pattern B chapters from a ≥5m source. Not every seed.

---

## Ingest (optional)

**Stub:** `bin/x-ingest.mjs` — `--tweet-id` | `--url` → `x-ingest/<id>-gist.md`  
A = yt-dlp + faster-whisper · B = vendor · C/D rejected.  
Mac: `ffmpeg` yes, A otherwise missing. Fine — v1 does not wait.

Source map: `gtm/research/x-transcript-ingest-options.md`.

---

## Kill

Unsupervised Pattern C · `@AutodevTeam` · invented pedigree · fresh X without live article · treating ASR as a gate.
