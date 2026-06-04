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
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        kind = parts[0]
        if kind == "N":
            if len(parts) != 6:
                raise ValueError(f"malformed N record at line {lineno}")
            _, nid, ts, te, status_code, ew = parts
            nodes.append(
                Node(
                    id=nid,
                    t_start=float(ts),
                    t_end=float(te),
                    status=_STATUS_FROM_CODE.get(int(status_code), "ok"),
                    error_weight=float(ew),
                )
            )
        elif kind == "E":
            if len(parts) != 4:
                raise ValueError(f"malformed E record at line {lineno}")
            _, src, dst, coupling = parts
            edges.append(Edge(src=src, dst=dst, coupling=float(coupling)))
        else:
            raise ValueError(f"unknown record kind '{kind}' at line {lineno}")
    return Incident(id="stream", title="Streamed incident", nodes=nodes, edges=edges)


def to_events(incident: Incident) -> str:
    """Serialise an incident back into the compact line format."""
    code = {"ok": 0, "degraded": 1, "failed": 2}
    lines = ["# CausalForge compact event stream"]
    for n in incident.nodes:
        lines.append(
            f"N {n.id} {n.t_start:g} {n.t_end:g} "
            f"{code.get(n.status, 0)} {n.error_weight:g}"
        )
    for e in incident.edges:
        lines.append(f"E {e.src} {e.dst} {e.coupling:g}")
    return "\n".join(lines) + "\n"
