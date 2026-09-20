# api/tests/test_teacher_routes.py
import pytest
from fastapi.testclient import TestClient
from api.auth import create_token
from api.dependencies import set_store
from api.main import app
from slice.store import Store


@pytest.fixture
def client():
    store = Store(":memory:")
    set_store(store)
    yield TestClient(app)
    store.close()


def test_teacher_routes_flow(client):
    teacher_token = create_token("teacher_1", "teacher")
    headers = {"Authorization": f"Bearer {teacher_token}"}

    # 1. Create concept
    resp = client.post(
        "/teacher/concepts",
        json={"markdown": "# Recursion\nBase cases and recursion.", "concept_name": "Recursion"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    run_id = data["run_id"]

    # 2. Get pending tags
    tags_resp = client.get(f"/teacher/concepts/{run_id}", headers=headers)
    assert tags_resp.status_code == 200
    tags_data = tags_resp.json()
    assert len(tags_data["concepts"]) >= 1

    # 3. Confirm tags
    confirm_resp = client.post(
        f"/teacher/concepts/{run_id}/confirm",
        json={"run_id": run_id, "confirmed": True, "edited_concepts": None},
        headers=headers,
    )
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["test"] is not None

    # 4. Get test
    test_resp = client.get(f"/teacher/tests/{run_id}", headers=headers)
    assert test_resp.status_code == 200
    assert len(test_resp.json()["questions"]) == 3

    # 5. Get analytics
    concept_id = tags_data["concept_id"]
    analytics_resp = client.get(f"/teacher/analytics/{concept_id}", headers=headers)
    assert analytics_resp.status_code == 200
    # Privacy check: no note markdown in analytics
    assert "markdown" not in analytics_resp.text


def test_student_forbidden_on_teacher_route(client):
    student_token = create_token("student_1", "student")
    headers = {"Authorization": f"Bearer {student_token}"}

    resp = client.post(
        "/teacher/concepts",
        json={"markdown": "# Math\nAddition", "concept_name": "Math"},
        headers=headers,
    )
    assert resp.status_code == 403
