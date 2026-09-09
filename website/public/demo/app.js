"use strict";
const boot = JSON.parse(document.getElementById("bootstrap").textContent);
const $ = (id) => document.getElementById(id);
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const icons = {
  grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  board:
    '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16M15 4v16M5.5 8h1M11.5 8h1M17.5 8h1M5.5 12h1M11.5 12h1"/>',
  agents:
    '<circle cx="9" cy="8" r="3"/><path d="M3 20v-3a6 6 0 0112 0v3M16 5a3 3 0 010 6M18 14a5 5 0 013 4v2"/>',
  activity: '<path d="M2 12h5l3-8 4 16 3-8h5"/>',
  settings:
    '<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3" fill="currentColor"/><circle cx="16" cy="17" r="3" fill="currentColor"/>',
  refresh:
    '<path d="M20 8a8 8 0 00-14-3L3 8m0-5v5h5M4 16a8 8 0 0014 3l3-3m0 5v-5h-5"/>',
  search: '<circle cx="10" cy="10" r="6.5"/><path d="m15 15 5 5"/>',
  arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
  graph:
    '<rect x="9" y="2" width="6" height="5" rx="1"/><rect x="2" y="17" width="6" height="5" rx="1"/><rect x="16" y="17" width="6" height="5" rx="1"/><path d="M12 7v5M5 17v-5h14v5"/>',
  play: '<path d="m8 4 12 8-12 8Z"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  alert: '<path d="m12 3 10 18H2Z"/><path d="M12 9v5m0 3v1"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>',
  terminal:
    '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m6 9 3 3-3 3m6 0h5"/>',
  file: '<path d="M14 2H5v20h14V7Zm0 0v6h5M8 12h8M8 16h6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  minus: '<path d="M5 12h14"/>',
  stop: '<rect x="5" y="5" width="14" height="14" rx="2"/>',
  inbox: '<path d="M4 4h16l2 11v5H2v-5Zm-2 11h6l2 3h4l2-3h6"/>',
  link: '<path d="m10 13 4-4M8 16l-1 1a4 4 0 01-6-6l5-5a4 4 0 016 0m0 2 1-1a4 4 0 016 6l-5 5a4 4 0 01-6 0" transform="translate(2 0)"/>',
};
const icon = (name) =>
  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.grid}</svg>`;
document
  .querySelectorAll("[data-icon]")
  .forEach((el) => (el.innerHTML = icon(el.dataset.icon)));
const colors = [
  "#9eb8ff",
  "#c1a4f8",
  "#8be1c2",
  "#efbd80",
  "#ed9fae",
  "#9dcddb",
  "#c4cf87",
  "#ada6e5",
];
let liveData = null,
  data = null,
  demo = false,
  demoData = null,
  fetching = false,
  lastSuccess = 0,
  dataSignature = "";
let query = "",
  filter = "all",
  zoom = 1,
  boardLimit = 20,
  renderedRoute = "",
  selected = null,
  drawerSignature = "",
  toastTimer;
const displayName = (value) =>
  String(value)
    .split("-")
    .filter(Boolean)
    .map((s) => s[0].toUpperCase() + s.slice(1))
    .join(" ");
const initials = (value) =>
  String(value)
    .split(/[-\s]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((v) => v[0].toUpperCase())
    .join("");
const age = (timestamp) => {
  if (!timestamp) return "Not reported";
  const n = Math.max(0, (Date.now() - Date.parse(timestamp)) / 1000);
  return n < 60
    ? "just now"
    : n < 3600
      ? `${Math.floor(n / 60)}m ago`
      : n < 86400
        ? `${Math.floor(n / 3600)}h ago`
        : `${Math.floor(n / 86400)}d ago`;
};
const badge = (status, label = status) =>
  `<span class="badge ${esc(status)}"><span class="dot"></span>${esc(label)}</span>`;
const avatar = (a) =>
  `<span class="avatar ${a.role === "project-manager" ? "manager" : ""} ${a.running ? "online" : ""}" title="${esc(a.id)}">${esc(initials(a.local_id))}</span>`;
const allAgents = () => data.pillars.flatMap((p) => p.agents);
const allTasks = () => data.pillars.flatMap((p) => p.tasks);
const findAgent = (id) => allAgents().find((a) => a.id === id);
const findTask = (id) => allTasks().find((t) => t.id === id);
const phase = (t) => (t.status === "running" ? t.stage || "working" : t.status);
const currentTask = (a) => findTask(a.current_task);
const currentText = (a) => {
  const t = currentTask(a);
  return t
    ? t.progress || t.title
    : a.counts.blocked
      ? "Waiting for a blocker to be resolved"
      : a.counts.ready
        ? "Ready for the next assignment"
        : a.counts.waiting
          ? "Waiting for a dependency"
          : "No active assignment";
};
const onlineColor = (a) =>
  a.status === "working"
    ? "green"
    : ["blocked", "interrupted"].includes(a.status)
      ? "amber"
      : a.running
        ? "blue"
        : "muted";
function route() {
  const [path, search = ""] = location.hash.slice(1).split("?");
  return {
    parts: (path || "overview").split("/"),
    params: new URLSearchParams(search),
  };
}
function openDetails(agent, task = null) {
  const base = location.hash.split("?")[0] || "#overview";
  location.hash =
    base +
    `?agent=${encodeURIComponent(agent)}${task ? `&task=${encodeURIComponent(task)}` : ""}`;
}
function closeDetails() {
  location.hash = location.hash.split("?")[0] || "#overview";
}
function toast(message) {
  clearTimeout(toastTimer);
  $("toast").textContent = message;
  $("toast").hidden = false;
  toastTimer = setTimeout(() => ($("toast").hidden = true), 4500);
}
async function request(path, options = {}) {
  const res = await fetch(path, {
    signal: AbortSignal.timeout(
      path.startsWith("/api/actions/") ? 120000 : 10000,
    ),
    ...options,
    headers: { Authorization: `Bearer ${boot.token}`, ...options.headers },
  });
  const value = await res.json();
  if (!res.ok) throw new Error(value.error || `Request failed (${res.status})`);
  return value;
}
function empty(title, body, symbol = "inbox") {
  return `<div class="empty">${icon(symbol)}<strong>${esc(title)}</strong>${esc(body)}</div>`;
}
function section(title, subtitle = "", right = "") {
  return `<div class="section-heading"><div><h2>${title}</h2>${subtitle ? `<p>${subtitle}</p>` : ""}</div>${right}</div>`;
}
function distribution(c) {
  return `<div class="distribution" aria-label="${c.completed} completed, ${c.running} running, ${c.blocked} blocked, ${c.ready + c.waiting} queued">${[
    ["completed", c.completed],
    ["running", c.running],
    ["blocked", c.blocked],
    ["queued", c.ready + c.waiting],
  ]
    .filter((x) => x[1])
    .map(([s, n]) => `<span class="${s}" style="flex:${n}"></span>`)
    .join("")}</div>`;
}
function filters(placeholder = "Search Pillars…", statusOptions = true) {
  return `<div class="tools"><label class="search">${icon("search")}<input id="search" aria-label="${esc(placeholder.replace("…", ""))}" placeholder="${esc(placeholder)}" value="${esc(query)}"></label>${
    statusOptions
      ? `<select id="filter" aria-label="Filter status">${[
          ["all", "All statuses"],
          ["active", "Active"],
          ["attention", "Needs attention"],
          ["ready", "Ready"],
          ["offline", "Offline"],
        ]
          .map(
            ([v, l]) =>
              `<option value="${v}" ${filter === v ? "selected" : ""}>${l}</option>`,
          )
          .join("")}</select>`
      : ""
  }</div>`;
}
function matches(text) {
  return text.toLowerCase().includes(query.toLowerCase());
}
function eventsPanel(events, limit = 6) {
  return events.length
    ? events
        .slice(0, limit)
        .map(
          (e) =>
            `<button class="event-row" data-task="${esc(e.task)}" data-agent="${esc(e.agent)}" style="width:100%;text-align:left;background:none;border-left:0;border-right:0;border-top:0;color:inherit"><span class="event-dot ${e.stage === "completed" ? "green" : e.stage === "blocked" ? "amber" : "blue"}"><span class="dot"></span></span><span class="event-copy"><strong>${esc(e.message)}</strong><p>${esc(e.agent)} · ${esc(e.title)}</p></span><time title="${esc(e.at)}">${age(e.at)}</time></button>`,
        )
        .join("")
    : empty(
        "Activity appears as work happens",
        "Task claims, progress, blockers, and deliveries will appear here.",
        "activity",
      );
}
function overview() {
  const pillars = data.pillars.filter(
    (p) =>
      matches(p.slug + " " + p.summary) &&
      (filter === "all" || p.status === filter),
  );
  return `<div class="page-heading"><div><h1>Your Pillars <span class="count">${data.pillars.length}</span></h1><p class="subtitle">Choose a Pillar to see its Harness Agents and their work.</p></div>${filters()}</div><div class="pillar-grid">${pillars.map(pillarCard).join("")}</div>${!pillars.length ? empty(data.pillars.length ? "No matching Pillars" : "Create your first Pillar", data.pillars.length ? "Try a different search or status." : "Add a Pillar with its contract and at least one Harness Agent.") : ""}`;
}
function pillarCard(p) {
  const active =
    p.tasks.find(
      (t) =>
        t.status === "running" &&
        p.agents.find((a) => a.id === t.agent)?.role !== "project-manager",
    ) || p.tasks.find((t) => t.status === "running");
  return `<a href="#pillar/${p.slug}/graph" class="pillar-card" aria-label="Open ${esc(displayName(p.slug))} Pillar"><div class="pillar-card-body"><div class="card-top"><span class="pillar-symbol" style="--pillar-color:${colors[data.pillars.indexOf(p) % colors.length]}">${icon(p.slug.includes("research") ? "search" : p.slug.includes("infra") ? "terminal" : "grid")}</span><h3>${esc(displayName(p.slug))}</h3>${badge(p.status)}</div><p class="card-summary">${esc(p.summary)}</p><div class="card-metrics"><div><strong>${p.counts.open}</strong><span>Open tasks</span></div><div><strong class="green">${p.counts.running}</strong><span>In progress</span></div><div><strong class="${p.counts.blocked ? "amber" : ""}">${p.counts.blocked}</strong><span>Blocked</span></div></div>${distribution(p.counts)}<div class="card-activity"><span class="dot ${active ? "green" : "muted"}"></span><span>${esc(active ? active.title : p.counts.ready ? `${p.counts.ready} tasks ready to be claimed` : p.counts.completed ? `${p.counts.completed} tasks delivered` : "Awaiting assignments")}</span></div></div><div class="card-bottom"><div class="avatars">${p.agents.slice(0, 4).map(avatar).join("")}</div><span>${p.agents.length} agents · ${p.online} online</span><span class="arrow">${icon("arrow")}</span></div></a>`;
}
function board(tasks, compact = false) {
  const selectedTasks = tasks.filter((t) =>
    matches(t.title + " " + t.agent + " " + (t.progress || "")),
  );
  const cols = [
    ["queued", "Queued", "muted"],
    ["working", "Working", "green"],
    ["validating", "Validating", "blue"],
    ["blocked", "Blocked", "amber"],
    ["completed", "Delivered", "green"],
  ];
  const column = (t) =>
    t.status === "running"
      ? ["validating", "publishing"].includes(t.stage)
        ? "validating"
        : "working"
      : t.status;
  return `<div class="board-wrap"><div class="board">${cols
    .map(([key, label, color]) => {
      const items = selectedTasks
        .filter((t) => column(t) === key)
        .sort((a, b) =>
          String(b.updated_at || b.created_at).localeCompare(
            a.updated_at || a.created_at,
          ),
        );
      return `<section class="column"><div class="column-head"><span class="dot ${color}"></span>${label}<span class="number">${items.length}</span></div>${
        items
          .slice(0, compact ? 5 : boardLimit)
          .map(taskCard)
          .join("") || '<div class="column-empty">No tasks here</div>'
      }${items.length > (compact ? 5 : boardLimit) ? (compact ? `<div class="column-empty">+${items.length - 5} more in task board</div>` : `<button class="load-more" data-more>Show more (${items.length - boardLimit} remaining)</button>`) : ""}</section>`;
    })
    .join("")}</div></div>`;
}
function taskCard(t) {
  const a = findAgent(t.agent);
  return `<button class="task-card" data-task="${esc(t.id)}" data-agent="${esc(t.agent)}"><div class="task-card-top"><span>${esc(displayName(t.pillar))}</span><span>${esc(t.id.slice(-6).toUpperCase())}</span></div><h3>${esc(t.title)}</h3>${t.dependencies.length ? `<div class="dependency-label">${icon("link")}${t.status === "queued" && !t.ready ? "Waiting on" : "Depends on"} ${t.dependencies.length} task${t.dependencies.length === 1 ? "" : "s"}</div>` : ""}<p class="task-progress">${esc(t.reason || t.progress || (t.status === "queued" ? (t.ready ? "Ready to be claimed" : "Waiting for dependencies") : "No step reported yet"))}</p>${t.stage === "publishing" ? badge("publishing", "Publishing") : ""}${a?.status === "interrupted" && t.status === "running" ? badge("interrupted", "Session offline") : ""}<div class="task-card-bottom">${a ? avatar(a) : ""}<span>${esc(a?.local_id || t.agent)}</span><span class="time">${age(t.updated_at || t.created_at)}</span></div></button>`;
}
function boardPage() {
  return `<div class="page-heading"><div><div class="eyebrow">Work in motion</div><h1>Task board</h1><p class="subtitle">Assignments move when Harness Agents update their own ledgers.</p></div><span class="badge">${allTasks().length} tasks · ${data.counts.open} open</span></div>${section("Across all Pillars", "Queued tasks include ready assignments and tasks waiting on dependencies.", filters("Search tasks or agents…", false))}${board(allTasks())}`;
}
function agentTable(agents) {
  const list = agents.filter((a) =>
    matches(a.id + " " + a.template + " " + currentText(a)),
  );
  return `<div class="panel table-wrap"><table class="agent-table"><thead><tr><th>Harness Agent</th><th>Status</th><th>Current work</th><th>Open</th><th>Delivered</th><th>Harness</th></tr></thead><tbody>${list.map((a) => `<tr tabindex="0" role="button" aria-label="Inspect ${esc(a.id)}" data-agent="${esc(a.id)}"><td><div class="agent-identity">${avatar(a)}<span><strong>${esc(displayName(a.local_id))}</strong><small>${esc(a.pillar)} · ${esc(a.role === "project-manager" ? "Project Manager" : a.template)}</small></span></div></td><td>${badge(a.status)}</td><td><div class="current-work">${esc(currentTask(a)?.title || currentText(a))}</div></td><td class="numeric">${a.counts.open}</td><td class="numeric">${a.counts.completed}</td><td class="muted">${a.provider === "claude" ? "Claude Code" : "Codex"}</td></tr>`).join("")}</tbody></table>${!list.length ? empty("No matching agents", "Try a different search.") : ""}</div>`;
}
function agentsPage() {
  return `<div class="page-heading"><div><div class="eyebrow">Native harness fleet</div><h1>Harness Agents</h1><p class="subtitle">Current assignments, individual workloads, and observed session state.</p></div><span class="badge active">${data.counts.online} / ${data.counts.agents} online</span></div>${section("Your fleet", "Select an agent to inspect its execution flow and task ledger.", filters("Search agents…", false))}${agentTable(allAgents())}`;
}
function graph(p) {
  const managers = p.agents.filter((a) => a.role === "project-manager"),
    workers = p.agents.filter((a) => a.role !== "project-manager");
  const cols = Math.min(3, Math.max(1, workers.length));
  const width = Math.max(700, cols * 240 + 40),
    positions = new Map();
  managers.forEach((a, i) =>
    positions.set(a.id, { x: width / 2 - 101 + i * 220, y: 35 }),
  );
  workers.forEach((a, i) =>
    positions.set(a.id, {
      x: 40 + (i % cols) * 240,
      y: (managers.length ? 210 : 45) + Math.floor(i / cols) * 185,
    }),
  );
  const height = Math.max(
    410,
    (managers.length ? 210 : 45) + Math.ceil(workers.length / cols) * 185,
  );
  let edges = "";
  if (managers.length) {
    const m = positions.get(managers[0].id);
    workers.forEach((a) => {
      const pos = positions.get(a.id);
      edges += `<path class="membership" d="M${m.x + 101} ${m.y + 112} C${m.x + 101} ${m.y + 163},${pos.x + 101} ${pos.y - 40},${pos.x + 101} ${pos.y}"/>`;
    });
  }
  const links = new Map();
  p.tasks.forEach((t) =>
    t.dependencies.forEach((d) => {
      const from = p.tasks.find((x) => x.id === d);
      if (from && from.agent !== t.agent) {
        const key = from.agent + ">" + t.agent;
        const old = links.get(key);
        links.set(key, {
          from: from.agent,
          to: t.agent,
          ready: old?.ready || from.status === "completed",
          active:
            old?.active ||
            (from.status === "completed" && t.status === "running"),
          count: (old?.count || 0) + 1,
        });
      }
    }),
  );
  links.forEach((l) => {
    const a = positions.get(l.from),
      b = positions.get(l.to);
    if (!a || !b) return;
    const sameRow = Math.abs(a.y - b.y) < 10;
    const ax = sameRow ? a.x + 202 : a.x + 162,
      ay = a.y + (sameRow ? 55 : 111),
      bx = sameRow ? b.x : b.x + 40,
      by = b.y + (sameRow ? 55 : 0);
    edges += `<path class="handoff ${l.ready ? (l.active ? "flowing" : "") : "pending"}" marker-end="url(#arrowhead)" d="M${ax} ${ay} C${ax + (sameRow ? 35 : 0)} ${ay + (sameRow ? 0 : 45)},${bx - (sameRow ? 35 : 0)} ${by - (sameRow ? 0 : 45)},${bx} ${by}"><title>${esc(l.from)} → ${esc(l.to)} · ${l.count} task dependencies</title></path>`;
  });
  return `<section class="panel graph-panel"><div class="panel-head"><div><h2>Agent graph</h2><p>${p.agents.length} Harness Agents · ${links.size} handoff connections</p></div><div class="graph-toolbar"><span id="zoom-value">${Math.round(zoom * 100)}%</span><button class="icon-button" data-zoom="out" aria-label="Zoom out">${icon("minus")}</button><button class="icon-button" data-zoom="in" aria-label="Zoom in">${icon("plus")}</button><button class="button" data-zoom="fit">Fit</button></div></div><div class="graph-viewport" id="graph-viewport"><div style="width:${width * zoom}px;height:${height * zoom}px"><div class="graph-canvas" style="width:${width}px;height:${height}px;transform:scale(${zoom})"><svg class="graph-edges" viewBox="0 0 ${width} ${height}" aria-label="Pillar assignment and handoff connections"><defs><marker id="arrowhead" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 0 10 5 0 10z" fill="#6cbaa2"/></marker></defs>${edges}</svg>${p.agents
    .map((a) => {
      const pos = positions.get(a.id),
        t =
          currentTask(a) ||
          p.tasks.find(
            (task) => task.agent === a.id && task.status === "blocked",
          );
      return `<button class="agent-node ${a.status} ${a.role === "project-manager" ? "manager" : ""}" style="left:${pos.x}px;top:${pos.y}px" data-agent="${esc(a.id)}" aria-label="Inspect ${esc(a.id)}"><div class="node-top">${avatar(a)}<strong>${esc(displayName(a.local_id))}</strong><span class="dot ${onlineColor(a)}"></span></div><div class="node-task">${esc(t?.title || (a.role === "project-manager" ? "Project Manager · Coordination" : currentText(a)))}</div><div class="node-bottom"><span>${a.counts.open} open · ${a.counts.completed} done</span><span class="stage">${esc(t ? phase(t) : a.status)}</span></div></button>`;
    })
    .join(
      "",
    )}</div></div></div><div class="graph-legend"><span><i class="legend-line"></i>PM assignment scope</span><span><i class="legend-line handoff"></i>Task dependency / handoff</span><span><span class="dot green"></span> Working</span><span><span class="dot amber"></span> Needs attention</span></div></section>`;
}
function pillarPage(slug, tab = "graph") {
  const p = data.pillars.find((p) => p.slug === slug);
  if (!p)
    return empty(
      "Pillar not found",
      "Return to All Pillars to select a current Pillar.",
    );
  const tabs = [
    ["graph", "graph", "Agent graph"],
    ["board", "board", "Task board"],
    ["agents", "agents", "Agent list"],
    ["contract", "file", "Contract"],
  ];
  return `<div class="page-heading"><div><div class="pillar-title"><span class="pillar-symbol" style="--pillar-color:${colors[data.pillars.indexOf(p) % colors.length]}">${icon("grid")}</span><div><h1>${esc(displayName(p.slug))}</h1><p class="subtitle">${esc(p.summary)}</p></div></div><div class="pillar-meta">${badge(p.status)}<span>${p.online} / ${p.agents.length} Harness Agents online</span><span>${p.counts.open} open tasks</span></div></div></div><nav class="tabs" aria-label="Pillar views">${tabs.map(([key, i, label]) => `<a class="tab ${key === tab ? "selected" : ""}" href="#pillar/${p.slug}/${key}" ${key === tab ? 'aria-current="page"' : ""}>${icon(i)}${label}</a>`).join("")}</nav>${p.error ? `<div class="alert-note">Ledger unavailable: ${esc(p.error)}. Counts are incomplete.</div>` : ""}${tab === "graph" ? graph(p) : tab === "board" ? section("Task board", "", filters("Search tasks or agents…", false)) + board(p.tasks) : tab === "agents" ? section("Harness Agents", "", filters("Search agents…", false)) + agentTable(p.agents) : contract(p)}`;
}
function contract(p) {
  return `<div class="contract-grid"><section class="panel"><div class="panel-body"><div class="small-label">Responsibility</div><h3>${esc(displayName(p.slug))}</h3><p>${esc(p.responsibility)}</p><div class="divider"></div><div class="small-label">How to consume</div><p>${esc(p.consumption)}</p><div class="divider"></div><div class="small-label">Constraints</div><p>${esc(p.constraints)}</p></div></section><section class="panel"><div class="panel-body"><div class="small-label">Public interface</div>${badge("ready", p.interface_state)}<code class="file-path">${esc(p.slug)}/pillar.toml</code><div class="divider"></div><div class="small-label">Declared outputs</div>${p.outputs.map((o) => `<p>${esc(o.description)}</p><code class="file-path">${esc(p.slug + "/" + o.path)} · ${esc(o.format)}</code>`).join("")}<div class="divider"></div><div class="small-label">Consumes</div>${p.dependencies.map((d) => `<a class="task-link" href="#pillar/${d}/contract">${icon("link")}${esc(displayName(d))}${icon("arrow")}</a>`).join("") || "<p>No peer dependencies declared.</p>"}</div></section></div>`;
}
function activityPage() {
  const list = data.events.filter((e) =>
    matches(e.message + " " + e.title + " " + e.agent),
  );
  return `<div class="page-heading"><div><div class="eyebrow">Observed task events</div><h1>Activity</h1><p class="subtitle">A timestamped trail of claims, work steps, checks, and deliveries.</p></div></div>${section("Latest events", "Most recent 100 events across your workspace.", filters("Search activity…", false))}<section class="panel">${eventsPanel(list, 100)}</section>`;
}
function settingsPage() {
  return `<div class="page-heading"><div><div class="eyebrow">Canonical contracts</div><h1>Project configuration</h1><p class="subtitle">Edit the workspace or a Pillar contract. Changes are validated before saving.</p></div></div><div class="panel config-panel"><div class="panel-body"><label for="config-path">Configuration</label><select id="config-path"><option value="/api/config">autodev.toml</option>${data.pillars.map((p) => `<option value="/api/pillars/${p.slug}/config">${p.slug}/pillar.toml</option>`).join("")}</select><textarea id="config" aria-label="Configuration content" spellcheck="false" placeholder="Loading configuration…" ${demo ? "disabled" : ""}></textarea><div class="config-actions"><button class="button primary" id="save-config" ${demo ? "disabled" : ""}>${icon("check")}Validate and save</button><span id="config-message">${demo ? "Configuration editing is disabled in the demonstration." : "Changes to contracts affect future task execution."}</span></div></div></div>`;
}
async function loadConfig() {
  if (demo) return;
  try {
    const value = await request($("config-path").value);
    $("config").value = value.content;
  } catch (e) {
    toast(e.message);
  }
}
async function saveConfig() {
  const button = $("save-config");
  button.disabled = true;
  $("config-message").textContent = "Validating…";
  try {
    await request($("config-path").value, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: $("config").value }),
    });
    $("config-message").textContent =
      "Saved. Restart the UI if you changed its port.";
    await refresh();
  } catch (e) {
    $("config-message").textContent = e.message;
  } finally {
    button.disabled = false;
  }
}
function executionFlow(t) {
  const steps = [
    ["queued", "Queued"],
    ["working", "Working"],
    ["validating", "Validation"],
    ["publishing", "Publication"],
    ["completed", "Delivered"],
  ];
  const current = phase(t);
  return `<div class="execution-flow" aria-label="Task execution stages">${steps
    .map(([key, label], i) => {
      const occurred =
        (t.events || []).some((e) => e.stage === key) || key === current;
      return `<div class="flow-step ${occurred ? "reached" : ""} ${current === key ? "current" : ""}"><i>${key === "completed" && t.status === "completed" ? "✓" : i + 1}</i>${label}</div>`;
    })
    .join("")}</div>`;
}
function taskLink(t) {
  return `<button class="task-link" data-task="${esc(t.id)}" data-agent="${esc(t.agent)}"><span class="dot ${t.status === "completed" ? "green" : t.status === "blocked" ? "amber" : "blue"}"></span><span>${esc(t.title)}<small>${esc(t.agent)}</small></span>${badge(phase(t))}</button>`;
}
function renderDrawer() {
  const r = route();
  const id = r.params.get("agent");
  if (!id) {
    if (!$("drawer").hidden) {
      $("drawer").hidden = true;
      $("drawer-backdrop").hidden = true;
      document.body.style.overflow = "";
    }
    selected = null;
    drawerSignature = "";
    return;
  }
  const a = findAgent(id);
  if (!a) return;
  const p = data.pillars.find((p) => p.slug === a.pillar);
  const taskId = r.params.get("task");
  const t = taskId
    ? p.tasks.find((t) => t.id === taskId && t.agent === id)
    : currentTask(a) ||
      p.tasks.find((t) => t.agent === id && t.status === "blocked");
  const own = p.tasks.filter((t) => t.agent === id);
  const signature = JSON.stringify([a, own, taskId, demo]);
  if (signature === drawerSignature) return;
  const drawerFocus = $("drawer").contains(document.activeElement)
    ? document.activeElement.id
    : null;
  const scroll = $("drawer").scrollTop;
  const priorOutput =
    selected?.agent === id ? $("session-output")?.textContent : null;
  const wasOpen = !$("drawer").hidden;
  drawerSignature = signature;
  selected = { agent: id, task: t?.id };
  $("drawer").hidden = false;
  $("drawer-backdrop").hidden = false;
  document.body.style.overflow = "hidden";
  $("drawer").innerHTML =
    `<div class="drawer-head"><a href="#pillar/${p.slug}/graph">${esc(displayName(p.slug))}</a><span class="slash">/</span><span>${esc(displayName(a.local_id))}</span><button class="icon-button" id="close-drawer" aria-label="Close agent details">${icon("close")}</button></div><div class="drawer-title">${avatar(a)}<div><h2>${esc(displayName(a.local_id))}</h2><p>${esc(a.provider === "claude" ? "Claude Code" : "Codex")} · ${esc(a.role === "project-manager" ? "Project Manager" : a.template)} · ${esc(p.slug)}</p></div><span style="margin-left:auto">${badge(a.status)}</span></div><div class="drawer-actions"><button class="button ${a.running ? "" : "primary"}" data-action="ensure" data-target="${esc(a.id)}" ${demo || a.running ? "disabled" : ""}>${icon("play")}Launch</button><button class="button" data-action="goal" data-target="${esc(a.id)}" ${demo || !a.running ? "disabled" : ""}>${icon("arrow")}Send goal</button><button class="button danger" data-action="stop" data-target="${esc(a.id)}" ${demo || !a.running ? "disabled" : ""}>${icon("stop")}Stop</button></div>${demo ? `<div class="alert-note">Simulated agent. Runtime controls are disabled. <button class="text-button" id="drawer-demo-play">${demoPaused ? "Resume simulation" : "Pause simulation"}</button></div>` : ""}${a.status === "interrupted" ? '<div class="alert-note">The ledger has a running task, but its tmux session is offline. The stage below is its last reported state.</div>' : ""}<div class="detail-stats"><div><strong>${a.counts.open}</strong>Open tasks</div><div><strong>${a.counts.completed}</strong>Delivered</div><div><strong>${a.counts.ready}</strong>Ready to claim</div></div>${
      t
        ? `<section class="drawer-task"><div class="small-label">${taskId ? "Selected task" : "Current assignment"} · ${esc(t.id.slice(-8))}</div>${badge(phase(t))}<h3>${esc(t.title)}</h3>${executionFlow(t)}${t.reason ? `<div class="alert-note">${esc(t.reason)}</div>` : ""}<div class="small-label">Last reported step</div><p class="task-instructions">${esc(t.progress || "No work step reported yet.")}<br><span class="faint">${age(t.updated_at || t.created_at)}</span></p><div class="divider"></div><div class="small-label">Assignment</div><p class="task-instructions">${esc(t.instructions)}</p><div class="divider"></div><div class="small-label">Acceptance criteria</div><ul class="check-list">${t.acceptance.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>${
            t.dependencies.length
              ? `<div class="small-label">Receives work from</div>${t.dependencies
                  .map((d) => findTask(d))
                  .filter(Boolean)
                  .map(taskLink)
                  .join("")}`
              : ""
          }${
            p.tasks.some((x) => x.dependencies.includes(t.id))
              ? `<div class="divider"></div><div class="small-label">Downstream tasks</div>${p.tasks
                  .filter((x) => x.dependencies.includes(t.id))
                  .map(taskLink)
                  .join("")}`
              : ""
          }<div class="divider"></div><div class="small-label">Execution history</div><div class="detail-events">${eventsPanel(
            (t.events || [])
              .slice()
              .reverse()
              .map((e) => ({ ...e, task: t.id, title: t.title, agent: a.id })),
            8,
          )}</div>${t.delivery ? `<div class="divider"></div><div class="small-label">Verified delivery · ${age(t.delivery.verified_at)}</div>${(t.delivery.artifacts || []).map((o) => `<code class="file-path">${esc(o.path)}</code>`).join("")}` : ""}</section>`
        : empty(
            "No active task",
            a.counts.ready
              ? "Assignments are ready in this agent’s queue."
              : "The agent has not claimed an assignment yet.",
          )
    }<div class="divider"></div><div class="small-label">Agent ledger · ${own.length} tasks</div>${
      own
        .slice()
        .sort((a, b) =>
          String(b.updated_at || b.created_at).localeCompare(
            a.updated_at || a.created_at,
          ),
        )
        .slice(0, 30)
        .map(taskLink)
        .join("") ||
      '<p class="muted" style="font-size:11px">No assignments yet.</p>'
    }<div class="divider"></div><div class="section-heading"><h2 style="font-size:12px">Session output</h2><button class="text-button" id="load-output">${icon("refresh")}Refresh output</button></div><pre class="output" id="session-output">${
      demo
        ? esc(
            "SIMULATED SESSION · no native harness connected\n\n" +
              own
                .flatMap((task) =>
                  task.events.map((e) => ({ ...e, title: task.title })),
                )
                .sort((a, b) => a.at.localeCompare(b.at))
                .slice(-16)
                .map(
                  (e) =>
                    `[${new Date(e.at).toLocaleTimeString()}] ${e.stage.toUpperCase()} · ${e.title}\n${e.message}`,
                )
                .join("\n\n"),
          )
        : "Select “Refresh output” to read the latest session output."
    }</pre><div class="small-label">Session</div><code class="file-path">${esc(a.session)}</code><div class="small-label" style="margin-top:15px">Required outputs</div>${a.deliverables.map((d) => `<code class="file-path">${esc(d.path)}</code>`).join("")}`;
  $("drawer").scrollTop = scroll;
  if (!demo && priorOutput && $("session-output"))
    $("session-output").textContent = priorOutput;
  if (!wasOpen) $("close-drawer").focus();
  else if (drawerFocus && $(drawerFocus))
    $(drawerFocus).focus({ preventScroll: true });
}
function render(force = false) {
  if (!data) return;
  const r = route(),
    parts = r.parts;
  const key = parts.join("/");
  const changed = key !== renderedRoute;
  if (changed) {
    query = "";
    filter = "all";
    zoom = 1;
    boardLimit = 20;
    renderedRoute = key;
  }
  const p =
    parts[0] === "pillar"
      ? data.pillars.find((p) => p.slug === parts[1])
      : null;
  $("workspace-name").textContent = data.project.name;
  const detailAgent = findAgent(r.params.get("agent"));
  const contextPillar = detailAgent
    ? data.pillars.find((item) => item.slug === detailAgent.pillar)
    : p;
  const pageLabel = {
    board: "All tasks",
    agents: "All Harness Agents",
    activity: "Workspace activity",
    settings: "Configuration",
  }[parts[0]];
  $("breadcrumb").innerHTML =
    `<a href="#overview">${esc(data.project.name)}</a>${contextPillar ? `<span class="slash">/</span><a href="#pillar/${contextPillar.slug}/graph">${esc(displayName(contextPillar.slug))}</a>${detailAgent ? `<span class="slash">/</span><strong aria-current="page">${esc(displayName(detailAgent.local_id))}</strong>` : ""}` : `<span class="slash">/</span><strong aria-current="page">${pageLabel || "All Pillars"}</strong>`}`;
  const navScroll = $("pillar-nav").scrollTop;
  $("pillar-nav").innerHTML = data.pillars
    .map((item) => {
      const expanded = contextPillar?.slug === item.slug;
      return `<div class="pillar-branch"><a class="pillar-item ${expanded ? "selected" : ""}" href="#pillar/${item.slug}/graph" ${expanded ? 'aria-current="true"' : ""}><span class="branch-chevron" aria-hidden="true">${expanded ? "⌄" : "›"}</span><span>${esc(displayName(item.slug))}</span><span class="dot ${item.status === "active" ? "green" : item.status === "attention" ? "amber" : "muted"}" title="${esc(item.status)}"></span></a>${expanded ? `<div class="agent-children" aria-label="${esc(displayName(item.slug))} Harness Agents">${item.agents.map((a) => `<a class="agent-child ${detailAgent?.id === a.id ? "selected" : ""}" href="#pillar/${item.slug}/graph?agent=${encodeURIComponent(a.id)}" ${detailAgent?.id === a.id ? 'aria-current="page"' : ""}><span class="dot ${onlineColor(a)}" title="${esc(a.status)}"></span><span>${esc(displayName(a.local_id))}</span></a>`).join("")}</div>` : ""}</div>`;
    })
    .join("");
  $("pillar-nav").scrollTop = navScroll;
  document
    .querySelectorAll("[data-nav]")
    .forEach((el) =>
      el.classList.toggle("selected", el.dataset.nav === parts[0]),
    );
  $("demo-banner").hidden = !demo;
  $("demo-toggle").innerHTML =
    icon("play") +
    `<span>${demo ? "Return to live workspace" : "Explore a 60-agent fleet"}<small>${demo ? "Leave demonstration" : "Interactive demonstration"}</small></span>`;
  if (boot.demoOnly) {
    $("demo-toggle").innerHTML = icon("arrow") + "Back to Autodev";
    $("exit-demo").textContent = "Back to Autodev";
  }
  $("footer-info").textContent = demo
    ? "Demo · 60 simulated agents"
    : `Observed ${age(data.observed_at)} · refreshes every 2 seconds`;
  const graphScroll = $("graph-viewport")
    ? [$("graph-viewport").scrollLeft, $("graph-viewport").scrollTop]
    : null;
  const boardScroll = document.querySelector(".board-wrap")?.scrollLeft;
  const focused = document.activeElement?.id;
  const selection = focused === "search" ? $("search").selectionStart : null;
  if (parts[0] !== "settings" || changed || force) {
    $("content").innerHTML =
      parts[0] === "pillar"
        ? pillarPage(parts[1], parts[2] || "graph")
        : parts[0] === "board"
          ? boardPage()
          : parts[0] === "agents"
            ? agentsPage()
            : parts[0] === "activity"
              ? activityPage()
              : parts[0] === "settings"
                ? settingsPage()
                : overview();
    if (parts[0] === "settings") {
      const slug = r.params.get("pillar");
      if (slug && data.pillars.some((p) => p.slug === slug))
        $("config-path").value = `/api/pillars/${slug}/config`;
      loadConfig();
    }
    if (graphScroll && $("graph-viewport")) {
      $("graph-viewport").scrollLeft = graphScroll[0];
      $("graph-viewport").scrollTop = graphScroll[1];
    }
    if (boardScroll && document.querySelector(".board-wrap"))
      document.querySelector(".board-wrap").scrollLeft = boardScroll;
    if (focused === "search" && $("search")) {
      $("search").focus();
      $("search").setSelectionRange(selection, selection);
    }
  }
  if (changed) window.scrollTo(0, 0);
  renderDrawer();
}
function connection(ok) {
  const el = $("connection");
  el.className = `connection ${ok ? "live" : "stale"}`;
  el.innerHTML = `<span class="dot"></span>${demo ? "Demo simulation" : ok ? "Live · 2s refresh" : "Disconnected · retrying"}`;
}
async function refresh() {
  if (boot.demoOnly) return;
  if (fetching) return;
  fetching = true;
  try {
    liveData = await request("/api/fleet");
    lastSuccess = Date.now();
    if (!demo) {
      data = liveData;
      $("error-banner").hidden = !data.errors.length;
      $("error-banner").textContent = data.errors.join(" ");
      const signature = JSON.stringify([
        data.project,
        data.pillars,
        data.counts,
        data.errors,
      ]);
      if (signature !== dataSignature) {
        dataSignature = signature;
        render();
      } else {
        $("footer-info").textContent =
          `Observed ${age(data.observed_at)} · refreshes every 2 seconds`;
      }
    }
    connection(true);
  } catch (e) {
    if (!demo) {
      $("error-banner").hidden = false;
      $("error-banner").textContent =
        `Live observation interrupted. Showing the last successful snapshot${lastSuccess ? " from " + new Date(lastSuccess).toLocaleTimeString() : ""}. ${e.message}`;
    }
    connection(false);
  } finally {
    fetching = false;
  }
}
async function runtimeAction(action, id, button) {
  if (demo) return;
  button.disabled = true;
  try {
    await request(`/api/actions/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ agents: [id], send_goal: true }),
    });
    toast(
      action === "stop"
        ? "Session stopped; work and ledger preserved."
        : action === "goal"
          ? "Operating goal sent."
          : "Harness Agent launched.",
    );
    drawerSignature = "";
    await refresh();
  } catch (e) {
    toast(e.message);
  } finally {
    if (button.isConnected) button.disabled = false;
  }
}
let demoPaused = false;
let demoSpeed = 1;
let demoTimer;
function demoControls() {
  if (!demo) return;
  $("demo-play").textContent = demoPaused ? "Play" : "Pause";
  $("demo-play").disabled = demoData.finished;
  $("demo-step").disabled = demoData.finished;
  $("demo-state").textContent = demoData.finished
    ? "Scenario complete"
    : `${demoPaused ? "Paused" : "Playing"} · step ${demoData.tick}`;
  $("demo-speed").value = String(demoSpeed);
  if ($("drawer-demo-play"))
    $("drawer-demo-play").textContent = demoPaused
      ? "Resume simulation"
      : "Pause simulation";
}
function demoStep() {
  if (!demo) return;
  FleetDemo.advance(demoData);
  data = demoData;
  render();
  demoControls();
}
function scheduleDemo() {
  clearTimeout(demoTimer);
  if (!demo || demoPaused || demoData.finished) return;
  demoTimer = setTimeout(() => {
    demoStep();
    scheduleDemo();
  }, 4000 / demoSpeed);
}
function toggleDemo() {
  if (boot.demoOnly && demo) {
    location.assign("/");
    return;
  }
  demo = !demo;
  query = "";
  filter = "all";
  renderedRoute = "";
  drawerSignature = "";
  if (demo) {
    demoData = FleetDemo.create();
    demoPaused = false;
    data = demoData;
    $("error-banner").hidden = true;
  } else {
    data = liveData;
  }
  const url = new URL(location.href);
  if (demo) url.searchParams.set("demo", "1");
  else url.searchParams.delete("demo");
  url.hash = "overview";
  history.replaceState(null, "", url);
  render(true);
  demoControls();
  scheduleDemo();
  connection(!!lastSuccess);
  if (!demo) refresh();
}
document.addEventListener("click", (e) => {
  const button = e.target.closest("button,a,[data-agent]");
  if (!button) return;
  if (button.id === "drawer-demo-play") {
    demoPaused = !demoPaused;
    demoControls();
    scheduleDemo();
    return;
  }
  if (button.dataset.action) {
    runtimeAction(button.dataset.action, button.dataset.target, button);
    return;
  }
  if (button.dataset.agent) {
    openDetails(button.dataset.agent, button.dataset.task);
    return;
  }
  if (button.id === "close-drawer") {
    closeDetails();
    return;
  }
  if (button.dataset.zoom) {
    const canvas = document.querySelector(".graph-canvas");
    zoom =
      button.dataset.zoom === "fit"
        ? Math.min(
            1,
            ($("graph-viewport").clientWidth - 20) / canvas.offsetWidth,
            ($("graph-viewport").clientHeight - 20) / canvas.offsetHeight,
          )
        : Math.min(
            1.4,
            Math.max(0.15, zoom + (button.dataset.zoom === "in" ? 0.1 : -0.1)),
          );
    render(true);
  }
  if (button.hasAttribute("data-more")) {
    boardLimit += 20;
    render(true);
  }
  if (button.id === "save-config") saveConfig();
  if (button.id === "load-output") {
    if (demo) {
      drawerSignature = "";
      renderDrawer();
      return;
    }
    const id = selected?.agent;
    if (!id) return;
    button.disabled = true;
    request(`/api/agents/${encodeURIComponent(id)}/output`)
      .then((v) => {
        if (selected?.agent === id && $("session-output"))
          $("session-output").textContent =
            v.text || "No session output captured yet.";
      })
      .catch((e) => toast(e.message))
      .finally(() => {
        if (button.isConnected) button.disabled = false;
      });
  }
});
document.addEventListener("input", (e) => {
  if (e.target.id === "search") {
    query = e.target.value;
    render(true);
  }
});
document.addEventListener("change", (e) => {
  if (e.target.id === "filter") {
    filter = e.target.value;
    render(true);
  }
  if (e.target.id === "config-path") loadConfig();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !$("drawer").hidden) {
    closeDetails();
    return;
  }
  if (e.key === "Enter" && e.target.matches("tr[data-agent]"))
    openDetails(e.target.dataset.agent);
  if (e.key === "Tab" && !$("drawer").hidden) {
    const targets = [
      ...$("drawer").querySelectorAll(
        "button:not(:disabled),a,input,textarea,select",
      ),
    ].filter((x) => x.offsetParent !== null);
    const first = targets[0],
      last = targets.at(-1);
    if (e.shiftKey && document.activeElement === first) {
      last.focus();
      e.preventDefault();
    } else if (!e.shiftKey && document.activeElement === last) {
      first.focus();
      e.preventDefault();
    }
  }
});
$("demo-play").onclick = () => {
  demoPaused = !demoPaused;
  demoControls();
  scheduleDemo();
};
$("demo-step").onclick = () => {
  demoPaused = true;
  demoStep();
  scheduleDemo();
};
$("demo-restart").onclick = () => {
  if (!demo) return;
  demoData = FleetDemo.create();
  data = demoData;
  drawerSignature = "";
  render(true);
  demoControls();
  scheduleDemo();
};
$("demo-speed").onchange = () => {
  demoSpeed = Number($("demo-speed").value);
  scheduleDemo();
};
$("drawer-backdrop").onclick = closeDetails;
$("demo-toggle").onclick = toggleDemo;
$("exit-demo").onclick = toggleDemo;
$("refresh").onclick = () => {
  if (demo) {
    toast(
      "You are viewing the demonstration. Return to live workspace for runtime data.",
    );
  } else refresh();
};
window.addEventListener("hashchange", () => render());
async function poll() {
  await refresh();
  setTimeout(poll, 2000);
}
if (boot.demoOnly || new URL(location.href).searchParams.get("demo") === "1") {
  const initialRoute = location.hash;
  toggleDemo();
  if (initialRoute) {
    location.hash = initialRoute;
    render(true);
  }
}
poll();
