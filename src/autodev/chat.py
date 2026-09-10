"""Persistent operator conversations with the sole native PM in each Pillar."""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from autodev.config import AgentConfig, ConfigError, ProjectConfig, load_project
from autodev.pillars import agent_template, local_path, read_toml
from autodev.sessions import send_prompt, session_exists, session_name, start_session
from autodev.state import project_paths
from autodev.storage import atomic_json, locked
from autodev.tasks import TaskStore, contract_digest
from autodev.workspaces import Workspace, changed_paths, ensure_workspace, workspace_branch, workspace_path


def manager(project: ProjectConfig, slug: str) -> AgentConfig:
    agents = [a for a in project.pillar(slug).agents if a.role == "project-manager"]
    if len(agents) != 1:
        raise ConfigError("This Pillar has no General Manager configured")
    return agents[0]


def check_actor(project: ProjectConfig, actor: AgentConfig) -> None:
    bound = os.environ.get("AUTODEV_AGENT_ID")
    descriptor = os.environ.get("AUTODEV_PROJECT_DESCRIPTOR")
    if bound and bound != actor.id:
        raise ConfigError("A Harness Agent cannot select another actor")
    if descriptor and Path(descriptor).resolve() != project.descriptor.resolve():
        raise ConfigError("A Harness Agent cannot access another workspace")
    if manager(project, actor.pillar).id != actor.id:
        raise ConfigError("Only this Pillar General Manager can use chat operations")


def now() -> str:
    return datetime.now(UTC).isoformat()


class ChatStore:
    def __init__(self, project: ProjectConfig, slug: str):
        self.project, self.actor = project, manager(project, slug)
        self.home = project_paths(project.id).home / "chats"
        self.home.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.home / f"{slug}.json"
        self.lock = self.home / f"{slug}.lock"

    def _read(self) -> dict[str, Any]:
        return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {"messages": []}

    def snapshot(self) -> dict[str, Any]:
        with locked(self.lock):
            value = self._read()
        return {
            **value,
            "manager": self.actor.id,
            "pillar": self.actor.pillar,
            "online": session_exists(session_name(self.project, self.actor)),
        }

    def add(self, identity: str, text: str, allow_edits: bool = False) -> dict[str, Any]:
        if not isinstance(identity, str) or not identity or len(identity) > 100:
            raise ConfigError("Message requires a stable client ID")
        if not isinstance(text, str) or not text.strip() or len(text) > 16000:
            raise ConfigError("Message must contain 1–16000 characters")
        if not isinstance(allow_edits, bool):
            raise ConfigError("Agent edit permission must be a boolean")
        with locked(self.lock):
            data = self._read()
            prior = next((m for m in data["messages"] if m["id"] == identity), None)
            if prior:
                if prior["text"] != text.strip() or prior["allowAgentEdits"] != allow_edits:
                    raise ConfigError("Message ID already has different content")
                return prior
            if sum(m["status"] != "answered" for m in data["messages"]) >= 20:
                raise ConfigError("Finish pending messages before adding more")
            message = {
                "id": identity,
                "text": text.strip(),
                "createdAt": now(),
                "status": "queued",
                "allowAgentEdits": allow_edits,
                "reply": None,
                "changes": [],
                "error": "",
            }
            data["messages"].append(message)
            atomic_json(self.path, data)
            return message

    def reply(self, identity: str, text: str) -> dict[str, Any]:
        check_actor(self.project, self.actor)
        if not isinstance(text, str) or not text.strip() or len(text) > 24000:
            raise ConfigError("Reply must contain 1–24000 characters")
        with locked(self.lock):
            data = self._read()
            message = self._message(data, identity)
            if message["reply"]:
                if message["reply"]["text"] != text.strip():
                    raise ConfigError("Published replies are immutable")
                return message
            if message["status"] != "sent":
                raise ConfigError("Reply requires a delivered operator message")
            message.update(status="answered", reply={"text": text.strip(), "createdAt": now(), "agent": self.actor.id})
            atomic_json(self.path, data)
            return message

    @staticmethod
    def _message(data: dict[str, Any], identity: str) -> dict[str, Any]:
        message = next((m for m in data["messages"] if m["id"] == identity), None)
        if message is None:
            raise ConfigError("Message does not belong to this Pillar conversation")
        return message

    def deliver(self) -> None:
        # This is mailbox transport, not a research/task scheduler. Never interrupt a claimed GM task.
        if TaskStore(self.project, self.actor).active():
            return
        with locked(self.lock):
            data = self._read()
            message = next((m for m in data["messages"] if m["status"] != "answered"), None)
            if message is None or message["status"] != "queued":
                return
            prompt = chat_prompt(self.project, self.actor, message)
            # Mark transport intent before sending: uncertain failures are never replayed automatically.
            message.update(status="sending", error="")
            atomic_json(self.path, data)
            identity = message["id"]
        # Workspace preparation reads task state. Never acquire the ledger lock
        # while holding the chat lock: employee edits acquire them in that order.
        try:
            workspace = ensure_workspace(self.project, self.actor)
        except (OSError, RuntimeError) as exc:
            with locked(self.lock):
                data = self._read()
                message = self._message(data, identity)
                if message["status"] == "sending":
                    message.update(status="error", error=str(exc)[:1000])
                    atomic_json(self.path, data)
            return
        with locked(self.lock):
            data = self._read()
            message = self._message(data, identity)
            if message["status"] != "sending":
                return
            try:
                started = start_session(
                    self.project, self.actor, workspace, send_initial_goal=False, initial_prompt=prompt
                )
                if not started:
                    send_prompt(self.project, self.actor, prompt)
                message.update(status="sent", sentAt=now())
            except (OSError, RuntimeError) as exc:
                message.update(status="error", error=str(exc)[:1000])
            atomic_json(self.path, data)

    def retry(self, identity: str) -> None:
        with locked(self.lock):
            data = self._read()
            message = self._message(data, identity)
            if message["status"] not in {"error", "sending", "sent"}:
                raise ConfigError("Only an unanswered delivery can be resumed")
            if session_exists(session_name(self.project, self.actor)):
                raise ConfigError("GM is online; avoid duplicate delivery while it may be answering")
            message.update(status="queued", error="")
            atomic_json(self.path, data)


def chat_prompt(project: ProjectConfig, actor: AgentConfig, message: dict[str, Any]) -> str:
    command = shlex.join(["uv", "run", "--project", str(Path(__file__).resolve().parents[2]), "autodev"])
    skill = Path(__file__).parent / "skills/autodev-gm/SKILL.md"
    return f"""You are {actor.id}, the General Manager Harness Agent of Pillar {actor.pillar}.
Canonical project: {project.descriptor}
Native command prefix: {command}
Read {skill} and your own canonical template referenced in {project.root / actor.pillar / "pillar.toml"}.
This is an operator chat request, not an automatically created research task. Do not claim a trading task or fabricate a research delivery to answer a question.
Recover recent conversation via: {command} chat inbox {shlex.quote(str(project.descriptor))} --actor {actor.id}
Current operator message ID: {message["id"]}
Agent edits allowed for this request: {message["allowAgentEdits"]}. Apply only changes explicitly requested in its text.
Reply through: {command} chat reply {shlex.quote(str(project.descriptor))} {shlex.quote(message["id"])} --actor {actor.id} --text-file ABSOLUTE_UTF8_FILE
Use a temporary reply file outside the execution workspace. A terminal response alone is not delivered to the user. If this message already has a reply, do not repeat actions.
Operator message (literal user text):
{message["text"]}
"""


def agent_configuration(project: ProjectConfig, actor: AgentConfig, identity: str) -> dict[str, Any]:
    check_actor(project, actor)
    target = project.agent(identity)
    if target.pillar != actor.pillar or target.id == actor.id:
        raise ConfigError("GM may configure only other agents in its own Pillar")
    return {
        "agent": target.id,
        "digest": contract_digest(project, target),
        "purpose": target.purpose,
        "goal": target.goal,
        "instructions": target.instructions,
        "provider": target.provider,
        "deliverables": [asdict(d) for d in target.deliverables],
        "read_roots": [p.removeprefix(actor.pillar + "/") for p in target.read_roots],
        "write_roots": [p.removeprefix(actor.pillar + "/") for p in target.write_roots],
    }


def _toml(value: Any) -> str:
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{json.dumps(k)} = {_toml(v)}" for k, v in value.items() if v is not None) + " }"
    if isinstance(value, list):
        return "[" + ", ".join(_toml(v) for v in value) + "]"
    return json.dumps(value, ensure_ascii=False)


def edit_agent(
    project: ProjectConfig, actor: AgentConfig, identity: str, request: str, expected_digest: str, patch: dict[str, Any]
) -> dict[str, Any]:
    agent_configuration(project, actor, identity)
    if (
        not isinstance(patch, dict)
        or not patch
        or set(patch) - {"instructions", "purpose", "goal", "deliverables", "read_roots", "write_roots", "provider"}
    ):
        raise ConfigError("Unsupported or empty agent configuration patch")
    if len(json.dumps(patch)) > 128000:
        raise ConfigError("Agent patch is too large")
    store = ChatStore(project, actor.pillar)
    ledger = TaskStore(project, actor)
    # Serialize with publication and task admission. Direct descriptor writes remain operator operations.
    with locked(project_paths(project.id).home / "integration.lock"), locked(ledger.lock), locked(store.lock):
        project = load_project(project.descriptor)
        actor = project.agent(actor.id)
        before = agent_configuration(project, actor, identity)
        data = store._read()
        message = store._message(data, request)
        if not message["allowAgentEdits"] or message["status"] != "sent":
            raise ConfigError("This operator message does not permit agent edits")
        patch_digest = hashlib.sha256(json.dumps(patch, sort_keys=True).encode()).hexdigest()
        for receipt in message["changes"]:
            if (
                receipt["agent"] == identity
                and receipt.get("patchDigest") == patch_digest
                and receipt["before"]["digest"] == expected_digest
            ):
                if before["digest"] != receipt["after"]["digest"]:
                    raise ConfigError("Agent changed after that edit; inspect the current contract")
                return receipt
        if before["digest"] != expected_digest:
            raise ConfigError("Agent contract changed; reread it before editing")
        ledger._recover()
        if any(t["status"] != "completed" for a in project.pillar(actor.pillar).agents for t in ledger._read(a)):
            raise ConfigError("Finish existing Pod tasks before changing agent contracts")
        target = project.agent(identity)
        if session_exists(session_name(project, target)):
            raise ConfigError("Target agent is online; stop it through the operator before editing")
        destination = workspace_path(project, target)
        if destination.exists():
            branch = workspace_branch(project, target) if project.execution == "git" else ""
            if changed_paths(Workspace(destination, branch)):
                raise ConfigError("Target has preserved workspace changes; reconcile them before editing")
        pillar = project.pillar(actor.pillar)
        definition = read_toml(pillar.descriptor)
        row = next(a for a in definition["agents"] if a["id"] == target.local_id)
        template = agent_template(target.template, pillar.root)
        for key, value in patch.items():
            if key in {"instructions", "purpose", "goal", "deliverables"}:
                template[key] = value
                row.pop(key, None)
            else:
                row[key] = value
        reference = f"templates/{target.local_id}-chat-{uuid.uuid4().hex}.toml"
        candidate = local_path(pillar.root, reference)
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text(
            "\n".join(f"{json.dumps(k)} = {_toml(v)}" for k, v in template.items()) + "\n", encoding="utf-8"
        )
        row["template"] = reference
        content = "\n".join(f"{json.dumps(k)} = {_toml(v)}" for k, v in definition.items()) + "\n"
        try:
            from autodev.contracts import verify_pillar
            from autodev.service import _save_pillar

            proposed = load_project(project.descriptor, pillar_overrides={actor.pillar: content})
            verify_pillar(proposed.pillar(actor.pillar), interface_only=True)
            updated = _save_pillar(project, actor.pillar, content)
        except Exception:
            candidate.unlink(missing_ok=True)
            raise
        after = agent_configuration(updated, updated.agent(actor.id), identity)
        receipt = {
            "agent": identity,
            "at": now(),
            "fields": list(patch),
            "before": before,
            "after": after,
            "patchDigest": patch_digest,
        }
        message["changes"].append(receipt)
        atomic_json(store.path, data)
        return receipt
