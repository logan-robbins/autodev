#!/usr/bin/env bash
# E-1 (gates C2): does --append-system-prompt survive mid-session compaction?
# Needs an authenticated `claude`. Runs in a scratch dir; no repo side effects.
set -euo pipefail

command -v claude >/dev/null || { echo "claude not on PATH"; exit 1; }

DIR="$(mktemp -d)"
trap 'rm -rf "$DIR"' EXIT
cd "$DIR"
printf 'CANARY-LAW: begin every reply with the literal token [LAW].\n' > law.md

cat <<'STEPS'
E-1 procedure (interactive, ~20 min):
  1. A session is starting with the canary law appended to the system prompt.
  2. Drive a long conversation (or run /compact) to force auto-compaction;
     confirm compaction happened (context indicator / --include-hook-events).
  3. After compaction, send a trivial prompt.
  4. PASS  = the reply still begins with [LAW].
     FAIL  = the prefix is gone  -> demote the spine to the C3 hook layer
             (charter digest on SessionStart/UserPromptSubmit).
  5. Repeat for Codex using model_instructions_file ONLY to confirm the
     replace-vs-append behaviour; do not adopt it as the spine.
STEPS

exec claude --append-system-prompt-file "$DIR/law.md"
