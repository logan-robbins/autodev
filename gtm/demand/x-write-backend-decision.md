# X write backend decision — `@LoganRobbinsAI`

**Decision (this week):** **Path A — own X Dev App + tiny approve-gated poster.**  
**Rejected:** Path D (wait for MCP write). Path C = fallback only.  
**Updated:** 2026-09-13  
**Sources:** `gtm/research/x-api-capability-map.md` · Logan: “write or run a program to post to the API”

---

## Pick

| | |
|---|---|
| **Primary** | **A.** developer.x.com app → OAuth 2.0 user context `@LoganRobbinsAI` → `POST /2/tweets` (+ `in_reply_to_tweet_id` for thread/reply, media INIT/APPEND/FINALIZE) |
| **Interim if app review stalls** | **B.** Typefully / Late / Buffer API queue — still approve-before-send |
| **Not strategy** | **C.** paste in UI |
| **Dead** | **D.** hope MCP grows a write tool |

MCP read stays. Write is **platform API**, not Cursor MCP.

---

## Why A

- Same create-once → post-many stack factories use  
- Threads / QT / replies programmable (template T-authority-quote-trailer)  
- Ads-ineligible ≠ write-ineligible (organic posts OK)  
- Approve gate is a **file/flag**, not a human paste box

---

## Logan / CoS setup (human, once)

1. X Developer Portal: create app (name e.g. `autodev-logan-growth-os`). User auth, **not** app-only.  
2. Scopes: `tweet.write` · `tweet.read` · `users.read` · `offline.access` · `media.write` if video.  
3. Auth as `@LoganRobbinsAI` (personal — this loop is personal only).  
4. Put secrets in env / OS keychain — **never** chat, never `gtm/` git.  
   - `X_CLIENT_ID` · `X_CLIENT_SECRET` · refresh token after first OAuth  
5. Demand/CoS run poster **only** on files under `gtm/demand/x-drafts/` with frontmatter `approved: true` + approver name.

Until step 4 exists, drafts stay queued. First trailer still blocked on authority slots.

---

## Poster contract (simple program)

`gtm/demand/bin/x-post.mjs` (to land when secrets exist):

```
read draft.md
if approved !== true → exit 1
POST https://api.x.com/2/tweets
  { text, quote_tweet_id?, reply?: { in_reply_to_tweet_id } }
write back posted_id + url
```

Thread = N calls with `in_reply_to_tweet_id`. Media = upload API then `media_ids`.  
**No loop over mentions. No like/RT farm.**

---

## Approve gate (unchanged)

Logan or delegated CoS sets `approved: true`. Demand never self-approves. No unsupervised replies.

---

## `@AutodevTeam`

Out of scope. When CEO entity is live + Ads-eligible, **new** app / new OAuth — do not reuse this app.

---

## Next

1. Logan: create X Dev App + OAuth (or say “use B this week”).  
2. Demand: land `bin/x-post.mjs` once env present.  
3. First approved post = CoS Link trailer **after** authority + N-count filled.
