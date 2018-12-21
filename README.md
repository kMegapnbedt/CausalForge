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
| Ingest     | `causalforge/ingest.py`      | Parse JSON or the compact stream into a graph  |
| Propagate  | `causalforge/rank.py`        | Flow temporal blame backward from failures     |
| Fuse       | `causalforge/rank.py`        | Combine blame, error evidence, blast radius    |
| Rank       | `causalforge/report.py`      | Sort suspects and render investigation output  |

---

## Quickstart

CausalForge requires only Python 3.11+. There is nothing to install; run it as a
module from the repository root.

```bash
# Rank root causes for the bundled incident, print a Markdown investigation
python -m causalforge analyze examples/incident_checkout.json

# Emit machine-readable JSON instead
python -m causalforge analyze examples/incident_checkout.json --format json

# Reconstruct just the timeline
python -m causalforge timeline examples/incident_checkout.json

# How much of the incident could this node explain?
python -m causalforge blast examples/incident_checkout.json --node cache.warmer

# Structural sanity check of the graph
python -m causalforge validate examples/incident_checkout.json
```

For the bundled `INC-2026-0417` incident, the primary suspect is
`cache.warmer` — a job that failed early, carried strong local error evidence,
and sits upstream of a five-node blast radius. That is the correct answer: the
loud symptom is a failed checkout, but the fire started at the cache warmer.

To build and run the C++ core against the same incident (expressed in the
compact stream format):

```bash
g++ -std=c++17 -Wall -Wextra -pedantic -O2 -o causal_rank engine/causal_rank.cpp
./causal_rank examples/incident_checkout.events
```

Both engines rank `cache.warmer` first with an identical score — that
cross-check is the tool's core correctness invariant.

---

## The ranking pipeline

An analysis run is a straight line through four passes. Each pass is pure: it
takes the previous state and returns new state, with no hidden globals, so the
whole pipeline is trivially reproducible.

1. **Ingest.** The incident file is parsed into `Node` and `Edge` dataclasses
   and wrapped in a `CausalGraph`, which builds forward and backward adjacency
   indices. Structural anomalies (dangling edges, self-loops, out-of-range
