"""Root-cause ranking engine.

This is the heart of CausalForge. Given a :class:`CausalGraph`, it produces a
ranked list of :class:`~causalforge.model.Suspect` candidates.

Algorithm overview
-------------------
1. **Seed blame.** Every failing/degraded node injects blame proportional to
   its severity (failed = 1.0, degraded = 0.4).
2. **Backward temporal propagation.** For a fixed number of damped rounds,
   blame flows from a node to its upstream neighbours along incoming edges. The
   transfer is ``blame * coupling * kernel(dt) * damping`` where ``kernel`` is
   an exponential half-life decay over the time gap ``downstream.start -
   upstream.end``. Upstream events that ended *after* the downstream event
   started receive only a small floor weight because they are unlikely causes.
3. **Evidence fusion.** Each node's propagated blame is combined with its local
   error weight.
4. **Blast-radius boost.** The fused suspicion is scaled by
   ``1 + ln(1 + radius) * radius_gain`` so culprits that explain more of the
   incident rank higher.

The pass is deterministic: a fixed round count and stable sort mean the same
incident always yields the same ranking.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List

from .blast import blast_radius
from .graph import CausalGraph
from .model import Suspect


@dataclass
class RankConfig:
    """Tunable coefficients for the ranking pass."""

    rounds: int = 6
    half_life: float = 5.0
    damping: float = 0.55
    radius_gain: float = 0.25
    late_floor: float = 0.15

    def validate(self) -> None:
        if self.rounds < 1:
            raise ValueError("rounds must be >= 1")
        if self.half_life <= 0:
            raise ValueError("half_life must be > 0")
        if not (0.0 < self.damping <= 1.0):
            raise ValueError("damping must be in (0, 1]")


def _temporal_kernel(upstream_end: float, downstream_start: float,
                     half_life: float, late_floor: float) -> float:
    """Exponential half-life decay over the causal time gap."""
    dt = downstream_start - upstream_end
    if dt < 0.0:
        return late_floor
    return math.exp(-math.log(2.0) * dt / half_life)


def _propagate(graph: CausalGraph, cfg: RankConfig) -> Dict[str, float]:
    """Run backward blame propagation and return per-node blame."""
    blame: Dict[str, float] = {}
    for node in graph.nodes():
        blame[node.id] = node.severity

    for _ in range(cfg.rounds):
        delta: Dict[str, float] = {}
        for node in graph.nodes():
            b = blame.get(node.id, 0.0)
            if b <= 1e-9:
                continue
            for edge in graph.in_edges(node.id):
                if not graph.has_node(edge.src):
                    continue
                up = graph.node(edge.src)
                kernel = _temporal_kernel(
                    up.t_end, node.t_start, cfg.half_life, cfg.late_floor
                )
                transfer = b * max(0.0, min(1.0, edge.coupling)) * kernel * cfg.damping
                delta[edge.src] = delta.get(edge.src, 0.0) + transfer
        for nid, d in delta.items():
            blame[nid] = blame.get(nid, 0.0) + d
    return blame


def _rationale(node, blame: float, radius: int) -> List[str]:
    reasons: List[str] = []
    if node.status == "failed":
        reasons.append("node reported a hard failure")
    elif node.status == "degraded":
        reasons.append("node reported degraded status")
    if node.error_weight >= 1.0:
        reasons.append(f"strong local error evidence ({node.error_weight:.2f})")
    elif node.error_weight > 0.0:
        reasons.append(f"local error evidence ({node.error_weight:.2f})")
    if blame >= 0.75:
        reasons.append("high propagated blame from downstream failures")
