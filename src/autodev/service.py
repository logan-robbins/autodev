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
from urllib.parse import parse_qs, urlparse

from autodev.config import ConfigError, ProjectConfig, load_project
from autodev.integrate import integrate
from autodev.operations import ensure_agents, select_agents, statuses, stop_agents
from autodev.product import (
    ProductError,
    derive_phase,
    enumerate_tree,
    join_run,
    load_leaf,
)
from autodev.sessions import send_goal
from autodev.state import project_paths
from autodev.trace import read_events

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


def _product_payload(project: ProjectConfig) -> dict[str, Any]:
    """Enumerate the tree (glob feature.json), grouping by pillar with derived phase."""
    tree = enumerate_tree(project)
    pillars = []
    for pillar in tree.pillars:
        features = []
        for feature in pillar.features:
            phase, owner_role = derive_phase(feature)
            features.append({**feature, "phase": phase, "owner_role": owner_role})
        pillars.append({"id": pillar.id, "features": features})
    return {"pillars": pillars}


def _feature_run_payload(project: ProjectConfig, feature_id: str, since: int | None) -> dict[str, Any]:
    """The drill-down RunView for a feature, with a ?since cursor for live recolor."""
    feature = enumerate_tree(project).feature(feature_id)
    cursor = 0
    if feature["run_ref"]:
        events = read_events(project_paths(project.id).home / feature["run_ref"])
        cursor = max((int(event.get("seq", 0)) for event in events), default=0)
    if since is not None and since >= cursor:
        return {"unchanged": True, "cursor": cursor}
    payload = join_run(project, feature).as_dict()
    payload["cursor"] = cursor
    return payload


def _leaf_payload(project: ProjectConfig, feature_id: str, leaf_id: str) -> dict[str, Any]:
    return load_leaf(project, feature_id, f"leaves/{leaf_id}/leaf.json")


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


def _dashboard(project: ProjectConfig, token: str) -> str:
    safe_token = json.dumps(token)
    safe_title = json.dumps(project.name)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Autodev · {escape(project.name)}</title><style>
body{{font:15px system-ui,sans-serif;margin:0;background:#f6f7f9;color:#1c2530}}
main{{max-width:1100px;margin:36px auto;padding:0 24px}}h1{{font-size:30px;margin-bottom:4px}}
.panel{{background:#fff;border:1px solid #e2e6eb;border-radius:12px;padding:18px;margin:18px 0;box-shadow:0 1px 2px rgba(20,30,45,.04)}}
.card{{background:#fff;border:1px solid #e2e6eb;border-radius:10px;padding:12px 14px;margin:10px 0}}
.pillar h3{{margin:14px 0 6px;font-size:16px;color:#3a4653}}
.row{{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}}
.badge{{display:inline-block;padding:2px 10px;border-radius:999px;font-size:12px;text-transform:capitalize;background:#eef1f5;color:#3a4653;border:1px solid #dbe0e6}}
.badge.engineering{{background:#e7f0ff;color:#1d6fe0}}.badge.shipped{{background:#e6f6ec;color:#1a7f3c}}
.loop span{{font:13px ui-monospace,monospace;margin-right:8px;color:#5a6675}}
.loop .done{{color:#1a7f3c}}.loop .active{{color:#1d6fe0;font-weight:700}}.loop .blocked{{color:#c0392b}}
.metrics{{display:flex;gap:18px;flex-wrap:wrap;margin:6px 0 2px}}.metric{{background:#eef1f5;border-radius:8px;padding:8px 14px}}
.metric b{{font-size:20px;display:block}}.muted{{color:#6b7683;font-size:13px}}
.node{{border-left:3px solid #dbe0e6;padding:4px 10px;margin:4px 0}}.node.active{{border-color:#1d6fe0;background:#f2f7ff}}
.node.done,.node.green{{border-color:#1a7f3c}}.node.failed,.node.red{{border-color:#c0392b}}
button{{margin:2px 4px 2px 0;padding:6px 11px;border:1px solid #cdd4dc;border-radius:7px;background:#fff;cursor:pointer}}
button:hover{{background:#f0f3f7}}code{{color:#2b5b9c}}
textarea{{box-sizing:border-box;width:100%;min-height:360px;background:#fbfcfd;color:#1c2530;border:1px solid #cdd4dc;border-radius:8px;padding:14px;font:13px ui-monospace,monospace;line-height:1.45}}
#message{{min-height:22px}}.meta{{color:#6b7683}}.unmet{{color:#c0392b;font-size:13px}}
</style></head><body><main><h1 id="title"></h1><p class="meta" id="meta">Loading…</p>
<section class="panel"><h2>Product</h2><div class="metrics" id="metrics"></div><div id="product">Loading…</div></section>
<section class="panel"><h2>Agents</h2><div id="agents">Loading…</div></section>
<section class="panel"><h2>Project configuration</h2><p>Edit the canonical <code>autodev.toml</code>. Saves are validated and atomic; commit accepted changes in Git.</p>
<textarea id="config" spellcheck="false"></textarea><p><button onclick="saveConfig()">Validate and save</button></p><p id="message"></p></section>
</main><script>
const token={safe_token}; const initialTitle={safe_title};
const esc=value=>String(value).replace(/[&<>"']/g,char=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[char]));
const SHORT={{'product-manager':'PM','project-manager':'PjM','engineering':'Eng'}};
const GLYPH={{done:'\\u2713',active:'\\u25cf',pending:'\\u25cb',blocked:'\\u2715'}};
async function request(path, options={{}}){{
  const response=await fetch(path,options); const data=await response.json();
  if(!response.ok) throw new Error(data.error||`HTTP ${{response.status}}`); return data;
}}
function loopStrip(loop){{
  return `<span class="loop">${{loop.map(s=>`<span class="${{s.s}}">${{SHORT[s.role]||s.role}} ${{GLYPH[s.s]||''}}</span>`).join('')}}</span>`;
}}
async function drill(featureId){{
  const target=document.getElementById(`run-${{featureId}}`); target.textContent='Loading run…';
  try{{
    const v=await request(`/api/features/${{featureId}}/run`);
    const nodes=v.run?v.run.nodes.map(n=>`<div class="node ${{n.status}} ${{n.step_id===v.run.active_step_id?'active':''}}">`+
      `<b>${{esc(n.kind)}}</b> ${{esc(n.step_id)}} · ${{esc(n.status)}}`+
      `${{n.tokens!=null?` · ${{n.tokens}} tok`:''}}${{n.gloss?` — ${{esc(n.gloss)}}`:''}}</div>`).join(''):'<p class="muted">No run yet.</p>';
    const leaves=(v.leaves||[]).map(l=>`<li>${{esc(l.id)}} <span class="muted">(${{esc(l.status)}}${{l.pod?', '+esc(l.pod):''}})</span></li>`).join('');
    const unmet=(v.unmet_depends_on||[]).map(e=>`<div class="unmet">${{esc(e[0])}} blocked on ${{esc(e[1])}}</div>`).join('');
    target.innerHTML=`<div>${{nodes}}</div><h4>Leaves</h4><ul>${{leaves||'<li class="muted">none</li>'}}</ul>${{unmet}}`;
  }}catch(error){{target.textContent=error.message;}}
}}
async function loadProduct(){{
  const data=await request('/api/product');
  const counts={{}};
  data.pillars.forEach(p=>p.features.forEach(f=>{{counts[f.phase]=(counts[f.phase]||0)+1;}}));
  document.getElementById('metrics').innerHTML=Object.keys(counts).sort().map(k=>
    `<div class="metric"><b>${{counts[k]}}</b><span class="muted">${{esc(k)}}</span></div>`).join('')||'<span class="muted">No features yet.</span>';
  document.getElementById('product').innerHTML=data.pillars.map(p=>
    `<div class="pillar"><h3>${{esc(p.id)}}</h3>${{p.features.map(f=>
      `<div class="card"><div class="row"><div><b>${{esc(f.name)}}</b> `+
      `<span class="badge ${{f.phase}}">${{esc(f.phase)}}</span> ${{f.approval==='proposed'?'<span class="badge">proposed</span>':''}}</div>`+
      `<div>${{loopStrip(f.loop)}}<button onclick="drill('${{f.id}}')">Details</button></div></div>`+
      `<div id="run-${{f.id}}" class="muted"></div></div>`).join('')}}</div>`).join('')||'<p class="muted">No pillars yet.</p>';
}}
async function action(action, agent){{
  try{{await request(`/api/actions/${{action}}`,{{method:'POST',headers:{{'Authorization':`Bearer ${{token}}`,'Content-Type':'application/json'}},body:JSON.stringify({{agents:[agent],send_goal:true}})}});await loadAgents();}}
  catch(error){{document.getElementById('message').textContent=error.message;}}
}}
async function loadAgents(){{
  const p=await request('/api/project'); document.title=`Autodev · ${{p.name}}`; document.getElementById('title').textContent=p.name||initialTitle;
  document.getElementById('meta').textContent=`${{p.root}} · port ${{p.ui_port}} · config ${{p.config_dirty?'modified':'committed'}}`;
  document.getElementById('agents').innerHTML=`<table style="width:100%"><tbody>${{p.agents.map(a=>
    `<tr><td>${{esc(a.agent)}}</td><td>${{esc(a.provider)}}</td><td>${{a.running?'running':'offline'}}</td><td>${{a.ownership_violations.length?'VIOLATION':(a.git_status?'dirty':'clean')}}</td><td><button onclick="action('ensure','${{a.agent}}')">Launch</button><button onclick="action('goal','${{a.agent}}')">Goal</button><button onclick="action('stop','${{a.agent}}')">Stop</button></td></tr>`).join('')}}</tbody></table>`;
}}
async function loadConfig(){{const data=await request('/api/config');document.getElementById('config').value=data.content;}}
async function saveConfig(){{const message=document.getElementById('message');message.textContent='Validating…';try{{
  await request('/api/config',{{method:'PUT',headers:{{'Authorization':`Bearer ${{token}}`,'Content-Type':'application/json'}},body:JSON.stringify({{content:document.getElementById('config').value}})}});
  message.textContent='Saved. Commit autodev.toml in Git; restart this UI if ui_port changed.';await loadProduct();
}}catch(error){{message.textContent=error.message;}}}}
function refresh(){{loadProduct().catch(()=>{{}});loadAgents().catch(()=>{{}});}}
Promise.all([loadAgents(),loadProduct(),loadConfig()]).catch(error=>document.getElementById('message').textContent=error.message);setInterval(refresh,5000);
</script></body></html>"""


class ProjectUIHandler(BaseHTTPRequestHandler):
    descriptor: Path
    project_id: str
    token: str

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
        if length > MAX_BODY_BYTES:
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

    def _since(self) -> int | None:
        values = parse_qs(urlparse(self.path).query).get("since")
        if not values:
            return None
        try:
            return int(values[0])
        except ValueError:
            return None

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        segments = [segment for segment in path.split("/") if segment]
        try:
            project = self._project()
            if path == "/":
                body = _dashboard(project, self.token).encode()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
            elif path == "/api/project":
                self._json(HTTPStatus.OK, _project_payload(project))
            elif path == "/api/config":
                self._json(HTTPStatus.OK, _config_payload(project))
            elif path == "/api/product":
                self._json(HTTPStatus.OK, _product_payload(project))
            elif len(segments) == 4 and segments[:2] == ["api", "features"] and segments[3] == "run":
                self._json(HTTPStatus.OK, _feature_run_payload(project, segments[2], self._since()))
            elif len(segments) == 5 and segments[:2] == ["api", "features"] and segments[3] == "leaves":
                self._json(HTTPStatus.OK, _leaf_payload(project, segments[2], segments[4]))
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        except ProductError as exc:
            self._json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
        except (ConfigError, OSError, RuntimeError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

    def do_PUT(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if not self._authorized():
            return
        if urlparse(self.path).path.rstrip("/") != "/api/config":
            self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        try:
            content = self._body().get("content")
            if not isinstance(content, str):
                raise TypeError("content must be a TOML string")
            project = _save_config(self.descriptor, content, project_id=self.project_id)
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
            self._json(HTTPStatus.OK, {"result": result})
        except (ConfigError, RuntimeError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

    def log_message(self, message: str, *args: object) -> None:
        print(f"autodev ui: {self.address_string()} - {message % args}", flush=True)


def project_ui_handler(project: ProjectConfig, token: str) -> type[ProjectUIHandler]:
    return type(
        "BoundProjectUIHandler",
        (ProjectUIHandler,),
        {"descriptor": project.descriptor, "project_id": project.id, "token": token},
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
