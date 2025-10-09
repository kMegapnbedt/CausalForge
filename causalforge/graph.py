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

    def validate(self) -> List[str]:
        """Return a list of human-readable structural warnings.

        Non-fatal: dangling edges, self loops, and orphan nodes are reported
        but the graph still functions.
        """
        warnings: List[str] = []
        for edge in self.incident.edges:
            if edge.src not in self._nodes:
                warnings.append(f"edge references unknown source '{edge.src}'")
            if edge.dst not in self._nodes:
                warnings.append(f"edge references unknown target '{edge.dst}'")
            if edge.src == edge.dst:
                warnings.append(f"self-loop on node '{edge.src}'")
            if not (0.0 <= edge.coupling <= 1.0):
                warnings.append(
                    f"coupling out of range on {edge.src}->{edge.dst}: {edge.coupling}"
                )
        return warnings

    def topo_order(self) -> List[str]:
        """A best-effort topological order.

        On cyclic graphs the remaining nodes are appended in id order after the
        acyclic prefix so callers always receive every node exactly once.
        """
        indeg: Dict[str, int] = {nid: 0 for nid in self._nodes}
        for edge in self.incident.edges:
            if edge.dst in indeg:
                indeg[edge.dst] += 1
        queue = sorted([nid for nid, d in indeg.items() if d == 0])
        order: List[str] = []
        seen: Set[str] = set()
        while queue:
            nid = queue.pop(0)
            if nid in seen:
                continue
            seen.add(nid)
            order.append(nid)
            children = sorted(e.dst for e in self._out.get(nid, []))
            for child in children:
                if child in indeg:
                    indeg[child] -= 1
                    if indeg[child] == 0 and child not in seen:
                        queue.append(child)
            queue.sort()
        for nid in sorted(self._nodes):
            if nid not in seen:
                order.append(nid)
        return order

    def edge_list(self) -> List[Tuple[str, str, float]]:
        return [(e.src, e.dst, e.coupling) for e in self.incident.edges]
