"""Project-scoped localhost UI and control API."""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import tempfile
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from autodev.config import ConfigError, ProjectConfig, load_project
from autodev.fleet import FleetMonitor, agent_output
from autodev.integrate import integrate
from autodev.operations import ensure_agents, select_agents, statuses, stop_agents
from autodev.pillars import pillar_payload
from autodev.sessions import send_goal
from autodev.state import project_paths
from autodev.tasks import TaskStore

LOOPBACK_HOST = "127.0.0.1"
MAX_BODY_BYTES = 1_000_000


def _control_token(project: ProjectConfig, *, home: Path | None = None) -> str:
    path = project_paths(project.id, home=home).home / "ui-token"
    if path.exists():
        token = path.read_text(encoding="utf-8").strip()
        if not token:
            raise RuntimeError(f"Autodev UI token is empty: {path}")
        return token
    path.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    path.write_text(token + "\n", encoding="utf-8")
    path.chmod(0o600)
    return token


def _descriptor_dirty(project: ProjectConfig) -> bool:
    if project.execution != "git":
        return False
    result = subprocess.run(
        ["git", "status", "--porcelain", "--", project.descriptor.name],
        cwd=project.root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "cannot inspect project configuration status")
    return bool(result.stdout.strip())


def _project_payload(project: ProjectConfig) -> dict[str, Any]:
    return {
        "id": project.id,
        "name": project.name,
        "root": str(project.root),
        "descriptor": str(project.descriptor),
        "base_branch": project.base_branch,
        "execution": project.execution,
        "pillars": [pillar_payload(pillar) for pillar in project.pillars],
        "ui_port": project.ui_port,
        "session_pattern": project.session_pattern,
        "bypass_permissions": project.bypass_permissions,
        "config_dirty": _descriptor_dirty(project),
        "agents": [status.as_dict() for status in statuses(project, project.agents)],
    }


def _config_payload(project: ProjectConfig) -> dict[str, Any]:
    return {
        "content": project.descriptor.read_text(encoding="utf-8"),
        "dirty": _descriptor_dirty(project),
    }


def _save_config(descriptor: Path, content: str, *, project_id: str) -> ProjectConfig:
    if not content.strip():
        raise ConfigError("project configuration cannot be empty")
    mode = descriptor.stat().st_mode & 0o777
    handle, temp_name = tempfile.mkstemp(prefix=".autodev-", suffix=".toml", dir=descriptor.parent)
    candidate_path = Path(temp_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        candidate_path.chmod(mode)
        candidate = load_project(candidate_path)
        if candidate.id != project_id:
            raise ConfigError(f"project.id cannot be changed from {project_id!r} in its running project UI")
        candidate_path.replace(descriptor)
    finally:
        candidate_path.unlink(missing_ok=True)
    return load_project(descriptor)


def _save_pillar(project: ProjectConfig, slug: str, content: str) -> ProjectConfig:
    target = project.pillar(slug).descriptor
    load_project(project.descriptor, pillar_overrides={slug: content})
    handle, name = tempfile.mkstemp(prefix=".pillar-", suffix=".toml", dir=target.parent)
    temporary = Path(name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(target.stat().st_mode & 0o777)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return load_project(project.descriptor)


def _dashboard(project: ProjectConfig, token: str) -> str:
    template = (Path(__file__).parent / "web/index.html").read_text(encoding="utf-8")
    return template.replace("__PROJECT_TITLE__", escape(project.name)).replace(
        "__BOOTSTRAP__", json.dumps({"token": token, "name": project.name}).replace("<", "\\u003c")
    )


class ProjectUIHandler(BaseHTTPRequestHandler):
    descriptor: Path
    project_id: str
    token: str
    monitor: FleetMonitor

    def _project(self) -> ProjectConfig:
        project = load_project(self.descriptor)
        if project.id != self.project_id:
            raise ConfigError(f"running UI expected project.id {self.project_id!r}; found {project.id!r}")
        return project

    def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length < 0 or length > MAX_BODY_BYTES:
            raise ValueError("request body is too large")
        if not length:
            return {}
        value = json.loads(self.rfile.read(length))
        if not isinstance(value, dict):
            raise TypeError("request body must be a JSON object")
        return value

    def _authorized(self) -> bool:
        if self.headers.get("Authorization") == f"Bearer {self.token}":
            return True
        self._json(HTTPStatus.UNAUTHORIZED, {"error": "invalid project UI token"})
        return False

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = urlparse(self.path).path.rstrip("/") or "/"
        try:
            if path == "/api/fleet":
                if self._authorized():
                    self._json(HTTPStatus.OK, self.monitor.snapshot())
                return
            if path.startswith("/assets/"):
                assets = {"app.js": "text/javascript", "demo.js": "text/javascript", "style.css": "text/css"}
                name = path.removeprefix("/assets/")
                if name not in assets:
                    self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                    return
                body = (Path(__file__).parent / "web" / name).read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", assets[name])
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(body)
                return
            project = self._project()
            if path.startswith("/api/agents/") and path.endswith("/output"):
                if self._authorized():
                    self._json(HTTPStatus.OK, agent_output(project, path.split("/")[3]))
            elif path == "/":
                body = _dashboard(project, self.token).encode()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
            elif path == "/api/project":
                self._json(HTTPStatus.OK, _project_payload(project))
            elif path.startswith("/api/ledgers/"):
                actor = project.agent(path.split("/")[-1])
                self._json(HTTPStatus.OK, {"tasks": TaskStore(project, actor).list()})
            elif path == "/api/config":
                self._json(HTTPStatus.OK, _config_payload(project))
            elif path.startswith("/api/pillars/") and path.endswith("/config"):
                slug = path.split("/")[3]
                self._json(HTTPStatus.OK, {"content": project.pillar(slug).descriptor.read_text(encoding="utf-8")})
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        except (ConfigError, OSError, RuntimeError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

    def do_PUT(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if not self._authorized():
            return
        path = urlparse(self.path).path.rstrip("/")
        is_pillar = path.startswith("/api/pillars/") and path.endswith("/config") and len(path.split("/")) == 5
        if path != "/api/config" and not is_pillar:
            self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        try:
            content = self._body().get("content")
            if not isinstance(content, str):
                raise TypeError("content must be a TOML string")
            project = (
                _save_pillar(self._project(), path.split("/")[3], content)
                if is_pillar
                else _save_config(self.descriptor, content, project_id=self.project_id)
            )
            self.monitor.invalidate()
            self._json(HTTPStatus.OK, {"project": _project_payload(project)})
        except (ConfigError, OSError, RuntimeError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if not self._authorized():
            return
        parts = urlparse(self.path).path.rstrip("/").split("/")
        if len(parts) != 4 or parts[1:3] != ["api", "actions"]:
            self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        action = parts[3]
        try:
            body = self._body()
            raw_agents = body.get("agents", [])
            if not isinstance(raw_agents, list) or any(not isinstance(item, str) for item in raw_agents):
                raise TypeError("agents must be a list of agent IDs")
            project = self._project()
            agents = select_agents(project, raw_agents)
            if action == "ensure":
                result: object = ensure_agents(
                    project,
                    agents,
                    base_ref=None,
                    start=True,
                    send_initial_goal=bool(body.get("send_goal", True)),
                )
            elif action == "goal":
                result = [{"agent": agent.id, "goal_sent": bool(send_goal(project, agent))} for agent in agents]
            elif action == "stop":
                result = stop_agents(project, agents)
            elif action == "integrate":
                if len(agents) != 1:
                    raise ValueError("integrate requires exactly one agent")
                result = {"message": integrate(project, agents[0])}
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": f"unknown action: {action}"})
                return
            self.monitor.invalidate()
            self._json(HTTPStatus.OK, {"result": result})
        except (ConfigError, RuntimeError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

    def log_message(self, message: str, *args: object) -> None:
        print(f"autodev ui: {self.address_string()} - {message % args}", flush=True)


def project_ui_handler(project: ProjectConfig, token: str) -> type[ProjectUIHandler]:
    return type(
        "BoundProjectUIHandler",
        (ProjectUIHandler,),
        {
            "descriptor": project.descriptor,
            "project_id": project.id,
            "token": token,
            "monitor": FleetMonitor(project.descriptor, project.id),
        },
    )


def serve_project(project: ProjectConfig) -> None:
    token = _control_token(project)
    handler = project_ui_handler(project, token)
    try:
        server = ThreadingHTTPServer((LOOPBACK_HOST, project.ui_port), handler)
    except OSError as exc:
        raise RuntimeError(
            f"cannot start project UI for {project.id!r} on {LOOPBACK_HOST}:{project.ui_port}: {exc}"
        ) from exc
    server.daemon_threads = True
    print(f"Autodev UI for {project.name}: http://{LOOPBACK_HOST}:{project.ui_port}/", flush=True)
    print(f"Project UI token: {project_paths(project.id).home / 'ui-token'}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
