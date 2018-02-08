"""CausalForge command-line interface.

Subcommands
-----------
``analyze``   Rank root causes for an incident and print a report.
``timeline``  Reconstruct and print the incident timeline.
``blast``     Report the blast radius of a specific node.
``convert``   Convert a JSON incident into the compact event stream (for the
              C++ engine) or vice versa.
``validate``  Structural validation of an incident graph.

All commands read the canonical JSON incident schema unless ``--events`` is
passed, in which case the compact line format is used.
"""

from __future__ import annotations
