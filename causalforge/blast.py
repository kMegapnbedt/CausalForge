"""Blast-radius computation.

The blast radius of a node is the set of downstream nodes it can influence via
directed causal edges. It answers "if this node is the culprit, how much of the
observed incident does it explain?". A larger radius makes a node a more
economical explanation and boosts its ranking score.
"""

from __future__ import annotations

from typing import Set

from .graph import CausalGraph


def reachable_set(graph: CausalGraph, start: str) -> Set[str]:
    """Return every node reachable downstream from ``start`` (excluding itself).
