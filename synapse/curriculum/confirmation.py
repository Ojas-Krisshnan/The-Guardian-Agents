"""
Teacher tag confirmation boundary.
Authoritative contract: Contracts.md Sections C.2, D.2, D.5.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from slice import callback
from slice.runner import Context
from synapse.schemas import (
    CanonicalNote,
    ConceptNode,
    RecordKind,
    TAG_CONFIRMATION_TIMEOUT_SECONDS,
    TeacherConfirmation,
)
from synapse.state_machine import RunState


def request_tag_confirmation(
    ctx: Context,
    concept_id: str,
    concepts: list[ConceptNode],
) -> str:
    """Park the run at TAG_CONFIRMATION and ask teacher to confirm or edit tags."""
    # Check if a question is already open
    open_qs = [q for q in ctx.store.open_questions(ctx.run_id) if not q.is_expired]
    if open_qs:
        return open_qs[0].id

    concept_dicts = [c.model_dump(mode="json") if hasattr(c, "model_dump") else c for c in concepts]
    context = {
        "concept_id": concept_id,
        "concepts": concept_dicts,
        "park_state": RunState.TAG_CONFIRMATION.value,
        "resume_state": RunState.TEST_READY.value,
        "timeout_seconds": getattr(ctx.settings, "tag_confirmation_timeout_seconds", TAG_CONFIRMATION_TIMEOUT_SECONDS),
    }

    qid = callback.ask(
        store=ctx.store,
        run_id=ctx.run_id,
        question=f"Please confirm or edit extracted tags for concept {concept_id}",
        context=context,
        settings=ctx.settings,
        park_state=RunState.TAG_CONFIRMATION,
        resume_state=RunState.TEST_READY,
    )
    return qid


def process_tag_confirmation(
    ctx: Context,
) -> tuple[TeacherConfirmation, CanonicalNote] | None:
    """Process human confirmation or timeout response from callback history."""
    # If confirmation already appended, avoid duplicate processing
    existing_conf = ctx.latest("confirmation")
    if existing_conf is not None:
        latest_note = ctx.latest("canonical_note")
        note_obj = CanonicalNote.model_validate(latest_note.payload) if latest_note else None
        conf_obj = TeacherConfirmation.model_validate(existing_conf.payload)
        return conf_obj, note_obj

    # Find latest answer
    answers = ctx.history("expert_answer")
    if not answers:
        return None

    last_answer_record = answers[-1]
    ans_payload = last_answer_record.payload if hasattr(last_answer_record, "payload") else last_answer_record

    raw_answer = ans_payload.get("answer")
    who = ans_payload.get("who") or "system"
    source = ans_payload.get("source") or ""

    # Determine latest canonical note to update
    note_record = ctx.latest("canonical_note")
    if not note_record:
        raise ValueError("Cannot confirm tags: canonical_note record not found in context history")

    note_data = dict(note_record.payload) if hasattr(note_record, "payload") else dict(note_record)
    concept_id = note_data.get("concept_id") or ctx.store.meta(ctx.run_id).get("scope", {}).get("concept_id", "")
    teacher_id = ctx.store.meta(ctx.run_id).get("scope", {}).get("teacher_id", "teacher")

    existing_concepts_raw = note_data.get("extracted_concepts", [])
    existing_concepts = [
        ConceptNode.model_validate(c) if isinstance(c, dict) else c
        for c in existing_concepts_raw
    ]

    # Check for timeout path: answer is None or source is unresolved_no_expert
    is_timeout = (raw_answer is None) or (source == "unresolved_no_expert") or (raw_answer == "")

    if is_timeout:
        # Rule D.5: Timeout produces confirmed=False, timed_out=True; extracted concepts unedited
        conf = TeacherConfirmation(
            concept_id=concept_id,
            teacher_id=teacher_id,
            confirmed=False,
            edited_concepts=None,
            confirmed_at=None,
            timed_out=True,
        )
        final_concepts = existing_concepts
    else:
        # Teacher answer path
        parsed_ans: dict[str, Any] = {}
        if isinstance(raw_answer, dict):
            parsed_ans = raw_answer
        elif isinstance(raw_answer, str):
            try:
                parsed_ans = json.loads(raw_answer)
            except Exception:
                parsed_ans = {"confirmed": True}

        # Rule D.5: A teacher submission is always confirmed=True; confirmed=False is invalid
        if parsed_ans.get("confirmed") is False:
            raise ValueError("Teacher confirmation cannot be submitted with confirmed=False. Only timeout produces confirmed=False.")

        edited_concepts = None
        if "edited_concepts" in parsed_ans and parsed_ans["edited_concepts"] is not None:
            edited_concepts = [
                ConceptNode.model_validate(c) if isinstance(c, dict) else c
                for c in parsed_ans["edited_concepts"]
            ]

        conf = TeacherConfirmation(
            concept_id=concept_id,
            teacher_id=teacher_id,
            confirmed=True,
            edited_concepts=edited_concepts,
            confirmed_at=datetime.now(timezone.utc),
            timed_out=False,
        )
        final_concepts = edited_concepts if edited_concepts is not None else existing_concepts

    # Append confirmation record
    ctx.append(
        RecordKind.CONFIRMATION.value,
        conf.model_dump(mode="json"),
        produced_by=who,
    )

    # Append updated canonical_note with teacher_confirmed=True
    updated_note = CanonicalNote(
        concept_id=concept_id,
        markdown=note_data.get("markdown", ""),
        extracted_concepts=final_concepts,
        teacher_confirmed=True,
        confirmed_at=conf.confirmed_at or datetime.now(timezone.utc),
    )
    ctx.append(
        RecordKind.CANONICAL_NOTE.value,
        updated_note.model_dump(mode="json"),
        produced_by=who,
    )

    return conf, updated_note
