import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from autodev.config import ConfigError, load_project
from autodev.integrate import IntegrationError, integrate
from autodev.task_plans import import_plan
from autodev.tasks import TaskStore
from autodev.workspaces import ensure_workspace


def result(root: Path, slug: str = "backend"):
    target = root / slug / "output/worker/result.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {"status": "completed", "summary": "Completed research", "evidence": ["Verified sources"], "artifacts": []}
        )
    )
    return target


def setup_store(project):
    agent = project.agents[0]
    return agent, TaskStore(project, agent)


def task(store, agent, title="One", **kwargs):
    return store.create(agent, title, acceptance=("Deliver the declared outputs with evidence.",), **kwargs)


def add_manager(root):
    import shutil

    from autodev.pillars import TEMPLATE_ROOT

    shutil.copy2(TEMPLATE_ROOT / "schemas/task-plan.schema.json", root / "backend/schemas/task-plan.schema.json")
    path = root / "backend/pillar.toml"
    path.write_text(
        path.read_text()
        + '\n[[agents]]\nid = "manager"\ntemplate = "project-manager"\nprovider = "codex"\n\n[[agents]]\nid = "reviewer"\ntemplate = "researcher"\nprovider = "claude"\nread_roots = ["output/worker/"]\n'
    )
    return load_project(root)


def test_worker_reads_delivers_and_completes_own_ledger(file_project: Path):
    project = load_project(file_project)
    agent, store = setup_store(project)
    workspace = ensure_workspace(project, agent)
    assigned = task(store, agent, "Research a question")
    assert store.claim()["id"] == assigned["id"]
    result(workspace.path)
    completed = store.complete(assigned["id"])
    assert completed["status"] == "completed"
    assert completed["delivery"]["artifacts"][0]["path"] == str(file_project / "backend/output/worker/result.json")
    assert (file_project / "backend/tasks/worker/ledger.json").exists()
    assert not (file_project / ".git").exists()


def test_pm_tends_ledgers_workers_see_only_their_own(file_project: Path):
    project = add_manager(file_project)
    manager = TaskStore(project, project.agent("backend--manager"))
    worker = TaskStore(project, project.agent("backend--worker"))
    reviewer = TaskStore(project, project.agent("backend--reviewer"))
    first = task(manager, worker.actor, "Research")
    second = task(manager, reviewer.actor, "Review", dependencies=(first["id"],))
    assert len(manager.list()) == 2
    assert [t["id"] for t in worker.list()] == [first["id"]]
    assert [t["id"] for t in reviewer.list()] == [second["id"]]
    with pytest.raises(ConfigError, match="visible"):
        worker.get(second["id"])
    with pytest.raises(ConfigError, match="Project Manager"):
        task(worker, reviewer.actor)
    with pytest.raises(ConfigError, match="tends"):
        task(worker, worker.actor)
    with pytest.raises(ConfigError, match="own Pod"):
        task(manager, project.agent("frontend--worker"))


def test_dependencies_wait_for_worker_completion(file_project: Path):
    project = add_manager(file_project)
    manager = TaskStore(project, project.agent("backend--manager"))
    first = TaskStore(project, project.agent("backend--worker"))
    second = TaskStore(project, project.agent("backend--reviewer"))
    a = ensure_workspace(project, first.actor)
    b = ensure_workspace(project, second.actor)
    one = task(manager, first.actor)
    two = task(manager, second.actor, dependencies=(one["id"],))
    assert second.claim() is None
    first.claim()
    result(a.path)
    first.complete(one["id"])
    ensure_workspace(project, second.actor)
    assert (b.path / "backend/output/worker/result.json").exists()
    assert second.claim()["id"] == two["id"]


def test_claim_is_exclusive_under_concurrent_worker_reads(file_project: Path):
    project = load_project(file_project)
    agent, store = setup_store(project)
    task(store, agent, "One")
    task(store, agent, "Two")
    with ThreadPoolExecutor(max_workers=4) as pool:
        claims = list(pool.map(lambda _: TaskStore(project, agent).claim(), range(4)))
    assert len({t["id"] for t in claims}) == 1
    assert [t["status"] for t in store.list()].count("running") == 1


def test_failed_delivery_does_not_complete_the_ledger(file_project: Path):
    project = load_project(file_project)
    agent, store = setup_store(project)
    workspace = ensure_workspace(project, agent)
    assigned = task(store, agent)
    store.claim()
    result(workspace.path)
    (workspace.path / "README.md").write_text("changed")
    with pytest.raises(ConfigError, match="ownership"):
        store.complete(assigned["id"])
    assert store.get(assigned["id"])["status"] == "running"


def test_worker_reports_block_pm_revises(file_project: Path):
    project = add_manager(file_project)
    manager = TaskStore(project, project.agent("backend--manager"))
    worker = TaskStore(project, project.agent("backend--worker"))
    assigned = task(manager, worker.actor)
    worker.claim()
    worker.block(assigned["id"], "Need a source document.")
    assert manager.get(assigned["id"])["reason"] == "Need a source document."
    manager.revise(assigned["id"], instructions="Use the new source.", acceptance=("Cite the source.",))
    assert worker.claim()["instructions"] == "Use the new source."


def test_publication_conflict_preserves_published_output(file_project: Path):
    project = load_project(file_project)
    agent = project.agents[0]
    workspace = ensure_workspace(project, agent)
    result(workspace.path)
    target = result(file_project)
    target.write_text("concurrent update")
    with pytest.raises(IntegrationError, match="conflict"):
        integrate(project, agent)
    assert target.read_text() == "concurrent update"


def test_consumer_check_failure_blocks_publication(file_project: Path):
    project = load_project(file_project)
    agent = project.agents[0]
    workspace = ensure_workspace(project, agent)
    result(workspace.path)
    (file_project / "frontend/interface.py").write_text("raise SystemExit(8)\n")
    with pytest.raises(ConfigError, match="check failed"):
        integrate(load_project(file_project), agent)
    assert not (file_project / "backend/output/worker/result.json").exists()


def plan_file(root: Path, tasks: list[dict]) -> Path:
    path = root / "plan.json"
    path.write_text(json.dumps({"status": "planned", "summary": "Parallel work", "tasks": tasks}))
    return path


def entry(key, agent="backend--worker", dependencies=()):
    return {
        "key": key,
        "title": key,
        "agent": agent,
        "instructions": "Produce the declared deliverables.",
        "acceptance": ["All contract checks pass."],
        "dependencies": list(dependencies),
    }


def test_pm_imports_plan_into_individual_ledgers_idempotently(file_project: Path):
    project = add_manager(file_project)
    actor = project.agent("backend--manager")
    path = plan_file(file_project, [entry("consume", "backend--reviewer", ["produce"]), entry("produce")])
    imported = import_plan(project, actor, path)
    assert imported[0]["plan_key"] == "produce"
    assert imported[1]["dependencies"] == [imported[0]["id"]]
    assert {t["id"] for t in import_plan(project, actor, path)} == {t["id"] for t in imported}
    worker = TaskStore(project, project.agent("backend--worker"))
    assert len(worker.list()) == 1
    assert (file_project / "backend/tasks/reviewer/ledger.json").exists()


@pytest.mark.parametrize(
    "tasks",
    [
        [entry("a", dependencies=["b"]), entry("b", dependencies=["a"])],
        [entry("a", dependencies=["missing"])],
        [entry("a"), entry("a")],
        [entry("a", agent="frontend--worker")],
    ],
)
def test_invalid_plan_creates_no_tasks(file_project: Path, tasks):
    project = add_manager(file_project)
    actor = project.agent("backend--manager")
    with pytest.raises(ConfigError):
        import_plan(project, actor, plan_file(file_project, tasks))
    assert TaskStore(project, actor).list() == []


def test_validation_allows_pod_reads_and_preserves_new_assignments(file_project: Path, monkeypatch):
    from autodev.contracts import verify_agent

    project = add_manager(file_project)
    manager = TaskStore(project, project.agent("backend--manager"))
    worker = TaskStore(project, project.agent("backend--worker"))
    workspace = ensure_workspace(project, worker.actor)
    assigned = task(manager, worker.actor)
    worker.claim()
    result(workspace.path)
    with ThreadPoolExecutor(max_workers=1) as pool:

        def during_validation(project, agent, root):
            assert pool.submit(manager.list).result(timeout=3)[0]["status"] == "running"
            pool.submit(task, manager, worker.actor, "Next assignment").result(timeout=3)
            return verify_agent(project, agent, root)

        monkeypatch.setattr("autodev.tasks.verify_agent", during_validation)
        worker.complete(assigned["id"])
    assert [t["status"] for t in worker.list()] == ["completed", "queued"]


@pytest.mark.parametrize("data", [[], {"schema_version": 1, "agent": "backend--worker", "tasks": [{}]}])
def test_malformed_ledger_has_actionable_error(file_project: Path, data):
    project = load_project(file_project)
    agent, store = setup_store(project)
    path = file_project / "backend/tasks/worker/ledger.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(data))
    with pytest.raises(ConfigError, match="ledger"):
        store.list()


def test_git_worker_completes_without_committing_ledger(project_repo: Path):
    import subprocess

    project = load_project(project_repo)
    agent, store = setup_store(project)
    workspace = ensure_workspace(project, agent)
    assigned = task(store, agent)
    store.claim()
    result(workspace.path)
    subprocess.run(["git", "add", "backend/output/worker/result.json"], cwd=workspace.path, check=True)
    subprocess.run(["git", "commit", "-m", "Deliver result"], cwd=workspace.path, check=True, capture_output=True)
    assert store.complete(assigned["id"])["status"] == "completed"
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=project_repo, text=True)
    assert status == ""
    assert (project_repo / "backend/tasks/worker/ledger.json").exists()


def test_progress_and_completion_record_observable_execution_stages(file_project: Path, monkeypatch):
    from autodev.contracts import verify_agent
    from autodev.integrate import integrate

    project = load_project(file_project)
    agent, store = setup_store(project)
    workspace = ensure_workspace(project, agent)
    assigned = task(store, agent)
    store.claim()
    store.progress(assigned["id"], "Writing the result envelope.")
    result(workspace.path)

    def validate(project, agent, root):
        assert store.get(assigned["id"])["stage"] == "validating"
        return verify_agent(project, agent, root)

    def publish(project, agent):
        assert store.get(assigned["id"])["stage"] == "publishing"
        return integrate(project, agent)

    monkeypatch.setattr("autodev.tasks.verify_agent", validate)
    monkeypatch.setattr("autodev.integrate.integrate", publish)
    completed = store.complete(assigned["id"])
    assert [e["stage"] for e in completed["events"]] == [
        "queued",
        "working",
        "working",
        "validating",
        "publishing",
        "completed",
    ]
    assert completed["stage"] == "completed"


def test_failed_validation_resets_visible_stage_and_records_reason(file_project: Path):
    project = load_project(file_project)
    agent, store = setup_store(project)
    ensure_workspace(project, agent)
    assigned = task(store, agent)
    store.claim()
    with pytest.raises(ConfigError):
        store.complete(assigned["id"])
    failed = store.get(assigned["id"])
    assert failed["status"] == "running"
    assert failed["stage"] == "working"
    assert failed["progress"].startswith("Completion failed:")
