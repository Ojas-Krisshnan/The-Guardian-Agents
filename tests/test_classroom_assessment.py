# tests/test_classroom_assessment.py
"""Tests for assessment creation, question set & answer key ingestion, validation, and publishing."""
from __future__ import annotations

from pathlib import Path
import pytest
from starlette.testclient import TestClient

from api.dependencies import set_store
from api.main import app
from slice.store import Store


@pytest.fixture
def clean_store(tmp_path: Path):
    db_file = tmp_path / "test_asm.db"
    store = Store(db_file)
    set_store(store)
    yield store, db_file
    store.close()


@pytest.fixture
def client(clean_store):
    return TestClient(app)


def test_assessment_lifecycle_and_validation(client, clean_store):
    # 1. Login Teacher
    t_resp = client.post("/auth/login", json={"username": "teacher_prof", "password": "password123"})
    t_token = t_resp.json()["token"]
    t_headers = {"Authorization": f"Bearer {t_token}"}

    # 2. Create Classroom
    c_resp = client.post(
        "/teacher/classrooms",
        headers=t_headers,
        json={"name": "Data Structures", "subject": "CS 201"},
    )
    classroom_id = c_resp.json()["id"]

    # 3. Create Assessment in draft state
    asm_resp = client.post(
        f"/teacher/classrooms/{classroom_id}/assessments",
        headers=t_headers,
        json={"title": "Recursion & Call Stack Quiz", "description": "Unit 2 Checkpoint"},
    )
    assert asm_resp.status_code == 200
    asm_data = asm_resp.json()
    assert asm_data["status"] == "draft"
    assessment_id = asm_data["id"]

    # 4. Attempt to publish empty assessment -> MUST FAIL (400)
    pub_fail = client.post(f"/teacher/assessments/{assessment_id}/publish", headers=t_headers)
    assert pub_fail.status_code == 400

    # 5. Question upload with invalid answer not in options -> MUST FAIL (422)
    invalid_q = {
        "questions": [
            {
                "question_text": "What stops recursion?",
                "options": ["A. Loop", "B. Condition", "C. Parameter", "D. Stack"],
                "correct_answer": "Z. NonExistent",
            }
        ]
    }
    q_fail = client.post(f"/teacher/assessments/{assessment_id}/questions/upload", headers=t_headers, json=invalid_q)
    assert q_fail.status_code == 422

    # 6. Upload valid question set
    valid_q = {
        "questions": [
            {
                "question_text": "What prevents a recursive function from calling itself forever?",
                "options": ["Base case", "Recursive step", "Global variable", "Memory heap"],
                "correct_answer": "Base case",
                "concept_id": "Recursion",
            },
            {
                "question_text": "Where are activation records allocated during recursive calls?",
                "options": ["Call stack", "Memory heap", "CPU register", "Disk cache"],
                "correct_answer": "Call stack",
                "concept_id": "Call Stack",
            },
        ]
    }
    q_success = client.post(f"/teacher/assessments/{assessment_id}/questions/upload", headers=t_headers, json=valid_q)
    assert q_success.status_code == 200
    saved_qs = q_success.json()
    assert len(saved_qs) == 2
    q1_id = saved_qs[0]["id"]
    q2_id = saved_qs[1]["id"]

    # 7. Map concepts
    map_resp = client.post(
        f"/teacher/assessments/{assessment_id}/map-concepts",
        headers=t_headers,
        json={"mappings": {q1_id: "Recursion", q2_id: "Call Stack"}},
    )
    assert map_resp.status_code == 200

    # 8. Update answer key
    ans_resp = client.post(
        f"/teacher/assessments/{assessment_id}/answers/upload",
        headers=t_headers,
        json={"answers": {q1_id: "Base case", q2_id: "Call stack"}},
    )
    assert ans_resp.status_code == 200

    # 9. Publish Assessment
    pub_success = client.post(f"/teacher/assessments/{assessment_id}/publish", headers=t_headers)
    assert pub_success.status_code == 200
    assert pub_success.json()["status"] == "published"

    # 10. Verify student sees the published assessment, but correct_answers are stripped!
    # Generate student
    gen = client.post(f"/teacher/classrooms/{classroom_id}/students/generate", headers=t_headers, json={"count": 1})
    stu_login_id = gen.json()["students"][0]["login_id"]

    stu_auth = client.post("/auth/login", json={"login_id": stu_login_id}).json()
    stu_headers = {"Authorization": f"Bearer {stu_auth['token']}"}

    # Student retrieves assessment questions
    take_resp = client.get(f"/student/assessments/{assessment_id}", headers=stu_headers)
    assert take_resp.status_code == 200
    take_data = take_resp.json()
    assert len(take_data["questions"]) == 2
    for q in take_data["questions"]:
        # Zero-Knowledge: student questions endpoint must NEVER leak correct_answer or explanation
        assert q["correct_answer"] is None
        assert q["explanation"] is None
