"""
Student attempt diagnosis agent.
Authoritative contract: Contracts.md Sections C.2, D.2, D.3, D.4.
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field

from slice.budget import Budget
from slice.config import Settings
from slice.llm import complete
from slice.records import new_id
from synapse.schemas import (
    Attempt,
    CanonicalNote,
    DEFAULT_MASTERY_ESTIMATE,
    Diagnosis,
    DiagnosisItem,
    MistakeClassification,
    StudentHistory,
    Test,
    TrendLabel,
)


class ModelDiagnosisItem(BaseModel):
    question_id: str
    classification: MistakeClassification
    reason: str


class ModelDiagnosisOutput(BaseModel):
    items: list[ModelDiagnosisItem] = Field(default_factory=list)
    mastery_estimate: float = Field(ge=0.0, le=1.0)
    trend: TrendLabel


def _deterministic_diagnose(
    attempt: Attempt,
    test: Test,
    history: Optional[StudentHistory] = None,
) -> Diagnosis:
    """Deterministic rule-based diagnosis when model is unavailable or in offline tests."""
    items: list[DiagnosisItem] = []
    question_map = {q.id: q for q in test.questions}

    for qid, student_ans in attempt.answers.items():
        q = question_map.get(qid)
        if not q:
            continue
        if student_ans != q.correct_answer:
            classification = (
                MistakeClassification.EMPTY if not student_ans
                else MistakeClassification.CONCEPTUAL_GAP
            )
            items.append(
                DiagnosisItem(
                    question_id=qid,
                    classification=classification,
                    reason=f"Student answered '{student_ans}' instead of '{q.correct_answer}' on concept {q.concept_id}.",
                )
            )

    # Calculate mastery: score / total
    total = max(attempt.total, len(test.questions), 1)
    score = attempt.score
    mastery = max(0.0, min(1.0, float(score) / float(total)))

    # Determine trend from history
    trend = TrendLabel.NEW
    if history and history.mastery_history:
        prev_mastery = history.mastery_history[-1][1]
        if mastery > prev_mastery + 0.1:
            trend = TrendLabel.IMPROVING
        elif mastery < prev_mastery - 0.1:
            trend = TrendLabel.DECLINING
        elif mastery < 0.5:
            trend = TrendLabel.STILL_WEAK
        else:
            trend = TrendLabel.STABLE

    return Diagnosis(
        id=new_id(),
        student_id=attempt.student_id,
        concept_id=attempt.concept_id,
        items=items,
        mastery_estimate=round(mastery, 2),
        trend=trend,
    )


def diagnose(
    attempt: Attempt,
    test: Test,
    canonical_note: Optional[CanonicalNote] = None,
    history: Optional[StudentHistory] = None,
    settings: Optional[Settings] = None,
    budget: Optional[Budget] = None,
) -> Diagnosis:
    """Diagnose student test attempt and produce structured Diagnosis record."""
    if settings and budget and settings.api_key:
        try:
            questions_text = "\n".join(
                f"- Q({q.id}): {q.text}\n  Correct: {q.correct_answer}\n  Student Answer: {attempt.answers.get(q.id, 'No answer')}"
                for q in test.questions
            )
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are an educational diagnostician. Analyze the student's test answers against the test questions. "
                        "Classify errors (conceptual_gap, careless_mistake, contradictory, unrelated, empty), "
                        "estimate mastery (0.0 to 1.0), and provide trend assessment (new, improving, stable, still_weak, declining)."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Concept: {attempt.concept_id}\n\nQuestions & Answers:\n{questions_text}",
                },
            ]
            result = complete(
                settings=settings,
                budget=budget,
                messages=messages,
                schema=ModelDiagnosisOutput,
                step="agents:diagnose",
            )
            if isinstance(result, ModelDiagnosisOutput):
                items = [
                    DiagnosisItem(
                        question_id=item.question_id,
                        classification=item.classification,
                        reason=item.reason[:300],
                    )
                    for item in result.items
                ]
                return Diagnosis(
                    id=new_id(),
                    student_id=attempt.student_id,
                    concept_id=attempt.concept_id,
                    items=items,
                    mastery_estimate=result.mastery_estimate,
                    trend=result.trend,
                )
        except Exception:
            pass

    return _deterministic_diagnose(attempt, test, history)
