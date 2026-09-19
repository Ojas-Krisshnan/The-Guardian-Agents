"""
Mastery calculation for student diagnoses.
Authoritative contract: Contracts.md Sections C.2, D.2, D.4.
"""
from __future__ import annotations

from typing import Any
from synapse.schemas import (
    DEFAULT_MASTERY_ESTIMATE,
    Diagnosis,
)


def calculate_mastery(
    diagnoses: list[Diagnosis | dict[str, Any]],
    student_id: str,
    concept_id: str,
) -> float:
    """Calculate current mastery estimate for a student on a concept from diagnosis history."""
    matching: list[float] = []
    for d in diagnoses:
        sid = d.student_id if isinstance(d, Diagnosis) else d.get("student_id")
        cid = d.concept_id if isinstance(d, Diagnosis) else d.get("concept_id")
        if sid == student_id and cid == concept_id:
            m = d.mastery_estimate if isinstance(d, Diagnosis) else d.get("mastery_estimate")
            if m is not None:
                matching.append(float(m))

    if not matching:
        return DEFAULT_MASTERY_ESTIMATE

    # Exponential recency weighting: 60% latest, 40% historical average if multiple
    if len(matching) == 1:
        return round(matching[0], 2)

    latest = matching[-1]
    older_avg = sum(matching[:-1]) / len(matching[:-1])
    weighted = (latest * 0.7) + (older_avg * 0.3)
    return round(max(0.0, min(1.0, weighted)), 2)
