# tests/verify_live_pipeline.py
"""Live E2E Verification of the Synapse AI Agent Pipeline on port 8000."""
import requests
import json
import secrets

BASE_URL = "http://127.0.0.1:8000"

def main():
    suffix = secrets.token_hex(3)
    print(f"--- Starting Live E2E AI Pipeline Test (suffix={suffix}) ---")

    # 1. Register Teacher
    t_reg = requests.post(f"{BASE_URL}/auth/register", json={
        "role": "teacher",
        "name": f"Dr. Pipeline {suffix}",
        "username": f"teacher_{suffix}",
        "email": f"t_{suffix}@synapse.edu",
        "password": "Password123!",
    })
    assert t_reg.status_code == 201, f"Teacher register failed: {t_reg.text}"
    t_token = t_reg.json()["token"]
    t_headers = {"Authorization": f"Bearer {t_token}"}
    print("Teacher registered successfully.")

    # Get connection code
    c_res = requests.get(f"{BASE_URL}/teacher/connection-code", headers=t_headers)
    assert c_res.status_code == 200, f"Get code failed: {c_res.text}"
    code = c_res.json()["code"]
    print(f"Teacher connection code: {code}")

    # Create classroom
    cr_res = requests.post(f"{BASE_URL}/teacher/classrooms", headers=t_headers, json={
        "name": f"CS Algorithms {suffix}",
        "subject": "Computer Science",
        "description": "Recursion & Trees",
    })
    assert cr_res.status_code in (200, 201), f"Create classroom failed: {cr_res.text}"
    class_id = cr_res.json()["id"]
    print(f"Classroom created: {class_id}")

    # Create assessment
    asm_res = requests.post(f"{BASE_URL}/teacher/classrooms/{class_id}/assessments", headers=t_headers, json={
        "title": "Recursion Mastery Quiz",
        "description": "Base cases and calls",
        "concept_ids": ["Recursion"],
    })
    assert asm_res.status_code in (200, 201), f"Create assessment failed: {asm_res.text}"
    asm_id = asm_res.json()["id"]
    print(f"Assessment created: {asm_id}")

    # Upload questions
    q_up = requests.post(f"{BASE_URL}/teacher/assessments/{asm_id}/questions/upload", headers=t_headers, json={
        "questions": [
            {
                "question_text": "What does a recursive base case prevent?",
                "options": ["Stack overflow", "Syntax error", "Slow network", "Null pointer"],
                "correct_answer": "Stack overflow",
                "concept_id": "Recursion",
                "explanation": "Base case stops execution before stack limits are exceeded.",
            },
            {
                "question_text": "Which memory structure stores recursive call stack frames?",
                "options": ["Call Stack", "Heap Memory", "Disk Storage", "GPU Cache"],
                "correct_answer": "Call Stack",
                "concept_id": "Recursion",
                "explanation": "Functions use stack frames on call stack.",
            }
        ]
    })
    assert q_up.status_code == 200, f"Question upload failed: {q_up.text}"
    print("Questions uploaded.")

    # Publish assessment
    pub = requests.post(f"{BASE_URL}/teacher/assessments/{asm_id}/publish", headers=t_headers)
    assert pub.status_code == 200, f"Publish failed: {pub.text}"
    print("Assessment published.")

    # 2. Register Student
    s_reg = requests.post(f"{BASE_URL}/auth/register", json={
        "role": "student",
        "name": f"Student Pipeline {suffix}",
        "username": f"student_{suffix}",
        "email": f"s_{suffix}@synapse.edu",
        "password": "Password123!",
    })
    assert s_reg.status_code == 201, f"Student register failed: {s_reg.text}"
    s_token = s_reg.json()["token"]
    s_headers = {"Authorization": f"Bearer {s_token}"}
    student_id = s_reg.json()["user"]["id"]
    print(f"Student registered: {student_id}")

    # Student connects to teacher
    conn = requests.post(f"{BASE_URL}/student/connect", headers=s_headers, json={"code": code})
    assert conn.status_code == 200, f"Student connect failed: {conn.text}"
    print("Student connected to teacher.")

    # Get student questions
    sq_res = requests.get(f"{BASE_URL}/student/assessments/{asm_id}", headers=s_headers)
    assert sq_res.status_code == 200, f"Fetch student assessment failed: {sq_res.text}"
    qs = sq_res.json()["questions"]
    q1_id = qs[0]["id"]
    q2_id = qs[1]["id"]

    # 3. Student Submits Attempt
    # Answer 1 correct ("Stack overflow"), Answer 2 incorrect ("Disk Storage")
    sub_res = requests.post(f"{BASE_URL}/student/assessments/{asm_id}/attempt", headers=s_headers, json={
        "answers": {
            q1_id: "Stack overflow",
            q2_id: "Disk Storage",
        }
    })
    assert sub_res.status_code == 200, f"Submit attempt failed: {sub_res.text}"
    att = sub_res.json()
    print("Assessment attempt submitted successfully.")
    print(f"Score: {att['score']}/{att['total']} ({att['percentage']}%)")
    assert att["score"] == 1
    assert att["total"] == 2

    # Verify AI Diagnosis is returned
    assert att["diagnosis"] is not None, "Expected diagnosis in attempt response"
    diag = att["diagnosis"]
    print(f"AI Diagnosis Concept: {diag['concept_id']}")
    print(f"Misconceptions Identified: {len(diag['items'])}")
    for item in diag["items"]:
        print(f"  - [{item['classification']}] {item['reason']}")

    # Verify Tailored Note is returned
    assert att["note"] is not None, "Expected tailored note in attempt response"
    print(f"Tailored Note Version: {att['note']['version']}")
    print(f"Tailored Note Excerpt: {att['note']['markdown'][:80]}...")

    # 4. Teacher Queries Connected Student Performance
    perf_res = requests.get(f"{BASE_URL}/teacher/students/{student_id}/performance", headers=t_headers)
    assert perf_res.status_code == 200, f"Teacher performance query failed: {perf_res.text}"
    perf = perf_res.json()
    print("Teacher received connected student performance successfully.")
    print(f"Overall Mastery: {perf['overall_mastery']}%")
    print(f"Recent Score: {perf['recent_score']}%")
    print(f"Trend: {perf['trend']}")

    # Verify Authoritative Diagnosis is in Teacher Performance
    assert perf["latest_diagnosis"] is not None, "Expected latest_diagnosis in teacher response"
    t_diag = perf["latest_diagnosis"]
    assert t_diag["concept_id"] == "Recursion"
    assert len(t_diag["items"]) == len(diag["items"])
    print(f"Teacher view of diagnosis items: {len(t_diag['items'])} items")

    # Verify Zero-Knowledge Isolation: private student note is NEVER in teacher response
    perf_dump = json.dumps(perf)
    assert att["note"]["markdown"] not in perf_dump, "CRITICAL: Student private note leaked to teacher response!"
    print("Zero-Knowledge Privacy Invariant strictly verified: No student note text accessible to teacher.")

    # 5. Unauthorized Teacher Access Blocked
    t2_reg = requests.post(f"{BASE_URL}/auth/register", json={
        "role": "teacher",
        "name": f"Dr. Intruder {suffix}",
        "username": f"intruder_{suffix}",
        "password": "Password123!",
    })
    t2_token = t2_reg.json()["token"]
    t2_headers = {"Authorization": f"Bearer {t2_token}"}
    unauth_res = requests.get(f"{BASE_URL}/teacher/students/{student_id}/performance", headers=t2_headers)
    assert unauth_res.status_code == 403, f"Expected 403 for unauthorized teacher, got {unauth_res.status_code}"
    print("Access authorization boundary verified: Unconnected teacher correctly rejected with 403 Forbidden.")

    print("\nALL LIVE E2E VERIFICATIONS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
