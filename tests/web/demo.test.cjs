const { test } = require("node:test");
const assert = require("node:assert/strict");
const { create, advance } = require("../../src/autodev/web/demo.js");
const now = Date.parse("2026-09-09T12:00:00Z");
test("60 distinct agent identities, 180 bounded tasks, public outputs owned by their publisher", () => {
  const state = create(now);
  assert.equal(state.pillars.length, 6);
  const agents = state.pillars.flatMap((p) => p.agents);
  assert.equal(new Set(agents.map((a) => a.id)).size, 60);
  assert.equal(state.counts.total, 180);
  assert.ok(state.counts.running >= 25);
  for (const p of state.pillars) {
    assert.equal(
      p.agents.filter((a) => a.role === "project-manager").length,
      1,
    );
    assert.equal(new Set(p.tasks.map((t) => t.title)).size, 30);
    for (const output of p.outputs)
      assert.ok(
        p.agents.some((a) =>
          a.deliverables.some(
            (d) =>
              d.path === `${p.slug}/${output.path}` &&
              d.format === output.format,
          ),
        ),
      );
  }
});
test("playback respects ownership, dependency readiness, full execution stages and bounded completion", () => {
  const state = create(now);
  let sawBlocked = false,
    sawInterrupted = false,
    sawHandoff = false;
  for (let i = 0; i < 180 && !state.finished; i++) {
    for (const p of state.pillars) {
      const tasks = new Map(p.tasks.map((t) => [t.id, t]));
      for (const a of p.agents) {
        const own = p.tasks.filter((t) => t.agent === a.id);
        assert.ok(
          own.filter((t) => t.status === "running" || t.status === "blocked")
            .length <= 1,
        );
        assert.equal(a.counts.total, own.length);
        if (a.current_task) assert.equal(tasks.get(a.current_task).agent, a.id);
      }
      for (const t of p.tasks) {
        for (const id of t.dependencies)
          assert.ok(
            tasks.has(id),
            "internal task dependencies remain within their Pillar",
          );
        if (t.status !== "queued")
          assert.ok(
            t.dependencies.every((id) => tasks.get(id).status === "completed"),
          );
        if (t.status === "completed") {
          assert.deepEqual(t.delivery.artifacts, [{ path: t.output }]);
          for (const stage of [
            "queued",
            "working",
            "validating",
            "publishing",
            "completed",
          ])
            assert.ok(t.events.some((e) => e.stage === stage));
        }
        assert.ok(t.events.length <= 100);
      }
    }
    sawBlocked ||= state.counts.blocked > 0;
    sawInterrupted ||= state.counts.interrupted > 0;
    sawHandoff ||= state.events.some((e) =>
      e.message.includes("receiving verified output"),
    );
    assert.ok(state.events.length <= 100);
    advance(state, now + (i + 1) * 4000);
  }
  assert.ok(sawBlocked);
  assert.ok(sawInterrupted);
  assert.ok(sawHandoff);
  assert.equal(state.counts.completed, 180);
  assert.equal(state.counts.open, 0);
  assert.ok(
    state.pillars.every((p) => p.interface_state === "implementation-ready"),
  );
  const completed = JSON.stringify(state);
  advance(state, now + 999999);
  assert.equal(
    JSON.stringify(state),
    completed,
    "completed playback stops without inventing more work",
  );
});
test("restart creates an independent reproducible scenario", () => {
  const first = create(now),
    second = create(now);
  assert.deepEqual(first, second);
  advance(first, now + 4000);
  assert.equal(second.tick, 6);
  assert.notDeepEqual(first, second);
});
