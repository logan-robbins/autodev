from __future__ import annotations

import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from autodev.config import load_project
from autodev.service import _control_token, project_ui_handler


@pytest.fixture
def project_ui(project_repo: Path, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AUTODEV_HOME", str(tmp_path / "state"))
    project = load_project(project_repo)
    token = _control_token(project)
    server = ThreadingHTTPServer(("127.0.0.1", 0), project_ui_handler(project, token))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", token, project
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_project_ui_exposes_only_its_bound_project(project_ui) -> None:
    url, _token, _project = project_ui
    with urlopen(f"{url}/api/project") as response:
        payload = json.load(response)

    assert payload["id"] == "sample-project"
    assert payload["ui_port"] == 8765
    assert payload["agents"][0]["provider"] == "codex"

    with urlopen(f"{url}/") as response:
        page = response.read().decode()
    assert "Project configuration" in page
    assert '<textarea id="config"' in page


def test_project_ui_mutations_require_token(project_ui) -> None:
    url, _token, _project = project_ui
    request = Request(
        f"{url}/api/actions/stop",
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(HTTPError) as error:
        urlopen(request)
    assert error.value.code == 401


def test_project_ui_saves_valid_configuration_atomically(project_ui) -> None:
    url, token, project = project_ui
    original = project.descriptor.read_text(encoding="utf-8")
    updated = original.replace('name = "Sample Project"', 'name = "Renamed Project"').replace(
        "ui_port = 8765", "ui_port = 8878"
    )
    request = Request(
        f"{url}/api/config",
        data=json.dumps({"content": updated}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="PUT",
    )

    with urlopen(request) as response:
        payload = json.load(response)

    assert payload["project"]["name"] == "Renamed Project"
    assert payload["project"]["ui_port"] == 8878
    assert load_project(project.root).name == "Renamed Project"
    assert payload["project"]["config_dirty"] is True


def test_project_ui_rejects_invalid_configuration_without_overwriting(project_ui) -> None:
    url, token, project = project_ui
    original = project.descriptor.read_text(encoding="utf-8")
    request = Request(
        f"{url}/api/config",
        data=json.dumps({"content": "not valid TOML = ["}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="PUT",
    )

    with pytest.raises(HTTPError) as error:
        urlopen(request)

    assert error.value.code == 400
    assert project.descriptor.read_text(encoding="utf-8") == original


def test_project_ui_refuses_project_identity_change(project_ui) -> None:
    url, token, project = project_ui
    original = project.descriptor.read_text(encoding="utf-8")
    updated = original.replace('id = "sample-project"', 'id = "different-project"')
    request = Request(
        f"{url}/api/config",
        data=json.dumps({"content": updated}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="PUT",
    )

    with pytest.raises(HTTPError) as error:
        urlopen(request)

    assert error.value.code == 400
    assert project.descriptor.read_text(encoding="utf-8") == original


def test_project_ui_token_is_project_scoped_and_owner_only(project_ui, tmp_path: Path) -> None:
    _url, _token, project = project_ui
    token_files = list(tmp_path.glob("**/ui-token"))

    assert len(token_files) == 1
    assert project.id in token_files[0].parts
    assert token_files[0].stat().st_mode & 0o777 == 0o600
