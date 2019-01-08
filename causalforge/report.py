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
