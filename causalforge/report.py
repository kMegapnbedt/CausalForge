"""Investigation report rendering.

Produces two artefacts from a ranked incident:

* **Markdown** — a human-readable investigation with a suspect table, timeline
  strip, and per-suspect rationale, ready to paste into a postmortem doc.
* **JSON** — a machine-readable investigation for downstream automation.
"""

from __future__ import annotations

import json
from typing import Dict, List

from .graph import CausalGraph
from .model import Incident, Suspect
from .timeline import build_timeline, timeline_text


def render_json(incident: Incident, graph: CausalGraph,
                suspects: List[Suspect]) -> str:
    timeline = build_timeline(graph)
    payload = {
        "incident": {
            "id": incident.id,
            "title": incident.title,
            "origin_ts": incident.origin_ts,
            "summary": incident.summary,
            "node_count": graph.order(),
            "edge_count": graph.size(),
        },
        "primary_suspect": suspects[0].node_id if suspects else None,
        "suspects": [s.to_dict() for s in suspects],
        "timeline": [
            {
                "node_id": e.node_id,
                "t_start": e.t_start,
                "t_end": e.t_end,
                "status": e.status,
                "kind": e.kind,
            }
            for e in timeline
        ],
        "warnings": graph.validate(),
