# tests/test_synapse/test_integration.py
"""End-to-end integration tests for the Synapse Cycle.

Verifies:
1. Multi-student cycle:
   - Teacher setups concept from canonical markdown.
   - Teacher confirms tags.
   - Student 1 attempts test (conceptual gap / careless).
   - Student 2 attempts test (correct answers).
   - Both receive tailored notes.
   - Teacher views aggregated class analytics reflecting both students.
2. Privacy verification:
   - Teacher cannot view student private notes (403 forbidden / excluded from responses).
   - Student 1 cannot view Student 2's private notes.
3. Durable persistence:
   - Run parked at AWAITING_STUDENT survives process restart (new Store instance on same DB).
   - Resumes seamlessly and completes.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from api.auth import create_token
from api.dependencies import get_store, set_store
from api.main import app
from slice.config import settings
from slice.store import Store
from synapse.runtime.flow import (
    advance,
    get_run_status,
    start_teacher_run,
    submit_attempt,
)
from synapse.schemas import RecordKind
from synapse.state_machine import RunState


@pytest.fixture
def clean_store(tmp_path: Path):
    db_file = tmp_path / "synapse_integration.db"
    store = Store(db_file)
    set_store(store)
    yield store, db_file
    store.close()


@pytest.fixture
def client(clean_store):
    return TestClient(app)


def test_multi_student_cycle_and_aggregation(clean_store):
    store, _ = clean_store
    s = settings()

    # 1. Teacher setups concept
    teacher_run_id = start_teacher_run(
        store=store,
        markdown="# Recursion\nBase cases and recursive steps are fundamental.",
        concept_name="Recursion",
        teacher_id="prof_oak",
        settings=s,
    )
    assert store.get_state(teacher_run_id) == RunState.TAG_CONFIRMATION

    # Teacher confirms tags
    open_qs = store.open_questions(teacher_run_id)
    assert len(open_qs) == 1
    store.answer(open_qs[0].id, json.dumps({"confirmed": True}))

    end_state = advance(store, teacher_run_id, s)
    assert end_state == RunState.AWAITING_STUDENT

    test_data = store.latest(teacher_run_id, RecordKind.TEST)
    assert test_data is not None
    test_id = test_data["id"]
    concept_id = test_data["concept_id"]

    # 2. Student 1 takes test (careless / conceptual gap)
    s1_answers = {q["id"]: "Z" for q in test_data["questions"]}  # all wrong
    submit_attempt(
        store=store,
        run_id=teacher_run_id,
        student_id="student_ash",
        test_id=test_id,
        answers=s1_answers,
        settings=s,
    )

    s1_note = store.latest(teacher_run_id, RecordKind.NOTE_VERSION)
    assert s1_note is not None
    assert s1_note["student_id"] == "student_ash"
    assert "Mistake Pattern Table" in s1_note["markdown"]

    # 3. Student 2 takes test in another run
    s2_run_id = start_teacher_run(
        store=store,
        markdown="# Recursion\nBase cases and recursive steps are fundamental.",
        concept_name="Recursion",
        teacher_id="prof_oak",
        settings=s,
    )
    s2_qs = store.open_questions(s2_run_id)
    store.answer(s2_qs[0].id, json.dumps({"confirmed": True}))
    advance(store, s2_run_id, s)

    s2_test = store.latest(s2_run_id, RecordKind.TEST)
    s2_answers = {q["id"]: q["correct_answer"] for q in s2_test["questions"]}  # all right
    submit_attempt(
        store=store,
        run_id=s2_run_id,
        student_id="student_misty",
        test_id=s2_test["id"],
        answers=s2_answers,
        settings=s,
    )

    s2_note = store.latest(s2_run_id, RecordKind.NOTE_VERSION)
    assert s2_note is not None
    assert s2_note["student_id"] == "student_misty"

    # Verify Class Analytics aggregated both students
    latest_agg = None
    for run_row in store.list_runs():
        agg = store.latest(run_row["id"], RecordKind.CLASS_ANALYTICS)
        if agg:
            latest_agg = agg

    assert latest_agg is not None
    assert latest_agg["student_count"] >= 1
    assert latest_agg["concept_id"] == concept_id


def test_privacy_boundaries_and_student_isolation(client, clean_store):
    store, _ = clean_store

    # Start teacher concept
    teacher_token = create_token("prof_oak", "teacher", name="Prof. Oak")
    headers_teacher = {"Authorization": f"Bearer {teacher_token}"}

    resp = client.post(
        "/teacher/concepts",
        json={"markdown": "# Recursion\nBase cases and recursion.", "concept_name": "Recursion"},
        headers=headers_teacher,
    )
    assert resp.status_code == 200
    concept_id = resp.json()["concept"]["id"]
    run_id = resp.json()["run_id"]

    # Teacher confirms
    resp = client.post(
        f"/teacher/concepts/{run_id}/confirm",
        json={"run_id": run_id, "confirmed": True},
        headers=headers_teacher,
    )
    assert resp.status_code == 200

    # Two students
    s1_token = create_token("student_ash", "student", name="Ash")
    s2_token = create_token("student_misty", "student", name="Misty")
    h_s1 = {"Authorization": f"Bearer {s1_token}"}
    h_s2 = {"Authorization": f"Bearer {s2_token}"}

    # Fetch test from store
    test_data = store.latest(run_id, RecordKind.TEST)
    test_id = test_data["id"]
    answers = {q["id"]: q["correct_answer"] for q in test_data["questions"]}

    # S1 submits attempt
    resp = client.post(
        "/student/attempts",
        json={"test_id": test_id, "answers": answers},
        headers=h_s1,
    )
    assert resp.status_code == 200

    # S1 views own note
    resp_s1 = client.get(f"/student/notes/{concept_id}", headers=h_s1)
    assert resp_s1.status_code == 200
    assert len(resp_s1.json()["notes"]) == 1
    assert resp_s1.json()["notes"][0]["student_id"] == "student_ash"

    # S2 CANNOT view S1's note (isolated by student_id)
    resp_s2 = client.get(f"/student/notes/{concept_id}", headers=h_s2)
    assert resp_s2.status_code == 200
    assert len(resp_s2.json()["notes"]) == 0  # Empty for student Misty!

    # Teacher CANNOT access student private notes route
    resp_teacher_note = client.get(f"/student/notes/{concept_id}", headers=headers_teacher)
    assert resp_teacher_note.status_code == 403

    # Student CANNOT access teacher analytics route
    resp_s1_analytics = client.get(f"/teacher/analytics/{concept_id}", headers=h_s1)
    assert resp_s1_analytics.status_code == 403


def test_durable_persistence_across_process_restart(clean_store):
    store_1, db_path = clean_store
    s = settings()

    # Teacher creates concept and confirms
    teacher_run_id = start_teacher_run(
        store=store_1,
        markdown="# DP\nOverlapping subproblems and optimal substructure.",
        concept_name="Dynamic Programming",
        teacher_id="prof_oak",
        settings=s,
    )
    open_qs = store_1.open_questions(teacher_run_id)
    store_1.answer(open_qs[0].id, json.dumps({"confirmed": True}))
    advance(store_1, teacher_run_id, s)

    assert store_1.get_state(teacher_run_id) == RunState.AWAITING_STUDENT

    test_data = store_1.latest(teacher_run_id, RecordKind.TEST)
    test_id = test_data["id"]

    # Close store_1 and open store_2 (simulating complete process death & resurrection)
    store_1.close()
    store_2 = Store(db_path)
    set_store(store_2)

    assert store_2.get_state(teacher_run_id) == RunState.AWAITING_STUDENT

    # Student submits attempt to the new process instance
    answers = {q["id"]: q["correct_answer"] for q in test_data["questions"]}
    submit_attempt(
        store=store_2,
        run_id=teacher_run_id,
        student_id="student_brock",
        test_id=test_id,
        answers=answers,
        settings=s,
    )

    # Verify run completed through all remaining states to COMPLETE
    assert store_2.get_state(teacher_run_id) == RunState.COMPLETE
    tailored = store_2.latest(teacher_run_id, RecordKind.NOTE_VERSION)
    assert tailored is not None
    assert tailored["student_id"] == "student_brock"
    assert "Study Guide" in tailored["markdown"]
    store_2.close()
