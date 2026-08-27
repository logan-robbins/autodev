"""Pure per-role/kind PreToolUse policy: the enforcement teeth (NEXT §7.2).

``decide`` is a pure function of a single tool call's shape — no I/O — so every
rule is testable with a synthetic ``PolicyInput``. The CLI verb (``policy
check``, C4b) resolves the run's role/kind and TDD state, calls ``decide``, and
turns a denial into the portable hard block (exit 2). Only Write/Edit are gated;
everything else is allowed.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import PurePosixPath

_WRITE_TOOLS = frozenset({"Write", "Edit", "MultiEdit"})
_FACTS_ROOT = "artifacts/facts"
_IMPL_ROOT = "src/impl"
_SOURCE_ROOT = "src"
_PILLARS_ROOT = "product/pillars"
_PILLAR_DOC_NAMES = frozenset({"README.md", "TECHNICAL.md"})

# Which role may run which typed `autodev product` verb (the verb-authority
# table). A verb absent here carries no role constraint.
_VERB_AUTHORITY = {
    "add-pillars": "product-manager",
    "add-features": "product-manager",
    "decompose-feature": "project-manager",
    "set-leaf-status": "engineering",
}


@dataclass(frozen=True)
class PolicyInput:
    role: str
    kind: str
    tool_name: str
    tool_input: dict
    write_roots: tuple[str, ...] = ()
    # Whether a failing test has already been recorded this pass (the TDD gate).
    red_test: bool = False


@dataclass(frozen=True)
class PolicyDecision:
    allow: bool
    reason: str = ""


def _target_path(tool_input: dict) -> str:
    for key in ("file_path", "path", "notebook_path"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _contains_segments(path: str, segments: str) -> bool:
    """True when ``segments`` appears as a contiguous run of path components.

    Robust to absolute worktree prefixes: ``/home/.../book/src/impl/x.py``
    contains ``src/impl``.
    """
    parts = PurePosixPath(path.replace("\\", "/")).parts
    wanted = tuple(part for part in segments.strip("/").split("/") if part)
    if not wanted:
        return False
    span = len(wanted)
    return any(parts[i : i + span] == wanted for i in range(len(parts) - span + 1))


def _allow() -> PolicyDecision:
    return PolicyDecision(allow=True)


def _autodev_product_verb(command: str) -> str | None:
    """The verb of an ``autodev product <verb>`` Bash command, else ``None``."""
    if not command:
        return None
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None
    for index in range(len(tokens) - 2):
        if tokens[index].endswith("autodev") and tokens[index + 1] == "product":
            return tokens[index + 2]
    return None


def _is_pillar_doc(path: str) -> bool:
    return _contains_segments(path, _PILLARS_ROOT) and PurePosixPath(path.replace("\\", "/")).name in _PILLAR_DOC_NAMES


def decide(pi: PolicyInput) -> PolicyDecision:
    """Return allow/deny for one tool call under the role/kind + verb-authority policy."""
    # Verb authority: only the owning role may run a tree-authoring product verb.
    if pi.tool_name == "Bash":
        verb = _autodev_product_verb(str(pi.tool_input.get("command", "")))
        required = _VERB_AUTHORITY.get(verb) if verb is not None else None
        if required is not None and pi.role != required:
            return PolicyDecision(False, f"only {required} may run `autodev product {verb}` (role is {pi.role})")
        return _allow()

    if pi.tool_name not in _WRITE_TOOLS:
        return _allow()
    path = _target_path(pi.tool_input)
    if not path:
        return _allow()

    # Technical Writer owns only the pillar docs; any other write is denied.
    if pi.role == "technical-writer":
        if _is_pillar_doc(path):
            return _allow()
        return PolicyDecision(False, "technical-writer may only write the pillar docs (README.md/TECHNICAL.md)")

    # Project Manager reconciles; it never edits pod source.
    if pi.role == "project-manager":
        if _contains_segments(path, _SOURCE_ROOT):
            return PolicyDecision(False, "project-manager must not edit pod source (src/**)")
        return _allow()

    if pi.kind == "search":
        if not _contains_segments(path, _FACTS_ROOT):
            return PolicyDecision(False, "search may only write facts under artifacts/facts/**")
        return _allow()

    if pi.kind == "contract":
        if _contains_segments(path, _IMPL_ROOT):
            return PolicyDecision(False, "contract must publish interfaces, not write src/impl/**")
        return _allow()

    if pi.kind == "implement":
        if _contains_segments(path, _SOURCE_ROOT) and not pi.red_test:
            return PolicyDecision(False, "implement may not write src/** before a failing test (TDD gate)")
        return _allow()

    # integrate is enforced physically by sparse checkout (C5); nothing to block here.
    return _allow()
