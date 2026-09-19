"""
Class-level aggregation across all student diagnoses.
Authoritative contract: Contracts.md Sections C.2, D.2.
"""
from __future__ import annotations

from typing import Any
from synapse.schemas import (
    ClassAnalytics,
    Diagnosis,
    MASTERY_WEAK_THRESHOLD,
    TrendLabel,
)


def aggregate(
    diagnoses: list[Diagnosis | dict[str, Any]],
    concept_id: str,
    concept_name: str,
) -> ClassAnalytics:
    """Aggregate multi-student performance data for a concept."""
    # Group latest diagnosis per student
    student_latest: dict[str, Any] = {}
    for d in diagnoses:
        sid = d.student_id if isinstance(d, Diagnosis) else d.get("student_id")
        cid = d.concept_id if isinstance(d, Diagnosis) else d.get("concept_id")
        if sid and (not cid or cid == concept_id):
            student_latest[sid] = d

    if not student_latest:
        return ClassAnalytics(
            concept_id=concept_id,
            concept_name=concept_name,
            student_count=0,
            average_mastery=0.0,
            trend_distribution={t: 0 for t in TrendLabel},
            weak_students=[],
        )

    student_count = len(student_latest)
    mastery_sum = 0.0
    trend_dist: dict[TrendLabel, int] = {t: 0 for t in TrendLabel}
    weak_students: list[str] = []

    for sid, d in student_latest.items():
        m = float(d.mastery_estimate if isinstance(d, Diagnosis) else d.get("mastery_estimate", 0.0))
        t_raw = d.trend if isinstance(d, Diagnosis) else d.get("trend", TrendLabel.NEW)
        t = TrendLabel(t_raw) if isinstance(t_raw, str) else t_raw

        mastery_sum += m
        trend_dist[t] = trend_dist.get(t, 0) + 1
        if m < MASTERY_WEAK_THRESHOLD:
            weak_students.append(sid)

    avg_mastery = round(mastery_sum / student_count, 2)

    return ClassAnalytics(
        concept_id=concept_id,
        concept_name=concept_name,
        student_count=student_count,
        average_mastery=avg_mastery,
        trend_distribution=trend_dist,
        weak_students=sorted(weak_students),
    )
