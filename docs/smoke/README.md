# Manual provider smokes (E-1 / E-2 / token format)

These three checks need a live, authenticated `claude` / `codex` session, which
the build environment does not have. All *pure logic* they gate is fully unit-
tested (see the PR); these scripts prove the real CLI behaviour end to end and
must be run once by a human with an authenticated account, in a scratch dir with
no repo side effects. Record the outcome in the PR.

| smoke | gates | pass condition |
|---|---|---|
| `e1_append_system_prompt.sh` | C2 (durable-law spine) | appended system prompt is still honoured after a forced compaction |
| `e2_pretooluse_block.sh` | C4b (enforcement teeth) | a PreToolUse hook that `exit 2`s blocks the Write **under bypass** |
| token format (below) | A11 (`read_tokens`) | the real transcript JSONL matches the parser's expected shape |

## E-1 — does `--append-system-prompt` survive compaction? (gates C2)

`bash docs/smoke/e1_append_system_prompt.sh` sets up the scratch dir and prints
the interactive steps. Pass ⇒ Claude's `--append-system-prompt-file` is the
durable spine as designed. Fail ⇒ the spine demotes to the C3 hook layer
(`charter digest` on SessionStart/UserPromptSubmit), which is already
implemented and independently tested. Codex has **no** append-only system-prompt
flag at 0.147.0 (`base_instructions` does not exist; `model_instructions_file`
replaces built-ins), so Codex relies on the C3 layer regardless of E-1.

## E-2 — do blocking PreToolUse hooks fire under bypass? (gates C4b)

`bash docs/smoke/e2_pretooluse_block.sh` runs the Claude case headlessly and
prints the Codex case. Pass (Claude) ⇒ exit-2 blocking works under
`--dangerously-skip-permissions`. For Codex, note that PreToolUse fires **only
for Bash** at 0.147.0 — Write/Edit are not intercepted — so the `implement`
write-gate cannot fire on Codex; the physical `src/impl/**` sparse exclusion (C5)
is the Codex fallback.

## Token format (gates A11)

After a real run, tail the transcript the hook payload's `transcript_path`
points at and confirm `trace.read_tokens` extracts a sane number:

```sh
uv run python - <<'PY'
from autodev.trace import read_tokens
print("claude:", read_tokens("<path-to-claude-transcript>.jsonl", "claude"))
print("codex :", read_tokens("<path-to-codex-transcript>.jsonl", "codex"))
PY
```

If a provider's real layout differs from `trace._claude_tokens` /
`trace._codex_tokens`, adjust those two helpers only.
