# CausalForge

**AI Failure Causality Explorer** — ingest execution events and their
dependencies, forge them into a causal graph, and rank the events most likely
to be the *origin* of an incident. CausalForge propagates blame backward from
failing sinks through a temporal decay kernel, fuses in local error evidence,
weighs each candidate by its blast radius, and exports incident timelines plus
Markdown and JSON investigations you can paste straight into a postmortem.

![CausalForge causal graph](docs/assets/forge-graph.svg)

CausalForge is built for the moment after the pager goes off: you have a pile
of spans, logs, and service edges, and you need to know *which node started the
fire* before you know *why*. It is deliberately small, deterministic, and
dependency-free — the Python package uses only the standard library, and the
C++ ranking core is a single portable `-std=c++17` translation unit. Nothing
phones home, nothing needs a cluster, and the same incident always produces the
same ranking.

---

## Table of contents

- [Why CausalForge](#why-causalforge)
- [The forge metaphor](#the-forge-metaphor)
- [Quickstart](#quickstart)
- [The ranking pipeline](#the-ranking-pipeline)
- [Architecture](#architecture)
- [The scoring model in depth](#the-scoring-model-in-depth)
- [Incident schema](#incident-schema)
- [The compact event stream](#the-compact-event-stream)
- [CLI reference and recipes](#cli-reference-and-recipes)
- [The C++ ranking core](#the-c-ranking-core)
- [Reports and artefacts](#reports-and-artefacts)
- [Operations playbook](#operations-playbook)
- [Extension seams](#extension-seams)
- [Design principles](#design-principles)
- [Repository layout](#repository-layout)
- [Glossary](#glossary)

---

## Why CausalForge

Distributed AI systems fail in *chains*. A stalled cache warmer slows a vector
retriever, which slows an orchestrator, which times out a payment call, which
surfaces as a failed checkout. The symptom (checkout failed) is loud and far
from the cause (cache warmer stalled). Human responders instinctively walk the
call graph backward in time — CausalForge encodes that instinct into a scoring
model you can run in a fraction of a second.

Most tracing tools show you *what happened*. CausalForge answers a sharper
question: **given everything that happened, which single event best explains
the damage?** It does this without machine learning, without a training set,
and without external services. The model is transparent enough to audit line by
line, which matters when a ranking is going to influence a postmortem.

Concretely, CausalForge gives you:

- A **deterministic root-cause ranking** with a per-suspect rationale.
- A **blast-radius estimate** for every node — how much of the incident each
  candidate could explain.
- A **reconstructed timeline** with an ASCII gantt strip.
- **Markdown and JSON investigation exports** for humans and automation.
- Two interchangeable engines (Python and C++) that produce identical rankings,
  so you can embed the fast path wherever you need it.

---

## The forge metaphor

CausalForge treats an incident like raw material passing through a forge. Cold
events go in; heat (blame) is applied from the failures; the material is
hammered across four stations; and a ranked, glowing suspect comes out the far
end. The visual identity — ember orange on graphite — runs through every
artefact the tool emits.

![Ranking pipeline](docs/assets/ranking-pipeline.svg)

The four stations map exactly onto the code:

| Station    | Module                       | What it does                                   |
| ---------- | ---------------------------- | ---------------------------------------------- |
