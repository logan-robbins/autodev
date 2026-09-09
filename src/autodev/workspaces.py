"""Create isolated sparse Git worktrees for configured agents."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from autodev.config import AgentConfig, ProjectConfig
from autodev.state import project_paths
from autodev.storage import atomic_json

AUTOMATIC_CONTEXT = (
    ".agents/skills/",
    ".claude/",
    ".codex/",
    ".gitignore",
    "AGENTS.md",
    "AGENTS.override.md",
    "CLAUDE.md",
    "README.md",
    "autodev.toml",
)


class WorkspaceError(RuntimeError):
    """Raised when an isolated Git worktree cannot be prepared safely."""


@dataclass(frozen=True)
class Workspace:
    path: Path
    branch: str


def workspace_branch(project: ProjectConfig, agent: AgentConfig) -> str:
    return f"autodev/{project.id}/{agent.id}"


def workspace_path(project: ProjectConfig, agent: AgentConfig, *, home: Path | None = None) -> Path:
    return project_paths(project.id, home=home).worktrees / agent.id


def sparse_paths(project: ProjectConfig, agent: AgentConfig) -> tuple[str, ...]:
    contracts = tuple(
        path
        for pillar in project.pillars
        for path in (
            f"{pillar.slug}/pillar.toml",
            f"{pillar.slug}/schemas/",
            f"{pillar.slug}/fixtures/",
            f"{pillar.slug}/templates/",
            f"{pillar.slug}/interface.py",
        )
    )
    dependencies = tuple(
        f"{slug}/{output.path}"
        for slug in project.pillar(agent.pillar).dependencies
        for output in project.pillar(slug).outputs
    )
    references = tuple(
        f"{pillar.slug}/{path}"
        for pillar in project.pillars
        for spec in (*pillar.inputs, *pillar.outputs, *(d for a in pillar.agents for d in a.deliverables))
        for path in (spec.schema, spec.fixture)
        if path
    )
    template_paths = tuple(
        f"{pillar.slug}/{a.template}"
        for pillar in project.pillars
        for a in pillar.agents
        if "/" in a.template or a.template.endswith(".toml")
    )
    return tuple(
        dict.fromkeys(
            (
                *AUTOMATIC_CONTEXT,
                *project.context_roots,
                *agent.read_roots,
                *agent.write_roots,
                *contracts,
                *dependencies,
                *references,
                *template_paths,
            )
        )
    )


def _git(
    cwd: Path,
    *args: str,
    input_text: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "no output"
        raise WorkspaceError(f"git {' '.join(args)} failed in {cwd}: {detail}")
    return result


def _validate_existing(path: Path, branch: str) -> None:
    if not (path / ".git").is_file():
        raise WorkspaceError(f"{path} exists but is not an Autodev Git worktree")
    actual = _git(path, "branch", "--show-current").stdout.strip()
    if actual != branch:
        raise WorkspaceError(f"{path} is on branch {actual!r}; expected {branch!r}")


def contract_files(project: ProjectConfig) -> tuple[str, ...]:
    """Authored configuration and referenced interface assets, never task ledgers."""
    paths = {project.descriptor}
    for pillar in project.pillars:
        paths.add(pillar.descriptor)
        stub = pillar.root / "interface.py"
        if stub.is_file():
            paths.add(stub)
        for agent in pillar.agents:
            if "/" in agent.template or agent.template.endswith(".toml"):
                paths.add(pillar.root / agent.template)
        for spec in (*pillar.inputs, *pillar.outputs, *(d for a in pillar.agents for d in a.deliverables)):
            for reference in (spec.schema, spec.fixture):
                if reference:
                    path = pillar.root / reference
                    paths.update(p for p in path.rglob("*") if p.is_file()) if path.is_dir() else paths.add(path)
    return tuple(sorted(path.relative_to(project.root).as_posix() for path in paths))


def validate_committed_contracts(project: ProjectConfig, ref: str) -> None:
    for name in contract_files(project):
        actual = _git(project.root, "hash-object", "--", name).stdout.strip()
        committed = _git(project.root, "rev-parse", "--verify", f"{ref}:{name}", check=False)
        if committed.returncode or committed.stdout.strip() != actual:
            raise WorkspaceError(f"commit current contract {name} on {ref} before preparing Git workspaces")


def ensure_workspace(
    project: ProjectConfig,
    agent: AgentConfig,
    *,
    base_ref: str | None = None,
    home: Path | None = None,
) -> Workspace:
    if project.execution == "filesystem":
        if base_ref is not None:
            raise WorkspaceError("--base-ref requires project.execution = git")
        return ensure_file_workspace(project, agent, home=home)
    branch = workspace_branch(project, agent)
    destination = workspace_path(project, agent, home=home)
    ref = base_ref or project.base_branch
    _git(project.root, "rev-parse", "--verify", f"{ref}^{{commit}}")
    validate_committed_contracts(project, ref)

    if destination.exists():
        _validate_existing(destination, branch)
        from autodev.tasks import TaskStore

        if not TaskStore(project, agent).active() and not _git(destination, "status", "--porcelain").stdout.strip():
            _git(destination, "merge", "--ff-only", project.base_branch)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        branch_exists = (
            _git(
                project.root,
                "show-ref",
                "--verify",
                "--quiet",
                f"refs/heads/{branch}",
                check=False,
            ).returncode
            == 0
        )
        if branch_exists:
            _git(project.root, "worktree", "add", "--no-checkout", str(destination), branch)
        else:
            _git(
                project.root,
                "worktree",
                "add",
                "--no-checkout",
                "-b",
                branch,
                str(destination),
                ref,
            )

    patterns = "\n".join(sparse_paths(project, agent)) + "\n"
    _git(destination, "sparse-checkout", "init", "--no-cone")
    _git(destination, "sparse-checkout", "set", "--no-cone", "--stdin", input_text=patterns)
    _git(destination, "checkout", branch)
    return Workspace(path=destination, branch=branch)


def git_status(workspace: Workspace) -> str:
    if not workspace.branch:
        return "\n".join(changed_paths(workspace))
    return _git(workspace.path, "status", "--short").stdout.rstrip()


def changed_paths(workspace: Workspace) -> tuple[str, ...]:
    if not workspace.branch:
        baseline = json.loads(snapshot_path(workspace).read_text(encoding="utf-8"))["files"]
        current = file_manifest(workspace.path)
        return tuple(sorted(name for name in set(baseline) | set(current) if baseline.get(name) != current.get(name)))
    result = _git(workspace.path, "status", "--porcelain", "-z").stdout
    paths: list[str] = []
    entries = result.split("\0")
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if not entry:
            continue
        status = entry[:2]
        path = entry[3:]
        if (status[0] in {"R", "C"} or status[1] in {"R", "C"}) and index < len(entries) and entries[index]:
            paths.append(entries[index])
            index += 1
        paths.append(path)
    return tuple(paths)


def path_is_owned(path: str, agent: AgentConfig) -> bool:
    candidate = path.rstrip("/")
    return any(
        candidate == root.rstrip("/") or candidate.startswith(root.rstrip("/") + "/") for root in agent.write_roots
    )


def ownership_violations(workspace: Workspace, agent: AgentConfig) -> tuple[str, ...]:
    return tuple(path for path in changed_paths(workspace) if not path_is_owned(path, agent))


def snapshot_path(workspace: Workspace) -> Path:
    return workspace.path.parent / f".{workspace.path.name}.snapshot.json"


def file_manifest(root: Path) -> dict[str, str]:
    from autodev.pillars import EXCLUDED_DIRECTORIES

    result = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        parent = Path(directory)
        excluded = set(EXCLUDED_DIRECTORIES)
        if parent.parent == root:
            excluded.update({"memory", "tasks"})
        links = [name for name in dirs if (parent / name).is_symlink()]
        dirs[:] = sorted(d for d in dirs if d not in excluded and d not in links)
        for name in sorted([*files, *links]):
            path = parent / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                result[relative] = "symlink:" + os.readlink(path)
            else:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                result[relative] = f"{path.stat().st_mode & 0o777:o}:{digest}"
    return result


def copy_workspace(source: Path, target: Path) -> None:
    from autodev.pillars import EXCLUDED_DIRECTORIES

    def ignore(directory: str, names: list[str]) -> set[str]:
        excluded = set(EXCLUDED_DIRECTORIES)
        if Path(directory).parent == source:
            excluded.update({"memory", "tasks"})
        return set(names) & excluded

    shutil.copytree(source, target, symlinks=True, ignore=ignore, dirs_exist_ok=True)


def copy_agent_workspace(project: ProjectConfig, agent: AgentConfig, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for relative in sparse_paths(project, agent):
        source = project.root / relative.rstrip("/")
        destination = target / relative.rstrip("/")
        if source.is_dir():
            copy_workspace(source, destination)
        elif source.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination, follow_symlinks=False)


def ensure_file_workspace(project: ProjectConfig, agent: AgentConfig, *, home: Path | None = None) -> Workspace:
    destination = workspace_path(project, agent, home=home)
    if destination.resolve().is_relative_to(project.root):
        raise WorkspaceError("AUTODEV_HOME must be outside the managed workspace")
    workspace = Workspace(destination, "")
    metadata = snapshot_path(workspace)
    if destination.exists():
        if not metadata.is_file():
            raise WorkspaceError(f"existing workspace has no snapshot: {destination}")
        data = json.loads(metadata.read_text(encoding="utf-8"))
        if data.get("project_root") != str(project.root) or data.get("agent") != agent.id:
            raise WorkspaceError("workspace snapshot belongs to a different project or Harness Agent")
        from autodev.tasks import TaskStore

        if not TaskStore(project, agent).active() and file_manifest(destination) == data["files"]:
            with tempfile.TemporaryDirectory(prefix="refresh-", dir=destination.parent) as directory:
                selected = Path(directory) / "selected"
                copy_agent_workspace(project, agent, selected)
                refreshed = file_manifest(selected)
                for name in set(data["files"]) - set(refreshed):
                    (destination / name).unlink()
                copy_workspace(selected, destination)
            data["files"] = file_manifest(destination)
            atomic_json(metadata, data)
        return workspace
    try:
        copy_agent_workspace(project, agent, destination)
        atomic_json(
            metadata, {"project_root": str(project.root), "agent": agent.id, "files": file_manifest(destination)}
        )
    except Exception:
        if destination.exists():
            shutil.rmtree(destination)
        raise
    return workspace
