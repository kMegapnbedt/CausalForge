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

import argparse
import sys
from typing import List, Optional

from .graph import CausalGraph
from .blast import blast_radius, reachable_set, weighted_blast
from .ingest import load_incident, parse_events, to_events
from .rank import RankConfig, rank_incident
from .report import render_json, render_markdown
from .timeline import build_timeline, timeline_text


def _read_incident(args) -> "Incident":  # noqa: F821 - forward ref for docs
    if args.events:
        with open(args.input, "r", encoding="utf-8") as fh:
