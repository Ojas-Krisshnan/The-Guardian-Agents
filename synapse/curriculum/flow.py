"""
Flow handlers for curriculum domain.
Authoritative contract: Contracts.md Sections A.5, C.2, C.3, D.2, D.5, D.8.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from slice import retrieve
from slice.runner import Context
from slice.store import Store
from synapse.curriculum.confirmation import (
    process_tag_confirmation,
    request_tag_confirmation,
)
from synapse.curriculum.extract import extract_concepts
from synapse.curriculum.test_generation import generate_test
from slice.records import new_id
from synapse.schemas import (
    CanonicalNote,
    ConceptNode,
    RecordKind,
    Test,
)
from synapse.state_machine import RunState


CORPUS_DIR = Path(__file__).parent / "corpus"
CANONICAL_NOTES_DIR = CORPUS_DIR / "canonical_notes"
CONCEPT_DEFINITIONS_DIR = CORPUS_DIR / "concept_definitions"


def handle_teacher_setup(ctx: Context) -> RunState:
    """Extract concepts from canonical note markdown and proceed to tag confirmation."""
    latest_note = ctx.latest(RecordKind.CANONICAL_NOTE.value)
    
    markdown = ""
    concept_name = "Core Concept"
    concept_id = new_id()

    scope = ctx.store.meta(ctx.run_id).get("scope", {})
    if scope.get("concept_name"):
        concept_name = scope["concept_name"]
    if scope.get("concept_id"):
        concept_id = scope["concept_id"]

    if latest_note is not None:
        payload = latest_note.payload if hasattr(latest_note, "payload") else latest_note
        markdown = payload.get("markdown", "")
        if payload.get("concept_name"):
            concept_name = payload["concept_name"]
        if payload.get("concept_id"):
            concept_id = payload["concept_id"]

    if not markdown:
        markdown = scope.get("markdown") or f"# {concept_name}\n\nOverview and concepts for {concept_name}."

    extracted = extract_concepts(
        markdown=markdown,
        concept_name=concept_name,
        settings=ctx.settings,
        budget=ctx.budget,
    )

    # Persist updated canonical note with extracted concepts
    canonical_note = CanonicalNote(
        concept_id=concept_id,
        markdown=markdown,
        extracted_concepts=extracted,
        teacher_confirmed=False,
    )
    ctx.append(
        RecordKind.CANONICAL_NOTE.value,
        canonical_note.model_dump(mode="json"),
        produced_by="curriculum:extract",
    )

    # Ensure concept_id is preserved in scope
    if not scope.get("concept_id"):
        scope["concept_id"] = concept_id
        ctx.store.update_meta(ctx.run_id, {"scope": scope})

    request_tag_confirmation(ctx, concept_id=concept_id, concepts=extracted)
    return RunState.TAG_CONFIRMATION


def handle_tag_confirmation(ctx: Context) -> RunState:
    """Park run for teacher confirmation, or process answer and advance to test_ready."""
    # If confirmation already appended, advance directly
    if ctx.latest(RecordKind.CONFIRMATION.value) is not None:
        return RunState.TEST_READY

    # Check if an answer has arrived in history
    answers = ctx.history("expert_answer")
    if answers:
        result = process_tag_confirmation(ctx)
        if result is not None:
            return RunState.TEST_READY

    # No answer yet: ensure question is asked and park
    latest_note_rec = ctx.latest(RecordKind.CANONICAL_NOTE.value)
    concepts: list[ConceptNode] = []
    concept_id = ctx.store.meta(ctx.run_id).get("scope", {}).get("concept_id", "")

    if latest_note_rec:
        payload = latest_note_rec.payload if hasattr(latest_note_rec, "payload") else latest_note_rec
        concepts = [
            ConceptNode.model_validate(c) if isinstance(c, dict) else c
            for c in payload.get("extracted_concepts", [])
        ]
        if not concept_id:
            concept_id = payload.get("concept_id", "")

    request_tag_confirmation(ctx, concept_id=concept_id, concepts=concepts)
    return RunState.TAG_CONFIRMATION


def handle_test_ready(ctx: Context) -> RunState:
    """Generate diagnostic test and transition to awaiting_student."""
    # If test is already generated, proceed to awaiting student
    existing_test = ctx.latest(RecordKind.TEST.value)
    if existing_test is not None:
        return RunState.AWAITING_STUDENT

    scope = ctx.store.meta(ctx.run_id).get("scope", {})
    concept_id = scope.get("concept_id", "")
    concept_name = scope.get("concept_name", "Curriculum Topic")

    concepts: list[ConceptNode] = []
    latest_note = ctx.latest(RecordKind.CANONICAL_NOTE.value)
    if latest_note:
        payload = latest_note.payload if hasattr(latest_note, "payload") else latest_note
        if not concept_id:
            concept_id = payload.get("concept_id", "")
        concepts = [
            ConceptNode.model_validate(c) if isinstance(c, dict) else c
            for c in payload.get("extracted_concepts", [])
        ]

    test_obj = generate_test(
        concept_id=concept_id,
        concept_name=concept_name,
        concepts=concepts,
        settings=ctx.settings,
        budget=ctx.budget,
    )

    ctx.append(
        RecordKind.TEST.value,
        test_obj.model_dump(mode="json"),
        produced_by="curriculum:test_generator",
    )

    return RunState.AWAITING_STUDENT


def ingest_corpus(store: Store) -> dict[str, Any]:
    """Ingest teacher-authored canonical notes and concept definitions into vector store.
    Rule D.8: Ingest the two subfolders, NOT the corpus root, and NEVER generated/ or student notes.
    """
    res1 = retrieve.ingest(store, CANONICAL_NOTES_DIR)
    res2 = retrieve.ingest(store, CONCEPT_DEFINITIONS_DIR)
    return {
        "canonical_notes": res1,
        "concept_definitions": res2,
    }
