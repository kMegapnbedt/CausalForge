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
