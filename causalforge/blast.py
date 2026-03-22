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

    Uses iterative depth-first traversal with a visited guard so cyclic graphs
    terminate.
    """
    if not graph.has_node(start):
        return set()
    seen: Set[str] = set()
    stack = [start]
    visited_start = False
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        if visited_start:
            seen.add(cur)
        visited_start = True
        for edge in graph.out_edges(cur):
            if edge.dst not in seen and edge.dst != start:
                stack.append(edge.dst)
    seen.discard(start)
    return seen


def blast_radius(graph: CausalGraph, start: str) -> int:
    """Number of downstream-reachable nodes from ``start``."""
    return len(reachable_set(graph, start))


def weighted_blast(graph: CausalGraph, start: str) -> float:
    """Coupling-weighted blast radius.

    Instead of counting nodes equally, sum the product of edge couplings along
    the shortest discovered path. This rewards culprits that are *tightly*
    coupled to a large downstream region.
    """
    if not graph.has_node(start):
        return 0.0
    best: dict = {start: 1.0}
    stack = [start]
    while stack:
        cur = stack.pop()
        base = best.get(cur, 0.0)
        for edge in graph.out_edges(cur):
            propagated = base * max(0.0, min(1.0, edge.coupling))
            if propagated > best.get(edge.dst, 0.0) + 1e-9:
                best[edge.dst] = propagated
                stack.append(edge.dst)
    return sum(v for k, v in best.items() if k != start)
