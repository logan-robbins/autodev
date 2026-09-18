#!/usr/bin/env node
/**
 * Approve-gated X poster (Path A).
 * Posts ONLY if draft frontmatter has approved: true.
 * Secrets from env — never from the draft file or git.
 *
 * Env: X_BEARER_TOKEN  (user-context OAuth2 access token with tweet.write)
 * Usage: node x-post.mjs /path/to/draft.md
 */
import { readFileSync, writeFileSync } from "node:fs";

const draftPath = process.argv[2];
if (!draftPath) {
  console.error("usage: node x-post.mjs <draft.md>");
  process.exit(2);
}

const raw = readFileSync(draftPath, "utf8");
const fm = raw.match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/);
if (!fm) {
  console.error("draft needs YAML frontmatter");
  process.exit(1);
}

const meta = Object.fromEntries(
  fm[1]
    .split("\n")
    .filter((l) => l.includes(":"))
    .map((l) => {
      const i = l.indexOf(":");
      return [l.slice(0, i).trim(), l.slice(i + 1).trim().replace(/^["']|["']$/g, "")];
    }),
);

if (meta.approved !== "true") {
  console.error("refusing: approved !== true");
  process.exit(1);
}
if (!meta.approver) {
  console.error("refusing: missing approver");
  process.exit(1);
}

if (meta.type === "fresh-post") {
  const article = meta.site_article || "";
  const homepage = /^https?:\/\/(www\.)?autodev-team\.com\/?$/i.test(article);
  if (!article.includes("autodev-team.com") || homepage) {
    console.error("refusing: fresh post needs site_article URL (not homepage)");
    process.exit(1);
  }
  if (meta.voice_ok !== "true") {
    console.error("refusing: fresh post needs voice_ok: true");
    process.exit(1);
  }
}

function loadToken() {
  if (process.env.X_BEARER_TOKEN) return process.env.X_BEARER_TOKEN;
  const file = process.env.X_TOKEN_FILE || "/home/box/.config/x-growth-os/token.json";
  try {
    const d = JSON.parse(readFileSync(file, "utf8"));
    return d.access_token || "";
  } catch {
    return "";
  }
}
const token = loadToken();
if (!token) {
  console.error("refusing: no user token (X_BEARER_TOKEN / X_TOKEN_FILE)");
  process.exit(1);
}

const text = (meta.text || fm[2].trim()).slice(0, 280);
if (!text) {
  console.error("refusing: empty text");
  process.exit(1);
}

const body = { text };
if (meta.quote_tweet_id) body.quote_tweet_id = meta.quote_tweet_id;
if (meta.in_reply_to_tweet_id) {
  body.reply = { in_reply_to_tweet_id: meta.in_reply_to_tweet_id };
}

const res = await fetch("https://api.x.com/2/tweets", {
  method: "POST",
  headers: {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify(body),
});

const json = await res.json();
if (!res.ok) {
  console.error("X API error", res.status, JSON.stringify(json));
  process.exit(1);
}

const id = json?.data?.id;
const url = id ? `https://x.com/i/web/status/${id}` : "";
const stamped = raw.replace(
  /^---\n/,
  `---\nposted_id: ${id}\nposted_url: ${url}\nposted_at: ${new Date().toISOString()}\n`,
);
writeFileSync(draftPath, stamped);
console.log(url || JSON.stringify(json));
