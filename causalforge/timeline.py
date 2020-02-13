"""Incident timeline reconstruction.

Turns the unordered node set into a chronologically sorted list of events with
relative offsets, gap markers, and a compact ASCII gantt strip suitable for
embedding in Markdown reports.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .graph import CausalGraph


