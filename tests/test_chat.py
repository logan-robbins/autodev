import fcntl
import json
from unittest.mock import Mock

import pytest
from test_tasks import add_manager

from autodev.chat import ChatStore, agent_configuration, check_actor, edit_agent
from autodev.config import ConfigError, load_project
from autodev.storage import atomic_json
from autodev.tasks import TaskStore
from autodev.workspaces import changed_paths, ensure_workspace


@pytest.fixture
def chat_project(file_project, monkeypatch):
    monkeypatch.setattr("autodev.chat.session_exists", lambda name: False)
    return add_manager(file_project)


def sent(project, allow=True):
    store = ChatStore(project, "backend")
    store.add("message-1", "Update worker instructions as requested.", allow)
    data = store._read()
    data["messages"][0]["status"] = "sent"
    atomic_json(store.path, data)
    return store


def test_chat_routes_only_to_pillar_manager_and_is_idempotent(chat_project):
    p = chat_project
    store = ChatStore(p, "backend")
    first = store.add("one", "Question?")
    assert store.add("one", "Question?") == first
    assert len(ChatStore(p, "backend").snapshot()["messages"]) == 1
    with pytest.raises(ConfigError, match="different content"):
        store.add("one", "Other question?")
    with pytest.raises(ConfigError, match="General Manager"):
        check_actor(p, p.agent("backend--worker"))
    with pytest.raises(ConfigError, match="no General Manager"):
        ChatStore(p, "frontend")
    assert store.path.stat().st_mode & 0o777 == 0o600


def test_delivery_waits_for_active_task_and_serializes_conversation(chat_project, monkeypatch):
    p = chat_project
    gm = p.agent("backend--manager")
    store = ChatStore(p, "backend")
    store.add("one", "First question")
    store.add("two", "Second question")
    tasks = TaskStore(p, gm)
    t = tasks.create(gm, "Coordinate", acceptance=("Coordinate work",))
    tasks.claim()
    launcher = Mock(return_value=True)
    monkeypatch.setattr("autodev.chat.start_session", launcher)
    store.deliver()
    launcher.assert_not_called()
    tasks.block(t["id"], "Fixture pause")
    store.deliver()
    assert launcher.call_count == 1
    assert launcher.call_args.kwargs["initial_prompt"].endswith("First question\n")
    store.deliver()
    assert launcher.call_count == 1
    store.reply("one", "First answer")
    store.deliver()
    assert launcher.call_count == 2
    assert [m["status"] for m in store.snapshot()["messages"]] == ["answered", "sent"]
    with pytest.raises(ConfigError, match="immutable"):
        store.reply("one", "Changed answer")


def test_actor_bindings_and_cross_pillar_edits_are_rejected(chat_project, monkeypatch):
    p = chat_project
    gm = p.agent("backend--manager")
    with pytest.raises(ConfigError, match="other agents"):
        agent_configuration(p, gm, "frontend--worker")
    with pytest.raises(ConfigError, match="other agents"):
        agent_configuration(p, gm, gm.id)
    monkeypatch.setenv("AUTODEV_AGENT_ID", "backend--worker")
    with pytest.raises(ConfigError, match="another actor"):
        check_actor(p, gm)
    monkeypatch.setenv("AUTODEV_AGENT_ID", gm.id)
    monkeypatch.setenv("AUTODEV_PROJECT_DESCRIPTOR", "/tmp/another-project.toml")
    with pytest.raises(ConfigError, match="another workspace"):
        check_actor(p, gm)


def test_workspace_preparation_does_not_hold_chat_lock(chat_project, monkeypatch):
    store = ChatStore(chat_project, "backend")
    store.add("one", "Question")

    def prepare(project, actor):
        # Fail immediately rather than hanging if delivery inverts the edit lock order.
        with store.lock.open("a") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        return ensure_workspace(project, actor)

    monkeypatch.setattr("autodev.chat.ensure_workspace", prepare)
    monkeypatch.setattr("autodev.chat.start_session", Mock(return_value=True))
    store.deliver()
    assert store.snapshot()["messages"][0]["status"] == "sent"


def test_requested_edit_preserves_individual_contracts_and_has_receipt(chat_project):
    p = chat_project
    gm = p.agent("backend--manager")
    store = sent(p)
    old = agent_configuration(p, gm, "backend--worker")
    other = p.agent("backend--reviewer").instructions
    patch = {"instructions": "A uniquely updated worker prompt."}
    receipt = edit_agent(p, gm, "backend--worker", "message-1", old["digest"], patch)
    updated = load_project(p.root)
    assert updated.agent("backend--worker").instructions == patch["instructions"]
    assert updated.agent("backend--reviewer").instructions == other
    assert updated.agent("backend--worker").deliverables == p.agent("backend--worker").deliverables
    assert receipt["before"]["instructions"] == old["instructions"]
    assert len(store.snapshot()["messages"][0]["changes"]) == 1
    assert edit_agent(p, gm, "backend--worker", "message-1", old["digest"], patch) == receipt
    assert len(store.snapshot()["messages"][0]["changes"]) == 1


def test_edits_require_permission_valid_contract_and_no_pending_tasks(chat_project):
    p = chat_project
    gm = p.agent("backend--manager")
    store = sent(p, False)
    old = agent_configuration(p, gm, "backend--worker")
    descriptor = p.pillar("backend").descriptor
    original = descriptor.read_bytes()
    with pytest.raises(ConfigError, match="does not permit"):
        edit_agent(p, gm, "backend--worker", "message-1", old["digest"], {"goal": "Changed"})
    data = store._read()
    data["messages"][0]["allowAgentEdits"] = True
    atomic_json(store.path, data)
    with pytest.raises(ConfigError):
        edit_agent(p, gm, "backend--worker", "message-1", old["digest"], {"write_roots": ["../frontend/"]})
    assert descriptor.read_bytes() == original
    with pytest.raises(ConfigError, match="contract changed"):
        edit_agent(p, gm, "backend--worker", "message-1", "stale", {"goal": "Changed"})
    TaskStore(p, gm).create(p.agent("backend--worker"), "Pending work", acceptance=("Do work",))
    with pytest.raises(ConfigError, match="Finish existing"):
        edit_agent(p, gm, "backend--worker", "message-1", old["digest"], {"goal": "Changed"})
    assert descriptor.read_bytes() == original


def test_identity_persists_without_replacing_authored_guidance(chat_project):
    p = chat_project
    (p.root / "AGENTS.md").write_text("Project-specific guidance.\n")
    gm = p.agent("backend--manager")
    worker = p.agent("backend--worker")
    a = ensure_workspace(p, gm)
    b = ensure_workspace(p, worker)
    text = (a.path / "AGENTS.md").read_text()
    assert gm.id in text and gm.pillar in text and "autodev-gm/SKILL.md" in text
    assert "Project-specific guidance." in text
    assert "autodev-gm/SKILL.md" not in (b.path / "AGENTS.md").read_text()
    assert (a.path / "CLAUDE.md").is_file()
    assert not changed_paths(a)
    ensure_workspace(p, gm)
    assert (a.path / "AGENTS.md").read_text() == text
    assert (p.root / "AGENTS.md").read_text() == "Project-specific guidance.\n"
    (a.path / "AGENTS.md").write_text("Tampered identity")
    assert "AGENTS.md" in changed_paths(a)
    ensure_workspace(p, gm)
    assert (a.path / "AGENTS.md").read_text() == "Tampered identity"  # preserve dirty work, never hide it


def test_http_chat_is_authenticated_and_persists_only_gm_messages(chat_project):
    import threading
    from http.server import ThreadingHTTPServer
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen

    from autodev.service import project_ui_handler

    server = ThreadingHTTPServer(("127.0.0.1", 0), project_ui_handler(chat_project, "test-token"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}/api/pillars/backend/chat"
    try:
        with pytest.raises(HTTPError) as error:
            urlopen(url)
        assert error.value.code == 401
        req = Request(
            url,
            data=json.dumps({"id": "browser-message", "text": "What is happening?"}).encode(),
            headers={"Authorization": "Bearer test-token", "Content-Type": "application/json"},
        )
        with urlopen(req) as response:
            assert response.status == 202
        with urlopen(Request(url, headers={"Authorization": "Bearer test-token"})) as response:
            value = json.load(response)
        assert value["manager"] == "backend--manager"
        assert value["messages"][0]["text"] == "What is happening?"
        assert value["messages"][0]["allowAgentEdits"] is False
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_native_fake_harness_receives_chat_and_publishes_reply(file_project, tmp_path, monkeypatch):
    import shutil
    import sys
    import time

    from autodev.sessions import stop_session

    if not shutil.which("tmux"):
        pytest.skip("tmux unavailable")
    p = add_manager(file_project)
    executable = tmp_path / "fake-chat-codex"
    executable.write_text(f"""#!{sys.executable}
import os,re,sys,tempfile,subprocess,time
prompt=sys.argv[-1]
identity=re.search(r"Current operator message ID: (.+)",prompt)[1]
time.sleep(1)
with tempfile.NamedTemporaryFile(mode="w",suffix=".txt") as f:
 f.write("Native fixture reply: "+os.environ["AUTODEV_AGENT_ID"]); f.flush()
 subprocess.run([sys.executable,"-m","autodev","chat","reply",os.environ["AUTODEV_PROJECT_DESCRIPTOR"],identity,"--text-file",f.name],check=True)
time.sleep(30)
""")
    executable.chmod(0o700)
    text = p.descriptor.read_text() + f"\n[providers.codex]\ncommand = {json.dumps(str(executable))}\n"
    p.descriptor.write_text(text)
    p = load_project(p.root)
    store = ChatStore(p, "backend")
    store.add("native-transport", "Fixture conversation only")
    try:
        store.deliver()
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and store.snapshot()["messages"][0]["status"] != "answered":
            time.sleep(0.1)
        message = store.snapshot()["messages"][0]
        assert message["status"] == "answered", message
        assert message["reply"]["text"] == "Native fixture reply: backend--manager"
        assert TaskStore(p, p.agent("backend--manager")).list() == []
    finally:
        stop_session(p, p.agent("backend--manager"))
