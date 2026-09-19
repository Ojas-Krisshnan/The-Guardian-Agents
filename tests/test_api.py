"""Tests for Person 5 API foundation, Runs API, Questions API, and Mock Advancement."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.auth import get_current_user
from api.deps import get_store
from api.main import app
from slice import callback
from slice.config import settings
from slice.records import RunState
from slice.store import Store


@pytest.fixture
def client(tmp_path):
    """Test client fixture providing an isolated Store database and default teacher auth."""
    test_db = str(tmp_path / "test_api.db")

    def _override_store():
        store = Store(test_db)
        try:
            yield store
        finally:
            store.close()

    def _override_current_user():
        return {"sub": "teacher", "role": "teacher"}

    app.dependency_overrides[get_store] = _override_store
    app.dependency_overrides[get_current_user] = _override_current_user
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


def test_app_import():
    """Verify that the FastAPI application imports and is instantiated."""
    assert app is not None
    assert app.title == "Synapse Cycle API"


def test_health_endpoint(client):
    """Verify GET /health returns HTTP 200 with status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_registered_routes():
    """Verify router routes for /auth, /runs and /questions are registered on app."""
    prefixes = [getattr(r, "original_router").prefix for r in app.routes if hasattr(r, "original_router")]
    assert "/auth" in prefixes
    assert "/runs" in prefixes
    assert "/questions" in prefixes


def test_create_run(client):
    """Verify POST /runs creates a new run with status 201."""
    payload = {"domain": "test_domain", "meta": {"user_id": "u123"}}
    response = client.post("/runs", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"].startswith("run_")
    assert data["domain"] == "test_domain"
    assert data["state"] == "drafting"
    assert data["meta"] == {"user_id": "u123"}


def test_list_runs(client):
    """Verify GET /runs returns list of runs."""
    client.post("/runs", json={"domain": "d1"})
    client.post("/runs", json={"domain": "d2"})

    response = client.get("/runs?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    domains = {r["domain"] for r in data}
    assert domains == {"d1", "d2"}


def test_get_run_success(client):
    """Verify GET /runs/{run_id} returns run details."""
    create_res = client.post("/runs", json={"domain": "demo", "meta": {"key": "val"}})
    run_id = create_res.json()["id"]

    response = client.get(f"/runs/{run_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == run_id
    assert data["domain"] == "demo"
    assert data["state"] == "drafting"
    assert data["meta"] == {"key": "val"}


def test_get_run_not_found(client):
    """Verify GET /runs/{run_id} returns HTTP 404 for nonexistent run."""
    response = client.get("/runs/run_nonexistent999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Run not found"}


def test_get_run_history_and_replay(client, tmp_path):
    """Verify GET /runs/{run_id}/history and /runs/{run_id}/replay."""
    create_res = client.post("/runs", json={"domain": "demo"})
    run_id = create_res.json()["id"]

    test_db = str(tmp_path / "test_api.db")
    store = Store(test_db)
    store.append(run_id, "thesis", {"content": "initial thesis"}, "builder")
    store.close()

    history_res = client.get(f"/runs/{run_id}/history?kind=thesis")
    assert history_res.status_code == 200
    h_data = history_res.json()
    assert len(h_data) == 1
    assert h_data[0]["kind"] == "thesis"

    replay_res = client.get(f"/runs/{run_id}/replay")
    assert replay_res.status_code == 200
    r_data = replay_res.json()
    assert len(r_data) == 1


# ------------------------------------------------------------- Question Tests


def test_get_run_questions_and_details(client, tmp_path):
    """Test A & B: Create question in setup, list via /runs/{run_id}/questions, get via /questions/{qid}."""
    create_res = client.post("/runs", json={"domain": "demo"})
    run_id = create_res.json()["id"]

    test_db = str(tmp_path / "test_api.db")
    store = Store(test_db)
    qid = callback.ask(store, run_id, "Is evidence sufficient?", {"step": 1}, settings())
    store.close()

    # GET /runs/{run_id}/questions
    q_list_res = client.get(f"/runs/{run_id}/questions")
    assert q_list_res.status_code == 200
    q_list = q_list_res.json()
    assert len(q_list) == 1
    assert q_list[0]["id"] == qid
    assert q_list[0]["is_answered"] is False

    # GET /questions/{question_id}
    q_res = client.get(f"/questions/{qid}")
    assert q_res.status_code == 200
    q_data = q_res.json()
    assert q_data["id"] == qid
    assert q_data["run_id"] == run_id


def test_answer_question_workflow(client, tmp_path):
    """Test C, D & G: Answer question, verify state change, and test duplicate answer 409 conflict."""
    create_res = client.post("/runs", json={"domain": "demo"})
    run_id = create_res.json()["id"]

    test_db = str(tmp_path / "test_api.db")
    store = Store(test_db)
    qid = callback.ask(store, run_id, "Clarify source metric?", {}, settings())
    store.close()

    # Answer question
    answer_res = client.post(f"/questions/{qid}/answer", json={"answer": "Yes verified", "who": "mentor"})
    assert answer_res.status_code == 200
    assert answer_res.json()["is_answered"] is True

    # GET /questions/{question_id}
    q_res = client.get(f"/questions/{qid}")
    assert q_res.status_code == 200
    assert q_res.json()["is_answered"] is True

    # Duplicate answer -> 409 Conflict
    dup_res = client.post(f"/questions/{qid}/answer", json={"answer": "Second try", "who": "mentor"})
    assert dup_res.status_code == 409
    assert dup_res.json()["detail"] == "Question is already answered"


def test_missing_question_and_answer_target(client):
    """Test E & F: 404 handling for nonexistent question and answer targets."""
    res_get = client.get("/questions/q_nonexistent999")
    assert res_get.status_code == 404

    res_post = client.post("/questions/q_nonexistent999/answer", json={"answer": "none"})
    assert res_post.status_code == 404


# ------------------------------------------------------ Mock Advancement Tests


def test_advance_missing_run(client):
    """Mock Test A: POST /runs/{run_id}/advance for nonexistent run returns 404."""
    res = client.post("/runs/run_nonexistent999/advance")
    assert res.status_code == 404
    assert res.json() == {"detail": "Run not found"}


def test_advance_existing_run(client):
    """Mock Test B: Advance an existing run through deterministic mock flow."""
    create_res = client.post("/runs", json={"domain": "demo"})
    run_id = create_res.json()["id"]

    adv_res = client.post(f"/runs/{run_id}/advance")
    assert adv_res.status_code == 200
    data = adv_res.json()
    assert data["id"] == run_id
    assert data["state"] in [s.value for s in RunState]
    assert data["state"] == "complete"

    # Verify store matches response
    get_res = client.get(f"/runs/{run_id}")
    assert get_res.json()["state"] == "complete"


def test_multiple_deterministic_advances(client):
    """Mock Test C: Verify history and replay records are generated deterministically."""
    create_res = client.post("/runs", json={"domain": "demo"})
    run_id = create_res.json()["id"]

    adv_res = client.post(f"/runs/{run_id}/advance")
    assert adv_res.status_code == 200
    assert adv_res.json()["state"] == "complete"

    replay_res = client.get(f"/runs/{run_id}/replay")
    assert replay_res.status_code == 200
    replay_data = replay_res.json()
    kinds = [v["kind"] for v in replay_data]
    assert "opportunity" in kinds
    assert "verdict" in kinds


def test_determinism_across_runs(client):
    """Mock Test D: Verify that two independent runs produce identical payload structures."""
    run1 = client.post("/runs", json={"domain": "demo"}).json()["id"]
    run2 = client.post("/runs", json={"domain": "demo"}).json()["id"]

    adv1 = client.post(f"/runs/{run1}/advance").json()
    adv2 = client.post(f"/runs/{run2}/advance").json()

    assert adv1["state"] == adv2["state"] == "complete"

    replay1 = client.get(f"/runs/{run1}/replay").json()
    replay2 = client.get(f"/runs/{run2}/replay").json()

    payloads1 = [(v["kind"], v["produced_by"], v["payload"]) for v in replay1 if v["kind"] != "input"]
    payloads2 = [(v["kind"], v["produced_by"], v["payload"]) for v in replay2 if v["kind"] != "input"]
    assert payloads1 == payloads2


def test_callback_continuation_flow(client, tmp_path):
    """Mock Test E: Verify advance pauses on awaiting_expert and resumes after answer."""
    create_res = client.post("/runs", json={"domain": "demo"})
    run_id = create_res.json()["id"]

    test_db = str(tmp_path / "test_api.db")
    store = Store(test_db)
    qid = callback.ask(store, run_id, "Expert review required?", {"resume_state": "drafting"}, settings())
    store.close()

    adv_res1 = client.post(f"/runs/{run_id}/advance")
    assert adv_res1.status_code == 200
    assert adv_res1.json()["state"] == "awaiting_expert"

    ans_res = client.post(f"/questions/{qid}/answer", json={"answer": "Approved", "who": "mentor"})
    assert ans_res.status_code == 200

    adv_res2 = client.post(f"/runs/{run_id}/advance")
    assert adv_res2.status_code == 200
    assert adv_res2.json()["state"] in ["complete", "gating"]
