"""Compatibility facade for the canonical proactive attention engine.

The implementation lives in :mod:`miyori.proactive`. This module intentionally
contains no storage schema, candidate generation, or attention policy of its own.
"""

from __future__ import annotations

from .proactive import (
    NEXUS_PROACTIVE_SCHEMA_VERSION,
    apply_proactive_decision,
    build_nexus_proactive,
)

__all__ = [
    "NEXUS_PROACTIVE_SCHEMA_VERSION",
    "apply_proactive_decision",
    "build_nexus_proactive",
]
