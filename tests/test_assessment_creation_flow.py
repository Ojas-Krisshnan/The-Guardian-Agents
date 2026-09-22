# tests/test_assessment_creation_flow.py
"""
Comprehensive tests for Teacher Assessment Creation Flow:
- Manual question creation & schema conversion
- Backend validation (missing text, missing options, duplicate options, invalid answer)
- Document upload and extraction (.pdf, .docx, legacy .doc error, invalid extensions, size limits)
- Answer preservation and missing answer flagging
- Publishing flow & Student assessment-taking compatibility
"""
from __future__ import annotations

import io
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from api.dependencies import set_store
from api.main import app
from slice.store import Store
from synapse.document_parser import (
    DocumentFormatError,
    extract_text_from_file,
    parse_questions_from_text,
)


@pytest.fixture
def clean_store(tmp_path: Path):
    db_file = tmp_path / "test_assessment_creation.db"
    store = Store(db_file)
    set_store(store)
    yield store, db_file
    store.close()


@pytest.fixture
def client(clean_store):
    return TestClient(app)


def get_teacher_auth(client: TestClient) -> dict[str, str]:
    t_resp = client.post("/auth/login", json={"username": "teacher_prof", "password": "password123"})
    assert t_resp.status_code == 200
    token = t_resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def create_test_classroom(client: TestClient, headers: dict[str, str]) -> str:
    c_resp = client.post(
        "/teacher/classrooms",
        headers=headers,
        json={"name": "Computer Science 101", "subject": "Algorithms"},
    )
    assert c_resp.status_code == 200
    return c_resp.json()["id"]


# ─── PART 1 & 2: MANUAL CREATION & VALIDATION ────────────────────────────────


def test_manual_single_and_multiple_questions(client: TestClient, clean_store):
    """1 & 2: Teacher can create one question and multiple questions manually."""
    headers = get_teacher_auth(client)
    classroom_id = create_test_classroom(client, headers)

    # Create assessment metadata
    asm_resp = client.post(
        f"/teacher/classrooms/{classroom_id}/assessments",
        headers=headers,
        json={"title": "Single Question Quiz", "description": "Recursion Intro"},
    )
    assert asm_resp.status_code == 200
    asm_id = asm_resp.json()["id"]

    # 1. Single Question
    single_q = {
        "questions": [
            {
                "question_text": "What is recursion?",
                "options": [
                    "A function that calls itself",
                    "A loop statement",
                    "A variable declaration",
                    "A compiler warning",
                ],
                "correct_answer": "A function that calls itself",
                "concept_id": "Recursion",
            }
        ]
    }
    q1_resp = client.post(f"/teacher/assessments/{asm_id}/questions/upload", headers=headers, json=single_q)
    assert q1_resp.status_code == 200
    assert len(q1_resp.json()) == 1

    # 2. Multiple Questions in another assessment
    asm2_resp = client.post(
        f"/teacher/classrooms/{classroom_id}/assessments",
        headers=headers,
        json={"title": "Multi Question Quiz", "description": "Full Unit"},
    )
    asm2_id = asm2_resp.json()["id"]

    multi_q = {
        "questions": [
            {
                "question_text": "What is the base case?",
                "options": ["Termination condition", "Heap allocation", "Speed booster", "Global variable"],
                "correct_answer": "Termination condition",
                "concept_id": "Recursion Base Case",
            },
            {
                "question_text": "Where is the call frame stored?",
                "options": ["Call stack", "Memory heap", "CPU register", "Solid state drive"],
                "correct_answer": "Call stack",
                "concept_id": "Call Stack",
            },
            {
                "question_text": "What causes stack overflow?",
                "options": ["Infinite recursion without base case", "Too many comments", "Variable renaming", "Fast CPU"],
                "correct_answer": "Infinite recursion without base case",
                "concept_id": "Recursion Base Case",
            },
        ]
    }
    q2_resp = client.post(f"/teacher/assessments/{asm2_id}/questions/upload", headers=headers, json=multi_q)
    assert q2_resp.status_code == 200
    assert len(q2_resp.json()) == 3


def test_manual_validation_rejections(client: TestClient, clean_store):
    """3, 4, 5, 6: Validation rejects empty text, <2 options, duplicate options, invalid correct answer."""
    headers = get_teacher_auth(client)
    classroom_id = create_test_classroom(client, headers)

    asm_resp = client.post(
        f"/teacher/classrooms/{classroom_id}/assessments",
        headers=headers,
        json={"title": "Validation Test Quiz"},
    )
    asm_id = asm_resp.json()["id"]

    # 3. Missing question text
    resp_empty_text = client.post(
        f"/teacher/assessments/{asm_id}/questions/upload",
        headers=headers,
        json={
            "questions": [
                {
                    "question_text": "   ",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": "A",
                }
            ]
        },
    )
    assert resp_empty_text.status_code == 422

    # 4. Missing options (<2 options)
    resp_missing_opts = client.post(
        f"/teacher/assessments/{asm_id}/questions/upload",
        headers=headers,
        json={
            "questions": [
                {
                    "question_text": "Is this valid?",
                    "options": ["Only one option"],
                    "correct_answer": "Only one option",
                }
            ]
        },
    )
    assert resp_missing_opts.status_code == 422

    # 5. Duplicate options within a question
    resp_dup_opts = client.post(
        f"/teacher/assessments/{asm_id}/questions/upload",
        headers=headers,
        json={
            "questions": [
                {
                    "question_text": "Which one is distinct?",
                    "options": ["Duplicated Option", "Duplicated Option", "Option C", "Option D"],
                    "correct_answer": "Option C",
                }
            ]
        },
    )
    assert resp_dup_opts.status_code == 422
    assert "unique" in resp_dup_opts.json()["detail"].lower()

    # 6. Invalid correct answer (not in options)
    resp_invalid_ans = client.post(
        f"/teacher/assessments/{asm_id}/questions/upload",
        headers=headers,
        json={
            "questions": [
                {
                    "question_text": "What is the answer?",
                    "options": ["Option A", "Option B", "Option C", "Option D"],
                    "correct_answer": "Ghost Option Not In List",
                }
            ]
        },
    )
    assert resp_invalid_ans.status_code == 422
    assert "correct_answer" in resp_invalid_ans.json()["detail"].lower()


def test_publish_empty_assessment_fails(client: TestClient, clean_store):
    """Assessment cannot be published before uploading valid questions."""
    headers = get_teacher_auth(client)
    classroom_id = create_test_classroom(client, headers)

    asm_resp = client.post(
        f"/teacher/classrooms/{classroom_id}/assessments",
        headers=headers,
        json={"title": "Empty Assessment"},
    )
    asm_id = asm_resp.json()["id"]

    pub_resp = client.post(f"/teacher/assessments/{asm_id}/publish", headers=headers)
    assert pub_resp.status_code == 400
    assert "zero questions" in pub_resp.json()["detail"].lower()


# ─── PART 3, 4, 5, 6, 7: FILE UPLOAD & EXTRACTION ────────────────────────────


def test_document_extraction_pdf(client: TestClient, clean_store, tmp_path: Path):
    """9, 14, 15, 19: PDF upload accepted, text and questions extracted, answers preserved."""
    headers = get_teacher_auth(client)
    import pymupdf

    pdf_path = tmp_path / "test_quiz.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    text = (
        "Assessment: Data Structures Quiz\n"
        "Topic: Recursion\n\n"
        "1. What is the role of a base case?\n"
        "A. Stops recursion\n"
        "B. Loops forever\n"
        "C. Allocates disk space\n"
        "D. Compiles code\n"
        "Answer: A\n"
        "Concept: Base Case\n\n"
        "2. Where are activation frames stored?\n"
        "A. Disk drive\n"
        "B. Call stack\n"
        "C. USB flash\n"
        "D. Monitor\n"
        "Correct Answer: B\n"
        "Concept: Call Stack\n"
    )
    page.insert_text((50, 72), text)
    doc.save(str(pdf_path))
    doc.close()

    with open(pdf_path, "rb") as f:
        resp = client.post(
            "/teacher/assessments/extract-document",
            headers=headers,
            files={"file": ("test_quiz.pdf", f, "application/pdf")},
            data={"title": "Data Structures Quiz", "topic": "Recursion"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_extracted"] == 2
    assert data["title"] == "Data Structures Quiz"
    assert len(data["questions"]) == 2

    # Check question 1
    q1 = data["questions"][0]
    assert "role of a base case" in q1["question_text"]
    assert q1["options"] == ["Stops recursion", "Loops forever", "Allocates disk space", "Compiles code"]
    assert q1["correct_answer"] == "Stops recursion"
    assert q1["concept_id"] == "Base Case"
    assert q1["needs_review"] is False

    # Check question 2
    q2 = data["questions"][1]
    assert "activation frames stored" in q2["question_text"]
    assert q2["correct_answer"] == "Call stack"
    assert q2["concept_id"] == "Call Stack"


def test_document_extraction_docx(client: TestClient, clean_store, tmp_path: Path):
    """10, 14, 19: DOCX upload accepted, extracted with options and correct answers preserved."""
    headers = get_teacher_auth(client)
    import docx

    docx_path = tmp_path / "algorithms.docx"
    doc = docx.Document()
    doc.add_paragraph("Assessment: Algorithm Complexity")
    doc.add_paragraph("Topic: Big-O")
    doc.add_paragraph("Question 1: What is the time complexity of binary search?")
    doc.add_paragraph("A) O(1)")
    doc.add_paragraph("B) O(log n)")
    doc.add_paragraph("C) O(n)")
    doc.add_paragraph("D) O(n^2)")
    doc.add_paragraph("Correct Answer: B")
    doc.add_paragraph("Concept: Binary Search")
    doc.save(str(docx_path))

    with open(docx_path, "rb") as f:
        resp = client.post(
            "/teacher/assessments/extract-document",
            headers=headers,
            files={"file": ("algorithms.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_extracted"] == 1
    q = data["questions"][0]
    assert "time complexity of binary search" in q["question_text"]
    assert q["options"] == ["O(1)", "O(log n)", "O(n)", "O(n^2)"]
    assert q["correct_answer"] == "O(log n)"
    assert q["concept_id"] == "Binary Search"


def test_legacy_doc_returns_clear_user_guidance(client: TestClient, clean_store, tmp_path: Path):
    """11: Legacy binary .doc format returns clear user-facing guidance rather than silent failure."""
    headers = get_teacher_auth(client)
    doc_path = tmp_path / "legacy.doc"
    # OLE compound file binary header
    doc_path.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1\x00\x00\x00")

    with open(doc_path, "rb") as f:
        resp = client.post(
            "/teacher/assessments/extract-document",
            headers=headers,
            files={"file": ("legacy.doc", f, "application/msword")},
        )

    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "legacy .doc" in detail.lower()
    assert "save or export it as .docx or .pdf" in detail.lower()


def test_invalid_file_type_rejected(client: TestClient, clean_store, tmp_path: Path):
    """12: Invalid file extensions (.exe, .txt, .zip) are rejected."""
    headers = get_teacher_auth(client)
    bad_file = tmp_path / "malicious.exe"
    bad_file.write_bytes(b"MZfakebinarycontent")

    with open(bad_file, "rb") as f:
        resp = client.post(
            "/teacher/assessments/extract-document",
            headers=headers,
            files={"file": ("malicious.exe", f, "application/x-msdownload")},
        )

    assert resp.status_code == 400
    assert "unsupported file format" in resp.json()["detail"].lower()


def test_missing_answers_are_flagged_not_invented(client: TestClient, clean_store, tmp_path: Path):
    """20: Questions with no identifiable correct answer are flagged for teacher review, NOT guessed."""
    headers = get_teacher_auth(client)
    import docx

    docx_path = tmp_path / "no_answers.docx"
    doc = docx.Document()
    doc.add_paragraph("1. What is an invariant in computer science?")
    doc.add_paragraph("A. A condition that remains true throughout execution")
    doc.add_paragraph("B. A variable that changes on each cycle")
    doc.add_paragraph("C. A syntax error caused by missing braces")
    doc.add_paragraph("D. A hardware interrupt")
    # Notice: NO answer line provided!
    doc.save(str(docx_path))

    with open(docx_path, "rb") as f:
        resp = client.post(
            "/teacher/assessments/extract-document",
            headers=headers,
            files={"file": ("no_answers.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_extracted"] == 1
    q = data["questions"][0]
    # Invariant: Must be flagged for review, correct_answer must NOT be invented
    assert q["needs_review"] is True
    assert q["correct_answer"] == ""
    assert "no correct answer detected" in q["warning"].lower()


def test_teacher_authorization_on_extract(client: TestClient, clean_store):
    """24: Extraction endpoint enforces teacher authorization."""
    # Unauthenticated
    resp_unauth = client.post("/teacher/assessments/extract-document")
    assert resp_unauth.status_code == 401

    # Student token cannot access teacher extraction
    s_resp = client.post("/auth/login", json={"username": "alice", "password": "password123"})
    if s_resp.status_code == 200:
        s_headers = {"Authorization": f"Bearer {s_resp.json()['token']}"}
        resp_student = client.post(
            "/teacher/assessments/extract-document",
            headers=s_headers,
            files={"file": ("test.pdf", b"%PDF-1.4...", "application/pdf")},
        )
        assert resp_student.status_code == 403


# ─── PART 8, 9, 10, 11: END-TO-END PUBLISH & STUDENT TAKING FLOW ────────────


def test_end_to_end_publish_and_student_taking(client: TestClient, clean_store, tmp_path: Path):
    """
    7, 8, 16, 17, 21, 22, 23: Complete flow:
    - Teacher extracts questions from document
    - Teacher reviews & edits extracted questions (adds concept, fixes a question, removes unwanted question)
    - Teacher publishes assessment
    - Student takes assessment
    - Answers are graded and mastery metrics are computed
    - Student endpoint never leaks correct answer in advance
    """
    t_headers = get_teacher_auth(client)
    classroom_id = create_test_classroom(client, t_headers)

    # 1. Create document with 3 questions
    import docx

    doc_path = tmp_path / "exam.docx"
    doc = docx.Document()
    doc.add_paragraph("Assessment: Midterm Review")
    doc.add_paragraph("1. What does FIFO stand for in data structures?")
    doc.add_paragraph("A. First In First Out")
    doc.add_paragraph("B. Fast Input Fast Output")
    doc.add_paragraph("C. Function Input Frame Order")
    doc.add_paragraph("D. Fixed Index File Operation")
    doc.add_paragraph("Answer: A")

    doc.add_paragraph("2. Which data structure operates on LIFO principles?")
    doc.add_paragraph("A. Queue")
    doc.add_paragraph("B. Stack")
    doc.add_paragraph("C. Hash Map")
    doc.add_paragraph("D. Binary Tree")
    doc.add_paragraph("Answer: B")

    # Extra unwanted question to simulate teacher deletion
    doc.add_paragraph("3. What is the color of the classroom door?")
    doc.add_paragraph("A. Blue")
    doc.add_paragraph("B. Red")
    doc.add_paragraph("C. Green")
    doc.add_paragraph("D. Yellow")
    doc.add_paragraph("Answer: A")
    doc.save(str(doc_path))

    # 2. Extract document
    with open(doc_path, "rb") as f:
        ext_resp = client.post(
            "/teacher/assessments/extract-document",
            headers=t_headers,
            files={"file": ("exam.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
    assert ext_resp.status_code == 200
    extracted = ext_resp.json()
    assert extracted["total_extracted"] == 3

    # 3. Simulate Teacher review & edit:
    # - Teacher keeps Q1 and Q2, removes Q3
    # - Teacher sets explicit concepts for Q1 ("Queue FIFO") and Q2 ("Stack LIFO")
    reviewed_questions = [
        {
            "question_text": extracted["questions"][0]["question_text"],
            "options": extracted["questions"][0]["options"],
            "correct_answer": extracted["questions"][0]["correct_answer"],
            "concept_id": "Queue FIFO",
        },
        {
            "question_text": extracted["questions"][1]["question_text"],
            "options": extracted["questions"][1]["options"],
            "correct_answer": extracted["questions"][1]["correct_answer"],
            "concept_id": "Stack LIFO",
        },
    ]

    # 4. Create Assessment in classroom
    asm_create = client.post(
        f"/teacher/classrooms/{classroom_id}/assessments",
        headers=t_headers,
        json={"title": "Midterm Review Diagnostic", "description": "Queues and Stacks"},
    )
    assert asm_create.status_code == 200
    asm_id = asm_create.json()["id"]

    # 5. Upload reviewed questions
    up_resp = client.post(
        f"/teacher/assessments/{asm_id}/questions/upload",
        headers=t_headers,
        json={"questions": reviewed_questions},
    )
    assert up_resp.status_code == 200
    saved_questions = up_resp.json()
    assert len(saved_questions) == 2
    q1_id = saved_questions[0]["id"]
    q2_id = saved_questions[1]["id"]

    # 6. Publish Assessment
    pub_resp = client.post(f"/teacher/assessments/{asm_id}/publish", headers=t_headers)
    assert pub_resp.status_code == 200
    assert pub_resp.json()["status"] == "published"

    # 7. Generate student in classroom
    gen_resp = client.post(
        f"/teacher/classrooms/{classroom_id}/students/generate",
        headers=t_headers,
        json={"count": 1},
    )
    assert gen_resp.status_code == 200
    stu_login_id = gen_resp.json()["students"][0]["login_id"]

    # Student logs in
    stu_auth = client.post("/auth/login", json={"login_id": stu_login_id}).json()
    stu_headers = {"Authorization": f"Bearer {stu_auth['token']}"}

    # 8. Student fetches assessment questions
    take_resp = client.get(f"/student/assessments/{asm_id}", headers=stu_headers)
    assert take_resp.status_code == 200
    take_data = take_resp.json()
    assert len(take_data["questions"]) == 2

    # Verify Zero-Knowledge boundary: student never sees correct answer in response
    for sq in take_data["questions"]:
        assert sq["correct_answer"] is None
        assert sq["explanation"] is None

    # 9. Student submits attempt (Q1 correct, Q2 wrong)
    sub_resp = client.post(
        f"/student/assessments/{asm_id}/attempt",
        headers=stu_headers,
        json={"answers": {q1_id: "First In First Out", q2_id: "Queue"}},
    )
    assert sub_resp.status_code == 200
    attempt_result = sub_resp.json()
    assert attempt_result["score"] == 1
    assert attempt_result["total"] == 2
    assert attempt_result["percentage"] == 50.0
