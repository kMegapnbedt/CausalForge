"""Incident timeline reconstruction.

Turns the unordered node set into a chronologically sorted list of events with
relative offsets, gap markers, and a compact ASCII gantt strip suitable for
embedding in Markdown reports.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .graph import CausalGraph


@dataclass
class TimelineEntry:
    node_id: str
    t_start: float
    t_end: float
    status: str
    kind: str
    lane: str  # ascii gantt strip for this event


def _lane(t_start: float, t_end: float, span_start: float, span_end: float,
          width: int = 40) -> str:
    total = max(1e-6, span_end - span_start)
    lead = int(round((t_start - span_start) / total * width))
    length = max(1, int(round((t_end - t_start) / total * width)))
    lead = max(0, min(width, lead))
    length = max(1, min(width - lead, length))
    return " " * lead + "#" * length


def build_timeline(graph: CausalGraph) -> List[TimelineEntry]:
    """Return events ordered by start time, then id."""
    nodes = sorted(graph.nodes(), key=lambda n: (n.t_start, n.id))
    if not nodes:
        return []
    span_start = min(n.t_start for n in nodes)
    span_end = max(n.t_end for n in nodes)
    entries: List[TimelineEntry] = []
    for n in nodes:
        entries.append(
            TimelineEntry(
                node_id=n.id,
                t_start=n.t_start,
                t_end=n.t_end,
                status=n.status,
                kind=n.kind,
                lane=_lane(n.t_start, n.t_end, span_start, span_end),
            )
        )
    return entries


def timeline_text(entries: List[TimelineEntry]) -> str:
    """Render a timeline as an aligned monospace block."""
    if not entries:
        return "(empty timeline)"
    width = max(len(e.node_id) for e in entries)
    lines = []
    for e in entries:
        marker = {"failed": "X", "degraded": "!", "ok": " "}.get(e.status, " ")
        lines.append(
            f"{e.node_id.ljust(width)} [{marker}] "
            f"{e.t_start:6.2f}-{e.t_end:6.2f}s |{e.lane}"
        )
    return "\n".join(lines)
