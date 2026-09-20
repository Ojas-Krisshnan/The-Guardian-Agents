"""
Tests for server-rendered web routes in Synapse.
Authoritative contract: Contracts.md Sections D.5, D.6.
"""
import pytest
from fastapi.testclient import TestClient

from api.main import app
from slice import callback
from slice.config import Settings
from slice.store import Store
from synapse.runtime.service import RuntimeService, set_service
from synapse.schemas import (
    CanonicalNote,
    ConceptNode,
    RecordKind,
    Test,
    TestQuestion,
)
from synapse.state_machine import RunState


@pytest.fixture
def web_client(tmp_path):
    store = Store(tmp_path / "web_test.db")
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


def test_web_teacher_tags_flow(web_client):
    """Verify web teacher tag editing, form submission, and redirect to confirmation."""
    client, svc = web_client

    run_id = svc.store.create_run(
        "synapse",
        meta={"scope": {"concept_id": "c_photo", "concept_name": "Photosynthesis", "cycle": 1}},
        initial_state=RunState.TAG_CONFIRMATION,
    )
    note = CanonicalNote(
        concept_id="c_photo",
        markdown="# Photosynthesis notes",
        extracted_concepts=[ConceptNode(id="c_01", name="Light Reactions", summary="Details")],
        teacher_confirmed=False,
    )
    svc.store.append(run_id, RecordKind.CANONICAL_NOTE.value, note.model_dump(mode="json"), "curriculum")

    # Ask tag confirmation callback question
    callback.ask(
        store=svc.store,
        run_id=run_id,
        question="Confirm tags",
        context={"concepts": [{"id": "c_01", "name": "Light Reactions", "summary": "Details"}]},
        settings=svc.settings,
        park_state=RunState.TAG_CONFIRMATION,
        resume_state=RunState.TEST_READY,
    )

    # GET tags page
    resp_get = client.get(f"/web/teacher/tags/{run_id}")
    assert resp_get.status_code == 200
    assert "Teacher Tag Confirmation" in resp_get.text
    assert "Light Reactions" in resp_get.text

    # POST tags form
    form_data = {
        "run_id": run_id,
        "concept_name_0": "Light Reactions (Refined)",
        "concept_summary_0": "Refined summary of reactions",
        "concept_id_0": "c_01",
    }
    resp_post = client.post(f"/web/teacher/tags/{run_id}", data=form_data, follow_redirects=False)
    assert resp_post.status_code == 303
    assert resp_post.headers["location"] == f"/web/teacher/tags/{run_id}/confirm"

    # GET confirm page
    resp_confirm = client.get(f"/web/teacher/tags/{run_id}/confirm")
    assert resp_confirm.status_code == 200
    assert "Curriculum Tags Confirmed" in resp_confirm.text


def test_web_student_attempt_flow(web_client):
    """Verify web student quiz rendering and submission."""
    client, svc = web_client

    run_id = svc.store.create_run(
        "synapse",
        meta={"scope": {"concept_id": "c_photo", "concept_name": "Photosynthesis", "cycle": 1}},
        initial_state=RunState.AWAITING_STUDENT,
    )
    test_obj = Test(
        id="test_web_01",
        concept_id="c_photo",
        concept_name="Photosynthesis",
        questions=[
            TestQuestion(
                id="q_w1",
                text="Which organelle houses chlorophyll?",
                correct_answer="Chloroplast",
                options=["Chloroplast", "Mitochondria", "Nucleus", "Ribosome"],
                concept_id="c_photo",
            )
        ],
    )
    note = CanonicalNote(
        concept_id="c_photo",
        markdown="# Chloroplasts\nChloroplasts contain chlorophyll.",
        extracted_concepts=[ConceptNode(id="c_chloroplast", name="Chloroplast", summary="Organelle")],
        teacher_confirmed=True,
    )
    svc.store.append(run_id, RecordKind.TEST.value, test_obj.model_dump(mode="json"), "curriculum")
    svc.store.append(run_id, RecordKind.CANONICAL_NOTE.value, note.model_dump(mode="json"), "curriculum")

    # GET attempt page
    resp_get = client.get("/web/student/attempts/test_web_01")
    assert resp_get.status_code == 200
    assert "Diagnostic Assessment: Photosynthesis" in resp_get.text
    assert "Which organelle houses chlorophyll?" in resp_get.text

    # POST attempt form
    form_data = {
        "run_id": run_id,
        "test_id": "test_web_01",
        "q_q_w1": "Chloroplast",
    }
    resp_post = client.post("/web/student/attempts/test_web_01", data=form_data)
    assert resp_post.status_code == 200
    res_json = resp_post.json()
    assert res_json["status"] == "success"
    assert res_json["score"] == 1
    assert res_json["total"] == 1
