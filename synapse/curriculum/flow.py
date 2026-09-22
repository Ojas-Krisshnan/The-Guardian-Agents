# synapse/curriculum/flow.py
"""State machine handlers and services for Curriculum + Test Generation (Person 3)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from synapse.curriculum.stub import stub_extract_concepts, stub_generate_test
from synapse.schemas import (
    CanonicalNote,
    ConceptNode,
    RecordKind,
    TeacherConfirmation,
    Test,
    utcnow,
)
from synapse.state_machine import RunState

_PROMPTS = Path(__file__).parent / "prompts"


def _read_prompt(name: str) -> str:
    path = _PROMPTS / f"{name}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def extract_concepts(
    canonical_note: CanonicalNote,
    concept_name: str = "Recursion",
    call: Callable | None = None,
    settings: Any = None,
    budget: Any = None,
) -> list[ConceptNode]:
    """Extract discrete testable concepts from a canonical note."""
    if call is not None and settings is not None and budget is not None:
        try:
            from pydantic import BaseModel, Field

            class ExtractedSchema(BaseModel):
                concepts: list[ConceptNode] = Field(default_factory=list)

            prompt = _read_prompt("concept_extraction")
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Concept Name: {concept_name}\n\nCanonical Note:\n{canonical_note.markdown}"},
            ]
            result = call(
                settings=settings,
                budget=budget,
                messages=messages,
                schema=ExtractedSchema,
                step="curriculum_extract",
            )
            if result and result.concepts:
                return result.concepts
        except Exception:
            pass  # Fall back to deterministic stub

    return stub_extract_concepts(canonical_note.markdown, concept_name)


def generate_test(
    concept: ConceptNode,
    canonical_note: CanonicalNote,
    call: Callable | None = None,
    settings: Any = None,
    budget: Any = None,
) -> Test:
    """Generate 3 multiple-choice questions for the confirmed concept."""
    if call is not None and settings is not None and budget is not None:
        try:
            prompt = _read_prompt("test_generation")
            messages = [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": (
                        f"Target Concept: {concept.name}\n"
                        f"Summary: {concept.summary}\n\n"
                        f"Canonical Note Context:\n{canonical_note.markdown}"
                    ),
                },
            ]
            result = call(
                settings=settings,
                budget=budget,
                messages=messages,
                schema=Test,
                step="test_generator",
            )
            if result and len(result.questions) >= 1:
                return result
        except Exception:
            pass

    return stub_generate_test(concept.id, concept.name)


async def handle_teacher_setup(ctx: Any) -> RunState:
    """Entry state: parses canonical note and extracts concepts."""
    note_payload = ctx.latest(RecordKind.CANONICAL_NOTE)
    scope = getattr(ctx, "scope", {})
    if hasattr(ctx, "store"):
        try:
            run_meta = ctx.store.get_run(ctx.run_id)
            if "scope" in run_meta:
                scope = run_meta["scope"]
        except Exception:
            pass

    concept_id = scope.get("concept_id", "default_concept")
    concept_name = scope.get("concept_name", "Recursion")

    if note_payload is None:
        raw_markdown = scope.get("markdown", f"# {concept_name}\nCore canonical concepts and definitions.")
        canonical = CanonicalNote(
            concept_id=concept_id,
            markdown=raw_markdown,
            extracted_concepts=[],
        )
    else:
        canonical = CanonicalNote.model_validate(note_payload)

    extracted = extract_concepts(
        canonical,
        concept_name=concept_name,
        settings=getattr(ctx, "settings", None),
        budget=getattr(ctx, "budget", None),
    )
    canonical.extracted_concepts = extracted

    ctx.append(RecordKind.CANONICAL_NOTE, canonical.model_dump(mode="json"), produced_by="curriculum:setup")
    return RunState.TAG_CONFIRMATION


async def handle_tag_confirmation(ctx: Any) -> RunState:
    """Parked state for human tag confirmation or timeout."""
    conf_payload = ctx.latest(RecordKind.CONFIRMATION)
    if conf_payload is not None:
        return RunState.TEST_READY

    note_payload = ctx.latest(RecordKind.CANONICAL_NOTE)
    if note_payload is None:
        return RunState.TAG_CONFIRMATION
    canonical = CanonicalNote.model_validate(note_payload)

    # Check store for questions
    open_qs = ctx.store.open_questions(ctx.run_id)
    if not open_qs:
        # Check if there is already an answered question
        row = ctx.store.db.execute(
            "SELECT * FROM questions WHERE run_id=? ORDER BY asked_at DESC LIMIT 1",
            (ctx.run_id,),
        ).fetchone()

        if row is None:
            # First entry: ask the teacher
            timeout_min = max(1, getattr(ctx.settings, "tag_confirmation_timeout_seconds", 600) // 60)
            context_data = {
                "concepts": [c.model_dump(mode="json") for c in canonical.extracted_concepts],
                "concept_id": canonical.concept_id,
            }
            ctx.store.ask(
                ctx.run_id,
                "Please review and confirm extracted concept tags",
                context_data,
                timeout_min,
            )
            return RunState.TAG_CONFIRMATION

        # Question was answered
        ans_text = row["answer"]
        timed_out = False
        confirmed = True
        edited_concepts = None

        if ans_text in ("unknown", "timeout", None):
            timed_out = True
            confirmed = False
        else:
            try:
                parsed = json.loads(ans_text) if isinstance(ans_text, str) else ans_text
                if isinstance(parsed, dict):
                    timed_out = bool(parsed.get("timed_out", False))
                    confirmed = bool(parsed.get("confirmed", not timed_out))
                    if "edited_concepts" in parsed and parsed["edited_concepts"]:
                        edited_concepts = [ConceptNode.model_validate(c) for c in parsed["edited_concepts"]]
            except Exception:
                pass

        teacher_id = getattr(ctx, "scope", {}).get("teacher_id", "teacher_1")
        conf = TeacherConfirmation(
            concept_id=canonical.concept_id,
            teacher_id=teacher_id,
            confirmed=confirmed,
            edited_concepts=edited_concepts,
            confirmed_at=utcnow(),
            timed_out=timed_out,
        )

        if edited_concepts:
            canonical.extracted_concepts = edited_concepts
        canonical.teacher_confirmed = True
        canonical.confirmed_at = utcnow()

        ctx.append(RecordKind.CONFIRMATION, conf.model_dump(mode="json"), produced_by="human:teacher")
        ctx.append(RecordKind.CANONICAL_NOTE, canonical.model_dump(mode="json"), produced_by="curriculum:confirmed")
        return RunState.TEST_READY

    # Still waiting for response
    return RunState.TAG_CONFIRMATION


async def handle_test_ready(ctx: Any) -> RunState:
    """Generates the validated 3-question MCQ test for confirmed concept."""
    test_payload = ctx.latest(RecordKind.TEST)
    if test_payload is not None:
        return RunState.AWAITING_STUDENT

    note_payload = ctx.latest(RecordKind.CANONICAL_NOTE)
    canonical = CanonicalNote.model_validate(note_payload) if note_payload else CanonicalNote(concept_id="c1", markdown="concept")

    target_concept = canonical.extracted_concepts[0] if canonical.extracted_concepts else ConceptNode(name="Recursion", summary="Recursion basics")

    test = generate_test(
        target_concept,
        canonical,
        settings=getattr(ctx, "settings", None),
        budget=getattr(ctx, "budget", None),
    )

    ctx.append(RecordKind.TEST, test.model_dump(mode="json"), produced_by="curriculum:test_generator")
    return RunState.AWAITING_STUDENT
