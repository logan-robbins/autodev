/* Browser-only scenario engine. No network, storage, or runtime actions. */
const FleetDemo = (() => {
  const specs = [
    [
      "research",
      "Build an evidence base for a new customer portal.",
      "brief.md",
      "text/markdown",
      [],
      [
        ["manager", "Plan evidence coverage"],
        ["interviewer", "Synthesize customer interviews"],
        ["source-auditor", "Audit source provenance"],
        ["workflow-researcher", "Map onboarding workflows"],
        ["market-researcher", "Compare competing portals"],
        ["accessibility-researcher", "Identify access barriers"],
        ["evidence-reviewer", "Review evidence quality"],
        ["synthesist", "Connect workflow findings"],
        ["brief-editor", "Assemble the research brief"],
        ["publisher", "Publish cited recommendations"],
      ],
    ],
    [
      "frontend",
      "Deliver an accessible customer portal against stable interfaces.",
      "portal/",
      "directory",
      ["research", "data", "infrastructure"],
      [
        ["manager", "Plan portal delivery"],
        ["navigation-designer", "Build Pillar navigation"],
        ["component-builder", "Implement task cards"],
        ["graph-engineer", "Render dependency handoffs"],
        ["activity-engineer", "Connect progress updates"],
        ["accessibility-engineer", "Implement keyboard controls"],
        ["interaction-reviewer", "Review navigation interactions"],
        ["integration-tester", "Verify live update rendering"],
        ["visual-reviewer", "Validate responsive layouts"],
        ["release-engineer", "Package the portal release"],
      ],
    ],
    [
      "infrastructure",
      "Provide reproducible environments and a verified delivery pipeline.",
      "deployment.json",
      "application/json",
      [],
      [
        ["manager", "Plan environment readiness"],
        ["pipeline-engineer", "Build isolated verification jobs"],
        ["environment-engineer", "Provision preview environments"],
        ["observability-engineer", "Wire service health signals"],
        ["security-reviewer", "Audit credential boundaries"],
        ["recovery-engineer", "Exercise rollback procedures"],
        ["pipeline-reviewer", "Verify pipeline outcomes"],
        ["reliability-tester", "Test failure recovery"],
        ["release-validator", "Validate deployment manifests"],
        ["release-operator", "Publish deployment evidence"],
      ],
    ],
    [
      "data",
      "Publish validated customer data through a deterministic interface.",
      "catalog.json",
      "application/json",
      [],
      [
        ["manager", "Plan data acceptance"],
        ["schema-designer", "Define customer record schemas"],
        ["ingestion-engineer", "Normalize source records"],
        ["entity-analyst", "Reconcile duplicate customers"],
        ["privacy-reviewer", "Check sensitive field handling"],
        ["quality-analyst", "Measure source completeness"],
        ["schema-validator", "Verify normalized records"],
        ["reconciliation-reviewer", "Review entity matches"],
        ["catalog-editor", "Compile the data dictionary"],
        ["publisher", "Publish the validated catalog"],
      ],
    ],
    [
      "analysis",
      "Translate published evidence into a launch recommendation.",
      "recommendation.md",
      "text/markdown",
      ["research", "data"],
      [
        ["manager", "Plan decision criteria"],
        ["baseline-analyst", "Establish adoption baselines"],
        ["scenario-analyst", "Model launch scenarios"],
        ["sensitivity-analyst", "Test uncertain assumptions"],
        ["cost-analyst", "Estimate operating costs"],
        ["risk-analyst", "Assess launch risks"],
        ["model-reviewer", "Review scenario calculations"],
        ["evidence-reviewer", "Verify analytical evidence"],
        ["recommendation-editor", "Draft the launch recommendation"],
        ["publisher", "Publish the decision brief"],
      ],
    ],
    [
      "project-management",
      "Coordinate launch outcomes through each Pillar’s public contract.",
      "launch-plan.json",
      "application/json",
      ["research", "frontend", "infrastructure", "data", "analysis"],
      [
        ["manager", "Plan launch coordination"],
        ["scope-planner", "Define launch outcomes"],
        ["dependency-planner", "Map public interface dependencies"],
        ["acceptance-analyst", "Specify acceptance evidence"],
        ["schedule-planner", "Sequence delivery milestones"],
        ["risk-coordinator", "Document escalation paths"],
        ["scope-reviewer", "Review outcome coverage"],
        ["dependency-reviewer", "Verify contract availability"],
        ["readiness-analyst", "Compile launch readiness"],
        ["plan-publisher", "Publish the launch plan"],
      ],
    ],
  ];
  const rounds = ["Interface fixture", "Candidate output", "Release evidence"];
  const counts = (tasks) => {
    const n = (status) => tasks.filter((t) => t.status === status).length;
    return {
      total: tasks.length,
      open: tasks.length - n("completed"),
      completed: n("completed"),
      running: n("running"),
      blocked: n("blocked"),
      ready: tasks.filter((t) => t.status === "queued" && t.ready).length,
      waiting: tasks.filter((t) => t.status === "queued" && !t.ready).length,
    };
  };
  function event(t, stage, message, now) {
    const at = new Date(now).toISOString();
    t.stage = stage;
    t.progress = message;
    t.updated_at = at;
    t.events.push({ at, stage, message });
    t.events = t.events.slice(-100);
  }
  function summarize(state, now) {
    for (const p of state.pillars) {
      const byId = new Map(p.tasks.map((t) => [t.id, t]));
      for (const t of p.tasks)
        t.ready =
          t.status === "queued" &&
          t.dependencies.every((id) => byId.get(id).status === "completed");
      for (const a of p.agents) {
        const own = p.tasks.filter((t) => t.agent === a.id);
        const current = own.find((t) => t.status === "running");
        a.counts = counts(own);
        a.current_task = current?.id || null;
        a.status = current
          ? a.running
            ? "working"
            : "interrupted"
          : a.counts.blocked
            ? "blocked"
            : a.running
              ? "idle"
              : "offline";
      }
      p.counts = counts(p.tasks);
      p.online = p.agents.filter((a) => a.running).length;
      p.interrupted = p.agents.filter((a) => a.status === "interrupted").length;
      p.status =
        p.counts.blocked || p.interrupted
          ? "attention"
          : p.counts.running
            ? "active"
            : p.counts.open
              ? "ready"
              : "idle";
      p.interface_state =
        p.counts.completed === p.counts.total
          ? "implementation-ready"
          : "interface-ready";
    }
    const tasks = state.pillars.flatMap((p) => p.tasks);
    state.counts = {
      ...counts(tasks),
      pillars: state.pillars.length,
      agents: 60,
      online: state.pillars.reduce((n, p) => n + p.online, 0),
      interrupted: state.pillars.reduce((n, p) => n + p.interrupted, 0),
    };
    state.events = tasks
      .flatMap((t) =>
        t.events.map((e) => ({
          ...e,
          task: t.id,
          title: t.title,
          agent: t.agent,
          pillar: t.pillar,
        })),
      )
      .sort((a, b) => b.at.localeCompare(a.at))
      .slice(0, 100);
    state.observed_at = new Date(now).toISOString();
    state.finished = state.counts.open === 0;
    return state;
  }
  function advance(state, now = Date.now()) {
    if (state.finished) return state;
    state.tick++;
    for (const [pi, p] of state.pillars.entries()) {
      const byId = new Map(p.tasks.map((t) => [t.id, t]));
      // Read readiness before this tick: handoffs become claimable on the next tick.
      const completed = new Set(
        p.tasks.filter((t) => t.status === "completed").map((t) => t.id),
      );
      for (const [ai, a] of p.agents.entries()) {
        const own = p.tasks.filter((t) => t.agent === a.id);
        let current = own.find(
          (t) => t.status === "running" || t.status === "blocked",
        );
        if (
          pi === 2 &&
          state.tick === 12 &&
          ai === 1 &&
          current?.status === "running"
        ) {
          a.running = false;
          a.resumeTick = state.tick + 4;
          event(
            current,
            current.stage,
            "Simulated session disconnected; the assignment remains claimed.",
            now,
          );
        }
        if (!a.running && state.tick >= a.resumeTick) {
          a.running = true;
          if (current)
            event(
              current,
              current.stage,
              "Simulated session resumed with its existing task ledger.",
              now,
            );
        }
        if (!a.running) continue;
        if (current?.status === "blocked") {
          if (state.tick < current.resumeTick) continue;
          current.status = "running";
          current.reason = null;
          event(
            current,
            "working",
            "Clarification received from the Pillar’s manager; the worker resumes its assignment.",
            now,
          );
          continue;
        }
        if (!current) {
          current = own.find(
            (t) =>
              t.status === "queued" &&
              t.dependencies.every((id) => completed.has(id)),
          );
          if (!current || state.tick < 1 + ((pi + ai) % 4)) continue;
          current.status = "running";
          current.started_at = new Date(now).toISOString();
          current.workTick = 0;
          const sources = current.dependencies
            .map((id) => byId.get(id))
            .filter((t) => t.agent !== a.id);
          event(
            current,
            "working",
            sources.length
              ? `Claimed after receiving verified output from ${sources.map((t) => t.agent.split("--")[1]).join(" and ")}.`
              : "Harness Agent claimed its next ready assignment.",
            now,
          );
          continue;
        }
        current.workTick++;
        if (
          pi % 2 === 0 &&
          ai === 2 &&
          current.round === 0 &&
          current.workTick === 2 &&
          !current.blockSeen
        ) {
          current.blockSeen = true;
          current.status = "blocked";
          current.resumeTick = state.tick + 4;
          current.reason = [
            "Two source records disagree on the acceptance baseline.",
            "",
            "Preview environment naming needs clarification.",
            "",
            "Scenario assumptions need an agreed baseline.",
          ][pi];
          event(current, "blocked", current.reason, now);
          continue;
        }
        const duration = 3 + ((pi + ai + current.round) % 4);
        if (current.workTick < duration) {
          event(
            current,
            "working",
            `${current.title.split(" · ")[0]}: ${current.workTick % 2 ? "assembling the declared output" : "checking evidence and edge cases"}.`,
            now,
          );
        } else if (current.workTick === duration) {
          event(
            current,
            "validating",
            `Checking ${current.output} against the declared format and acceptance criteria.`,
            now,
          );
        } else if (current.workTick === duration + 1) {
          event(
            current,
            "publishing",
            "Validating the combined output against the Pillar’s consumer checks.",
            now,
          );
        } else {
          current.status = "completed";
          current.delivery = {
            verified_at: new Date(now).toISOString(),
            artifacts: [{ path: current.output }],
          };
          const next = p.tasks.filter(
            (t) =>
              t.status === "queued" &&
              t.dependencies.includes(current.id) &&
              t.agent !== a.id,
          );
          event(
            current,
            "completed",
            `Published ${current.output}.${next.length ? " Handoff available to " + [...new Set(next.map((t) => t.agent.split("--")[1]))].join(", ") + "." : " Delivery evidence recorded."}`,
            now,
          );
        }
      }
    }
    return summarize(state, now);
  }
  function create(now = Date.now()) {
    const state = {
      project: {
        id: "demo",
        name: "Customer portal launch · Demo",
        execution: "simulation",
      },
      pillars: [],
      tick: 0,
      errors: [],
    };
    for (const [
      pi,
      [slug, summary, output, format, dependencies, roles],
    ] of specs.entries()) {
      const agents = roles.map(([local, purpose], i) => ({
        id: `${slug}--${local}`,
        local_id: local,
        pillar: slug,
        template: i === 0 ? "project-manager" : local,
        role: i === 0 ? "project-manager" : "worker",
        provider: (i + pi) % 2 ? "claude" : "codex",
        session: `demo-${slug}-${local}`,
        running: true,
        status: "idle",
        counts: {},
        current_task: null,
        purpose,
        write_roots: [`${slug}/output/${local}/`],
        deliverables: [
          {
            id: "result",
            path: `${slug}/output/${local}/${i === 0 ? "task-plan.json" : i === 9 ? output : "result.json"}`,
            format: i === 9 ? format : "application/json",
          },
        ],
      }));
      const id = (i, r) => `demo-${slug}-${i}-${r}`;
      const tasks = agents.flatMap((a, i) =>
        rounds.map((round, r) => {
          const upstream =
            i === 6
              ? [1, 2]
              : i === 7
                ? [3, 4]
                : i === 8
                  ? [5, 6]
                  : i === 9
                    ? [7, 8]
                    : [];
          const output = a.deliverables[0].path;
          const t = {
            id: id(i, r),
            agent: a.id,
            pillar: slug,
            title: `${a.purpose} · ${round.toLowerCase()}`,
            instructions: `${a.purpose}. ${r === 0 ? "Establish a functioning interface fixture before implementation." : r === 1 ? "Build and verify the candidate behind the declared interface." : "Validate the final output and record reproducible release evidence."} Write the result to ${output}.`,
            acceptance: [
              `Output at ${output} matches its declared format and required structure.`,
              "Evidence supports the assignment’s acceptance criteria.",
              "Declared consumer checks pass before publication.",
            ],
            status: "queued",
            stage: "queued",
            progress: "",
            reason: null,
            created_at: new Date(now - 180000).toISOString(),
            updated_at: new Date(now - 180000).toISOString(),
            dependencies: [
              ...(r ? [id(i, r - 1)] : []),
              ...upstream.map((x) => id(x, r)),
            ],
            ready: false,
            events: [],
            delivery: null,
            round: r,
            output,
          };
          event(
            t,
            "queued",
            "Assignment added to this Harness Agent’s ledger.",
            now - 180000,
          );
          return t;
        }),
      );
      state.pillars.push({
        slug,
        summary,
        responsibility: summary,
        consumption: `Consume ${slug}/output/${agents[9].local_id}/${output} through ${slug}/pillar.toml. Fixtures remain usable while implementation progresses.`,
        constraints:
          "Simulated interface and artifacts; no files are created. Peer Pillars consume public outputs, never internal task ledgers.",
        interface_state: "interface-ready",
        dependencies,
        outputs: [
          {
            id: "published-output",
            path: `output/${agents[9].local_id}/${output}`,
            format,
            description: summary,
          },
        ],
        agents,
        tasks,
        error: null,
      });
    }
    summarize(state, now - 90000);
    for (let i = 0; i < 6; i++) advance(state, now - (5 - i) * 15000);
    return state;
  }
  return { create, advance };
})();
if (typeof module !== "undefined") module.exports = FleetDemo;
