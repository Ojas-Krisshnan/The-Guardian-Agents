"""
Flow handlers for Person 2 agents domain: diagnosing, tailoring, reviewing.
Authoritative contract: Contracts.md Sections A.5, C.2, C.3, D.2, D.4.
"""
from __future__ import annotations

from typing import Any
from slice.runner import Context
from synapse.agents.diagnosis import diagnose
from synapse.agents.review import review
from synapse.agents.tailoring import tailor
from synapse.schemas import (
    Attempt,
    CanonicalNote,
    Diagnosis,
    NoteVersion,
    RecordKind,
    ReviewResult,
    ReviewStatus,
    StudentHistory,
    Test,
    TestQuestion,
)
from synapse.state_machine import RunState, state_after_review


def _get_revisions_so_far(ctx: Context) -> int:
    """Number of failed review records already stored for this run + cycle."""
    review_history = ctx.history(RecordKind.REVIEW.value)
    count = 0
    for r in review_history:
        p = r.payload if hasattr(r, "payload") else r
        status = p.get("status")
        passed = p.get("passed", True)
        if status == ReviewStatus.FAILED.value or (not passed and status != ReviewStatus.REVISION_LIMIT_REACHED.value):
            count += 1
    return count


def handle_diagnosing(ctx: Context) -> RunState:
    """Diagnose student attempt against test questions and transition to TAILORING."""
    attempt_dict = ctx.latest(RecordKind.ATTEMPT.value)
    test_dict = ctx.latest(RecordKind.TEST.value)
    canonical_dict = ctx.latest(RecordKind.CANONICAL_NOTE.value)

    scope = ctx.store.meta(ctx.run_id).get("scope", {})
    concept_id = scope.get("concept_id", "default_concept")
    student_id = scope.get("student_id", "student_01")

    if attempt_dict:
        attempt = Attempt.model_validate(attempt_dict)
    else:
        # Fallback if attempt was not yet placed in latest
        attempt = Attempt(
            student_id=student_id,
            test_id="test_default",
            concept_id=concept_id,
            answers={},
            score=0,
            total=1,
        )

    if test_dict:
        test = Test.model_validate(test_dict)
    else:
        test = Test(
            id="test_default",
            concept_id=concept_id,
            concept_name="General",
            questions=[
                TestQuestion(
                    id="q_default",
                    text=f"Basic diagnostic item for {concept_id}",
                    correct_answer="Correct",
                    options=["Correct", "Choice B", "Choice C", "Choice D"],
                    concept_id=concept_id,
                )
            ],
        )

    canonical_note = CanonicalNote.model_validate(canonical_dict) if canonical_dict else None

    # Run diagnosis
    diagnosis_record = diagnose(
        attempt=attempt,
        test=test,
        canonical_note=canonical_note,
        settings=ctx.settings,
        budget=ctx.budget,
    )

    ctx.append(
        RecordKind.DIAGNOSIS.value,
        diagnosis_record.model_dump(mode="json"),
        produced_by="agents:diagnostician",
    )

    return RunState.TAILORING


def handle_tailoring(ctx: Context) -> RunState:
    """Produce personalized note candidate and transition to REVIEWING."""
    canonical_dict = ctx.latest(RecordKind.CANONICAL_NOTE.value)
    diagnosis_dict = ctx.latest(RecordKind.DIAGNOSIS.value)

    scope = ctx.store.meta(ctx.run_id).get("scope", {})
    concept_id = scope.get("concept_id", "default_concept")
    student_id = scope.get("student_id", "student_01")

    canonical_note = (
        CanonicalNote.model_validate(canonical_dict)
        if canonical_dict
        else CanonicalNote(concept_id=concept_id, markdown=f"# Concept {concept_id}\nContent")
    )

    diagnosis = (
        Diagnosis.model_validate(diagnosis_dict)
        if diagnosis_dict
        else Diagnosis(
            student_id=student_id,
            concept_id=concept_id,
            mastery_estimate=0.5,
            trend="new",
        )
    )

    # Check for previous review objections in this cycle
    objections: list[str] = []
    latest_review = ctx.latest(RecordKind.REVIEW.value)
    if latest_review and not latest_review.get("passed", True):
        objections = latest_review.get("objections", [])

    # Monotonic version per student + concept
    prev_final_note = ctx.latest(RecordKind.NOTE_VERSION.value)
    version = (prev_final_note.get("version", 0) if prev_final_note else 0) + 1

    candidate = tailor(
        canonical_note=canonical_note,
        diagnosis=diagnosis,
        objections=objections,
        version=version,
        settings=ctx.settings,
        budget=ctx.budget,
    )

    ctx.append(
        RecordKind.NOTE_CANDIDATE.value,
        candidate.model_dump(mode="json"),
        produced_by="agents:tailor",
    )

    return RunState.REVIEWING


def handle_reviewing(ctx: Context) -> RunState:
    """Review note candidate. Loops to TAILORING on failure (up to 3 times) or transitions to NOTE_SAVED."""
    canonical_dict = ctx.latest(RecordKind.CANONICAL_NOTE.value)
    candidate_dict = ctx.latest(RecordKind.NOTE_CANDIDATE.value)
    diagnosis_dict = ctx.latest(RecordKind.DIAGNOSIS.value)

    scope = ctx.store.meta(ctx.run_id).get("scope", {})
    concept_id = scope.get("concept_id", "default_concept")
    student_id = scope.get("student_id", "student_01")

    canonical_note = (
        CanonicalNote.model_validate(canonical_dict)
        if canonical_dict
        else CanonicalNote(concept_id=concept_id, markdown=f"# Concept {concept_id}\nContent")
    )

    candidate = (
        NoteVersion.model_validate(candidate_dict)
        if candidate_dict
        else NoteVersion(
            student_id=student_id,
            concept_id=concept_id,
            version=1,
            markdown=canonical_note.markdown,
        )
    )

    diagnosis = (
        Diagnosis.model_validate(diagnosis_dict)
        if diagnosis_dict
        else Diagnosis(
            student_id=student_id,
            concept_id=concept_id,
            mastery_estimate=0.5,
            trend="new",
        )
    )

    revisions_so_far = _get_revisions_so_far(ctx)

    review_result = review(
        canonical_note=canonical_note,
        candidate=candidate,
        diagnosis=diagnosis,
        revisions_so_far=revisions_so_far,
        settings=ctx.settings,
        budget=ctx.budget,
    )

    ctx.append(
        RecordKind.REVIEW.value,
        review_result.model_dump(mode="json"),
        produced_by="agents:reviewer",
    )

    return state_after_review(review_result.status)
