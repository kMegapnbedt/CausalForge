"""Immutable-ish data model for CausalForge.

These dataclasses are the vocabulary the rest of the package speaks in. They
map one-to-one onto the JSON incident schema documented in ``docs/schema.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

# Status vocabulary. Kept as plain strings on the wire but normalised to these
# canonical tokens once inside the engine.
STATUS_OK = "ok"
STATUS_DEGRADED = "degraded"
STATUS_FAILED = "failed"

_STATUS_SEVERITY = {
    STATUS_OK: 0.0,
    STATUS_DEGRADED: 0.4,
    STATUS_FAILED: 1.0,
}


@dataclass
class Node:
    """A single execution event participating in an incident.

    Attributes
    ----------
    id:
        Stable unique identifier (e.g. ``retriever.fetch`` or ``svc-checkout``).
    kind:
        Free-form category used for grouping in reports (``service``,
        ``tool_call``, ``model``, ``queue`` ...).
    t_start / t_end:
        Wall-clock offsets in seconds relative to the incident origin. Used by
        the temporal propagation kernel.
    status:
        One of ``ok``, ``degraded`` or ``failed``.
    error_weight:
        Local error evidence in the range ``[0, +inf)``. Higher means more
        direct proof this node misbehaved (stack traces, 5xx counts, ...).
    labels:
        Arbitrary metadata carried through to reports untouched.
    """

    id: str
    kind: str = "event"
    t_start: float = 0.0
    t_end: float = 0.0
    status: str = STATUS_OK
    error_weight: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)

    @property
    def severity(self) -> float:
        """Numeric severity derived from :attr:`status`."""
        return _STATUS_SEVERITY.get(self.status, 0.0)

    @property
    def duration(self) -> float:
        return max(0.0, self.t_end - self.t_start)


@dataclass
class Edge:
    """A directed causal dependency: ``src`` can influence ``dst``.

    ``coupling`` in ``[0, 1]`` expresses how strongly a fault in ``src`` is
    expected to manifest in ``dst``. A synchronous, blocking call is close to
    ``1.0``; a best-effort fire-and-forget notification is closer to ``0.1``.
    """

    src: str
    dst: str
    coupling: float = 1.0
    relation: str = "calls"


@dataclass
class Incident:
    """A complete incident: metadata plus the graph payload."""

    id: str
    title: str
    nodes: List[Node] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)
    origin_ts: Optional[str] = None
    summary: str = ""

    def node_index(self) -> Dict[str, Node]:
        return {n.id: n for n in self.nodes}


@dataclass
class Suspect:
    """A ranked root-cause candidate produced by the engine."""

    node_id: str
    score: float
    blame: float
    error_weight: float
    blast_radius: int
    rationale: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "node_id": self.node_id,
            "score": round(self.score, 4),
            "blame": round(self.blame, 4),
            "error_weight": round(self.error_weight, 4),
            "blast_radius": self.blast_radius,
            "rationale": list(self.rationale),
        }
