# tests/test_classroom_auth.py
"""Tests for Teacher and Student authentication, role protection, and classroom isolation."""
from __future__ import annotations

from pathlib import Path
import pytest
from starlette.testclient import TestClient

from api.dependencies import set_store
from api.main import app
from slice.store import Store
from synapse.database import create_teacher_user


@pytest.fixture
def clean_store(tmp_path: Path):
    db_file = tmp_path / "test_auth.db"
    store = Store(db_file)
    set_store(store)
    yield store, db_file
    store.close()


@pytest.fixture
def client(clean_store):
    return TestClient(app)


def test_teacher_auth_and_classroom_creation(client, clean_store):
    store, _ = clean_store

    # 1. Login with seeded teacher
    resp = client.post("/auth/login", json={"username": "teacher_prof", "password": "password123"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "token" in data
    assert data["user"]["role"] == "teacher"
    token = data["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get Me
    me_resp = client.get("/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["role"] == "teacher"

    # 3. Create Classroom
    c_resp = client.post(
        "/teacher/classrooms",
        headers=headers,
        json={
            "name": "Algorithms & Complexity",
            "subject": "CS 301",
            "description": "Advanced algorithmic design and proofs",
            "academic_year": "2026-Fall",
        },
    )
    assert c_resp.status_code == 200
    c_data = c_resp.json()
    assert c_data["name"] == "Algorithms & Complexity"
    assert c_data["subject"] == "CS 301"
    classroom_id = c_data["id"]

    # 4. Generate 5 unique student IDs
    gen_resp = client.post(f"/teacher/classrooms/{classroom_id}/students/generate", headers=headers, json={"count": 5})
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()
    assert len(gen_data["students"]) == 5

    # Check ID format and uniqueness
    login_ids = [s["login_id"] for s in gen_data["students"]]
    assert len(set(login_ids)) == 5
    for lid in login_ids:
        assert lid.startswith("STU-")
        assert len(lid) == 10  # "STU-" + 6 chars

    # 5. Student Login with first generated ID
    first_student_id = login_ids[0]
    stu_login_resp = client.post("/auth/login", json={"login_id": first_student_id})
    assert stu_login_resp.status_code == 200
    stu_auth = stu_login_resp.json()
    assert stu_auth["user"]["role"] == "student"
    assert stu_auth["user"]["login_id"] == first_student_id
    stu_token = stu_auth["token"]
    stu_headers = {"Authorization": f"Bearer {stu_token}"}

    # 6. Verify role boundaries: Student CANNOT create a classroom or access teacher routes
    forbidden_resp = client.post(
        "/teacher/classrooms",
        headers=stu_headers,
        json={"name": "Fake Class", "subject": "Hacking"},
    )
    assert forbidden_resp.status_code == 403

    # Teacher CANNOT access student attempt endpoints
    t_forbidden = client.get("/student/classrooms", headers=headers)
    assert t_forbidden.status_code == 403


def test_classroom_isolation_between_teachers(client, clean_store):
    store, _ = clean_store

    # Create Teacher 2 directly
    create_teacher_user(
        store.db,
        username="teacher_turing",
        password="secretpassword",
        name="Alan Turing",
        email="alan@turing.edu",
        user_id="teacher_turing",
    )

    # Login Teacher 1
    t1_resp = client.post("/auth/login", json={"username": "teacher_prof", "password": "password123"})
    t1_headers = {"Authorization": f"Bearer {t1_resp.json()['token']}"}

    # Teacher 1 creates classroom
    c1_resp = client.post(
        "/teacher/classrooms",
        headers=t1_headers,
        json={"name": "Teacher 1 Class", "subject": "CS 101"},
    )
    c1_id = c1_resp.json()["id"]

    # Login Teacher 2
    t2_resp = client.post("/auth/login", json={"username": "teacher_turing", "password": "secretpassword"})
    t2_headers = {"Authorization": f"Bearer {t2_resp.json()['token']}"}

    # Teacher 2 cannot access Teacher 1's classroom
    denied = client.get(f"/teacher/classrooms/{c1_id}", headers=t2_headers)
    assert denied.status_code == 403

    # Teacher 2 cannot generate students in Teacher 1's classroom
    denied_gen = client.post(f"/teacher/classrooms/{c1_id}/students/generate", headers=t2_headers, json={"count": 2})
    assert denied_gen.status_code == 403
