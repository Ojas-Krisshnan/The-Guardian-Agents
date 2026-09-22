# tests/test_synapse/test_curriculum.py
import json
import pytest
from slice.config import Settings
from slice.store import Store
from slice.runner import Context
from synapse.curriculum.flow import (
    extract_concepts,
    generate_test,
    handle_teacher_setup,
    handle_tag_confirmation,
    handle_test_ready,
)
from synapse.schemas import CanonicalNote, ConceptNode, RecordKind
from synapse.state_machine import RunState


@pytest.fixture
def store():
    st = Store(":memory:")
    yield st
    st.close()


@pytest.fixture
def settings():
    return Settings(
        api_key="",
        model="dummy",
        fallback_model="dummy",
        escalation_model="dummy",
        max_tokens=1000,
        max_tokens_per_run=10000,
        max_attempts_per_step=3,
        expert_timeout_minutes=10,
        langfuse_public="",
        langfuse_secret="",
        langfuse_host="",
    )


def test_concept_extraction():
    note = CanonicalNote(
        concept_id="c1",
        markdown="# Recursion\nRecursion solves problems by calling itself.",
    )
    concepts = extract_concepts(note, "Recursion")
    assert len(concepts) >= 2
    assert all(isinstance(c, ConceptNode) for c in concepts)
    assert any(c.name == "Recursion" for c in concepts)
    assert all(len(c.summary) > 5 for c in concepts)


def test_generate_test():
    concept = ConceptNode(name="Recursion", summary="Base cases and recursive steps")
    note = CanonicalNote(concept_id="c1", markdown="Recursion note")
    test = generate_test(concept, note)
    assert test.concept_id == concept.id
    assert len(test.questions) == 3
    for q in test.questions:
        assert len(q.options) == 4
        assert len(set(q.options)) == 4
        assert q.correct_answer in q.options


@pytest.mark.anyio
async def test_handle_teacher_setup(store, settings):
    run_id = store.create_run("synapse", {"concept_id": "c1", "concept_name": "Recursion"})
    note = CanonicalNote(concept_id="c1", markdown="Notes on recursion")
    store.append(run_id, RecordKind.CANONICAL_NOTE, note.model_dump(mode="json"), produced_by="teacher")

    ctx = Context(store, run_id, settings)
    next_state = await handle_teacher_setup(ctx)
    assert next_state == RunState.TAG_CONFIRMATION

    latest_note = store.latest(run_id, RecordKind.CANONICAL_NOTE)
    assert latest_note is not None
    assert len(latest_note["extracted_concepts"]) >= 2


@pytest.mark.anyio
async def test_handle_tag_confirmation_parks_and_resumes(store, settings):
    run_id = store.create_run("synapse", {"concept_id": "c1", "teacher_id": "t1"})
    note = CanonicalNote(
        concept_id="c1",
        markdown="Recursion notes",
        extracted_concepts=[ConceptNode(name="Recursion", summary="Recursion basics")],
    )
    store.append(run_id, RecordKind.CANONICAL_NOTE, note.model_dump(mode="json"), produced_by="test")

    ctx = Context(store, run_id, settings)
    # First entry parks the run with a question
    state1 = await handle_tag_confirmation(ctx)
    assert state1 == RunState.TAG_CONFIRMATION
    open_qs = store.open_questions(run_id)
    assert len(open_qs) == 1
    qid = open_qs[0].id

    # Teacher answers
    store.answer(qid, json.dumps({"confirmed": True, "edited_concepts": None}))

    # Re-entry processes answer and transitions to TEST_READY
    state2 = await handle_tag_confirmation(ctx)
    assert state2 == RunState.TEST_READY

    conf = store.latest(run_id, RecordKind.CONFIRMATION)
    assert conf is not None
    assert conf["confirmed"] is True
    assert conf["timed_out"] is False


@pytest.mark.anyio
async def test_handle_test_ready(store, settings):
    run_id = store.create_run("synapse", {"concept_id": "c1"})
    note = CanonicalNote(
        concept_id="c1",
        markdown="Recursion notes",
        extracted_concepts=[ConceptNode(name="Recursion", summary="Recursion basics")],
        teacher_confirmed=True,
    )
    store.append(run_id, RecordKind.CANONICAL_NOTE, note.model_dump(mode="json"), produced_by="test")

    ctx = Context(store, run_id, settings)
    state = await handle_test_ready(ctx)
    assert state == RunState.AWAITING_STUDENT

    test_rec = store.latest(run_id, RecordKind.TEST)
    assert test_rec is not None
    assert len(test_rec["questions"]) == 3
