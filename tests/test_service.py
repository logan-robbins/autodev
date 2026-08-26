from __future__ import annotations

import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from autodev import trace
from autodev.config import load_project
from autodev.service import _control_token, project_ui_handler
from autodev.state import project_paths
from autodev.trace import new_event


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


@pytest.fixture
def product_ui(product_tree: Path, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AUTODEV_HOME", str(tmp_path / "state"))
    project = load_project(product_tree)
    # Seed the live run that certified-l3-book points at (run_ref runs/book-7).
    run_dir = project_paths(project.id).runs / "book-7"
    trace.emit(
        run_dir,
        new_event(
            "run_started",
            run_id="book-7",
            role="engineering",
            node_ref={"level": "feature", "pillar": "replay-engine", "feature": "certified-l3-book"},
            goal="g",
        ),
    )
    trace.emit(
        run_dir,
        new_event(
            "step_declared",
            step_id="contract",
            parent=None,
            kind="contract",
            objective="publish",
            inputs=[],
            expects="",
            done_when="",
            agent="book",
        ),
    )
    trace.emit(
        run_dir, new_event("step_finished", step_id="contract", status="done", output_artifacts=["iface"], tokens=12)
    )
    trace.emit(
        run_dir,
        new_event(
            "step_declared",
            step_id="impl",
            parent=None,
            kind="implement",
            objective="build store",
            inputs=["iface"],
            expects="",
            done_when="",
            agent="book",
        ),
    )
    trace.emit(
        run_dir, new_event("step_started", step_id="impl", agent="book", agent_type="implement", provider="claude")
    )
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


def test_api_product_enumerates_pillars_and_features_with_phase(product_ui) -> None:
    url, _token, _project = product_ui
    with urlopen(f"{url}/api/product") as response:
        payload = json.load(response)

    assert [p["id"] for p in payload["pillars"]] == ["replay-engine"]
    features = {f["id"]: f for f in payload["pillars"][0]["features"]}
    assert features["certified-l3-book"]["phase"] == "engineering"  # derived from loop
    assert features["fast-ingest"]["phase"] == "project-manager"
    # loop strip data is present per feature.
    assert features["certified-l3-book"]["loop"][2] == {"role": "engineering", "s": "active"}


def test_api_feature_run_renders_dag_with_leaves_and_unmet_deps(product_ui) -> None:
    url, _token, _project = product_ui
    with urlopen(f"{url}/api/features/certified-l3-book/run") as response:
        payload = json.load(response)

    assert payload["phase"] == "engineering"
    node_ids = [n["step_id"] for n in payload["run"]["nodes"]]
    assert node_ids == ["contract", "impl"]  # topologically ordered
    assert payload["run"]["active_step_id"] == "impl"  # defaults to the running node
    edges = {tuple(edge) for edge in payload["run"]["edges"]}
    assert ("contract", "impl") in edges  # iface artifact resolves the edge
    # leaves + unmet depends_on readable.
    leaf_ids = {leaf["id"] for leaf in payload["leaves"]}
    assert leaf_ids == {"bucket", "store"}
    assert ["store", "bucket"] in payload["unmet_depends_on"]
    # per-node tokens + gloss field present.
    contract = next(n for n in payload["run"]["nodes"] if n["step_id"] == "contract")
    assert contract["tokens"] == 12
    assert "gloss" in contract


def test_api_feature_run_since_cursor_reports_unchanged(product_ui) -> None:
    url, _token, _project = product_ui
    with urlopen(f"{url}/api/features/certified-l3-book/run") as response:
        cursor = json.load(response)["cursor"]
    with urlopen(f"{url}/api/features/certified-l3-book/run?since={cursor}") as response:
        payload = json.load(response)
    assert payload == {"unchanged": True, "cursor": cursor}


def test_api_leaf_is_readable(product_ui) -> None:
    url, _token, _project = product_ui
    with urlopen(f"{url}/api/features/certified-l3-book/leaves/store") as response:
        leaf = json.load(response)
    assert leaf["id"] == "store"
    assert leaf["depends_on"] == ["bucket"]


def test_api_unknown_feature_is_404(product_ui) -> None:
    url, _token, _project = product_ui
    with pytest.raises(HTTPError) as error:
        urlopen(f"{url}/api/features/ghost/run")
    assert error.value.code == 404


def test_dashboard_is_light_product_tree_built_from_json(product_ui) -> None:
    url, _token, _project = product_ui
    with urlopen(f"{url}/") as response:
        page = response.read().decode()
    # light palette + product structure, built by globbing feature.json (no scraping).
    assert "#f6f7f9" in page
    assert "/api/product" in page
    assert "loopStrip" in page  # per-feature loop strip
    assert "drill(" in page and "/api/features/" in page  # drill to the run DAG
    assert "Product" in page
    # existing config editor stays.
    assert "Project configuration" in page
    assert '<textarea id="config"' in page


def test_project_ui_exposes_only_its_bound_project(project_ui) -> None:
    url, _token, _project = project_ui
    with urlopen(f"{url}/api/project") as response:
        payload = json.load(response)

    assert payload["id"] == "sample-project"
    assert payload["ui_port"] == 8765
    assert payload["bypass_permissions"] is False
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
    updated = (
        original.replace('name = "Sample Project"', 'name = "Renamed Project"')
        .replace("ui_port = 8765", "ui_port = 8878")
        .replace("bypass_permissions = false", "bypass_permissions = true")
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
    assert payload["project"]["bypass_permissions"] is True
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
