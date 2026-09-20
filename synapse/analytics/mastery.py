# synapse/analytics/mastery.py
"""Mastery calculation for Synapse Cycle.

NOTE: This heuristic is a domain opinion / pedagogical scoring model,
not an architectural constraint. Different pedagogical rules or weights
can be configured here without changing the system architecture.
"""
from __future__ import annotations

from synapse.schemas import Diagnosis, MistakeClassification

# Domain opinion penalties per mistake classification
MISTAKE_PENALTIES: dict[MistakeClassification, float] = {
    MistakeClassification.CONCEPTUAL_GAP: 0.25,
    MistakeClassification.CARELESS_MISTAKE: 0.10,
    MistakeClassification.CONTRADICTORY: 0.15,
    MistakeClassification.UNRELATED: 0.05,
    MistakeClassification.EMPTY: 0.05,
}


def calculate_mastery(diagnosis: Diagnosis) -> float:
    """Calculates student mastery score in [0.0, 1.0] from a Diagnosis.

    Heuristic (domain opinion):
    - Start at base mastery 1.0 (perfect score assumption).
    - Deduct 0.25 for each conceptual gap.
    - Deduct 0.10 for each careless mistake.
    - Deduct 0.15 for each contradictory answer.
    - Deduct 0.05 for each unrelated response.
    - Deduct 0.05 for each empty response.
    - Clamp result to [0.0, 1.0].
    """
    total_penalty = sum(
        MISTAKE_PENALTIES.get(item.classification, 0.0)
        for item in diagnosis.items
    )
    raw_mastery = 1.0 - total_penalty
    clamped = max(0.0, min(1.0, raw_mastery))
    return round(clamped, 4)
