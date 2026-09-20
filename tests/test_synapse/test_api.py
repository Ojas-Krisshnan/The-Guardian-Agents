"""
Tests for Synapse API endpoints and privacy enforcement.
Authoritative contract: Contracts.md Sections C.4, D.5, D.9, F.3.
"""
import pytest
from fastapi.testclient import TestClient

from api.main import app
from slice.config import Settings
from slice.store import Store
from synapse.runtime.service import RuntimeService, set_service
from synapse.schemas import (
    CanonicalNote,
    ConceptNode,
    NoteVersion,
    RecordKind,
    Test,
    TestQuestion,
)
from synapse.state_machine import RunState


@pytest.fixture
def api_client(tmp_path):
    store = Store(tmp_path / "api_test.db")
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
    svc = RuntimeService(store=store, settings=settings)
    set_service(svc)

    with TestClient(app) as client:
        yield client, svc


def test_teacher_concepts_flow(api_client):
    """Verify teacher concept creation, pending retrieval, and tag confirmation."""
    client, svc = api_client
    headers = {"X-User-Id": "t_01", "X-User-Role": "teacher"}

    # 1. Create concept
    resp = client.post(
        "/teacher/concepts",
        json={"markdown": "# Photosynthesis\n## Light Reactions\nDetails.", "concept_name": "Photosynthesis"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    run_id = data["run_id"]
    assert data["concept"]["name"] == "Photosynthesis"

    # 2. Get pending concepts
    resp_pending = client.get(f"/teacher/concepts/{run_id}", headers=headers)
    assert resp_pending.status_code == 200
    pending_data = resp_pending.json()
    assert pending_data["run_id"] == run_id
    assert len(pending_data["concepts"]) >= 1

    # 3. Path vs Body mismatch -> 422
    resp_mismatch = client.post(
        f"/teacher/concepts/{run_id}/confirm",
        json={"run_id": "different_run_id", "confirmed": True},
        headers=headers,
    )
    assert resp_mismatch.status_code == 422

    # 4. Valid confirmation
    resp_confirm = client.post(
        f"/teacher/concepts/{run_id}/confirm",
        json={"run_id": run_id, "confirmed": True, "edited_concepts": pending_data["concepts"]},
        headers=headers,
    )
    assert resp_confirm.status_code == 200
    confirm_data = resp_confirm.json()
    assert confirm_data["run_id"] == run_id
    assert confirm_data["state"] in [RunState.TEST_READY.value, RunState.AWAITING_STUDENT.value]

    # 5. Second confirmation -> 409
    resp_second = client.post(
        f"/teacher/concepts/{run_id}/confirm",
        json={"run_id": run_id, "confirmed": True},
        headers=headers,
    )
    assert resp_second.status_code == 409


def test_teacher_test_not_ready_and_ready(api_client):
    """Verify 404 test_not_ready before test generation, and 200 Test once ready."""
    client, svc = api_client
    headers = {"X-User-Id": "t_01", "X-User-Role": "teacher"}

    run_id = svc.store.create_run("synapse", initial_state=RunState.TEACHER_SETUP)
    # Test not ready
    resp = client.get(f"/teacher/tests/{run_id}", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "test_not_ready"

    # Seed test record
    test_obj = Test(
        id="test_01",
        concept_id="c_photo",
        concept_name="Photosynthesis",
        questions=[
            TestQuestion(
                id="q1",
                text="What gas is released?",
                correct_answer="Oxygen",
                options=["Oxygen", "Nitrogen", "Hydrogen", "Carbon"],
                concept_id="c_photo",
            )
        ],
    )
    svc.store.append(run_id, RecordKind.TEST.value, test_obj.model_dump(mode="json"), "curriculum")

    resp_ready = client.get(f"/teacher/tests/{run_id}", headers=headers)
    assert resp_ready.status_code == 200
    assert resp_ready.json()["concept_name"] == "Photosynthesis"


def test_student_attempt_and_notes_privacy(api_client):
    """Verify student attempt submission, pipeline execution, and private note isolation."""
    client, svc = api_client
    student_headers = {"X-User-Id": "student_alice", "X-User-Role": "student"}

    # Setup a run at AWAITING_STUDENT
    run_id = svc.store.create_run(
        "synapse",
        meta={"scope": {"concept_id": "c_photo", "student_id": "student_alice", "cycle": 1}},
        initial_state=RunState.AWAITING_STUDENT,
    )
    test_obj = Test(
        id="test_photo_01",
        concept_id="c_photo",
        concept_name="Photosynthesis",
        questions=[
            TestQuestion(
                id="q1",
                text="What gas is released?",
                correct_answer="Oxygen",
                options=["Oxygen", "Nitrogen", "Hydrogen", "Carbon"],
                concept_id="c_photo",
            )
        ],
    )
    canonical_note = CanonicalNote(
        concept_id="c_photo",
        markdown="# Photosynthesis\nLight reactions produce Oxygen.",
        extracted_concepts=[ConceptNode(id="c1", name="Light Reactions", summary="Produces Oxygen")],
        teacher_confirmed=True,
    )
    svc.store.append(run_id, RecordKind.TEST.value, test_obj.model_dump(mode="json"), "curriculum")
    svc.store.append(run_id, RecordKind.CANONICAL_NOTE.value, canonical_note.model_dump(mode="json"), "curriculum")

    # Submit attempt
    resp_submit = client.post(
        "/student/attempts",
        json={"test_id": "test_photo_01", "answers": {"q1": "Oxygen"}},
        headers=student_headers,
    )
    assert resp_submit.status_code == 200
    submit_data = resp_submit.json()
    assert submit_data["attempt"]["score"] == 1
    assert submit_data["diagnosis"] is not None
    assert submit_data["note"] is not None
    assert submit_data["analysis"] is not None

    # Verify student notes endpoint
    resp_notes = client.get("/student/notes/c_photo", headers=student_headers)
    assert resp_notes.status_code == 200
    notes_data = resp_notes.json()
    assert len(notes_data["notes"]) >= 1
    assert notes_data["notes"][0]["student_id"] == "student_alice"

    # Privacy check: another student cannot see Alice's notes
    bob_headers = {"X-User-Id": "student_bob", "X-User-Role": "student"}
    resp_bob = client.get("/student/notes/c_photo", headers=bob_headers)
    assert resp_bob.status_code == 200
    assert len(resp_bob.json()["notes"]) == 0

    # Privacy check: teacher endpoints must never contain NoteVersion or markdown notes
    teacher_headers = {"X-User-Id": "t_01", "X-User-Role": "teacher"}
    resp_analytics = client.get("/teacher/analytics/c_photo", headers=teacher_headers)
    assert resp_analytics.status_code == 200
    assert "markdown" not in resp_analytics.text


def test_runs_status_endpoint(api_client):
    """Verify run status endpoint returns correct structure and counters."""
    client, svc = api_client
    run_id = svc.store.create_run(
        "synapse",
        meta={"scope": {"concept_id": "c_photo", "cycle": 2}},
        initial_state=RunState.AWAITING_STUDENT,
    )
    resp = client.get(f"/runs/{run_id}/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == run_id
    assert data["state"] == RunState.AWAITING_STUDENT.value
    assert data["current_cycle"] == 2
