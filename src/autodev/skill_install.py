"""Install the repository-owned operator skill for local Codex and Claude clients."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SKILL_NAME = "autodev-operator"


@dataclass(frozen=True)
class SkillLink:
    client: str
    path: Path
    source: Path
    created: bool


def operator_skill_source() -> Path:
    source = Path(__file__).resolve().parent / "skills" / SKILL_NAME
    if not (source / "SKILL.md").is_file():
        raise RuntimeError(f"packaged Autodev operator skill is missing: {source}")
    return source


def _install_link(*, client: str, destination: Path, source: Path) -> SkillLink:
    if destination.is_symlink():
        return SkillLink(client=client, path=destination, source=source, created=False)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.symlink_to(source, target_is_directory=True)
    return SkillLink(client=client, path=destination, source=source, created=True)


def _validate_destination(*, client: str, destination: Path, source: Path) -> None:
    if destination.is_symlink():
        try:
            resolved = destination.resolve(strict=True)
        except FileNotFoundError as exc:
            raise RuntimeError(f"refusing to replace broken {client} skill link: {destination}") from exc
        if resolved != source:
            raise RuntimeError(f"refusing to replace existing {client} skill link: {destination} -> {resolved}")
    elif destination.exists():
        raise RuntimeError(f"refusing to replace existing {client} skill path: {destination}")


def install_operator_skill(*, home: Path | None = None) -> tuple[SkillLink, ...]:
    source = operator_skill_source().resolve()
    user_home = (home or Path.home()).expanduser().resolve()
    destinations = (
        ("codex", user_home / ".agents" / "skills" / SKILL_NAME),
        ("claude", user_home / ".claude" / "skills" / SKILL_NAME),
    )
    for client, destination in destinations:
        _validate_destination(client=client, destination=destination, source=source)
    return tuple(
        _install_link(client=client, destination=destination, source=source) for client, destination in destinations
    )
