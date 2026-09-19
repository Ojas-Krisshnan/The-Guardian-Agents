"""
Trend calculation across student learning cycles.
Authoritative contract: Contracts.md Sections C.2, D.2.
"""
from __future__ import annotations

from typing import Any
from synapse.schemas import (
    Diagnosis,
    TrendLabel,
)


def calculate_trend(
    diagnoses: list[Diagnosis | dict[str, Any]],
) -> TrendLabel:
    """Determine learning trend from diagnosis trajectory."""
    masteries: list[float] = []
    for d in diagnoses:
        m = d.mastery_estimate if isinstance(d, Diagnosis) else d.get("mastery_estimate")
        if m is not None:
            masteries.append(float(m))

    if len(masteries) <= 1:
        return TrendLabel.NEW

    prev = masteries[-2]
    latest = masteries[-1]

    diff = latest - prev
    if diff >= 0.08:
        return TrendLabel.IMPROVING
    elif diff <= -0.08:
        return TrendLabel.DECLINING
    elif latest < 0.5:
        return TrendLabel.STILL_WEAK
    else:
        return TrendLabel.STABLE
