# Research and Analysis example

Copy this entire directory to start an ordinary filesystem project. Both peer
Pillars begin interface-ready and return explicit unavailable fixtures. No real
research, analysis, or completed ledger is included.

`research/pillar.toml` describes the research output. Its Pod has a researcher,
a reviewer, and an optional Project Manager. The sample PM plan at
`research/fixtures/work-plan.json` assigns independent work to the two workers.
Supply a research question in task instructions before dispatching them.

`analysis/pillar.toml` is a separate capability boundary with one analyst and no
manager. It declares consumption of research's current contract. This illustrates
cross-Pillar contract discovery without exposing another Pod's task ledgers.

From the Autodev checkout, validate this copy, verify both interfaces, and import
the plan using `task import WORKSPACE WORKSPACE/research/fixtures/work-plan.json
--actor research--manager`. Revise its tasks to include the actual question.
Only launch providers when ready to run work. Runtime state stays outside this
folder; canonical per-agent ledgers are created within each Pillar on use.
