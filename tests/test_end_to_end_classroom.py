# tests/test_end_to_end_classroom.py
"""Complete end-to-end integration test of the full Synapse Cycle classroom platform."""
from __future__ import annotations

from pathlib import Path
import pytest
from starlette.testclient import TestClient

from api.dependencies import set_store
from api.main import app
from slice.store import Store


@pytest.fixture
def clean_store(tmp_path: Path):
    db_file = tmp_path / "test_e2e.db"
    store = Store(db_file)
    set_store(store)
    yield store, db_file
    store.close()


@pytest.fixture
def client(clean_store):
    return TestClient(app)


def test_complete_classroom_learning_and_diagnostic_cycle(client, clean_store):
    # ─── 1. TEACHER SETUP & CLASSROOM CREATION ──────────────────────────────
    t_login = client.post("/auth/login", json={"username": "teacher_prof", "password": "password123"})
    assert t_login.status_code == 200
    t_token = t_login.json()["token"]
    t_headers = {"Authorization": f"Bearer {t_token}"}

    c_resp = client.post(
        "/teacher/classrooms",
        headers=t_headers,
        json={
            "name": "Data Structures & Algorithms — Sec 4",
            "subject": "CS 204",
            "description": "Recursion, Dynamic Programming, and Graph algorithms",
            "academic_year": "2026-Fall",
        },
    )
    assert c_resp.status_code == 200
    classroom_id = c_resp.json()["id"]

    # ─── 2. GENERATE STUDENT ACCOUNTS ───────────────────────────────────────
    gen_resp = client.post(
        f"/teacher/classrooms/{classroom_id}/students/generate",
        headers=t_headers,
        json={"count": 5},
    )
    assert gen_resp.status_code == 200
    students = gen_resp.json()["students"]
    assert len(students) == 5
    student1_login = students[0]["login_id"]
    student2_login = students[1]["login_id"]

    # ─── 3. CREATE ASSESSMENT & UPLOAD QUESTIONS + ANSWERS ──────────────────
    asm_resp = client.post(
        f"/teacher/classrooms/{classroom_id}/assessments",
        headers=t_headers,
        json={"title": "Recursion & Call Stack Diagnostic", "description": "Unit 2 Evaluation"},
    )
    assessment_id = asm_resp.json()["id"]

    # Upload real teacher questions
    questions_payload = {
        "questions": [
            {
                "question_text": "What is the primary role of a base case in a recursive function?",
                "options": [
                    "To terminate recursion and prevent stack overflow",
                    "To allocate additional dynamic heap memory",
                    "To double execution speed via compiler optimization",
                    "To declare global variables",
                ],
                "correct_answer": "To terminate recursion and prevent stack overflow",
                "concept_id": "Recursion Base Case",
            },
            {
                "question_text": "What happens if a recursive function never reaches its base case?",
                "options": [
                    "Call stack overflow runtime error",
                    "Immediate syntax compilation error",
                    "Function returns None safely",
                    "Memory heap compacts automatically",
                ],
                "correct_answer": "Call stack overflow runtime error",
                "concept_id": "Call Stack",
            },
            {
                "question_text": "In a divide-and-conquer algorithm, what does the recursive step do?",
                "options": [
                    "Divides the problem and calls itself on smaller subproblems",
                    "Immediately halts execution and exits",
                    "Transforms the code into iterative assembly instructions",
                    "Clears all active stack frames",
                ],
                "correct_answer": "Divides the problem and calls itself on smaller subproblems",
                "concept_id": "Recursive Step",
            },
        ]
    }
    q_resp = client.post(f"/teacher/assessments/{assessment_id}/questions/upload", headers=t_headers, json=questions_payload)
    assert q_resp.status_code == 200
    uploaded_qs = q_resp.json()
    assert len(uploaded_qs) == 3
    q1_id = uploaded_qs[0]["id"]
    q2_id = uploaded_qs[1]["id"]
    q3_id = uploaded_qs[2]["id"]

    # Publish assessment
    pub_resp = client.post(f"/teacher/assessments/{assessment_id}/publish", headers=t_headers)
    assert pub_resp.status_code == 200
    assert pub_resp.json()["status"] == "published"

    # ─── 4. STUDENT 1 ATTEMPT (ENCOUNTERS MISCONCEPTION) ────────────────────
    s1_auth = client.post("/auth/login", json={"login_id": student1_login}).json()
    s1_token = s1_auth["token"]
    s1_headers = {"Authorization": f"Bearer {s1_token}"}
    student1_user_id = s1_auth["user"]["id"]

    # Student 1 answers: Q1 wrong ("To double execution speed via compiler optimization" -> Conceptual Gap),
    # Q2 correct ("Call stack overflow runtime error"), Q3 correct ("Divides the problem...")
    s1_answers = {
        q1_id: "To double execution speed via compiler optimization",
        q2_id: "Call stack overflow runtime error",
        q3_id: "Divides the problem and calls itself on smaller subproblems",
    }
    att1_resp = client.post(
        f"/student/assessments/{assessment_id}/attempt",
        headers=s1_headers,
        json={"answers": s1_answers},
    )
    assert att1_resp.status_code == 200
    att1_data = att1_resp.json()
    assert att1_data["score"] == 2
    assert att1_data["total"] == 3
    assert att1_data["percentage"] == 66.7
    assert att1_data["diagnosis"] is not None
    # Verify tailored private study note was generated
    assert att1_data["note"] is not None
    assert "Study Guide" in att1_data["note"]["markdown"]
    assert "[[" in att1_data["note"]["markdown"]

    # ─── 5. STUDENT 2 ATTEMPT (FLAWLESS SCORE) ──────────────────────────────
    s2_auth = client.post("/auth/login", json={"login_id": student2_login}).json()
    s2_headers = {"Authorization": f"Bearer {s2_auth['token']}"}
    student2_user_id = s2_auth["user"]["id"]

    s2_answers = {
        q1_id: "To terminate recursion and prevent stack overflow",
        q2_id: "Call stack overflow runtime error",
        q3_id: "Divides the problem and calls itself on smaller subproblems",
    }
    att2_resp = client.post(
        f"/student/assessments/{assessment_id}/attempt",
        headers=s2_headers,
        json={"answers": s2_answers},
    )
    assert att2_resp.status_code == 200
    att2_data = att2_resp.json()
    assert att2_data["score"] == 3
    assert att2_data["total"] == 3
    assert att2_data["percentage"] == 100.0

    # ─── 6. STUDENT INDIVIDUAL ANALYTICS & PRIVACY BOUNDARY ─────────────────
    s1_analytics = client.get("/student/analytics", headers=s1_headers).json()
    assert s1_analytics["total_attempts"] == 1
    assert s1_analytics["overall_mastery"] == 66.7

    s1_notes = client.get("/student/notes", headers=s1_headers).json()
    assert len(s1_notes["notes"]) >= 1
    assert s1_notes["notes"][0]["student_id"] == student1_user_id

    # PRIVACY TEST: Student 2 cannot access Student 1's attempt details
    att1_id = att1_data["id"]
    forbidden_att = client.get(f"/student/attempts/{att1_id}", headers=s2_headers)
    assert forbidden_att.status_code == 403

    # PRIVACY TEST: Teacher CANNOT access student's private notes endpoint
    teacher_notes_denied = client.get(f"/student/notes/{q1_id}", headers=t_headers)
    assert teacher_notes_denied.status_code == 403

    # ─── 7. TEACHER CLASSROOM ANALYTICS & AI TEACHING INSIGHTS ──────────────
    analytics_resp = client.get(f"/teacher/classrooms/{classroom_id}/analytics", headers=t_headers)
    assert analytics_resp.status_code == 200
    analytics = analytics_resp.json()
    assert analytics["total_students"] == 5
    assert analytics["total_attempts"] == 2
    # Average mastery across 66.7% and 100% = 83.4%
    assert analytics["average_mastery"] > 80.0
    # Distribution
    assert analytics["distribution"]["90-100"] == 1  # Student 2
    assert analytics["distribution"]["60-69"] == 1   # Student 1

    # AI Teaching Insights
    insights_resp = client.get(f"/teacher/classrooms/{classroom_id}/insights", headers=t_headers)
    assert insights_resp.status_code == 200
    insights = insights_resp.json()
    assert len(insights) >= 1
    ins = insights[0]
    assert "finding" in ins
    assert "evidence" in ins
    assert "recommendation" in ins
    assert len(ins["finding"]) > 0
    assert len(ins["recommendation"]) > 0
