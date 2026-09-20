# tests/test_teacher_student_connection.py
"""Comprehensive tests for Student ↔ Teacher Connection & Performance Analytics."""
from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from api.main import app
from slice.store import Store
from synapse.api_contracts import ConnectedStudentPerformanceResponse, ConnectedStudentSummary


@pytest.fixture
def clean_store(tmp_path):
    """Provide an isolated, clean SQLite store."""
    db_path = tmp_path / "test_synapse.db"
    store = Store(db_path)
    old_store = app.dependency_overrides.get("get_store")
    app.dependency_overrides[Store] = lambda: store
    try:
        from api.dependencies import get_store
        app.dependency_overrides[get_store] = lambda: store
    except Exception:
        pass
    yield store
    store.close()
    if old_store:
        app.dependency_overrides["get_store"] = old_store
    else:
        app.dependency_overrides.pop(Store, None)
        app.dependency_overrides.pop("get_store", None)


@pytest.fixture
def client(clean_store):
    return TestClient(app)


def test_student_teacher_connection_and_analytics_lifecycle(client, clean_store):
    """Test full connection lifecycle:
    1. Teacher registers and gets connection code.
    2. Student registers and connects via code.
    3. Relationship is persisted in SQLite.
    4. Student takes assessment, producing real analytics.
    5. Teacher views connected student performance with real values.
    6. Unrelated teacher is denied access (HTTP 403).
    7. Role protections enforced.
    """
    # ─── 1. REGISTER TEACHER & STUDENT ──────────────────────────────────────────
    t_reg = client.post(
        "/auth/register",
        json={
            "role": "teacher",
            "name": "Prof Charles Xavier",
            "username": "prof_x",
            "email": "prof_x@xavier.edu",
            "password": "Password123!",
        },
    )
    assert t_reg.status_code == 201, t_reg.text
    t_token = t_reg.json()["token"]
    t_id = t_reg.json()["user"]["id"]
    t_headers = {"Authorization": f"Bearer {t_token}"}

    s_reg = client.post(
        "/auth/register",
        json={
            "role": "student",
            "name": "Jean Grey",
            "username": "jean_grey",
            "email": "jean@xavier.edu",
            "password": "Password123!",
        },
    )
    assert s_reg.status_code == 201, s_reg.text
    s_token = s_reg.json()["token"]
    s_id = s_reg.json()["user"]["id"]
    s_headers = {"Authorization": f"Bearer {s_token}"}

    # ─── 2. TEACHER CREATES CLASSROOM & GETS CONNECTION CODE ───────────────────
    c_resp = client.post(
        "/teacher/classrooms",
        headers=t_headers,
        json={"name": "Telepathy 101", "subject": "Cognitive Science"},
    )
    assert c_resp.status_code == 200
    classroom_id = c_resp.json()["id"]

    code_resp = client.get("/teacher/connection-code", headers=t_headers)
    assert code_resp.status_code == 200
    code_data = code_resp.json()
    assert code_data["code"].startswith("SYN-")
    assert code_data["teacher_id"] == t_id
    connection_code = code_data["code"]

    # Teacher initially has 0 connected students
    initial_students = client.get("/teacher/students", headers=t_headers)
    assert initial_students.status_code == 200
    assert initial_students.json() == []

    # ─── 3. STUDENT CONNECTS USING CODE ─────────────────────────────────────────
    # Invalid code fails with 400
    bad_conn = client.post("/student/connect", headers=s_headers, json={"code": "SYN-INVALID"})
    assert bad_conn.status_code == 400

    # Valid code succeeds
    conn_resp = client.post("/student/connect", headers=s_headers, json={"code": connection_code})
    assert conn_resp.status_code == 200
    conn_data = conn_resp.json()
    assert conn_data["success"] is True
    assert conn_data["teacher"]["id"] == t_id
    assert conn_data["teacher"]["name"] == "Prof Charles Xavier"

    # Idempotent re-connect works without error
    reconn_resp = client.post("/student/connect", headers=s_headers, json={"code": connection_code})
    assert reconn_resp.status_code == 200

    # Student can inspect their connected teachers
    s_teachers = client.get("/student/teacher", headers=s_headers)
    assert s_teachers.status_code == 200
    assert any(t["id"] == t_id for t in s_teachers.json()["teachers"])

    # ─── 4. PERSISTENCE IN SQLITE VERIFICATION ─────────────────────────────────
    # Verify directly via store
    assert clean_store.is_student_connected_to_teacher(t_id, s_id) is True

    # ─── 5. TEACHER LISTS CONNECTED STUDENTS (PRE-ATTEMPT) ─────────────────────
    t_students = client.get("/teacher/students", headers=t_headers)
    assert t_students.status_code == 200
    stu_list = t_students.json()
    assert len(stu_list) == 1
    assert stu_list[0]["student_id"] == s_id
    assert stu_list[0]["name"] == "Jean Grey"
    assert stu_list[0]["total_attempts"] == 0
    assert stu_list[0]["overall_mastery"] is None
    assert stu_list[0]["trend"] == "no_data"

    # Teacher views pre-attempt performance
    pre_perf = client.get(f"/teacher/students/{s_id}/performance", headers=t_headers)
    assert pre_perf.status_code == 200
    pre_data = pre_perf.json()
    assert pre_data["total_attempts"] == 0
    assert pre_data["recent_attempts"] == []
    assert pre_data["overall_mastery"] is None

    # ─── 6. STUDENT TAKES ASSESSMENT (REAL PERFORMANCE DATA GENERATION) ────────
    # Teacher creates and publishes assessment
    asm_resp = client.post(
        f"/teacher/classrooms/{classroom_id}/assessments",
        headers=t_headers,
        json={"title": "Midterm Exam", "description": "Core concepts", "concept_ids": ["c-telepathy"]},
    )
    assert asm_resp.status_code == 200
    asm_id = asm_resp.json()["id"]

    # Upload questions
    q_resp = client.post(
        f"/teacher/assessments/{asm_id}/questions/upload",
        headers=t_headers,
        json={
            "questions": [
                {
                    "concept_id": "c-telepathy",
                    "question_text": "What is the primary carrier wave?",
                    "options": ["Gamma", "Alpha", "Delta"],
                    "correct_answer": "Gamma",
                },
                {
                    "concept_id": "c-telepathy",
                    "question_text": "What is the synaptic threshold?",
                    "options": ["-70mV", "+40mV", "0mV"],
                    "correct_answer": "-70mV",
                },
            ]
        },
    )
    assert q_resp.status_code == 200
    q1_id = q_resp.json()[0]["id"]
    q2_id = q_resp.json()[1]["id"]

    # Publish assessment
    pub = client.post(f"/teacher/assessments/{asm_id}/publish", headers=t_headers)
    assert pub.status_code == 200

    # Student submits attempt (Answers 1 correct, 1 incorrect = 50%)
    sub_resp = client.post(
        f"/student/assessments/{asm_id}/attempt",
        headers=s_headers,
        json={"answers": {q1_id: "Gamma", q2_id: "0mV"}},
    )
    assert sub_resp.status_code == 200
    assert sub_resp.json()["percentage"] == 50.0

    # ─── 7. TEACHER VIEWS REAL UPDATED STUDENT PERFORMANCE ─────────────────────
    t_students_after = client.get("/teacher/students", headers=t_headers)
    assert t_students_after.status_code == 200
    s_summary = t_students_after.json()[0]
    assert s_summary["total_attempts"] == 1
    assert s_summary["overall_mastery"] == 50.0
    assert s_summary["recent_score"] == 50.0

    # Detailed performance view
    perf_resp = client.get(f"/teacher/students/{s_id}/performance", headers=t_headers)
    assert perf_resp.status_code == 200
    perf = perf_resp.json()
    assert perf["student_id"] == s_id
    assert perf["total_attempts"] == 1
    assert perf["overall_mastery"] == 50.0
    assert perf["recent_score"] == 50.0
    assert len(perf["recent_attempts"]) == 1
    assert perf["recent_attempts"][0]["title"] == "Midterm Exam"
    assert perf["recent_attempts"][0]["percentage"] == 50.0
    assert "c-telepathy" in perf["concept_mastery"]
    assert perf["concept_mastery"]["c-telepathy"] == 50.0
    assert "c-telepathy" in perf["concepts_needing_attention"]
    assert perf["diagnostics_summary"]["total_questions_answered"] == 2
    assert perf["diagnostics_summary"]["correct_answers"] == 1
    assert perf["diagnostics_summary"]["incorrect_answers"] == 1

    # ─── 8. PRIVACY & SECURITY: TEACHER B CANNOT ACCESS STUDENT ────────────────
    # Create Teacher 2 (unrelated)
    t2_reg = client.post(
        "/auth/register",
        json={
            "role": "teacher",
            "name": "Magneto",
            "username": "erik_lehnsherr",
            "email": "erik@brotherhood.org",
            "password": "Password123!",
        },
    )
    assert t2_reg.status_code == 201
    t2_headers = {"Authorization": f"Bearer {t2_reg.json()['token']}"}

    # Teacher 2 has 0 students
    t2_students = client.get("/teacher/students", headers=t2_headers)
    assert t2_students.status_code == 200
    assert t2_students.json() == []

    # Teacher 2 attempts direct access to Teacher 1's student -> 403 Forbidden!
    forbidden_resp = client.get(f"/teacher/students/{s_id}/performance", headers=t2_headers)
    assert forbidden_resp.status_code == 403

    # ─── 9. ROLE PROTECTIONS ───────────────────────────────────────────────────
    # Student cannot access /teacher/students
    stu_forbidden = client.get("/teacher/students", headers=s_headers)
    assert stu_forbidden.status_code == 403

    # Teacher cannot access /student/connect
    tea_forbidden = client.post("/student/connect", headers=t_headers, json={"code": connection_code})
    assert tea_forbidden.status_code == 403

    # Student cannot access /teacher/students/{id}/performance
    stu_forbidden_perf = client.get(f"/teacher/students/{s_id}/performance", headers=s_headers)
    assert stu_forbidden_perf.status_code == 403
