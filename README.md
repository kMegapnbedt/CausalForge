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
   couplings) are collected as non-fatal warnings.

2. **Seed.** Every node injects blame proportional to its status severity:
   `failed = 1.0`, `degraded = 0.4`, `ok = 0.0`. This is the heat the forge
   applies.

3. **Propagate.** For a fixed number of damped rounds, blame flows from each
   node to its *upstream* neighbours along incoming edges. Every transfer is
   attenuated by (a) the edge coupling, (b) a temporal half-life kernel over the
   causal time gap, and (c) a global damping factor. Because the round count is
   fixed, the pass terminates without needing a convergence oracle and stays
   deterministic.

4. **Fuse and rank.** Each node's propagated blame is added to its local error
   weight, then scaled by a blast-radius boost. Suspects are sorted by score
   descending (ties broken by node id) and each gets a plain-language rationale.

---

## Architecture

```
                        ┌──────────────────────────────────────────┐
   incident.json ─────► │  ingest.py                                 │
   or .events           │    load_incident / parse_events            │
                        │      → Incident{Node[], Edge[]}            │
                        └───────────────────┬────────────────────────┘
                                            │
                                            ▼
                        ┌──────────────────────────────────────────┐
                        │  graph.py — CausalGraph                    │
                        │    out_adj / in_adj / topo / validate      │
                        └───────────────────┬────────────────────────┘
                                            │
                     ┌──────────────────────┼───────────────────────┐
                     ▼                       ▼                       ▼
          ┌────────────────┐      ┌──────────────────┐    ┌──────────────────┐
          │ rank.py         │      │ blast.py          │   │ timeline.py       │
          │  _propagate     │◄────►│  reachable_set    │   │  build_timeline   │
          │  _rationale     │      │  weighted_blast   │   │  timeline_text    │
          │  rank_incident  │      └──────────────────┘    └──────────────────┘
          └───────┬─────────┘
                  │  Suspect[]
                  ▼
          ┌────────────────┐          ┌────────────────────────────────────┐
          │ report.py       │          │ engine/causal_rank.cpp (C++17)      │
          │  render_markdown│          │  independent, identical scoring     │
          │  render_json    │          │  reads the compact event stream     │
          └───────┬─────────┘          └────────────────────────────────────┘
                  │
                  ▼
        Markdown / JSON investigation
```

The Python package is the reference implementation and the source of truth for
the schema. The C++ core is a self-contained mirror of the scoring math,
designed to be embedded in latency-sensitive contexts or invoked from a shell
pipeline. Keeping the two in lockstep is intentional: the `.events` fixture is
the shared contract, and both engines must rank it identically.

---

## The scoring model in depth

The final score for a node is:

```
score(n) = ( blame(n) + error_weight(n) ) * radius_factor(n)
```

### Temporal blame propagation

Blame starts at the failing sinks and flows backward. During a propagation
round, a node `n` with current blame `b` sends to each upstream neighbour `u`
(connected by edge `u → n` with coupling `c`):

```
transfer = b * clamp(c, 0, 1) * kernel(u.t_end, n.t_start) * damping
```

where the temporal kernel is an exponential half-life decay over the causal
gap `dt = n.t_start - u.t_end`:

```
kernel(u.t_end, n.t_start) = exp(-ln(2) * dt / half_life)      if dt >= 0
                           = late_floor                        if dt <  0
```

The intuition: if an upstream event finished *just before* a downstream failure
started, the kernel is near `1.0` — strong causal support. If it finished a long
time before, the kernel decays toward zero. If it finished *after* the
downstream event even started, it is an implausible cause and receives only a
small `late_floor` weight (default `0.15`).

Damping (`0.55` by default) shrinks each hop so blame cannot amplify without
bound as it travels through long chains. The pass runs a fixed number of
`rounds` (default `6`), which is comfortably more than the depth of typical
incident graphs.

### Error-evidence fusion

Propagated blame captures *structural* suspicion — "downstream things failed and
you are upstream of them." But a node may also carry *direct* evidence:
exception counts, log severity, retry storms, elevated 5xx rates. That is the
`error_weight`, and it is added to the propagated blame before scaling. A node
with both high blame and high local evidence is the strongest possible suspect.

### Blast-radius boost

Given two nodes with equal fused suspicion, the one that can influence more of
the graph is the more *economical* explanation — it accounts for more of the
observed damage with a single cause. CausalForge boosts by:

```
radius_factor(n) = 1 + ln(1 + blast_radius(n)) * radius_gain
```

The logarithm keeps the boost gentle: doubling the reachable set does not double
the score. `radius_gain` defaults to `0.25`.

### Determinism

Every coefficient is fixed, the round count is fixed, and the final sort breaks
ties by node id. Run the same incident a thousand times and you get the same
ranking a thousand times. This is a deliberate design choice — a root-cause tool
that gives different answers on reruns is worse than no tool at all.

---

## Incident schema

The canonical input is a JSON object. See `docs/schema.md` for the field-by-field
reference. In brief:

```json
{
  "id": "INC-2026-0417",
  "title": "Checkout completion errors after retriever timeout",
  "origin_ts": "2026-04-17T09:14:22Z",
  "summary": "Human-readable one-paragraph context.",
  "nodes": [
    {
      "id": "cache.warmer",
      "kind": "job",
      "t_start": 0.0,
      "t_end": 8.5,
      "status": "failed",
      "error_weight": 1.4,
      "labels": { "team": "platform" }
    }
  ],
  "edges": [
    { "src": "cache.warmer", "dst": "vector.retriever", "coupling": 0.9, "relation": "warms" }
  ]
}
```

- `t_start` / `t_end` are seconds relative to the incident origin.
- `status` is one of `ok`, `degraded`, `failed`.
- `error_weight` is any non-negative number; scale it however your telemetry
  makes sense, the model only cares about relative magnitude.
- `coupling` is `0..1`; `relation` is a free-form label carried into reports.

---

## The compact event stream

For shell pipelines and the C++ engine, CausalForge also speaks a
whitespace-delimited line format:

```
# comments start with hash
N <id> <t_start> <t_end> <status_code> <error_weight>
E <src> <dst> <coupling>
```

where `status_code` is `0` (ok), `1` (degraded), `2` (failed). This is the exact
grammar the C++ core parses, and the Python package can read it with
`--events` or produce it with `causalforge convert`. The bundled
`examples/incident_checkout.events` is the same incident as the JSON fixture,
which is why both engines agree.

---

## CLI reference and recipes

```
python -m causalforge <command> <input> [options]
```

| Command    | Purpose                                                     |
| ---------- | ----------------------------------------------------------- |
| `analyze`  | Rank likely root causes and render a report                 |
| `timeline` | Reconstruct and print the incident timeline                 |
| `blast`    | Report the blast radius of a single node                    |
| `convert`  | JSON → compact stream, or compact stream → JSON analysis    |
| `validate` | Structural validation and graph statistics                  |

Global options common to every command: `--events` (treat input as the compact
stream) and `-o/--output FILE` (write to a file instead of stdout).

**Recipe — full investigation to a file**

```bash
python -m causalforge analyze examples/incident_checkout.json \
  --format markdown -o postmortem.md
```

**Recipe — tune the propagation for a bursty incident**

```bash
python -m causalforge analyze examples/incident_checkout.json \
  --half-life 2.5 --damping 0.7 --rounds 8
```

A shorter half-life makes the model more sensitive to tight temporal
correlation; higher damping lets blame travel further up long chains.

**Recipe — feed the C++ core from the JSON incident**

```bash
python -m causalforge convert examples/incident_checkout.json > incident.events
./causal_rank incident.events
```

**Recipe — CI gate on structural health**

```bash
python -m causalforge validate incident.json || exit 1
```

`validate` exits non-zero when it finds dangling edges, self-loops, or
out-of-range couplings, so it drops cleanly into a pre-merge check.

---

## The C++ ranking core

`engine/causal_rank.cpp` is a single self-contained translation unit. It reads
the compact stream from a file argument or stdin, builds the same graph, runs
the same backward propagation and blast-radius passes, and prints a ranked
table. It uses only the C++ standard library.

```bash
# Optimised build
g++ -std=c++17 -Wall -Wextra -pedantic -O2 -o causal_rank engine/causal_rank.cpp

# Syntax-only validation (used in CI)
g++ -std=c++17 -Wall -Wextra -pedantic -fsyntax-only engine/causal_rank.cpp

# Pipe an incident in
cat examples/incident_checkout.events | ./causal_rank
```

The core exists so the scoring math can be embedded where a Python interpreter
is inconvenient — an agent runtime, a sidecar, a build hook. Because it shares
the fixture with the Python package, any divergence between the two shows up
immediately as a different ranking on the same input.

---

## Reports and artefacts

**Markdown investigation** (`--format markdown`, the default) contains:

- an incident header with the primary suspect,
- a ranked suspect table (score, blame, error weight, blast radius),
- a "why these suspects" section with per-node rationale,
- a timeline with an ASCII gantt strip,
- any structural warnings.

**JSON investigation** (`--format json`) contains the same information in a
machine-readable shape: `incident` metadata, `primary_suspect`, the full
`suspects` array with rationale, the ordered `timeline`, and `warnings`. Feed it
to a dashboard, an alerting rule, or an incident bot.

---

## Operations playbook

- **Ingesting from tracing systems.** Map each span to a `Node` (span name →
  `id`, span kind → `kind`, start/end → `t_start`/`t_end`) and each parent/child
  or client/server relationship to an `Edge`. Derive `error_weight` from span
  status and log volume; set `status` from span error flags.
- **Choosing couplings.** Synchronous, blocking calls are close to `1.0`.
  Asynchronous best-effort emissions (fire-and-forget queues, metrics) are
  closer to `0.1–0.3`. Coupling is the single most impactful knob on ranking
  quality.
- **Reading the score.** A high score with high blast radius and high error
  weight is a confident call. A high score driven purely by blast radius with
  near-zero blame is a *structural* suspect — plausible topologically but
  lacking evidence; treat it as a lead, not a verdict.
- **Reproducibility.** Because runs are deterministic, archive the incident file
  alongside the report. Re-running later reproduces the exact ranking, which is
  invaluable during a postmortem review.

---

## Extension seams

CausalForge is small on purpose, and the seams are explicit:

- **New status vocabulary** — extend `_STATUS_SEVERITY` in `model.py`.
- **Alternative temporal kernels** — replace `_temporal_kernel` in `rank.py`
  (e.g. a Gaussian window instead of exponential decay). The signature is
  stable, so the rest of the pipeline is unaffected.
- **New evidence signals** — add fields to `Node` and fold them into the fusion
  step in `rank_incident`.
- **New input adapters** — add a loader to `ingest.py` that returns an
  `Incident`; every downstream stage is format-agnostic.
- **New report formats** — add a `render_*` function in `report.py`; the CLI
  wires it in via a `--format` choice.
- **New blast metrics** — `blast.py` already offers node-count and
  coupling-weighted variants; add path-length or fan-out metrics alongside them.

---

## Design principles

1. **Deterministic or nothing.** A root-cause tool that flickers between answers
   erodes trust faster than being occasionally wrong.
2. **Transparent math over opaque models.** Every coefficient is visible and
   documented; a responder can audit exactly why a node ranked where it did.
3. **Zero dependencies.** Standard library only, on both sides. It runs anywhere
   Python 3.11 or a C++17 compiler runs.
4. **Two engines, one truth.** The shared fixture keeps Python and C++ honest.
5. **Reports are the product.** The scoring is a means; the investigation
   document is what a human actually uses.

See `DESIGN.md` and `ARCHITECTURE.md` for the deeper rationale.

---

## Repository layout

```
causalforge/
├── causalforge/            # Python package (reference implementation)
│   ├── __init__.py         # public API + version
│   ├── __main__.py         # python -m causalforge
│   ├── cli.py              # argparse CLI (analyze/timeline/blast/convert/validate)
│   ├── model.py            # Node / Edge / Incident / Suspect dataclasses
│   ├── graph.py            # CausalGraph: adjacency, topo order, validation
│   ├── ingest.py           # JSON and compact-stream parsers
│   ├── rank.py             # scoring model: propagation + fusion + boost
│   ├── blast.py            # blast-radius (count + coupling-weighted)
│   ├── timeline.py         # timeline reconstruction + ASCII gantt
│   └── report.py           # Markdown / JSON investigation renderers
├── engine/
│   └── causal_rank.cpp     # portable C++17 ranking core (mirror)
├── examples/
│   ├── incident_checkout.json     # canonical JSON incident fixture
│   └── incident_checkout.events   # same incident, compact stream
├── docs/
│   ├── assets/             # animated SVG identity assets
│   ├── schema.md           # incident schema reference
│   ├── scoring.md          # scoring model reference
│   └── cli.md              # command reference
└── (root materials: LICENSE, CHANGELOG, ROADMAP, ...)
```

---

## Glossary

- **Blame** — accumulated, backward-propagated suspicion originating at failing
  sinks and decayed by time and coupling.
- **Blast radius** — the set (or count) of downstream nodes a given node can
  influence via directed edges.
- **Causal graph** — the directed graph of execution events and their
  dependency edges.
- **Coupling** — `0..1` strength of causal influence along an edge.
- **Damping** — per-hop attenuation applied during propagation to prevent
  runaway amplification.
- **Error weight** — direct, local evidence that a node misbehaved.
- **Half-life** — the time gap at which the temporal kernel halves; controls how
  quickly stale upstream events are discounted.
- **Node / event** — one execution unit (service call, tool invocation, job).
- **Primary suspect** — the top-ranked node; the tool's best single-cause
  explanation.
- **Sink** — a node with no outgoing edges (a leaf effect, e.g. the frontend).
- **Source** — a node with no incoming edges (a potential ultimate cause).
- **Suspect** — a ranked root-cause candidate with score, blame, radius and
  rationale.
- **Temporal kernel** — the exponential decay function over the causal time gap.

---

CausalForge is released under the Apache License 2.0. See `LICENSE`,
`CONTRIBUTING.md`, and `SECURITY.md` for the details of contributing and
reporting issues.
