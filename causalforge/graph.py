"""Causal graph structure and traversal helpers.

The :class:`CausalGraph` wraps an :class:`~causalforge.model.Incident` with the
adjacency indices the ranking and blast-radius passes need. It is deliberately
small: no external graph library, just dictionaries of adjacency lists.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Set, Tuple

from .model import Edge, Incident, Node


class CausalGraph:
    """A directed graph view over an incident.

    Cycles are permitted (retry loops, mutual timeouts). All traversals guard
