# synapse/agents/__init__.py
"""Student Intelligence Pipeline: Diagnosis, Tailoring, and Review Agents (Person 2)."""
from __future__ import annotations

from .flow import (
    diagnose,
    handle_diagnosing,
    handle_reviewing,
    handle_tailoring,
    review_note,
    tailor_note,
)

__all__ = [
    "diagnose",
    "tailor_note",
    "review_note",
    "handle_diagnosing",
    "handle_tailoring",
    "handle_reviewing",
]
