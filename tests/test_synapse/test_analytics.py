# tests/test_synapse/test_analytics.py
"""Comprehensive unit tests for Person 4 analytics: mastery scoring, trends, and class aggregation."""
import pytest
from datetime import datetime

from synapse.analytics.aggregation import aggregate
from synapse.analytics.mastery import calculate_mastery
from synapse.analytics.trends import calculate_trend
from synapse.schemas import (
    AnalysisPayload,
    ClassAnalytics,
    Diagnosis,
    DiagnosisItem,
    MASTERY_WEAK_THRESHOLD,
    MistakeClassification,
    NoteVersion,
    TrendLabel,
)


def _diag(mistakes: list[MistakeClassification]) -> Diagnosis:
    """Helper to build a Diagnosis with a specific list of mistakes."""
    items = [
        DiagnosisItem(
            question_id=f"q_{i}",
            classification=m,
            reason=f"Classification: {m.value}",
        )
        for i, m in enumerate(mistakes)
    ]
    return Diagnosis(
        student_id="student_test",
        concept_id="concept_test",
        items=items,
        mastery_estimate=0.5,
        trend=TrendLabel.NEW,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 1. MASTERY CALCULATION TESTS
# ══════════════════════════════════════════════════════════════════════════════

def test_mastery_no_mistakes():
    """No mistakes -> base mastery of 1.0."""
    d = _diag([])
    assert calculate_mastery(d) == 1.0


def test_mastery_one_conceptual_gap():
    """One conceptual gap deducts 0.25 -> 0.75."""
    d = _diag([MistakeClassification.CONCEPTUAL_GAP])
    assert calculate_mastery(d) == 0.75


def test_mastery_one_careless_mistake():
    """One careless mistake deducts 0.10 -> 0.90."""
    d = _diag([MistakeClassification.CARELESS_MISTAKE])
    assert calculate_mastery(d) == 0.90


def test_mastery_one_contradictory():
    """One contradictory answer deducts 0.15 -> 0.85."""
    d = _diag([MistakeClassification.CONTRADICTORY])
    assert calculate_mastery(d) == 0.85


def test_mastery_one_unrelated():
    """One unrelated response deducts 0.05 -> 0.95."""
    d = _diag([MistakeClassification.UNRELATED])
    assert calculate_mastery(d) == 0.95


def test_mastery_one_empty():
    """One empty response deducts 0.05 -> 0.95."""
    d = _diag([MistakeClassification.EMPTY])
    assert calculate_mastery(d) == 0.95


def test_mastery_multiple_penalties():
    """Combined deductions: 1.0 - (0.25 + 0.10 + 0.15 + 0.05 + 0.05) = 0.40."""
    d = _diag([
        MistakeClassification.CONCEPTUAL_GAP,
        MistakeClassification.CARELESS_MISTAKE,
        MistakeClassification.CONTRADICTORY,
        MistakeClassification.UNRELATED,
        MistakeClassification.EMPTY,
    ])
    assert calculate_mastery(d) == 0.40


def test_mastery_clamps_at_zero():
    """5 conceptual gaps = 5 * 0.25 = 1.25 penalty. Floor must clamp at 0.0."""
    d = _diag([MistakeClassification.CONCEPTUAL_GAP] * 5)
    assert calculate_mastery(d) == 0.0


def test_mastery_never_exceeds_one():
    """Mastery ceiling is 1.0."""
    d = _diag([])
    mastery = calculate_mastery(d)
    assert mastery <= 1.0
    assert mastery == 1.0


# ══════════════════════════════════════════════════════════════════════════════
# 2. TREND CALCULATION TESTS
# ══════════════════════════════════════════════════════════════════════════════

def test_trend_new_when_history_empty():
    """Empty cycle history yields TrendLabel.NEW."""
    assert calculate_trend(0.8, []) == TrendLabel.NEW


def test_trend_improving_strictly_greater_than_threshold():
    """Delta > 0.15 -> IMPROVING."""
    # Previous 0.60, current 0.76 (delta = +0.16 > 0.15)
    assert calculate_trend(0.76, [(1, 0.60)]) == TrendLabel.IMPROVING


def test_trend_declining_strictly_less_than_threshold():
    """Delta < -0.15 -> DECLINING."""
    # Previous 0.80, current 0.64 (delta = -0.16 < -0.15)
    assert calculate_trend(0.64, [(1, 0.80)]) == TrendLabel.DECLINING


def test_trend_boundary_positive_fifteen():
    """Delta exactly +0.15 is NOT strictly > 0.15."""
    # Previous 0.50, current 0.65 -> delta = 0.15. Mastery >= 0.5 -> STABLE.
    assert calculate_trend(0.65, [(1, 0.50)]) == TrendLabel.STABLE


def test_trend_boundary_negative_fifteen():
    """Delta exactly -0.15 is NOT strictly < -0.15."""
    # Previous 0.80, current 0.65 -> delta = -0.15. Mastery >= 0.5 -> STABLE.
    assert calculate_trend(0.65, [(1, 0.80)]) == TrendLabel.STABLE


def test_trend_still_weak_when_delta_between_and_mastery_under_half():
    """Delta within [-0.15, 0.15] and current_mastery < 0.5 -> STILL_WEAK."""
    # Previous 0.30, current 0.35 -> delta = +0.05, mastery = 0.35 < 0.5
    assert calculate_trend(0.35, [(1, 0.30)]) == TrendLabel.STILL_WEAK


def test_trend_stable_when_delta_between_and_mastery_at_or_above_half():
    """Delta within [-0.15, 0.15] and current_mastery >= 0.5 -> STABLE."""
    # Previous 0.70, current 0.75 -> delta = +0.05, mastery = 0.75 >= 0.5
    assert calculate_trend(0.75, [(1, 0.70)]) == TrendLabel.STABLE


def test_trend_boundary_mastery_exact_half():
    """Current mastery exactly 0.5 is NOT < 0.5; therefore STABLE."""
    # Previous 0.50, current 0.50 -> delta = 0.0, mastery = 0.50 -> STABLE
    assert calculate_trend(0.50, [(1, 0.50)]) == TrendLabel.STABLE


def test_trend_uses_latest_cycle_in_multi_cycle_history():
    """Uses history[-1] as previous mastery."""
    history = [(1, 0.20), (2, 0.40), (3, 0.60)]
    # Current 0.80 compared against cycle 3 (0.60): delta = +0.20 -> IMPROVING
    assert calculate_trend(0.80, history) == TrendLabel.IMPROVING


# ══════════════════════════════════════════════════════════════════════════════
# 3. CLASS ANALYTICS AGGREGATION TESTS
# ══════════════════════════════════════════════════════════════════════════════

def test_aggregation_empty_payloads():
    """Empty list returns zeroed ClassAnalytics without crashing."""
    ca = aggregate([], concept_name="Recursion")
    assert ca.student_count == 0
    assert ca.average_mastery == 0.0
    assert ca.weak_students == []
    assert ca.trend_distribution == {}


def test_aggregation_multiple_students():
    """Aggregates 3 students: verifies count, avg mastery, trend counts, weak list."""
    payloads = [
        AnalysisPayload(
            student_id="student_1",
            concept_id="c_rec",
            mastery_estimate=0.90,
            trend=TrendLabel.IMPROVING,
            cycle_number=1,
        ),
        AnalysisPayload(
            student_id="student_2",
            concept_id="c_rec",
            mastery_estimate=0.60,
            trend=TrendLabel.STABLE,
            cycle_number=1,
        ),
        AnalysisPayload(
            student_id="student_3",
            concept_id="c_rec",
            mastery_estimate=0.30,
            trend=TrendLabel.STILL_WEAK,
            cycle_number=1,
        ),
    ]

    ca = aggregate(payloads, concept_name="Recursion")

    # Student count
    assert ca.student_count == 3
    assert ca.concept_id == "c_rec"
    assert ca.concept_name == "Recursion"

    # Average mastery: (0.90 + 0.60 + 0.30) / 3 = 0.60
    assert ca.average_mastery == 0.60

    # Trend distribution
    assert ca.trend_distribution[TrendLabel.IMPROVING] == 1
    assert ca.trend_distribution[TrendLabel.STABLE] == 1
    assert ca.trend_distribution[TrendLabel.STILL_WEAK] == 1

    # Weak students: threshold is MASTERY_WEAK_THRESHOLD (0.5)
    # Only student_3 (0.30) is strictly < 0.5
    assert ca.weak_students == ["student_3"]


def test_aggregation_weak_threshold_boundary():
    """A student with exactly MASTERY_WEAK_THRESHOLD (0.5) is not weak (< is strict)."""
    payloads = [
        AnalysisPayload(
            student_id="student_borderline",
            concept_id="c_rec",
            mastery_estimate=MASTERY_WEAK_THRESHOLD,
            trend=TrendLabel.STABLE,
            cycle_number=1,
        ),
        AnalysisPayload(
            student_id="student_below",
            concept_id="c_rec",
            mastery_estimate=0.49,
            trend=TrendLabel.STILL_WEAK,
            cycle_number=1,
        ),
    ]
    ca = aggregate(payloads)
    assert ca.weak_students == ["student_below"]


# ══════════════════════════════════════════════════════════════════════════════
# 4. FLOW HANDLERS TESTS
# ══════════════════════════════════════════════════════════════════════════════

class MockContext:
    def __init__(self, records=None, scope=None):
        self.records = records or []
        self.scope = scope or {}
        self.appended = []

    def get_latest(self, kind):
        for r in reversed(self.records):
            if getattr(r, "kind", None) == kind:
                return getattr(r, "payload", None)
        return None

    def find_all(self, kind):
        return [
            getattr(r, "payload", None)
            for r in self.records
            if getattr(r, "kind", None) == kind
        ]

    def append(self, kind, payload):
        class Rec:
            def __init__(self, k, p):
                self.kind = k
                self.payload = p
        rec = Rec(kind, payload)
        self.records.append(rec)
        self.appended.append((kind, payload))


def test_handle_analysing():
    """handle_analysing calculates mastery, trend, appends analysis payload, transitions to aggregating."""
    import asyncio
    from synapse.analytics.flow import handle_analysing
    from synapse.schemas import RecordKind
    from synapse.state_machine import RunState

    diag = _diag([MistakeClassification.CARELESS_MISTAKE])
    ctx = MockContext(
        scope={"concept_id": "c_rec", "student_id": "student_1", "cycle": 2, "mastery_history": [(1, 0.70)]}
    )
    ctx.append(RecordKind.DIAGNOSIS, diag)

    next_state = asyncio.run(handle_analysing(ctx))
    assert next_state == RunState.AGGREGATING
    assert len(ctx.appended) == 2  # 1 diagnosis + 1 analysis
    kind, payload = ctx.appended[-1]
    assert kind == RecordKind.ANALYSIS
    assert isinstance(payload, AnalysisPayload)
    assert payload.mastery_estimate == 0.90
    assert payload.trend == TrendLabel.IMPROVING  # 0.90 - 0.70 = 0.20 > 0.15


def test_handle_aggregating():
    """handle_aggregating aggregates payloads, builds graph, transitions to complete."""
    import asyncio
    from synapse.analytics.flow import handle_aggregating
    from synapse.schemas import RecordKind
    from synapse.state_machine import RunState

    p1 = AnalysisPayload(student_id="s1", concept_id="c_rec", mastery_estimate=0.8, trend=TrendLabel.STABLE, cycle_number=1)
    p2 = AnalysisPayload(student_id="s2", concept_id="c_rec", mastery_estimate=0.4, trend=TrendLabel.STILL_WEAK, cycle_number=1)
    note = NoteVersion(student_id="s1", concept_id="c_rec", version=1, markdown="Recursion note")

    ctx = MockContext(
        records=[],
        scope={"concept_id": "c_rec", "student_id": "s1"}
    )
    ctx.append(RecordKind.ANALYSIS, p1)
    ctx.append(RecordKind.ANALYSIS, p2)
    ctx.append(RecordKind.NOTE_VERSION, note)

    next_state = asyncio.run(handle_aggregating(ctx))
    assert next_state == RunState.COMPLETE
    kinds = [k for k, p in ctx.appended]
    assert RecordKind.CLASS_ANALYTICS in kinds
    assert RecordKind.CONCEPT_GRAPH in kinds


