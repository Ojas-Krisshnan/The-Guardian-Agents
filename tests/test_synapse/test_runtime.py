# tests/test_synapse/test_runtime.py
import json
import pytest
from slice.config import Settings
from slice.store import Store
from synapse.curriculum.stub import stub_generate_test
from synapse.runtime.flow import (
    advance,
    get_run_status,
    start_teacher_run,
    submit_attempt,
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


def test_start_teacher_run(store, settings):
    run_id = start_teacher_run(
        store=store,
        markdown="# Recursion\nCore definitions and base cases.",
        concept_name="Recursion",
        teacher_id="teacher_1",
        settings=settings,
    )
    status = get_run_status(store, run_id)
    assert status.run_id == run_id
    assert status.state == RunState.TAG_CONFIRMATION

    open_qs = store.open_questions(run_id)
    assert len(open_qs) == 1


def test_tag_confirmation_to_awaiting_student(store, settings):
    run_id = start_teacher_run(
        store=store,
        markdown="# Recursion\nCore definitions and base cases.",
        concept_name="Recursion",
        teacher_id="teacher_1",
        settings=settings,
    )

    open_qs = store.open_questions(run_id)
    assert len(open_qs) == 1
    qid = open_qs[0].id

    # Teacher confirms
    store.answer(qid, json.dumps({"confirmed": True, "edited_concepts": None}))

    # Advance
    end_state = advance(store, run_id, settings)
    assert end_state == RunState.AWAITING_STUDENT

    # Test is ready
    test_data = store.latest(run_id, RecordKind.TEST)
    assert test_data is not None
    assert len(test_data["questions"]) == 3


def test_full_student_cycle_to_complete(store, settings):
    run_id = start_teacher_run(
        store=store,
        markdown="# Recursion\nCore definitions and base cases.",
        concept_name="Recursion",
        teacher_id="teacher_1",
        settings=settings,
    )

    open_qs = store.open_questions(run_id)
    store.answer(open_qs[0].id, json.dumps({"confirmed": True}))
    advance(store, run_id, settings)

    test_data = store.latest(run_id, RecordKind.TEST)
    test_id = test_data["id"]
    answers = {q["id"]: q["correct_answer"] for q in test_data["questions"]}

    # Student submits attempt
    submit_attempt(
        store=store,
        run_id=run_id,
        student_id="student_A",
        test_id=test_id,
        answers=answers,
        settings=settings,
    )

    status = get_run_status(store, run_id)
    assert status.state == RunState.COMPLETE

    # Verify all artifacts are generated and persisted
    assert store.latest(run_id, RecordKind.ATTEMPT) is not None
    assert store.latest(run_id, RecordKind.DIAGNOSIS) is not None
    assert store.latest(run_id, RecordKind.NOTE_VERSION) is not None
    assert store.latest(run_id, RecordKind.ANALYSIS) is not None
    assert store.latest(run_id, RecordKind.CLASS_ANALYTICS) is not None
    assert store.latest(run_id, RecordKind.CONCEPT_GRAPH) is not None
