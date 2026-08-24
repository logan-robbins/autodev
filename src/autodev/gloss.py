"""Layer-2 gloss: one bounded Haiku line per completed stage.

Layer 1 (``trace.to_dag``) is a pure fold and needs no model. Layer 2 adds a
single one-line gloss per *completed* stage via headless ``claude -p``, cached in
the ``step_finished.gloss`` event so it is computed at most once and never for a
live node. Gloss is presentation-only: if ``claude`` is absent or errors, the
caller keeps the ungloss'd DAG.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence

from autodev.trace import StageNode

GLOSS_MODEL = "haiku"
GLOSS_INSTRUCTION = (
    "In one terse line of at most 12 words, say what this step accomplished. "
    "No preamble, no quotes, no trailing period."
)

# A stage is glossable once it has finished (verify stages report red/green).
_COMPLETED = frozenset({"done", "failed", "red", "green"})


class GlossError(RuntimeError):
    """Raised when the headless gloss call fails."""


def should_gloss(node: StageNode) -> bool:
    """True only for a completed stage that has no gloss yet (the cache check)."""
    return node.status in _COMPLETED and not node.gloss


def gloss_step(
    transcript_slice: str,
    *,
    claude_cmd: Sequence[str],
    model: str = GLOSS_MODEL,
    timeout: float = 30.0,
) -> str:
    """Return a one-line gloss of ``transcript_slice`` via ``claude -p --model``."""
    prompt = f"{GLOSS_INSTRUCTION}\n\n{transcript_slice}"
    command = [*claude_cmd, "-p", "--model", model, "--output-format", "text", prompt]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GlossError(f"gloss call failed: {exc}") from exc
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "no output"
        raise GlossError(f"gloss call exited {result.returncode}: {detail}")
    output = result.stdout.strip()
    return output.splitlines()[0].strip() if output else ""
