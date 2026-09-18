#!/usr/bin/env node
/**
 * E2E ingest stub: tweet_id | video_url → gist md
 * Path A: yt-dlp + ffmpeg + faster-whisper when installed
 * Path B: vendor if SUPADATA_API_KEY (or sibling) set — not called unless present
 * Never prints secrets. No hand-watch.
 *
 * Usage:
 *   node x-ingest.mjs --tweet-id 2098162488013455784
 *   node x-ingest.mjs --url https://...
 */
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { execFileSync, spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const outDir = join(here, "..", "x-ingest");
mkdirSync(outDir, { recursive: true });

function arg(name) {
  const i = process.argv.indexOf(name);
  return i >= 0 ? process.argv[i + 1] : "";
}
const tweetId = arg("--tweet-id");
const videoUrl = arg("--url");
if (!tweetId && !videoUrl) {
  console.error("usage: node x-ingest.mjs --tweet-id <id> | --url <video_url>");
  process.exit(2);
}

function hasBin(bin) {
  const r = spawnSync("which", [bin], { encoding: "utf8" });
  return r.status === 0 && Boolean(r.stdout.trim());
}

const id = tweetId || Buffer.from(videoUrl).toString("hex").slice(0, 16);
const gistPath = join(outDir, `${id}-gist.md`);
const jsonPath = join(outDir, `${id}.json`);

const tools = {
  ytdlp: hasBin("yt-dlp"),
  ffmpeg: hasBin("ffmpeg"),
  whisper: hasBin("faster-whisper") || hasBin("whisper"),
};
const pathA = tools.ytdlp && tools.ffmpeg && tools.whisper;
const pathB = Boolean(process.env.SUPADATA_API_KEY || process.env.SOCIALKIT_API_KEY || process.env.CITO_API_KEY);

const sourceUrl = videoUrl || (tweetId ? `https://x.com/i/web/status/${tweetId}` : "");

const payload = {
  tweet_id: tweetId || null,
  video_url: videoUrl || null,
  source_url: sourceUrl,
  duration_ms: null,
  transcript_path: null,
  gist_md_path: gistPath,
  chapter_candidates: [],
  path: pathA ? "A" : pathB ? "B_ready" : "pending_asr",
  tools,
  note: pathA
    ? "A tools present — next: resolve variants / yt-dlp then ASR"
    : "A missing (need yt-dlp + faster-whisper). B if vendor key in env. Resolve tweet media via MCP get_posts_by_id variants.",
};

writeFileSync(
  gistPath,
  `---
status: ${payload.path}
tweet_id: ${tweetId || ""}
source_url: ${sourceUrl}
duration_ms:
asr: ${pathA ? "ready" : "pending"}
---

# Gist ${id}

## Source
- tweet_id: ${tweetId || "—"}
- url: ${sourceUrl}

## Transcript
_Pending ASR. Path A = yt-dlp + ffmpeg + faster-whisper. Path B = vendor. No hand-watch._

## Chapters (Pattern B)
_Fill from ASR segments once A/B runs._

## Logan-angle (for article)
- Frontier claim:
- Staffing-agency foil:
- AI-sucks / engineers beat:
`,
);

writeFileSync(jsonPath, JSON.stringify(payload, null, 2));
console.log("gist", gistPath);
console.log("json", jsonPath);
console.log("path", payload.path);
if (!pathA && !pathB) process.exit(0);
