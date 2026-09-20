# synapse/analytics/trends.py
"""Trend calculation across learning cycles for Synapse Cycle."""
from __future__ import annotations

from synapse.schemas import TrendLabel


def calculate_trend(
    current_mastery: float,
    history: list[tuple[int, float]],
) -> TrendLabel:
    """Calculates student progress trend comparing current mastery with cycle history.

    Rules:
    - If history is empty: TrendLabel.NEW
    - delta = current_mastery - previous_mastery (from the most recent cycle in history)
    - If delta > 0.15: TrendLabel.IMPROVING
    - Elif delta < -0.15: TrendLabel.DECLINING
    - Elif current_mastery < 0.5: TrendLabel.STILL_WEAK
    - Else: TrendLabel.STABLE
    """
    if not history:
        return TrendLabel.NEW

    prev_mastery = history[-1][1]
    # Round to avoid IEEE 754 floating point precision anomalies near exact boundaries
    delta = round(current_mastery - prev_mastery, 6)

    if delta > 0.15:
        return TrendLabel.IMPROVING
    elif delta < -0.15:
        return TrendLabel.DECLINING
    elif current_mastery < 0.5:
        return TrendLabel.STILL_WEAK
    else:
        return TrendLabel.STABLE
