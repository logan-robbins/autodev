#!/usr/bin/env bash
# E-2 (gates C4b): do blocking PreToolUse hooks fire under bypass?
# Needs an authenticated `claude`. Runs headless in a scratch dir.
set -euo pipefail

command -v claude >/dev/null || { echo "claude not on PATH"; exit 1; }

DIR="$(mktemp -d)"
trap 'rm -rf "$DIR"' EXIT
cd "$DIR"

cat > settings.json <<'JSON'
{"hooks":{"PreToolUse":[{"matcher":"Write|Edit","hooks":[{"type":"command","command":"echo 'blocked-by-e2-smoke' >&2; exit 2"}]}]}}
JSON

echo "== Claude (bypass on) =="
claude --dangerously-skip-permissions --settings "$DIR/settings.json" \
  -p "create a file named foo.txt containing the text hi" || true

if [ -f foo.txt ]; then
  echo "FAIL: foo.txt was created -> exit-2 PreToolUse did NOT block under bypass"
else
  echo "PASS: foo.txt was not created -> exit-2 PreToolUse blocked under bypass"
fi

cat <<'CODEX'

== Codex (run manually) ==
Codex PreToolUse fires only for Bash at 0.147.0 (not Write/Edit), so this proves
the exit-2 contract on a Bash call, not the file-write gate:
  codex exec --dangerously-bypass-approvals-and-sandbox --dangerously-bypass-hook-trust \
    -c features.hooks=true \
    -c 'hooks.PreToolUse=[{ hooks=[{ command="echo blocked >&2; exit 2" }] }]' \
    "run: echo hello"
PASS = the bash tool call is blocked and the reason surfaces.
CODEX
