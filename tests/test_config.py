from __future__ import annotations

from pathlib import Path

import pytest

from autodev.config import (
    SCHEMA_VERSION,
    ConfigError,
    descriptor_path,
    load_project,
    render_session_name,
)

_SCHEMA_3_TABLES = """
[loop]
sequence = ["project-manager", "engineering", "project-manager"]
reenter_product_manager_when = ["new-requirement", "queues-exhausted"]
max_concurrent = 3

[roles.product-manager]
shape = "research"
charter = "Own a Pillar; emit Features."

[roles.project-manager]
shape = "reconcile"
charter = "Own a Feature; split into leaves."

[roles.engineering]
shape = "contract-first"
charter = "Own a Leaf; red tests first."
"""


def _add_tables(project_repo: Path, tables: str) -> None:
    descriptor = project_repo / "autodev.toml"
    descriptor.write_text(descriptor.read_text(encoding="utf-8") + tables, encoding="utf-8")


def test_loads_single_file_project_contract(project_repo: Path) -> None:
    project = load_project(project_repo)

    assert project.id == "sample-project"
    assert project.root == project_repo
    assert project.base_branch == "main"
    assert project.agent("backend").provider == "codex"
    assert project.agent("backend").write_roots == ("src/backend/",)
    assert project.providers["codex"].command == "codex"
    assert project.providers["codex"].model is None
    assert project.session_pattern == "autodev-{project}-{agent}"
    assert project.ui_port == 8765
    assert project.bypass_permissions is False


def test_discovers_descriptor_from_child_directory(project_repo: Path) -> None:
    child = project_repo / "src" / "backend"
    assert descriptor_path(cwd=child) == project_repo / "autodev.toml"


def test_rejects_overlapping_agent_ownership(project_repo: Path) -> None:
    descriptor = project_repo / "autodev.toml"
    descriptor.write_text(
        descriptor.read_text(encoding="utf-8")
        + """

[[agents]]
id = "frontend"
provider = "claude"
purpose = "Own nested paths."
goal = "Complete one item."
write_roots = ["src/backend/api/"]
read_roots = []
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="write roots overlap"):
        load_project(project_repo)


@pytest.mark.parametrize("root", ["/tmp/outside", "../outside", ".", "autodev.toml"])
def test_rejects_unsafe_write_roots(project_repo: Path, root: str) -> None:
    descriptor = project_repo / "autodev.toml"
    descriptor.write_text(
        descriptor.read_text(encoding="utf-8").replace('"src/backend/"', f'"{root}"'),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="relative path|cannot grant"):
        load_project(project_repo)


def test_descriptor_must_live_at_git_root(project_repo: Path) -> None:
    nested = project_repo / "src" / "autodev.toml"
    nested.write_text((project_repo / "autodev.toml").read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(ConfigError, match="must be at the Git worktree root"):
        load_project(nested)


def test_custom_tmux_session_pattern_is_validated_and_rendered(project_repo: Path) -> None:
    descriptor = project_repo / "autodev.toml"
    descriptor.write_text(
        descriptor.read_text(encoding="utf-8").replace(
            'session_pattern = "autodev-{project}-{agent}"',
            'session_pattern = "dev_{provider}_{project}_{agent}"',
        ),
        encoding="utf-8",
    )

    project = load_project(project_repo)

    assert render_session_name(project.session_pattern, project.id, project.agent("backend")) == (
        "dev_codex_sample-project_backend"
    )


@pytest.mark.parametrize(
    ("pattern", "message"),
    [
        ("autodev-{project}", "exactly one {agent}"),
        ("autodev-{project}-{agent}-{unknown}", "unknown fields"),
        ("autodev:{project}:{agent}", "must render only"),
    ],
)
def test_rejects_invalid_tmux_session_patterns(project_repo: Path, pattern: str, message: str) -> None:
    descriptor = project_repo / "autodev.toml"
    descriptor.write_text(
        descriptor.read_text(encoding="utf-8").replace(
            'session_pattern = "autodev-{project}-{agent}"',
            f'session_pattern = "{pattern}"',
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match=message):
        load_project(project_repo)


@pytest.mark.parametrize("port", [0, 1023, 65536, '"8765"', "true"])
def test_rejects_invalid_project_ui_port(project_repo: Path, port: object) -> None:
    descriptor = project_repo / "autodev.toml"
    descriptor.write_text(
        descriptor.read_text(encoding="utf-8").replace("ui_port = 8765", f"ui_port = {port}"),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="runtime.ui_port"):
        load_project(project_repo)


# --- B1: schema 3 ------------------------------------------------------------


def test_schema_version_is_three() -> None:
    assert SCHEMA_VERSION == 3


def test_bare_schema_3_still_loads(project_repo: Path) -> None:
    # A descriptor with no [loop]/[roles.*]/pod is valid: the tables are additive.
    project = load_project(project_repo)
    assert project.loop is None
    assert project.roles == {}
    assert project.agent("backend").pod is None


def test_loads_loop_roles_and_pod(project_repo: Path) -> None:
    _add_tables(project_repo, _SCHEMA_3_TABLES)
    descriptor = project_repo / "autodev.toml"
    descriptor.write_text(
        descriptor.read_text(encoding="utf-8").replace(
            'provider = "codex"',
            'provider = "codex"\npod = "backend"',
        ),
        encoding="utf-8",
    )
    project = load_project(project_repo)

    assert project.loop is not None
    assert project.loop.sequence == ("project-manager", "engineering", "project-manager")
    assert project.loop.max_concurrent == 3
    assert project.roles["engineering"].shape == "contract-first"
    assert project.roles["product-manager"].charter.startswith("Own a Pillar")
    assert project.agent("backend").pod == "backend"


def test_rejects_schema_two(project_repo: Path) -> None:
    descriptor = project_repo / "autodev.toml"
    descriptor.write_text(
        descriptor.read_text(encoding="utf-8").replace("schema_version = 3", "schema_version = 2"),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="schema_version must be 3"):
        load_project(project_repo)


def test_rejects_bad_role_shape(project_repo: Path) -> None:
    _add_tables(project_repo, '\n[roles.designer]\nshape = "vibes"\ncharter = "make it pretty"\n')
    with pytest.raises(ConfigError, match="roles.designer.shape"):
        load_project(project_repo)


# --- D1: the document shape (technical-writer) -------------------------------


def test_document_shape_role_loads(project_repo: Path) -> None:
    _add_tables(
        project_repo,
        '\n[roles.technical-writer]\nshape = "document"\ncharter = "Own the pillar docs; run last."\n',
    )
    project = load_project(project_repo)
    assert project.roles["technical-writer"].shape == "document"


def test_unknown_shape_still_rejected_after_document_added(project_repo: Path) -> None:
    _add_tables(project_repo, '\n[roles.designer]\nshape = "documentt"\ncharter = "typo"\n')
    with pytest.raises(ConfigError, match="roles.designer.shape"):
        load_project(project_repo)


# --- D2: the [pods] template -------------------------------------------------

_POD_TABLES = (
    _SCHEMA_3_TABLES
    + """
[pods]
[pods.members.product-manager]
provider = "claude"
[pods.members.engineering]
provider = "codex"
"""
)


def test_loads_pods_template(project_repo: Path) -> None:
    _add_tables(project_repo, _POD_TABLES)
    project = load_project(project_repo)
    assert project.pods is not None
    assert set(project.pods.members) == {"product-manager", "engineering"}
    assert project.pods.members["engineering"].provider == "codex"
    assert project.pods.members["product-manager"].model is None


def test_pods_member_naming_undeclared_role_rejected(project_repo: Path) -> None:
    _add_tables(
        project_repo,
        _SCHEMA_3_TABLES + '\n[pods]\n[pods.members.designer]\nprovider = "claude"\n',
    )
    with pytest.raises(ConfigError, match="pods.members.designer names an undeclared"):
        load_project(project_repo)


def test_pods_member_bad_provider_rejected(project_repo: Path) -> None:
    _add_tables(
        project_repo,
        _SCHEMA_3_TABLES + '\n[pods]\n[pods.members.engineering]\nprovider = "gemini"\n',
    )
    with pytest.raises(ConfigError, match="pods.members.engineering.provider must be one of"):
        load_project(project_repo)


# --- D3: [[agents]] or [pods] required; empty write_roots allowed ------------

_BASE_DESCRIPTOR = """schema_version = 3

[project]
id = "sample-project"
name = "Sample Project"
base_branch = "main"
instructions = "One canonical path."
context_roots = []
verify_commands = []

[runtime]
session_pattern = "autodev-{project}-{agent}"
ui_port = 8765
bypass_permissions = false
"""


def _write_descriptor(project_repo: Path, body: str) -> None:
    (project_repo / "autodev.toml").write_text(body, encoding="utf-8")


def test_template_only_descriptor_loads(project_repo: Path) -> None:
    _write_descriptor(
        project_repo,
        _BASE_DESCRIPTOR + _SCHEMA_3_TABLES + '\n[pods]\n[pods.members.engineering]\nprovider = "codex"\n',
    )
    project = load_project(project_repo)
    assert project.agents == ()
    assert project.pods is not None


def test_descriptor_with_neither_agents_nor_pods_rejected(project_repo: Path) -> None:
    _write_descriptor(project_repo, _BASE_DESCRIPTOR)
    with pytest.raises(ConfigError, match="must declare at least one \\[\\[agents\\]\\] table or a \\[pods\\]"):
        load_project(project_repo)


def test_verb_only_agent_with_empty_write_roots_loads(project_repo: Path) -> None:
    _write_descriptor(
        project_repo,
        _BASE_DESCRIPTOR
        + '\n[[agents]]\nid = "pm"\nprovider = "claude"\npurpose = "Author the tree."\n'
        + 'goal = "Expand pillars."\nwrite_roots = []\nread_roots = ["product/"]\n',
    )
    project = load_project(project_repo)
    assert project.agent("pm").write_roots == ()


def test_rejects_loop_sequence_entry_without_role(project_repo: Path) -> None:
    _add_tables(
        project_repo,
        '\n[loop]\nsequence = ["ghost-role"]\n\n[roles.engineering]\nshape = "contract-first"\ncharter = "x"\n',
    )
    with pytest.raises(ConfigError, match="loop.sequence entry 'ghost-role' is not a configured"):
        load_project(project_repo)


def test_rejects_non_positive_max_concurrent(project_repo: Path) -> None:
    _add_tables(
        project_repo,
        '\n[roles.engineering]\nshape = "contract-first"\ncharter = "x"\n'
        '\n[loop]\nsequence = ["engineering"]\nmax_concurrent = 0\n',
    )
    with pytest.raises(ConfigError, match="loop.max_concurrent must be a positive integer"):
        load_project(project_repo)


def _loop_tables(*, max_attempts: str | None) -> str:
    extra = f"\nmax_attempts = {max_attempts}" if max_attempts is not None else ""
    return (
        '\n[roles.engineering]\nshape = "contract-first"\ncharter = "x"\n'
        f'\n[loop]\nsequence = ["engineering"]\nmax_concurrent = 2{extra}\n'
    )


def test_loop_max_attempts_parses_and_defaults(project_repo: Path) -> None:
    _add_tables(project_repo, _loop_tables(max_attempts="2"))
    project = load_project(project_repo)
    assert project.loop is not None
    assert project.loop.max_attempts == 2


def test_loop_max_attempts_defaults_to_one_when_omitted(project_repo: Path) -> None:
    _add_tables(project_repo, _loop_tables(max_attempts=None))
    project = load_project(project_repo)
    assert project.loop is not None
    assert project.loop.max_attempts == 1  # default self-retry budget


def test_loop_max_attempts_allows_zero(project_repo: Path) -> None:
    # 0 is a valid budget (escalate on the first failure), distinct from the default.
    _add_tables(project_repo, _loop_tables(max_attempts="0"))
    assert load_project(project_repo).loop.max_attempts == 0


def test_rejects_negative_max_attempts(project_repo: Path) -> None:
    _add_tables(project_repo, _loop_tables(max_attempts="-1"))
    with pytest.raises(ConfigError, match="loop.max_attempts must be a non-negative integer"):
        load_project(project_repo)


def test_rejects_unknown_loop_key(project_repo: Path) -> None:
    _add_tables(
        project_repo,
        '\n[roles.engineering]\nshape = "contract-first"\ncharter = "x"\n'
        '\n[loop]\nsequence = ["engineering"]\nmax_concurrent = 2\nbogus = 1\n',
    )
    with pytest.raises(ConfigError, match=r"\[loop\] has unknown field\(s\): bogus"):
        load_project(project_repo)


def test_examples_scaffold_defaults_max_attempts_to_one(project_repo: Path) -> None:
    # The shipped company scaffold omits max_attempts, so it loads with the default 1.
    example = Path(__file__).resolve().parents[1] / "examples" / "autodev.toml"
    (project_repo / "autodev.toml").write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
    project = load_project(project_repo)
    assert project.loop is not None
    assert project.loop.max_attempts == 1


@pytest.mark.parametrize("value", ["0", "1", '"true"'])
def test_rejects_non_boolean_permission_bypass(project_repo: Path, value: str) -> None:
    descriptor = project_repo / "autodev.toml"
    descriptor.write_text(
        descriptor.read_text(encoding="utf-8").replace(
            "bypass_permissions = false",
            f"bypass_permissions = {value}",
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="runtime.bypass_permissions"):
        load_project(project_repo)
