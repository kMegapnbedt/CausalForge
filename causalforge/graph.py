"""Causal graph structure and traversal helpers.

The :class:`CausalGraph` wraps an :class:`~causalforge.model.Incident` with the
adjacency indices the ranking and blast-radius passes need. It is deliberately
small: no external graph library, just dictionaries of adjacency lists.
"""

from __future__ import annotations

