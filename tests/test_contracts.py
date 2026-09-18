import json
from pathlib import Path

import pytest

from autodev.config import ConfigError, load_project
from autodev.contracts import check_schema, validate_value, verify_pillar


def test_interface_fixture_is_valid_but_not_implementation(file_project: Path):
    pillar = load_project(file_project).pillar("backend")
    assert verify_pillar(pillar, interface_only=True)[0]["id"] == "result"
    with pytest.raises(ConfigError, match="interface-ready"):
        verify_pillar(pillar)


def test_missing_business_output_cannot_pass_as_ready(file_project: Path):
    path = file_project / "backend/pillar.toml"
    path.write_text(path.read_text().replace('state = "interface-ready"', 'state = "implementation-ready"'))
    with pytest.raises(ConfigError, match="missing output"):
        verify_pillar(load_project(file_project).pillar("backend"))


@pytest.mark.parametrize(
    "data", [{}, {"status": True}, {"status": "other", "summary": "x", "evidence": [], "artifacts": []}]
)
def test_invalid_fixtures_fail(file_project: Path, data):
    (file_project / "backend/fixtures/result.json").write_text(json.dumps(data))
    with pytest.raises(ConfigError):
        verify_pillar(load_project(file_project).pillar("backend"), interface_only=True)


def test_failed_check_rejects_interface(file_project: Path):
    (file_project / "backend/interface.py").write_text("raise SystemExit(9)\n")
    with pytest.raises(ConfigError, match="check failed"):
        verify_pillar(load_project(file_project).pillar("backend"), interface_only=True)


def test_unknown_schema_keywords_fail_instead_of_being_ignored():
    with pytest.raises(ConfigError, match="unsupported"):
        check_schema({"type": "string", "pattern": "x"})


def test_boolean_is_not_an_integer():
    with pytest.raises(ConfigError, match="expected integer"):
        validate_value(True, {"type": "integer"})


@pytest.mark.parametrize("value", [["string", "null"], {}, None])
def test_schema_type_must_be_supported_single_type(value):
    with pytest.raises(ConfigError, match="supported type"):
        check_schema({"type": value})


def test_check_context_is_explicit_and_does_not_leak(file_project, monkeypatch):
    import os
    import sys

    from autodev.contracts import run_checks

    script = file_project / "inspect_context.py"
    script.write_text(
        "import os,json\nfrom pathlib import Path\n"
        "Path('context.json').write_text(json.dumps({k:v for k,v in os.environ.items() if k.startswith('AUTODEV_CHECK_')}))\n"
    )
    import shlex

    command = shlex.join([sys.executable, str(script)])
    monkeypatch.setenv("AUTODEV_CHECK_TASK_ID", "untrusted-inherited-value")
    run_checks((command,), file_project, context={"AUTODEV_CHECK_TASK_ID": "runtime-assignment"})
    assert json.loads((file_project / "context.json").read_text()) == {"AUTODEV_CHECK_TASK_ID": "runtime-assignment"}
    run_checks((command,), file_project)
    assert json.loads((file_project / "context.json").read_text()) == {}
    assert os.environ["AUTODEV_CHECK_TASK_ID"] == "untrusted-inherited-value"
