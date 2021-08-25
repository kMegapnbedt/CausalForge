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
