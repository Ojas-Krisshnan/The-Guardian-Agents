# tests/test_ai_agent_pipeline.py
"""Comprehensive tests for the Real Synapse AI Agent Pipeline for Student Test Submissions."""
from __future__ import annotations

import asyncio
from dataclasses import replace
import json
from unittest.mock import MagicMock, patch
import pytest
from starlette.testclient import TestClient

from api.dependencies import get_settings_dep, get_store
from api.main import app
from slice.config import Settings, settings as get_settings
from slice.runner import Context
from slice.store import Store
from synapse.schemas import (
    Diagnosis,
    DiagnosisItem,
    MistakeClassification,
    NoteVersion,
    RecordKind,
    TrendLabel,
)


@pytest.fixture
def clean_store(tmp_path):
    """Provide an isolated, clean SQLite store."""
    db_path = tmp_path / "test_synapse_agent.db"
    store = Store(db_path)
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


def test_authoritative_ai_pipeline_with_mocked_llm(client, clean_store):
    """Verify that student test submission triggers the real AI diagnosis agent and note tailoring agent,
    which persists authoritative analysis shared with teacher dashboard while maintaining zero-knowledge note isolation.
    """
    # 1. Register Teacher
    t_res = client.post(
        "/auth/register",
        json={
            "role": "teacher",
            "name": "Dr. Ada Lovelace",
            "username": "ada",
            "email": "ada@synapse.edu",
            "password": "Password123!",
        },
    )
    assert t_res.status_code == 201
    t_token = t_res.json()["token"]
    t_headers = {"Authorization": f"Bearer {t_token}"}

    # Get teacher connection code
    code_res = client.get("/teacher/connection-code", headers=t_headers)
    assert code_res.status_code == 200
    connect_code = code_res.json()["code"]

    # Teacher creates Classroom
    cr_res = client.post(
        "/teacher/classrooms",
        headers=t_headers,
        json={
            "name": "Computer Science 101",
            "subject": "Computer Science",
            "description": "Intro to Algorithms",
        },
    )
    assert cr_res.status_code in (200, 201), cr_res.text
    classroom_id = cr_res.json()["id"]

    # Teacher creates Assessment
    asm_res = client.post(
        f"/teacher/classrooms/{classroom_id}/assessments",
        headers=t_headers,
        json={"title": "Recursion Foundations", "description": "Base cases and recurrence relations", "concept_ids": ["Recursion"]},
    )
    assert asm_res.status_code in (200, 201)
    assessment_id = asm_res.json()["id"]

    # Teacher uploads questions
    q_up = client.post(
        f"/teacher/assessments/{assessment_id}/questions/upload",
        headers=t_headers,
        json={
            "questions": [
                {
                    "question_text": "What is the primary role of a base case in recursion?",
                    "options": [
                        "To terminate recursive calls",
                        "To allocate memory on heap",
                        "To optimize network bandwidth",
                        "To declare types",
                    ],
                    "correct_answer": "To terminate recursive calls",
                    "concept_id": "Recursion",
                    "explanation": "Base case stops further recursive calls.",
                },
                {
                    "question_text": "What happens if a recursive function lacks a base case?",
                    "options": [
                        "Stack overflow error",
                        "Faster compilation",
                        "Zero return value",
                        "Automatic garbage collection",
                    ],
                    "correct_answer": "Stack overflow error",
                    "concept_id": "Recursion",
                    "explanation": "Infinite recursion consumes the call stack.",
                },
            ]
        },
    )

    # Teacher publishes assessment
    pub_res = client.post(f"/teacher/assessments/{assessment_id}/publish", headers=t_headers)
    assert pub_res.status_code == 200

    # 2. Register Student
    s_res = client.post(
        "/auth/register",
        json={
            "role": "student",
            "name": "Alan Turing",
            "username": "alan",
            "email": "alan@synapse.edu",
            "password": "Password123!",
        },
    )
    assert s_res.status_code == 201
    s_token = s_res.json()["token"]
    s_headers = {"Authorization": f"Bearer {s_token}"}
    student_id = s_res.json()["user"]["id"]

    # Student connects to teacher
    conn_res = client.post("/student/connect", headers=s_headers, json={"code": connect_code})
    assert conn_res.status_code == 200

    # Fetch assessment questions to get IDs
    q_res = client.get(f"/student/assessments/{assessment_id}", headers=s_headers)
    assert q_res.status_code == 200
    qs = q_res.json()["questions"]
    q1_id = qs[0]["id"]
    q2_id = qs[1]["id"]

    mock_tailor_text = "# Tailored Note: Mastering Recursion\n\nRemember: a base case prevents stack overflow."

    call_count = 0

    def mock_complete(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        step = kwargs.get("step", "")
        if "diagnosis" in step:
            return Diagnosis(
                concept_id="Recursion",
                student_id=student_id,
                items=[
                    DiagnosisItem(
                        question_id=q2_id,
                        classification=MistakeClassification.CONCEPTUAL_GAP,
                        reason="Student confused call stack exhaustion with compilation optimization.",
                    )
                ],
                mastery_estimate=0.5,
                trend=TrendLabel.NEW,
            )
        else:
            return mock_tailor_text

    configured_settings = replace(get_settings(), api_key="sk-test-live-key")
    app.dependency_overrides[get_settings_dep] = lambda: configured_settings

    try:
        with patch("slice.llm.complete", side_effect=mock_complete):
            sub_res = client.post(
                f"/student/assessments/{assessment_id}/attempt",
                headers=s_headers,
                json={
                    "answers": {
                        q1_id: "To terminate recursive calls",  # correct
                        q2_id: "Faster compilation",           # incorrect
                    }
                },
            )

        assert sub_res.status_code == 200, sub_res.text
        attempt_data = sub_res.json()

        # Verify score
        assert attempt_data["score"] == 1
        assert attempt_data["total"] == 2
        assert attempt_data["percentage"] == 50.0

        # Verify AI Diagnosis is returned to student
        diag = attempt_data["diagnosis"]
        assert diag is not None
        assert diag["concept_id"] == "Recursion"
        assert len(diag["items"]) == 1
        assert diag["items"][0]["classification"] == "conceptual_gap"
        assert "confused call stack exhaustion" in diag["items"][0]["reason"]

        # Verify Tailored Note is returned to student
        note = attempt_data["note"]
        assert note is not None
        assert note["concept_id"] == "Recursion"
        assert note["diagnosis_id"] == diag["id"]
        assert "Tailored Note: Mastering Recursion" in note["markdown"]

        # Verify LLM was called twice (once for diagnosis, once for note tailoring)
        assert call_count >= 2

        # 4. Teacher Queries Connected Student Performance
        perf_res = client.get(f"/teacher/students/{student_id}/performance", headers=t_headers)
        assert perf_res.status_code == 200, perf_res.text
        perf = perf_res.json()

        # Teacher receives the SAME authoritative AI diagnosis
        assert perf["latest_diagnosis"] is not None
        t_diag = perf["latest_diagnosis"]
        assert t_diag["concept_id"] == "Recursion"
        assert len(t_diag["items"]) == 1
        assert t_diag["items"][0]["classification"] == "conceptual_gap"
        assert "confused call stack exhaustion" in t_diag["items"][0]["reason"]

        # ZERO-KNOWLEDGE PRIVACY INVARIANT: Teacher response must NEVER expose private student note markdown
        perf_str = json.dumps(perf)
        assert "Tailored Note: Mastering Recursion" not in perf_str
        assert "markdown" not in perf
    finally:
        app.dependency_overrides.pop(get_settings_dep, None)


def test_unconnected_teacher_cannot_access_student_performance(client, clean_store):
    """Verify authorization boundary: an unrelated teacher receives 403."""
    # Register teacher A
    t_a = client.post(
        "/auth/register",
        json={"role": "teacher", "name": "Teacher A", "username": "t_a", "password": "Password123!"},
    ).json()

    # Register teacher B
    t_b = client.post(
        "/auth/register",
        json={"role": "teacher", "name": "Teacher B", "username": "t_b", "password": "Password123!"},
    ).json()
    tb_headers = {"Authorization": f"Bearer {t_b['token']}"}

    # Register student connected to teacher A
    s = client.post(
        "/auth/register",
        json={"role": "student", "name": "Student S", "username": "student_s", "password": "Password123!"},
    ).json()

    code_a = client.get("/teacher/connection-code", headers={"Authorization": f"Bearer {t_a['token']}"}).json()["code"]
    client.post("/student/connect", headers={"Authorization": f"Bearer {s['token']}"}, json={"code": code_a})

    # Teacher B tries to query student S performance -> 403 Forbidden
    resp = client.get(f"/teacher/students/{s['user']['id']}/performance", headers=tb_headers)
    assert resp.status_code == 403


def test_idempotent_diagnosis_and_tailoring(clean_store):
    """Verify that handle_diagnosing and handle_tailoring reuse existing outputs on duplicate cycles."""
    from synapse.agents.flow import handle_diagnosing
    from synapse.schemas import RunScope, Test, TestQuestion

    scope = RunScope(concept_id="Recursion", student_id="stu_1", teacher_id="tea_1", cycle=1)
    run_id = clean_store.create_run("synapse", scope.model_dump(mode="json"))

    test = Test(
        id="t1",
        concept_id="Recursion",
        concept_name="Recursion",
        questions=[
            TestQuestion(id="q1", text="Q1", options=["A", "B", "C", "D"], correct_answer="A", concept_id="Recursion")
        ],
    )
    clean_store.append(run_id, RecordKind.TEST, test.model_dump(mode="json"), produced_by="test")

    # Manually append an existing diagnosis
    existing_diag = Diagnosis(
        id="diag_fixed_123",
        student_id="stu_1",
        concept_id="Recursion",
        items=[DiagnosisItem(question_id="q1", classification=MistakeClassification.CONCEPTUAL_GAP, reason="Already diagnosed")],
        mastery_estimate=0.4,
        trend=TrendLabel.NEW,
    )
    clean_store.append(run_id, RecordKind.DIAGNOSIS, existing_diag.model_dump(mode="json"), produced_by="agent")

    ctx = Context(clean_store, run_id, get_settings())

    # Call handle_diagnosing with mock that would fail if called
    with patch("slice.llm.complete") as mock_complete:
        asyncio.run(handle_diagnosing(ctx))
        # Should NOT make LLM call because diagnosis already exists
        mock_complete.assert_not_called()

    # Check store still has the same diagnosis
    latest = clean_store.latest(run_id, RecordKind.DIAGNOSIS)
    assert latest["id"] == "diag_fixed_123"


def test_offline_graceful_fallback_without_api_key(clean_store):
    """Verify pipeline completes deterministically using stubs when no API key is set."""
    from synapse.runtime.flow import submit_attempt
    from synapse.schemas import CanonicalNote, RunScope, Test, TestQuestion

    scope = RunScope(concept_id="Recursion", student_id="stu_offline", teacher_id="tea_1", cycle=1)
    run_id = clean_store.create_run("synapse", scope.model_dump(mode="json"))

    test = Test(
        id="t_off",
        concept_id="Recursion",
        concept_name="Recursion",
        questions=[
            TestQuestion(id="q1", text="Base case?", options=["Yes", "No", "Maybe", "Never"], correct_answer="Yes", concept_id="Recursion")
        ],
    )
    clean_store.append(run_id, RecordKind.TEST, test.model_dump(mode="json"), produced_by="test")

    canonical = CanonicalNote(concept_id="Recursion", markdown="# Recursion\nBase cases matter.")
    clean_store.append(run_id, RecordKind.CANONICAL_NOTE, canonical.model_dump(mode="json"), produced_by="test")

    s = replace(get_settings(), api_key="")

    submit_attempt(
        store=clean_store,
        run_id=run_id,
        student_id="stu_offline",
        test_id="t_off",
        answers={"q1": "No"},  # incorrect
        settings=s,
    )

    diag_data = clean_store.latest(run_id, RecordKind.DIAGNOSIS)
    note_data = clean_store.latest(run_id, RecordKind.NOTE_VERSION)

    assert diag_data is not None
    assert len(diag_data["items"]) == 1
    assert diag_data["items"][0]["classification"] in [
        MistakeClassification.CONTRADICTORY.value,
        MistakeClassification.CONCEPTUAL_GAP.value,
    ]

    assert note_data is not None
    assert note_data["diagnosis_id"] == diag_data["id"]
    assert "Study Guide" in note_data["markdown"] or "Study Note" in note_data["markdown"]
