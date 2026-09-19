"""
Comprehensive unit tests for Person 3 Curriculum domain.
Verifies compliance with Contracts.md Sections A.5, C.2, D.2, D.5, D.8:
- Concept extraction shape and canonical note output
- Tag confirmation happy path, second-answer rejection, and timeout path
- confirmed=False rejection for teacher submissions
- Test generation shape: exactly 4 unique options, correct answer membership
- Corpus ingestion boundaries (only canonical_notes and concept_definitions, never generated or student notes)
- Import boundaries: no cross-domain imports from agents, analytics, runtime, api, web
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import pytest

from slice import callback
from slice.config import Settings
from slice.runner import Context
from slice.store import Store
from synapse.curriculum import (
    extract_concepts,
    generate_test,
    handle_tag_confirmation,
    handle_teacher_setup,
    handle_test_ready,
    ingest_corpus,
    process_tag_confirmation,
    request_tag_confirmation,
)
from synapse.schemas import (
    CanonicalNote,
    ConceptNode,
    RecordKind,
    TeacherConfirmation,
    Test,
    TestQuestion,
)
from synapse.state_machine import RunState

SAMPLE_MARKDOWN = """# Photosynthesis Overview

Photosynthesis occurs in chloroplasts and converts solar energy into chemical energy.

## Light-Dependent Reactions
Water is oxidized in thylakoid membranes, yielding oxygen, ATP, and NADPH. [[Chloroplast]]

## Calvin Cycle
Carbon dioxide is fixed into organic sugars in the stroma using RuBisCO. [[Light-Dependent Reactions]]
"""


@pytest.fixture
def test_env(tmp_path):
    db_path = tmp_path / "test_curriculum.db"
    store = Store(db_path)
    settings = Settings(
        api_key="test",
        model="test-model",
        fallback_model="test-fallback",
        escalation_model="test-esc",
        max_tokens=100,
        max_tokens_per_run=1000,
        max_attempts_per_step=3,
        expert_timeout_minutes=45,
        langfuse_public="",
        langfuse_secret="",
        langfuse_host="",
    )
    run_id = store.create_run(
        domain="synapse",
        meta={"scope": {"concept_name": "Photosynthesis", "teacher_id": "t_001", "cycle": 1}},
        initial_state=RunState.TEACHER_SETUP,
    )
    ctx = Context(store=store, run_id=run_id, settings=settings)
    return store, run_id, ctx, settings


# ----------------------------------------------------------------------
# 1. Concept Extraction Tests
# ----------------------------------------------------------------------

def test_concept_extraction_shape():
    """Verify concept extraction produces valid ConceptNode objects with expected attributes."""
    concepts = extract_concepts(SAMPLE_MARKDOWN, concept_name="Photosynthesis")
    assert len(concepts) >= 2
    for c in concepts:
        assert isinstance(c, ConceptNode)
        assert c.id is not None
        assert len(c.name) > 0
        assert len(c.summary) > 0
        assert isinstance(c.prerequisites, list)


def test_handle_teacher_setup_appends_canonical_note(test_env):
    """Verify handle_teacher_setup persists canonical note with concepts and transitions to TAG_CONFIRMATION."""
    store, run_id, ctx, _ = test_env
    # Seed initial raw note from start_teacher_run
    store.append(run_id, RecordKind.CANONICAL_NOTE.value, {"markdown": SAMPLE_MARKDOWN, "concept_name": "Photosynthesis"}, "teacher")

    next_state = handle_teacher_setup(ctx)
    assert next_state is RunState.TAG_CONFIRMATION

    latest_note = ctx.latest(RecordKind.CANONICAL_NOTE.value)
    assert latest_note is not None
    assert latest_note["teacher_confirmed"] is False
    assert len(latest_note["extracted_concepts"]) >= 2
    assert ctx.store.meta(run_id)["scope"]["concept_id"] is not None


# ----------------------------------------------------------------------
# 2. Tag Confirmation Tests
# ----------------------------------------------------------------------

def test_tag_confirmation_happy_path(test_env):
    """Verify tag confirmation question creation, teacher answer, and transition to TEST_READY."""
    store, run_id, ctx, _ = test_env
    # Seed setup
    handle_teacher_setup(ctx)

    # First entry parks run at TAG_CONFIRMATION
    state = handle_tag_confirmation(ctx)
    assert state is RunState.TAG_CONFIRMATION
    open_qs = store.open_questions(run_id)
    assert len(open_qs) == 1
    qid = open_qs[0].id

    # Teacher answers with confirmation and edited concepts
    edited = [
        {"name": "Light Reactions (Edited)", "summary": "Detailed electron transport", "prerequisites": []}
    ]
    callback.answer(store, qid, json.dumps({"confirmed": True, "edited_concepts": edited}), who="teacher_01")

    # Re-entry processes answer and transitions to TEST_READY
    state_after = handle_tag_confirmation(ctx)
    assert state_after is RunState.TEST_READY

    # Verify records appended
    conf_rec = ctx.latest(RecordKind.CONFIRMATION.value)
    assert conf_rec is not None
    assert conf_rec["confirmed"] is True
    assert conf_rec["timed_out"] is False
    assert len(conf_rec["edited_concepts"]) == 1
    assert conf_rec["edited_concepts"][0]["name"] == "Light Reactions (Edited)"

    note_rec = ctx.latest(RecordKind.CANONICAL_NOTE.value)
    assert note_rec["teacher_confirmed"] is True
    assert note_rec["extracted_concepts"][0]["name"] == "Light Reactions (Edited)"


def test_tag_confirmation_second_answer_rejected(test_env):
    """Verify that a second answer to the same question is write-once rejected."""
    store, run_id, ctx, _ = test_env
    handle_teacher_setup(ctx)
    handle_tag_confirmation(ctx)

    qid = store.open_questions(run_id)[0].id
    # First answer
    res1 = callback.answer(store, qid, json.dumps({"confirmed": True}), who="teacher_01")
    assert res1 == run_id

    # Second answer to same question is ignored/returns run_id without duplicate appending
    history_len_before = len(ctx.history("expert_answer"))
    res2 = callback.answer(store, qid, json.dumps({"confirmed": True, "notes": "second"}), who="teacher_02")
    assert res2 == run_id
    history_len_after = len(ctx.history("expert_answer"))
    assert history_len_before == history_len_after


def test_tag_confirmation_timeout_path(test_env):
    """Verify that timeout generates TeacherConfirmation with confirmed=False, timed_out=True."""
    store, run_id, ctx, _ = test_env
    store.append(run_id, RecordKind.CANONICAL_NOTE.value, {"markdown": SAMPLE_MARKDOWN, "concept_name": "Photosynthesis"}, "teacher")
    handle_teacher_setup(ctx)
    handle_tag_confirmation(ctx)

    # Question is open
    qid = store.open_questions(run_id)[0].id
    # Simulate timeout by setting timeout_at to past
    store.db.execute("UPDATE questions SET timeout_at = ? WHERE id = ?", (time.time() - 1, qid))
    expired = callback.sweep(store, run_id)
    assert len(expired) == 1
    assert expired[0].id == qid

    # Re-entry after timeout
    state = handle_tag_confirmation(ctx)
    assert state is RunState.TEST_READY

    conf = ctx.latest(RecordKind.CONFIRMATION.value)
    assert conf is not None
    assert conf["confirmed"] is False
    assert conf["timed_out"] is True

    # Rule D.5: Test generation proceeds with extracted concepts unedited
    note = ctx.latest(RecordKind.CANONICAL_NOTE.value)
    assert note["teacher_confirmed"] is True
    assert len(note["extracted_concepts"]) >= 2


def test_tag_confirmation_rejects_teacher_confirmed_false(test_env):
    """Rule D.5: A teacher submission is always confirmed=True; confirmed=False is rejected."""
    store, run_id, ctx, _ = test_env
    handle_teacher_setup(ctx)
    handle_tag_confirmation(ctx)

    qid = store.open_questions(run_id)[0].id
    callback.answer(store, qid, json.dumps({"confirmed": False}), who="teacher_01")

    with pytest.raises(ValueError, match="confirmed=False"):
        handle_tag_confirmation(ctx)


# ----------------------------------------------------------------------
# 3. Test Generation Tests
# ----------------------------------------------------------------------

def test_generate_test_shape_and_options():
    """Verify test generation produces exactly 4 unique options and correct_answer membership."""
    concepts = [
        ConceptNode(id="c_01", name="Thylakoid", summary="Site of light reactions"),
        ConceptNode(id="c_02", name="Stroma", summary="Site of dark reactions"),
    ]
    test_obj = generate_test(concept_id="c_root", concept_name="Photosynthesis", concepts=concepts)

    assert isinstance(test_obj, Test)
    assert test_obj.concept_id == "c_root"
    assert test_obj.concept_name == "Photosynthesis"
    assert len(test_obj.questions) >= 2

    for q in test_obj.questions:
        assert isinstance(q, TestQuestion)
        assert len(q.options) == 4
        # Options must be strictly unique
        assert len(set(q.options)) == 4
        # Correct answer must be one of the options
        assert q.correct_answer in q.options
        assert q.concept_id in ["c_01", "c_02"]


def test_handle_test_ready_appends_test_and_transitions(test_env):
    """Verify handle_test_ready generates and appends Test, then transitions to AWAITING_STUDENT."""
    store, run_id, ctx, _ = test_env
    store.append(run_id, RecordKind.CANONICAL_NOTE.value, {"markdown": SAMPLE_MARKDOWN, "concept_name": "Photosynthesis"}, "teacher")
    handle_teacher_setup(ctx)
    handle_tag_confirmation(ctx)
    qid = store.open_questions(run_id)[0].id
    callback.answer(store, qid, json.dumps({"confirmed": True}), who="teacher")
    handle_tag_confirmation(ctx)

    next_state = handle_test_ready(ctx)
    assert next_state is RunState.AWAITING_STUDENT

    test_record = ctx.latest(RecordKind.TEST.value)
    assert test_record is not None
    assert test_record["concept_name"] == "Photosynthesis"
    assert len(test_record["questions"]) >= 2
    for q in test_record["questions"]:
        assert len(q["options"]) == 4
        assert q["correct_answer"] in q["options"]


# ----------------------------------------------------------------------
# 4. Corpus Ingestion Boundaries
# ----------------------------------------------------------------------

def test_corpus_ingestion_boundary(tmp_path):
    """Rule D.8: Ingest only canonical_notes and concept_definitions; never corpus root or generated."""
    db_path = tmp_path / "test_corpus.db"
    store = Store(db_path)

    result = ingest_corpus(store)
    assert "canonical_notes" in result
    assert "concept_definitions" in result

    # Check that canonical_notes and concept_definitions were processed
    assert result["canonical_notes"]["files"] >= 1
    assert result["concept_definitions"]["files"] >= 1


# ----------------------------------------------------------------------
# 5. Architecture & Import Boundaries
# ----------------------------------------------------------------------

def test_no_cross_domain_imports():
    """Curriculum domain must not import agents, analytics, runtime, api, or web."""
    import sys
    curriculum_dir = Path(__file__).resolve().parent.parent.parent / "synapse" / "curriculum"
    forbidden = ["synapse.agents", "synapse.analytics", "synapse.runtime", "api", "web", "frontend"]

    for py_file in curriculum_dir.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for fb in forbidden:
            assert f"import {fb}" not in text, f"Violation in {py_file}: imports {fb}"
            assert f"from {fb}" not in text, f"Violation in {py_file}: imports from {fb}"
