from __future__ import annotations

from pathlib import Path

import pytest

from autodev.cli import main
from autodev.skill_install import install_operator_skill, operator_skill_source


def test_installs_repository_owned_skill_for_codex_and_claude(tmp_path: Path) -> None:
    links = install_operator_skill(home=tmp_path)

    assert [(link.client, link.created) for link in links] == [("codex", True), ("claude", True)]
    assert {link.path for link in links} == {
        tmp_path / ".agents" / "skills" / "autodev-operator",
        tmp_path / ".claude" / "skills" / "autodev-operator",
    }
    assert all(link.path.is_symlink() for link in links)
    assert all(link.path.resolve() == operator_skill_source().resolve() for link in links)

    repeated = install_operator_skill(home=tmp_path)
    assert all(not link.created for link in repeated)


def test_refuses_to_replace_existing_skill(tmp_path: Path) -> None:
    conflict = tmp_path / ".claude" / "skills" / "autodev-operator"
    conflict.mkdir(parents=True)

    with pytest.raises(RuntimeError, match="refusing to replace existing claude skill path"):
        install_operator_skill(home=tmp_path)

    assert not (tmp_path / ".agents" / "skills" / "autodev-operator").exists()


def test_skill_install_cli_reports_both_clients(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr("autodev.cli.install_operator_skill", lambda: install_operator_skill(home=tmp_path))

    assert main(["skill", "install"]) == 0

    output = capsys.readouterr().out
    assert "codex: installed" in output
    assert "claude: installed" in output
