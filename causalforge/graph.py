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
    against them with visited sets so the structure never loops forever.
    """

    def __init__(self, incident: Incident) -> None:
        self.incident = incident
        self._nodes: Dict[str, Node] = incident.node_index()
        self._out: Dict[str, List[Edge]] = {}
        self._in: Dict[str, List[Edge]] = {}
        for edge in incident.edges:
            self._out.setdefault(edge.src, []).append(edge)
            self._in.setdefault(edge.dst, []).append(edge)

    # -- basic accessors -------------------------------------------------
    def nodes(self) -> Iterable[Node]:
        return self._nodes.values()

    def node(self, node_id: str) -> Node:
        return self._nodes[node_id]

    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    def out_edges(self, node_id: str) -> List[Edge]:
        return self._out.get(node_id, [])

    def in_edges(self, node_id: str) -> List[Edge]:
        return self._in.get(node_id, [])

    def order(self) -> int:
        return len(self._nodes)

    def size(self) -> int:
        return len(self.incident.edges)

    # -- structural queries ----------------------------------------------
    def sinks(self) -> List[Node]:
        """Nodes with no outgoing edges (leaf effects)."""
        return [n for n in self._nodes.values() if not self._out.get(n.id)]

    def sources(self) -> List[Node]:
        """Nodes with no incoming edges (potential ultimate causes)."""
        return [n for n in self._nodes.values() if not self._in.get(n.id)]

    def failing(self) -> List[Node]:
        return [n for n in self._nodes.values() if n.severity > 0.0]
