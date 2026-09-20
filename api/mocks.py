# api/mocks.py
"""Mock domain service implementations for testing."""
from __future__ import annotations

from typing import Any
from synapse.curriculum.stub import stub_extract_concepts, stub_generate_test
from synapse.schemas import (
    AnalysisPayload,
    Attempt,
    ClassAnalytics,
    ConceptNode,
    Diagnosis,
    DiagnosisItem,
    GraphEdge,
    MistakeClassification,
    NoteVersion,
    ReviewResult,
    ReviewStatus,
    RunScope,
    Test,
    TrendLabel,
)


class MockCurriculumService:
    async def create_concept(self, markdown: str, name: str = "Recursion") -> tuple[ConceptNode, str]:
        concepts = stub_extract_concepts(markdown, name)
        return concepts[0], "run_mock_123"

    async def get_test(self, run_id: str) -> Test:
        return stub_generate_test("c1", "Recursion")


class MockAnalyticsService:
    async def get_teacher_analytics(self, concept_id: str) -> ClassAnalytics:
        return ClassAnalytics(
            concept_id=concept_id,
            concept_name="Recursion",
            student_count=5,
            average_mastery=0.72,
            trend_distribution={TrendLabel.STABLE: 3, TrendLabel.IMPROVING: 2},
            weak_students=[],
        )
