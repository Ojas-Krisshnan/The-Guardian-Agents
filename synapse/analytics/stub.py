# synapse/analytics/stub.py
"""Stub-first test doubles and canned data helpers for Person 4 analytics.

Analytics is entirely deterministic logic (no LLM calls required).
This stub provides quick sample records for testing and integration.
"""
from __future__ import annotations

from synapse.schemas import (
    AnalysisPayload,
    ClassAnalytics,
    ConceptGraph,
    ConceptNode,
    Diagnosis,
    DiagnosisItem,
    GraphEdge,
    MistakeClassification,
    TrendLabel,
)


def sample_diagnosis(
    student_id: str = "student_1",
    concept_id: str = "concept_recursion",
    mistakes: list[MistakeClassification] | None = None,
) -> Diagnosis:
    """Returns a deterministic Diagnosis instance with specified or default mistakes."""
    if mistakes is None:
        mistakes = [MistakeClassification.CARELESS_MISTAKE]

    items = [
        DiagnosisItem(
            question_id=f"q_{i}",
            classification=m,
            reason=f"Mistake classified as {m.value}",
        )
        for i, m in enumerate(mistakes)
    ]
    return Diagnosis(
        student_id=student_id,
        concept_id=concept_id,
        items=items,
        mastery_estimate=0.9,
        trend=TrendLabel.STABLE,
    )


def sample_analysis_payload(
    student_id: str = "student_1",
    concept_id: str = "concept_recursion",
    mastery: float = 0.85,
    trend: TrendLabel = TrendLabel.IMPROVING,
    cycle: int = 1,
) -> AnalysisPayload:
    """Returns a deterministic AnalysisPayload instance."""
    return AnalysisPayload(
        student_id=student_id,
        concept_id=concept_id,
        mastery_estimate=mastery,
        trend=trend,
        cycle_number=cycle,
    )


def sample_concept_graph() -> ConceptGraph:
    """Returns a valid deterministic 3-node ConceptGraph DAG."""
    c_func = ConceptNode(id="c_func", name="Functions", summary="Reusable functions", prerequisites=[])
    c_rec = ConceptNode(id="c_rec", name="Recursion", summary="Recursive problem solving", prerequisites=["c_func"])
    c_trees = ConceptNode(id="c_trees", name="Trees", summary="Hierarchical trees", prerequisites=["c_rec"])

    edges = [
        GraphEdge(from_concept="c_func", to_concept="c_rec", relationship="prerequisite"),
        GraphEdge(from_concept="c_rec", to_concept="c_trees", relationship="prerequisite"),
    ]
    return ConceptGraph(nodes=[c_func, c_rec, c_trees], edges=edges)
