# X transcript ingest options — E2E flywheel

**Updated:** 2026-09-13  
**For:** Demand `x-e2e-flywheel.md` / ingest stub (`tweet_id` | `video_url` → gist md)  
**Constraint:** Official X API has **no transcript endpoint**. Get media URL → ASR (or vendor that wraps both).

## v1 default (CoS 2026-09-13) — ASR optional

Factories mostly riff the **seed post hook** + timestamp theater + Article QT. Full watch / full ASR is **not** required for factory-parity views.

| Mode | When | Input | Output |
|---|---|---|---|
| **Riff (default)** | Every Watch #3 / video seed | Seed text · author · caption chapter stamps · `duration_ms` if present | Logan-voice blog + X (exaggerate/contrast) — no transcript gate |
| **ASR upgrade (v1.5)** | Want real Pattern B chapters from ≥5m source | `variants` / yt-dlp → Whisper | Timestamp chapters for trailer |

`pending_asr` must **not** block article→X. Ingest stub: always emit riff pack; ASR only if Demand opts in.

---

## Recommended path (Autodev) — when ASR *is* chosen

| Stage | Tool | Notes |
|---|---|---|
| 1. Resolve | MCP `get_posts_by_id` + `expansions=attachments.media_keys` + `media.fields=duration_ms,variants,type,public_metrics` | Native X video → pick highest `bit_rate` mp4 from `variants` |
| 2. Linked video | Parse `entities.urls` / expanded URLs | YouTube / Vimeo / Mux → `yt-dlp` (install) not X variants |
| 3. Download | `yt-dlp` or curl the mp4 variant | Mac has `ffmpeg`; **no** `yt-dlp`/`whisper` installed yet — Demand stub should install or call vendor |
| 4. ASR | **faster-whisper** (local) or OpenAI Whisper API | Chapters from segment timestamps for Pattern B |
| 5. Gist | LLM compress → `gtm/demand/x-ingest/<id>-gist.md` | Input to article draft (Logan voice) |

**When ASR opted in:** Path **A** (own stack) once `yt-dlp` + `faster-whisper` exist. Path **B** (vendor) as unblock. **Default flywheel does not wait on this.**

---

## Option matrix

### A — Own stack (preferred long-term)

| Piece | How | Pros | Cons |
|---|---|---|---|
| X media URL | API `variants[]` | Already on Path A OAuth / MCP read | No captions; must download |
| External URL | `yt-dlp <url>` | YT / many hosts | Need install; ToS/rate care |
| ASR | `faster-whisper` (local GPU/CPU) or `openai` Whisper API | Full control; timestamps; cheap at volume | Local setup; long ≥50m videos = time/credits |
| Chapters | Segment `start` → `MM:SS - topic` | Pattern B trailer free | Needs gist quality |

**Stub interface:**
```
input:  { tweet_id } | { video_url }
output: { duration_ms, source_url, transcript_path, gist_md_path, chapter_candidates[] }
```

### B — Vendor transcript APIs (fast unblock)

| Vendor | Input | Output | Notes |
|---|---|---|---|
| [Supadata](https://supadata.ai/twitter-transcript-api) | x.com status URL | text + timestamps; Whisper fallback | No X API key; paid |
| [SocialKit](https://docs.socialkit.dev/api-reference/twitter-transcript-api) | tweet URL | segments + full text | Video tweets only |
| [Cito](https://citoapi.com/docs/api/twitter-transcript/) | tweet URL | text / verbose / srt / vtt | Whisper; 50+ langs |

Use when: native download blocked, need same-day E2E, or ≥50m factory videos overwhelm local ASR. Secrets off-repo (same pattern as Path A token).

### C — Native captions only

X sometimes ships captions; **not exposed** as a first-class MCP/API transcript field in our connector. Do not depend on this.

### D — Hand-watch / computerUse

Rejected for flywheel. Logan rule: no hand-watch.

---

## Live API note (this pass)

- **Confirmed:** `get_posts_by_id` on `2099094124628492717` returned `variants` (256k–10.3Mbps mp4 + HLS). Resolve step works on current MCP.
- `get_posts_by_id` with `media.fields=…,variants` is the resolve step for native video.
- Frontier seeds often attach **native** long video (Pattern B comps) or link out — stub must branch.
- Watch #2/#3 already filters `duration_ms` ≥5m when native.

---

## Demand wiring

1. Land ingest stub: `tweet_id` → resolve → download/ASR **or** vendor → `*-gist.md`.
2. E2E: Watch #3 video → ingest → article MD → CoS auto-publish → Pattern A/B X → optional supervised reply → metrics.
3. Install on Demand runner: `yt-dlp`, `faster-whisper` (or wire Whisper API key via secure input).
4. Cap: refuse if NSFW / off-topic hard-filter fails **before** ASR spend.
5. **Riff-first:** never block E2E on `pending_asr`.

@Autodev Demand — pick A (install) or B (vendor) for v0 stub in `x-e2e-flywheel.md`; Research prefers A with B fallback.
