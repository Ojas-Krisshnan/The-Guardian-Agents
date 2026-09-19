"""Tests for Authentication and Role-Based Protection."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.auth import create_access_token
from api.deps import get_store
from api.main import app
from slice import callback
from slice.config import settings
from slice.store import Store


@pytest.fixture
def client(tmp_path):
    """Test client fixture providing an isolated Store database per test."""
    test_db = str(tmp_path / "test_auth_api.db")

    def _override_store():
        store = Store(test_db)
        try:
            yield store
        finally:
            store.close()

    app.dependency_overrides[get_store] = _override_store
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


@pytest.fixture
def teacher_headers():
    """Return authorization header for teacher role."""
    token = create_access_token({"sub": "teacher", "role": "teacher"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def student_headers():
    """Return authorization header for student role."""
    token = create_access_token({"sub": "student", "role": "student"})
    return {"Authorization": f"Bearer {token}"}


def test_login_success_teacher(client):
    """Verify POST /auth/login with valid teacher credentials."""
    response = client.post("/auth/login", json={"username": "teacher", "password": "teacher123"})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["role"] == "teacher"


def test_login_success_student(client):
    """Verify POST /auth/login with valid student credentials."""
    response = client.post("/auth/login", json={"username": "student", "password": "student123"})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["role"] == "student"


def test_login_invalid_credentials(client):
    """Verify POST /auth/login with invalid credentials returns 401."""
    res1 = client.post("/auth/login", json={"username": "teacher", "password": "wrong_password"})
    assert res1.status_code == 401
    assert res1.json()["detail"] == "Invalid username or password"

    res2 = client.post("/auth/login", json={"username": "unknown_user", "password": "teacher123"})
    assert res2.status_code == 401
    assert res2.json()["detail"] == "Invalid username or password"


def test_unauthenticated_request_rejected(client):
    """Verify protected endpoints reject requests without token with 401."""
    res = client.get("/runs")
    assert res.status_code == 401


def test_invalid_token_rejected(client):
    """Verify protected endpoints reject invalid token with 401."""
    headers = {"Authorization": "Bearer fake.invalid.token"}
    res = client.get("/runs", headers=headers)
    assert res.status_code == 401


def test_teacher_endpoint_allowed_for_teacher(client, teacher_headers):
    """Verify POST /runs is allowed for teacher role (201 Created)."""
    res = client.post("/runs", json={"domain": "auth_test"}, headers=teacher_headers)
    assert res.status_code == 201
    assert res.json()["domain"] == "auth_test"


def test_teacher_endpoint_forbidden_for_student(client, student_headers):
    """Verify POST /runs returns 403 Forbidden for student role."""
    res = client.post("/runs", json={"domain": "auth_test"}, headers=student_headers)
    assert res.status_code == 403
    assert "Forbidden" in res.json()["detail"]


def test_student_can_read_runs_and_advance(client, teacher_headers, student_headers):
    """Verify student role can read runs and invoke advance."""
    # Teacher creates run
    create_res = client.post("/runs", json={"domain": "auth_test"}, headers=teacher_headers)
    run_id = create_res.json()["id"]

    # Student reads run
    get_res = client.get(f"/runs/{run_id}", headers=student_headers)
    assert get_res.status_code == 200

    # Student advances run
    adv_res = client.post(f"/runs/{run_id}/advance", headers=student_headers)
    assert adv_res.status_code == 200


def test_student_forbidden_to_answer_question(client, teacher_headers, student_headers, tmp_path):
    """Verify student role is forbidden (403) from answering expert questions."""
    create_res = client.post("/runs", json={"domain": "auth_test"}, headers=teacher_headers)
    run_id = create_res.json()["id"]

    test_db = str(tmp_path / "test_auth_api.db")
    store = Store(test_db)
    qid = callback.ask(store, run_id, "Teacher review needed?", {}, settings())
    store.close()

    # Student attempts answer -> 403
    ans_res = client.post(f"/questions/{qid}/answer", json={"answer": "student answer"}, headers=student_headers)
    assert ans_res.status_code == 403

    # Teacher answers -> 200
    ans_res_t = client.post(f"/questions/{qid}/answer", json={"answer": "teacher answer"}, headers=teacher_headers)
    assert ans_res_t.status_code == 200
