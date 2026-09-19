"""
Deterministic stubs for Person 4 analytics domain for testing without external dependencies.
"""
from __future__ import annotations

from typing import Any
from synapse.schemas import (
    AnalysisPayload,
    ClassAnalytics,
    ConceptGraph,
    ConceptNode,
    GraphEdge,
    TrendLabel,
)


def stub_calculate_mastery(student_id: str, concept_id: str) -> float:
    return 0.75


def stub_calculate_trend() -> TrendLabel:
    return TrendLabel.IMPROVING


def stub_aggregate(concept_id: str, concept_name: str) -> ClassAnalytics:
    return ClassAnalytics(
        concept_id=concept_id,
        concept_name=concept_name,
        student_count=10,
        average_mastery=0.72,
        trend_distribution={
            TrendLabel.IMPROVING: 6,
            TrendLabel.STABLE: 3,
            TrendLabel.STILL_WEAK: 1,
            TrendLabel.DECLINING: 0,
            TrendLabel.NEW: 0,
        },
        weak_students=["student_weak_01"],
    )


def stub_concept_graph() -> ConceptGraph:
    nodes = [
        ConceptNode(id="c_cell", name="Cell Biology", summary="Basics of cell biology", prerequisites=[]),
        ConceptNode(id="c_organelles", name="Organelles", summary="Chloroplasts and mitochondria", prerequisites=["c_cell"]),
        ConceptNode(id="c_photo", name="Photosynthesis", summary="Energy conversion in plants", prerequisites=["c_organelles"]),
    ]
    edges = [
        GraphEdge(from_concept="c_cell", to_concept="c_organelles", relationship="prerequisite"),
        GraphEdge(from_concept="c_organelles", to_concept="c_photo", relationship="prerequisite"),
    ]
    return ConceptGraph(nodes=nodes, edges=edges)
