"""Immutable-ish data model for CausalForge.

These dataclasses are the vocabulary the rest of the package speaks in. They
map one-to-one onto the JSON incident schema documented in ``docs/schema.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

