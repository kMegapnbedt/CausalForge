"""Incident ingestion.

Two input formats are supported, both parsed with the standard library only:

* **JSON incident** (``docs/schema.md``) — the canonical, rich format loaded by
  :func:`load_incident`.
* **Compact event log** — one event per line, shared with the C++ engine, parsed
  by :func:`parse_events`. Handy for streaming from shell pipelines.
"""

from __future__ import annotations

import json
from typing import List

from .model import Edge, Incident, Node


def load_incident(path: str) -> Incident:
    """Load a JSON incident file into an :class:`Incident`."""
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return incident_from_dict(raw)


def incident_from_dict(raw: dict) -> Incident:
    nodes = [
        Node(
            id=str(n["id"]),
            kind=str(n.get("kind", "event")),
            t_start=float(n.get("t_start", 0.0)),
            t_end=float(n.get("t_end", n.get("t_start", 0.0))),
            status=str(n.get("status", "ok")),
            error_weight=float(n.get("error_weight", 0.0)),
            labels={str(k): str(v) for k, v in n.get("labels", {}).items()},
        )
        for n in raw.get("nodes", [])
    ]
    edges = [
        Edge(
            src=str(e["src"]),
            dst=str(e["dst"]),
            coupling=float(e.get("coupling", 1.0)),
            relation=str(e.get("relation", "calls")),
        )
        for e in raw.get("edges", [])
    ]
    return Incident(
        id=str(raw.get("id", "incident")),
        title=str(raw.get("title", "Untitled incident")),
        nodes=nodes,
        edges=edges,
        origin_ts=raw.get("origin_ts"),
        summary=str(raw.get("summary", "")),
    )


_STATUS_FROM_CODE = {0: "ok", 1: "degraded", 2: "failed"}


def parse_events(text: str) -> Incident:
    """Parse the compact line format shared with the C++ engine.

    Grammar (whitespace separated)::

        N <id> <t_start> <t_end> <status_code> <error_weight>
        E <src> <dst> <coupling>

    Lines beginning with ``#`` and blank lines are ignored.
    """
    nodes: List[Node] = []
    edges: List[Edge] = []
