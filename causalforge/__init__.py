"""CausalForge — AI Failure Causality Explorer.

CausalForge ingests execution events and their dependencies, assembles a
directed causal graph, and ranks the nodes most likely to be the *origin* of
an incident. The scoring model blends three signals:

* **Temporal propagation** — blame flows backward from failing sinks toward
  upstream causes, attenuated by an exponential time-decay kernel so that
  events which finished long before a downstream failure are down-weighted.
* **Error evidence** — locally observed error weight (exception counts, log
  severity, retry storms) is folded into each node's suspicion score.
* **Blast radius** — nodes that can influence a larger downstream subgraph are
  boosted, because a fault there explains more of the observed damage.

The package is dependency-free and relies only on the Python standard library.
It mirrors the ranking core implemented in ``engine/causal_rank.cpp``.
"""

from __future__ import annotations

from .model import Node, Edge, Incident, Suspect
from .graph import CausalGraph
from .rank import rank_incident, RankConfig
from .blast import blast_radius, reachable_set
from .timeline import build_timeline, TimelineEntry
from .report import render_markdown, render_json
from .ingest import load_incident, parse_events

__all__ = [
    "Node",
    "Edge",
    "Incident",
    "Suspect",
    "CausalGraph",
    "rank_incident",
    "RankConfig",
    "blast_radius",
    "reachable_set",
    "build_timeline",
    "TimelineEntry",
    "render_markdown",
    "render_json",
    "load_incident",
    "parse_events",
]

__version__ = "0.5.0"
