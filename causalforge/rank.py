"""Root-cause ranking engine.

This is the heart of CausalForge. Given a :class:`CausalGraph`, it produces a
ranked list of :class:`~causalforge.model.Suspect` candidates.

Algorithm overview
-------------------
1. **Seed blame.** Every failing/degraded node injects blame proportional to
   its severity (failed = 1.0, degraded = 0.4).
2. **Backward temporal propagation.** For a fixed number of damped rounds,
   blame flows from a node to its upstream neighbours along incoming edges. The
