# synapse/analytics/aggregation.py
"""Aggregation pipeline: collects student AnalysisPayloads into ClassAnalytics."""
from __future__ import annotations

from collections import Counter

from synapse.schemas import (
    AnalysisPayload,
    ClassAnalytics,
    MASTERY_WEAK_THRESHOLD,
    TrendLabel,
)


def aggregate(
    payloads: list[AnalysisPayload],
    concept_name: str = "",
) -> ClassAnalytics:
    """Aggregates student analysis payloads for a concept into ClassAnalytics.

    Args:
        payloads: List of AnalysisPayload records for student attempts on a concept.
        concept_name: Optional human-readable concept name. If omitted, defaults
            to concept_id (as AnalysisPayload only carries concept_id).

    Returns:
        ClassAnalytics with average mastery, trend distribution, student count,
        and weak students list (< MASTERY_WEAK_THRESHOLD).
    """
    if not payloads:
        return ClassAnalytics(
            concept_id="",
            concept_name=concept_name,
            student_count=0,
            average_mastery=0.0,
            trend_distribution={},
            weak_students=[],
        )

    concept_id = payloads[0].concept_id
    resolved_name = concept_name or concept_id
    student_count = len(payloads)
    total_mastery = sum(p.mastery_estimate for p in payloads)
    avg_mastery = round(total_mastery / student_count, 4)

    # Compute distribution of trends across students
    trend_counts = Counter(p.trend for p in payloads)
    trend_distribution: dict[TrendLabel, int] = {
        trend: count for trend, count in trend_counts.items()
    }

    # Identify weak students using the architectural constant
    weak_students = [
        p.student_id
        for p in payloads
        if p.mastery_estimate < MASTERY_WEAK_THRESHOLD
    ]

    return ClassAnalytics(
        concept_id=concept_id,
        concept_name=resolved_name,
        student_count=student_count,
        average_mastery=avg_mastery,
        trend_distribution=trend_distribution,
        weak_students=weak_students,
    )
