---
slug: ship-financial-research-models-client-packs-with-autodev
title: How we ship research, financial models, and client packs with Autodev
description: OpenAI’s ChatGPT for Financial Services demos three jobs. Here’s the Autodev playbook to ship them as production systems — data contracts, model pipelines, client-pack generation, review gates.
canonical_proposed: /blog/ship-financial-research-models-client-packs-with-autodev
status: draft-for-cos-publish
seed: https://x.com/OpenAI/status/2098118191029624911
voice_ok: true
author: Logan Robbins
riff: how-to from seed outcomes — not contrast, not staffing thesis
replaces_flywheel: chatgpt-for-finance-wont-kill-the-staffing-cut
---

# How we ship research, financial models, and client packs with Autodev

OpenAI’s ChatGPT for Financial Services pitch names three jobs: **develop research**, **build financial models**, and **create customized client materials**. Fine product demo. The question that matters for a shop that actually ships: how do you turn those three into **production systems** — versioned, gated, owned by humans with judgment — instead of a chat tab that regenerates the deck every Tuesday.

This is the Autodev playbook. Onshore hybrid human–AI staff-aug. Hours/scope agreed ahead. Invoice at Autodev UAT. Change orders before start. CoS-routed Grok Bots execute inside contracts; the human still owns architecture.

## Diagram (one page)

```
seed outcomes (OpenAI Finance)
        │
        ├─ research ──► data contracts + sources of truth + citation gates
        ├─ models   ──► model pipeline + assumptions ledger + replay tests
        └─ client packs ──► pack templates + review queue + export lock
                │
                ▼
        Autodev UAT milestone → invoice → change order if scope moves
```

Same three outcomes. Different machine: **system under review**, not a Work SKU session.

## 1. Research as a system

**Outcome:** analysts get research that cites sources, not vibes.

1. **Data contracts first.** Name the feeds (market data, filings, internal books). Schema, refresh cadence, who owns the break when a field dies.
2. **Source-of-truth map.** Every claim in the brief points at a row, filing, or prior model — not “Astra said so.”
3. **Citation gate.** CoS routes a Research-style bot to draft; a human reviewer refuses publish without citations. No citation → no ship.
4. **Artifact, not chat.** Output lands as a dated MD/PDF under a project ledger. Chat is the scratchpad; the ledger is the product.

Autodev beat: bots draft and chase links; humans refuse garbage; UAT is “brief is citeable,” not “looks smart in the tab.”

## 2. Financial models as a pipeline

**Outcome:** a model you can replay, not a spreadsheet that only works on the author’s laptop.

1. **Assumptions ledger.** Rates, growth, margins, scenarios — versioned. Change an assumption → new run id.
2. **Pipeline, not paste.** Inputs → transforms → outputs with a single command (or bot job). No silent Excel macros.
3. **Replay tests.** Last week’s inputs produce last week’s outputs within tolerance. Fail the gate if they don’t.
4. **Owner stamp.** Named human signs the model for client use. Bots don’t “own” P&L.

Autodev beat: Engineering-shaped bots build the harness; the scarce thing stays scarce — judgment on which assumptions are allowed in the building.

## 3. Client materials as a pack factory

**Outcome:** customized client packs that match the approved research + model — not a fresh hallucination per meeting.

1. **Template lock.** Slide/memo skeleton owned by the firm. Style and forbidden claims list live next to it.
2. **Bind to artifacts.** Pack pulls from the research ledger + model run id. If either moves, pack regen is a change order, not a vibe edit.
3. **Review queue.** CoS routes Demand/Offer-class polish only after Research + model gates pass. Order matters.
4. **Export lock.** Final PDF/PPTX stamped with run ids. Client gets a receipt, not “we regenerated it live.”

Autodev beat: the factory is the product. The chat demo is the brochure.

## How Autodev runs the loop

| Role | Job on this playbook |
|---|---|
| **Chief of Staff** | Front door. Routes. Refuses out-of-order handoffs. |
| **Research bot** | Drafts citeable research inside contracts. |
| **Demand / Offer bots** | Pack polish and client-facing copy after gates. |
| **Human owner** | Architecture, assumptions, sign-off, UAT. |

Four Autodev Grok Bots under one CoS is the harness — not the thesis of the post. The thesis is: **ship the three OpenAI Finance outcomes as systems**.

## What “done” means (UAT)

- Research brief: citeable, ledgered, reviewer-stamped  
- Model: assumptions ledger + replay green + owner stamp  
- Client pack: bound to both, export locked  

Miss any gate → not done. Don’t invoice. Don’t send to the client.

## Start

Want this loop scoped on your book: [autodev-team.com](https://autodev-team.com). Quote: `hello@autodev-team.com`.

Seed we derived from: [OpenAI — ChatGPT for Financial Services](https://x.com/OpenAI/status/2098118191029624911).
