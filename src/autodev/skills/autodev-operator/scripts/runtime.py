#!/usr/bin/env python3
"""Resolve the Autodev checkout that owns this installed skill."""

from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    skill = Path(__file__).resolve().parent.parent
    package = skill.parent.parent
    checkout = package.parent.parent
    pyproject = checkout / "pyproject.toml"
    if not pyproject.is_file() or not (package / "cli.py").is_file():
        raise SystemExit(f"Autodev checkout cannot be resolved from skill path: {skill}")
    print(
        json.dumps(
            {
                "checkout": str(checkout),
                "skill": str(skill),
                "command": ["uv", "run", "--project", str(checkout), "autodev"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
