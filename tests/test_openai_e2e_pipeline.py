# tests/test_openai_e2e_pipeline.py
"""End-to-End pipeline verification: Student submission -> OpenAI Diagnosis -> Persistence -> Teacher query -> OpenAI Tailoring -> Student Notes."""
from __future__ import annotations

from dataclasses import replace
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import pytest
from starlette.testclient import TestClient

from api.dependencies import get_settings_dep, get_store
from api.main import app
from slice.config import Settings, settings as get_settings
from slice.store import Store


@pytest.fixture
def clean_store(tmp_path):
    db_path = tmp_path / "test_e2e_openai.db"
    store = Store(str(db_path))
    old_store = app.dependency_overrides.get(get_store)
    app.dependency_overrides[Store] = lambda: store
    app.dependency_overrides[get_store] = lambda: store
    yield store
    store.close()
    if old_store:
        app.dependency_overrides[get_store] = old_store
    else:
        app.dependency_overrides.pop(Store, None)
        app.dependency_overrides.pop(get_store, None)


@pytest.fixture
def client(clean_store):
    return TestClient(app)


def test_openai_full_student_teacher_pipeline(client, clean_store):
    """Verifies complete end-to-end cycle using configured OpenAI provider:
    1. Teacher creates classroom & publishes assessment.
    2. Student connects and submits attempt with specific mistake.
    3. OpenAI API is invoked through slice/llm.py to generate real structured diagnosis.
    4. Diagnosis is persisted in database and visible to connected teacher.
    5. OpenAI API is invoked through slice/llm.py to generate tailored note targeting the diagnosis.
    6. Note is persisted and visible to student; private note markdown is strictly isolated from teacher.
    """
    # 1. Setup Teacher
    t_res = client.post(
        "/auth/register",
        json={
            "role": "teacher",
            "name": "Prof. Turing",
            "username": "turing",
            "email": "turing@synapse.edu",
            "password": "Password123!",
        },
    )
    assert t_res.status_code == 201
    t_token = t_res.json()["token"]
    t_headers = {"Authorization": f"Bearer {t_token}"}

    code_res = client.get("/teacher/connection-code", headers=t_headers)
    assert code_res.status_code == 200
    connect_code = code_res.json()["code"]

    cr_res = client.post(
        "/teacher/classrooms",
        headers=t_headers,
        json={"name": "Discrete Math", "subject": "Math", "description": "Graph Theory and Induction"},
    )
    assert cr_res.status_code in (200, 201)
    classroom_id = cr_res.json()["id"]

    asm_res = client.post(
        f"/teacher/classrooms/{classroom_id}/assessments",
        headers=t_headers,
        json={"title": "Induction Basics", "concept_ids": ["Induction"]},
    )
    assessment_id = asm_res.json()["id"]

    q_up = client.post(
        f"/teacher/assessments/{assessment_id}/questions/upload",
        headers=t_headers,
        json={
            "questions": [
                {
                    "question_text": "What is the inductive step in mathematical induction?",
                    "options": [
                        "Proving P(k) implies P(k+1)",
                        "Testing n=1 only",
                        "Assuming statement is false",
                        "Listing 100 examples",
                    ],
                    "correct_answer": "Proving P(k) implies P(k+1)",
                    "concept_id": "Induction",
                },
                {
                    "question_text": "Why is the base case necessary?",
                    "options": [
                        "To anchor the induction chain",
                        "To compute running time",
                        "To reduce theorem length",
                        "To format LaTeX equations",
                    ],
                    "correct_answer": "To anchor the induction chain",
                    "concept_id": "Induction",
                },
            ]
        },
    )
    assert q_up.status_code in (200, 201)

    pub_res = client.post(f"/teacher/assessments/{assessment_id}/publish", headers=t_headers)
    assert pub_res.status_code == 200

    # 2. Setup Student
    s_res = client.post(
        "/auth/register",
        json={
            "role": "student",
            "name": "Ada Lovelace",
            "username": "ada_student",
            "email": "ada_student@synapse.edu",
            "password": "Password123!",
        },
    )
    assert s_res.status_code == 201
    s_token = s_res.json()["token"]
    s_headers = {"Authorization": f"Bearer {s_token}"}
    student_id = s_res.json()["user"]["id"]

    conn_res = client.post("/student/connect", headers=s_headers, json={"code": connect_code})
    assert conn_res.status_code == 200

    # Fetch question IDs
    q_res = client.get(f"/student/assessments/{assessment_id}", headers=s_headers)
    assert q_res.status_code == 200
    qs = q_res.json()["questions"]
    q1_id = qs[0]["id"]
    q2_id = qs[1]["id"]

    # Configure Settings for OpenAI
    openai_settings = replace(
        get_settings(),
        provider="openai",
        openai_api_key="sk-test-live-pipeline-key",
        openai_model="gpt-4o-mini",
        openai_fallback_model="gpt-4o",
    )
    app.dependency_overrides[get_settings_dep] = lambda: openai_settings

    # Mock OpenAI client chat completions create method
    diag_ai_response = json.dumps({
        "id": "diag_ai_ind_001",
        "student_id": student_id,
        "concept_id": "Induction",
        "items": [
            {
                "question_id": q1_id,
                "classification": "conceptual_gap",
                "reason": "Student believed empirical testing substitutes for inductive step deduction.",
            }
        ],
        "mastery_estimate": 0.5,
        "trend": "new",
        "created_at": "2026-09-20T20:00:00Z",
    })

    tailor_ai_markdown = (
        "# Personalized Study Note: Mathematical Induction\n\n"
        "## Diagnostic Feedback\n"
        "You answered Q1 with empirical examples. Remember that induction requires proving that `P(k) -> P(k+1)` holds generally for all `k`.\n\n"
        "| Misconception | Mathematical Truth |\n"
        "| --- | --- |\n"
        "| Checking 100 examples is sufficient | An inductive step proves infinitely many cases deductively |\n\n"
        "Explore [[Induction]] to review the standard ladder analogy."
    )

    api_calls = []

    def mock_openai_create(*args, **kwargs):
        api_calls.append(kwargs)
        step_model = kwargs.get("model", "")
        messages = kwargs.get("messages", [])
        # Check if this is diagnosis or tailoring
        user_prompt = messages[-1]["content"] if messages else ""
        if "structured Diagnosis JSON object" in user_prompt:
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=diag_ai_response), finish_reason="stop")],
                usage=SimpleNamespace(total_tokens=180),
            )
        else:
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=tailor_ai_markdown), finish_reason="stop")],
                usage=SimpleNamespace(total_tokens=260),
            )

    try:
        with patch("openai.resources.chat.completions.Completions.create", side_effect=mock_openai_create):
            sub_res = client.post(
                f"/student/assessments/{assessment_id}/attempt",
                headers=s_headers,
                json={
                    "answers": {
                        q1_id: "Listing 100 examples",              # Incorrect
                        q2_id: "To anchor the induction chain",     # Correct
                    }
                },
            )

        assert sub_res.status_code == 200, sub_res.text
        att_resp = sub_res.json()

        # Score verification
        assert att_resp["score"] == 1
        assert att_resp["total"] == 2

        # Verify AI Diagnosis received by student
        assert att_resp["diagnosis"] is not None
        assert att_resp["diagnosis"]["concept_id"] == "Induction"
        assert att_resp["diagnosis"]["mastery_estimate"] == 0.5
        assert len(att_resp["diagnosis"]["items"]) == 1
        assert "empirical testing" in att_resp["diagnosis"]["items"][0]["reason"]

        # Verify Tailored Note received by student
        assert att_resp["note"] is not None
        assert "Personalized Study Note: Mathematical Induction" in att_resp["note"]["markdown"]
        assert "[[Induction]]" in att_resp["note"]["markdown"]

        # Verify OpenAI API was called through slice/llm.py
        assert len(api_calls) >= 2
        for call in api_calls:
            assert call["model"] == "gpt-4o-mini"

        # 3. Teacher queries student performance
        perf_res = client.get(f"/teacher/students/{student_id}/performance", headers=t_headers)
        assert perf_res.status_code == 200
        perf = perf_res.json()

        # Teacher receives the same authoritative diagnosis
        assert perf["latest_diagnosis"] is not None
        assert perf["latest_diagnosis"]["concept_id"] == "Induction"
        assert "empirical testing" in perf["latest_diagnosis"]["items"][0]["reason"]

        # ZERO-KNOWLEDGE PRIVACY CHECK: Teacher cannot see student note markdown
        assert "Personalized Study Note" not in json.dumps(perf)
        assert "markdown" not in perf

        # 4. Student can query private notes
        notes_res = client.get("/student/notes", headers=s_headers)
        assert notes_res.status_code == 200
        notes_data = notes_res.json()
        notes_list = notes_data["notes"] if isinstance(notes_data, dict) else notes_data
        assert len(notes_list) >= 1
        assert any("Mathematical Induction" in n["markdown"] for n in notes_list)

    finally:
        app.dependency_overrides.pop(get_settings_dep, None)
