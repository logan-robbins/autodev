# Autodev ontology

This is the canonical vocabulary for Autodev v1. It describes the implemented
model. Memory is explicitly deferred at the user's request.

| Entity | Definition |
| --- | --- |
| Workspace | A project root containing `autodev.toml` and peer Pillar directories. It can be an ordinary folder or a Git repository. |
| Pillar | A self-contained capability boundary at `<workspace>/<slug>/`. The required `pillar.toml` is at its root; all descendants belong to that boundary. |
| Pillar Contract | The structured, agent-native description of a Pillar's responsibilities, inputs, outputs, consumption, constraints, fixtures, dependencies, and checks. |
| Pod | The one implicit group of Harness Agents assigned to a Pillar. It has no separate declaration, owner field, or required PM. |
| Harness Agent | A named template instance backed by a full native harness. Its identity and ledger persist across session restarts. |
| Harness Agent Contract | The instance's purpose, instructions, owned paths, required deliverable locations/formats/schemas, and task obligations. |
| Agent template | A reusable role and delivery contract. Shipped templates include an optional Project Manager. A custom template belongs in its Pillar. |
| Project Manager Harness Agent | The optional, sole Pod-wide ledger role. It tends each worker's assignments and reads progress/output evidence. It cannot complete workers' tasks or access another Pod's internal ledgers. |
| Task ledger | One agent's structured task record at `<pillar>/tasks/<agent>/ledger.json`. The worker reads and updates its own progress; its PM normally tends assignments. |
| Task | A bounded assignment with explicit acceptance criteria, dependencies, and one executing Harness Agent. |
| Delivery | The validated output of a task, recorded in that worker's ledger with artifact locations and verification evidence. |
| Session | A running native harness incarnation in its own tmux session, with an explicit actor and canonical project identity. |
| Orchestrator | The user-facing control-plane conversation. It establishes Pillars and their public contracts and coordinates the overall project. It does not replace workers' ledger loops. |

## Invariants

- Pillars are direct children and peers. No departments, intermediate hierarchy,
  or nested Pillars. Arbitrary depth is allowed inside one Pillar.
- Presence of `pillar.toml` declares a boundary, including when invalid. Validation
  errors do not silently merge that boundary into another Pillar.
- Every valid Pillar assigns at least one template-based Harness Agent. A manager
  is optional; at most one agent has the Project Manager role in a Pod.
- Agent roots cannot overlap or grant ownership of a contract, schema, template,
  or ledger. Consumers use public outputs and declared read context.
- Workers see their own ledger view. The PM sees the ledgers across its own Pod.
  These are context/API boundaries; the host's permissions govern actual OS access.
- The worker reads a task, claims it, delivers its required artifacts, and records
  completion or blockage itself. It continues with the next ready task. A PM
  tends assignments and responds to blocked state; no separate acceptance queue
  is imposed on the worker loop.
- Interfaces and executable fixtures exist first. `interface-ready` does not
  assert implementation availability. `implementation-ready` requires actual
  outputs and validation.
- Pillar-authored material belongs in its own document/workspace space. Runtime
  execution copies and logs are external. No memory backend or commands are
  implemented in this revision.
