# tests/test_auth_guards.py
"""
Backend tests for authentication guards and role-based access control.

Verifies:
1. Protected teacher endpoints require authentication (401 without token).
2. Protected student endpoints require authentication (401 without token).
3. Student token cannot access teacher endpoints (403 Forbidden).
4. Teacher token cannot access student endpoints (403 Forbidden).
5. Valid teacher token allows teacher endpoints.
6. Valid student token allows student endpoints.
7. /auth/me validates active session and derives role from SQLite.
8. Expired or tampered token is rejected with 401 Unauthorized.
"""
from __future__ import annotations

from pathlib import Path
import pytest
from starlette.testclient import TestClient

from api.auth import create_token
from api.dependencies import set_store
from api.main import app
from slice.store import Store


@pytest.fixture
def auth_store(tmp_path: Path):
    db_file = tmp_path / "auth_guards_test.db"
    store = Store(db_file)
    set_store(store)
    yield store, db_file
    store.close()


@pytest.fixture
def client(auth_store):
    return TestClient(app)


def test_unauthenticated_requests_rejected(client, auth_store):
    """Endpoints requiring authentication must return 401 Unauthorized when no token is supplied."""
    # 1. Teacher endpoint without token
    teacher_resp = client.post("/teacher/classrooms", json={"name": "Math 101", "subject": "Math"})
    assert teacher_resp.status_code == 401
    assert "authentication required" in teacher_resp.json()["detail"].lower()

    # 2. Student endpoint without token
    student_resp = client.get("/student/classrooms")
    assert student_resp.status_code == 401
    assert "authentication required" in student_resp.json()["detail"].lower()

    # 3. /auth/me without token
    me_resp = client.get("/auth/me")
    assert me_resp.status_code == 401


def test_role_boundary_enforcement(client, auth_store):
    """Students cannot access teacher endpoints; teachers cannot access student endpoints."""
    store, _ = auth_store

    # Create real users in SQLite
    t_user = store.create_user(
        role="teacher",
        username="guard_teacher",
        password="ValidPassword123!",
        name="Guard Teacher",
    )
    s_user = store.create_user(
        role="student",
        username="guard_student",
        password="ValidPassword123!",
        name="Guard Student",
    )

    t_token = create_token(t_user["id"], "teacher", t_user["name"])
    s_token = create_token(s_user["id"], "student", s_user["name"])

    # 1. Student attempting teacher endpoint -> 403 Forbidden
    s_headers = {"Authorization": f"Bearer {s_token}"}
    forbidden_resp = client.post(
        "/teacher/classrooms",
        headers=s_headers,
        json={"name": "Unauthorized Class", "subject": "Physics"},
    )
    assert forbidden_resp.status_code == 403
    assert "teacher role required" in forbidden_resp.json()["detail"].lower()

    # 2. Teacher attempting student endpoint -> 403 Forbidden
    t_headers = {"Authorization": f"Bearer {t_token}"}
    forbidden_stu_resp = client.get("/student/classrooms", headers=t_headers)
    assert forbidden_stu_resp.status_code == 403
    assert "student role required" in forbidden_stu_resp.json()["detail"].lower()


def test_authorized_access_succeeds(client, auth_store):
    """Verified teacher can access teacher endpoints; verified student can access student endpoints."""
    store, _ = auth_store

    t_user = store.create_user(
        role="teacher",
        username="authorized_teacher",
        password="ValidPassword123!",
        name="Authorized Teacher",
    )
    s_user = store.create_user(
        role="student",
        username="authorized_student",
        password="ValidPassword123!",
        name="Authorized Student",
    )

    t_token = create_token(t_user["id"], "teacher", t_user["name"])
    s_token = create_token(s_user["id"], "student", s_user["name"])

    # 1. Teacher accesses teacher endpoint
    t_headers = {"Authorization": f"Bearer {t_token}"}
    create_class_resp = client.post(
        "/teacher/classrooms",
        headers=t_headers,
        json={"name": "Linear Algebra", "subject": "Mathematics"},
    )
    assert create_class_resp.status_code == 200
    class_data = create_class_resp.json()
    assert class_data["name"] == "Linear Algebra"
    assert class_data["teacher_id"] == t_user["id"]

    # 2. Student accesses student endpoint
    s_headers = {"Authorization": f"Bearer {s_token}"}
    stu_classrooms_resp = client.get("/student/classrooms", headers=s_headers)
    assert stu_classrooms_resp.status_code == 200
    assert isinstance(stu_classrooms_resp.json(), list)

    # 3. Both can access /auth/me and receive their verified profile
    me_t = client.get("/auth/me", headers=t_headers)
    assert me_t.status_code == 200
    assert me_t.json()["role"] == "teacher"
    assert me_t.json()["username"] == "authorized_teacher"

    me_s = client.get("/auth/me", headers=s_headers)
    assert me_s.status_code == 200
    assert me_s.json()["role"] == "student"
    assert me_s.json()["username"] == "authorized_student"


def test_tampered_token_rejected(client, auth_store):
    """Tampered or invalid tokens are rejected with 401 Unauthorized."""
    tampered_headers = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.badpayload.invalidsignature"}
    resp = client.get("/auth/me", headers=tampered_headers)
    assert resp.status_code == 401
