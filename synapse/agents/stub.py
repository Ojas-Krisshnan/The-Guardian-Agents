"""
Deterministic stubs for Person 2 agents domain for testing without models.
"""
from __future__ import annotations

from typing import Optional
from synapse.schemas import (
    Attempt,
    CanonicalNote,
    Diagnosis,
    DiagnosisItem,
    MistakeClassification,
    NoteVersion,
    ReviewResult,
    ReviewStatus,
    StudentHistory,
    Test,
    TrendLabel,
)
from synapse.state_machine import resolve_review_status


def stub_diagnose(
    attempt: Attempt,
    test: Test,
    canonical_note: Optional[CanonicalNote] = None,
    history: Optional[StudentHistory] = None,
) -> Diagnosis:
    items = [
        DiagnosisItem(
            question_id=test.questions[0].id if test.questions else "q_default",
            classification=MistakeClassification.CONCEPTUAL_GAP,
            reason="Diagnostic stub finding: basic misconception identified.",
        )
    ]
    return Diagnosis(
        id="diag_stub_01",
        student_id=attempt.student_id,
        concept_id=attempt.concept_id,
        items=items,
        mastery_estimate=0.65,
        trend=TrendLabel.STABLE,
    )


def stub_tailor(
    canonical_note: CanonicalNote,
    diagnosis: Diagnosis,
    history: Optional[StudentHistory] = None,
    objections: Optional[list[str]] = None,
    version: int = 1,
) -> NoteVersion:
    return NoteVersion(
        student_id=diagnosis.student_id,
        concept_id=diagnosis.concept_id,
        version=version,
        markdown=f"# Tailored Note for {diagnosis.concept_id}\n\nAddressed: {diagnosis.items[0].reason if diagnosis.items else 'None'}\n\n{canonical_note.markdown}",
        diagnosis_id=diagnosis.id,
        review_id=None,
    )


def stub_review(
    canonical_note: CanonicalNote,
    candidate: NoteVersion,
    diagnosis: Diagnosis,
    should_pass: bool = True,
    revisions_so_far: int = 0,
) -> ReviewResult:
    objections = [] if should_pass else ["Stub objection: insufficient coverage."]
    status = resolve_review_status(passed=should_pass, revisions_so_far=revisions_so_far)
    return ReviewResult(
        id="rev_stub_01",
        passed=should_pass,
        canonical_coverage=should_pass,
        diagnosis_addressed=should_pass,
        links_valid=True,
        objections=objections,
        status=status,
    )
