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
