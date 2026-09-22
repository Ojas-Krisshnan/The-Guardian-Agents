# api/tests/test_student_routes.py
import pytest
from fastapi.testclient import TestClient
from api.auth import create_token
from api.dependencies import set_store
from api.main import app
from slice.store import Store
from synapse.runtime.stub import seed_test_run


@pytest.fixture
def client():
    store = Store(":memory:")
    set_store(store)
    yield TestClient(app)
    store.close()


def test_student_submit_and_view_notes(client):
    from api.dependencies import get_store
    store = get_store()

    # Seed an active test ready for students
    run_id, concept_id, test_id = seed_test_run(store, "teacher_1", "Recursion")

    student_token = create_token("student_A", "student")
    headers = {"Authorization": f"Bearer {student_token}"}

    # 1. Submit attempt
    test_data = store.latest(run_id, "test")
    answers = {q["id"]: q["correct_answer"] for q in test_data["questions"]}

    resp = client.post(
        "/student/attempts",
        json={"test_id": test_id, "answers": answers},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["attempt"]["score"] == 3
    assert data["diagnosis"]["mastery_estimate"] == 1.0
    assert "Mistake Pattern Table" in data["note"]["markdown"]

    # 2. Get own notes
    notes_resp = client.get(f"/student/notes/{concept_id}", headers=headers)
    assert notes_resp.status_code == 200
    notes_data = notes_resp.json()
    assert len(notes_data["notes"]) == 1
    assert notes_data["notes"][0]["student_id"] == "student_A"

    # 3. Privacy check: Student B cannot see Student A's notes
    student_b_token = create_token("student_B", "student")
    headers_b = {"Authorization": f"Bearer {student_b_token}"}
    notes_b_resp = client.get(f"/student/notes/{concept_id}", headers=headers_b)
    assert notes_b_resp.status_code == 200
    assert len(notes_b_resp.json()["notes"]) == 0  # Student B has no notes yet!

    # 4. Get student graph
    graph_resp = client.get("/student/graph", headers=headers)
    assert graph_resp.status_code == 200
    graph_data = graph_resp.json()
    assert len(graph_data["nodes"]) >= 1
