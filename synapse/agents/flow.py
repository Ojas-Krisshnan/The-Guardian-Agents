# synapse/agents/flow.py
"""State machine flow handlers for Person 2 (diagnosing, tailoring, reviewing)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

from synapse.agents.stub import stub_diagnose, stub_review_note, stub_tailor_note
from synapse.schemas import (
    Attempt,
    CanonicalNote,
    Diagnosis,
    NoteVersion,
    RecordKind,
    ReviewResult,
    ReviewStatus,
    Test,
)
from synapse.state_machine import RunState, resolve_review_status, state_after_review

_PROMPTS = Path(__file__).parent / "prompts"


def _read_prompt(name: str) -> str:
    path = _PROMPTS / f"{name}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _has_model_access(settings: Any) -> bool:
    if settings is None:
        return False
    if hasattr(settings, "active_api_key"):
        return bool(settings.active_api_key)
    try:
        from slice.llm import get_provider_config
        pcfg = get_provider_config(settings)
        return bool(pcfg.api_key)
    except Exception:
        return False


def diagnose(
    attempt: Attempt,
    test: Test | None = None,
    canonical: CanonicalNote | None = None,
    call: Callable | None = None,
    settings: Any = None,
    budget: Any = None,
) -> Diagnosis:
    """Classifies mistakes, estimates mastery, and detects trend via slice.llm.complete."""
    if call is None:
        try:
            from slice.llm import complete as default_complete
            call = default_complete
        except ImportError:
            call = None

    if call is not None and settings is not None and budget is not None and _has_model_access(settings):
        prompt = _read_prompt("diagnosis")
        question_context = []
        if test and test.questions:
            for q in test.questions:
                student_ans = attempt.answers.get(q.id, "")
                question_context.append({
                    "question_id": q.id,
                    "question_text": q.text,
                    "options": q.options,
                    "correct_answer": q.correct_answer,
                    "concept_id": q.concept_id,
                    "student_answer": student_ans,
                    "is_correct": student_ans == q.correct_answer,
                })

        messages = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": (
                    f"Student ID: {attempt.student_id}\n"
                    f"Concept ID: {attempt.concept_id}\n"
                    f"Attempt Score: {attempt.score}/{attempt.total}\n"
                    f"Evaluation Context:\n{json.dumps(question_context, indent=2)}\n\n"
                    f"Analyze the student's attempt. Return a structured Diagnosis JSON object "
                    f"with student_id, concept_id, items, mastery_estimate (0.0 to 1.0), and trend."
                ),
            },
        ]
        res = call(
            settings=settings,
            budget=budget,
            messages=messages,
            schema=Diagnosis,
            step="diagnosis",
        )
        if res and isinstance(res, Diagnosis):
            res.student_id = attempt.student_id
            res.concept_id = attempt.concept_id
            return res
        raise RuntimeError("Model returned invalid diagnosis schema.")

    return stub_diagnose(attempt, test, canonical)


def tailor_note(
    student_id: str,
    concept_id: str,
    diagnosis: Diagnosis,
    canonical_note: CanonicalNote | None = None,
    canonical_name: str | None = None,
    version: int = 1,
    existing_concepts: list[str] | None = None,
    objections: list[str] | None = None,
    call: Callable | None = None,
    settings: Any = None,
    budget: Any = None,
) -> NoteVersion:
    """Generates candidate markdown note with mistake pattern table and [[links]]."""
    if canonical_name is None:
        if canonical_note and canonical_note.extracted_concepts:
            canonical_name = canonical_note.extracted_concepts[0].name
        else:
            canonical_name = "Recursion"

    if call is None:
        try:
            from slice.llm import complete as default_complete
            call = default_complete
        except ImportError:
            call = None

    if call is not None and settings is not None and budget is not None and _has_model_access(settings):
        prompt = _read_prompt("tailoring")
        diag_summary = {
            "mastery_estimate": diagnosis.mastery_estimate,
            "trend": diagnosis.trend.value if hasattr(diagnosis.trend, "value") else str(diagnosis.trend),
            "items": [
                {
                    "question_id": item.question_id,
                    "classification": item.classification.value if hasattr(item.classification, "value") else str(item.classification),
                    "reason": item.reason,
                }
                for item in diagnosis.items
            ],
        }
        available_concepts = existing_concepts or [canonical_name]
        messages = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": (
                    f"Student ID: {student_id}\n"
                    f"Concept: {canonical_name}\n"
                    f"Version: {version}\n"
                    f"Authoritative AI Diagnosis:\n{json.dumps(diag_summary, indent=2)}\n\n"
                    f"Available Concepts for [[links]]: {available_concepts}\n"
                    + (f"Reviewer objections to resolve:\n{objections}\n" if objections else "")
                    + "\nWrite the complete personalized markdown study note addressing the diagnosed gaps."
                ),
            },
        ]
        markdown_res = call(
            settings=settings,
            budget=budget,
            messages=messages,
            step="tailoring",
        )
        if markdown_res and isinstance(markdown_res, str) and len(markdown_res.strip()) > 10:
            return NoteVersion(
                student_id=student_id,
                concept_id=concept_id,
                version=version,
                markdown=markdown_res.strip(),
                diagnosis_id=diagnosis.id,
            )
        raise RuntimeError("Model returned invalid tailored note output.")

    return stub_tailor_note(
        student_id=student_id,
        concept_id=concept_id,
        diagnosis=diagnosis,
        canonical_name=canonical_name,
        version=version,
        existing_concepts=existing_concepts or [canonical_name],
        objections=objections,
    )


def review_note(
    note: NoteVersion,
    diagnosis: Diagnosis,
    canonical_note: CanonicalNote,
    existing_concepts: set[str] | None = None,
    revisions_so_far: int = 0,
    force_fail: bool = False,
    call: Callable | None = None,
    settings: Any = None,
    budget: Any = None,
) -> ReviewResult:
    """Validates candidate note against coverage, diagnosis, links, and quality."""
    return stub_review_note(
        note=note,
        diagnosis=diagnosis,
        canonical_note=canonical_note,
        existing_concepts=existing_concepts,
        revisions_so_far=revisions_so_far,
        force_fail=force_fail,
    )


async def handle_diagnosing(ctx: Any) -> RunState:
    """Diagnoses student misconceptions from their latest test attempt."""
    # Idempotency check: if authoritative diagnosis already exists, reuse it!
    existing_diag = ctx.latest(RecordKind.DIAGNOSIS)
    if existing_diag is not None:
        return RunState.TAILORING

    attempt_data = ctx.latest(RecordKind.ATTEMPT)
    if attempt_data is None:
        return RunState.ATTEMPT_RECEIVED

    attempt = Attempt.model_validate(attempt_data)
    test_data = ctx.latest(RecordKind.TEST)
    test = Test.model_validate(test_data) if test_data else None

    note_data = ctx.latest(RecordKind.CANONICAL_NOTE)
    canonical = CanonicalNote.model_validate(note_data) if note_data else None

    diagnosis_rec = diagnose(
        attempt=attempt,
        test=test,
        canonical=canonical,
        settings=getattr(ctx, "settings", None),
        budget=getattr(ctx, "budget", None),
    )

    ctx.append(RecordKind.DIAGNOSIS, diagnosis_rec.model_dump(mode="json"), produced_by="agent:diagnosis")
    return RunState.TAILORING


async def handle_tailoring(ctx: Any) -> RunState:
    """Generates candidate personalized markdown note using the authoritative diagnosis."""
    diag_data = ctx.latest(RecordKind.DIAGNOSIS)
    if diag_data is None:
        return RunState.DIAGNOSING
    diagnosis = Diagnosis.model_validate(diag_data)

    note_data = ctx.latest(RecordKind.CANONICAL_NOTE)
    canonical = CanonicalNote.model_validate(note_data) if note_data else None

    # Check previous finalized note version if any
    prev_note_data = ctx.latest(RecordKind.NOTE_VERSION)
    version = 1
    if prev_note_data:
        version = int(prev_note_data.get("version", 0)) + 1

    # Check if there were objections from a previous failed review in this cycle
    rev_data = ctx.latest(RecordKind.REVIEW)
    objections = None
    if rev_data and not rev_data.get("passed", True):
        objections = rev_data.get("objections", [])
    elif ctx.latest(RecordKind.NOTE_CANDIDATE) is not None and rev_data and rev_data.get("passed", True):
        # Idempotency: review already passed for existing candidate note
        return RunState.REVIEWING

    existing_names = [c.name for c in (canonical.extracted_concepts if canonical else [])]

    candidate = tailor_note(
        student_id=diagnosis.student_id,
        concept_id=diagnosis.concept_id,
        diagnosis=diagnosis,
        canonical_note=canonical,
        version=version,
        existing_concepts=existing_names,
        objections=objections,
        settings=getattr(ctx, "settings", None),
        budget=getattr(ctx, "budget", None),
    )

    ctx.append(RecordKind.NOTE_CANDIDATE, candidate.model_dump(mode="json"), produced_by="agent:tailoring")
    return RunState.REVIEWING


async def handle_reviewing(ctx: Any) -> RunState:
    """Validates candidate note and controls the revision loop back-edge."""
    cand_data = ctx.latest(RecordKind.NOTE_CANDIDATE)
    if cand_data is None:
        return RunState.TAILORING
    candidate = NoteVersion.model_validate(cand_data)

    diag_data = ctx.latest(RecordKind.DIAGNOSIS)
    diagnosis = Diagnosis.model_validate(diag_data) if diag_data else Diagnosis(student_id="s", concept_id="c")

    note_data = ctx.latest(RecordKind.CANONICAL_NOTE)
    canonical = CanonicalNote.model_validate(note_data) if note_data else CanonicalNote(concept_id="c", markdown="Recursion")

    existing_names = set(c.name for c in canonical.extracted_concepts) if canonical.extracted_concepts else {"Recursion"}

    # Count failed reviews for this run + cycle
    history_reviews = ctx.history(RecordKind.REVIEW)
    revisions_so_far = sum(1 for r in history_reviews if getattr(r, "payload", {}).get("status") == ReviewStatus.FAILED.value)

    review_res = review_note(
        note=candidate,
        diagnosis=diagnosis,
        canonical_note=canonical,
        existing_concepts=existing_names,
        revisions_so_far=revisions_so_far,
        settings=getattr(ctx, "settings", None),
        budget=getattr(ctx, "budget", None),
    )

    ctx.append(RecordKind.REVIEW, review_res.model_dump(mode="json"), produced_by="agent:review")

    # Determine next state: TAILORING if failed < limit; NOTE_SAVED if passed or limit reached
    next_state = state_after_review(review_res.status)
    return next_state
