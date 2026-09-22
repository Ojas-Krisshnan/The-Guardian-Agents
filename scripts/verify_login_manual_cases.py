# scripts/verify_login_manual_cases.py
"""Comprehensive verification of the 5 manual test cases (Cases A, B, C, D, E)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starlette.testclient import TestClient
from api.main import app
from slice.store import Store
from api.dependencies import set_store
from pathlib import Path

def run_checks():
    db_path = Path("synapse_cycle.db")
    store = Store(db_path)
    set_store(store)
    client = TestClient(app)

    print("=" * 60)
    print("VERIFYING LOGIN CASES AGAINST SYNAPSE CYCLE")
    print("=" * 60)

    # CASE A: WRONG PASSWORD (Existing account, wrong password)
    # Default teacher account is 'teacher_prof'
    resp_a = client.post("/auth/login", json={"username": "teacher_prof", "password": "DefinitelyWrongPassword999!"})
    print(f"[CASE A - Wrong Password] Status: {resp_a.status_code}, Response: {resp_a.json()}")
    assert resp_a.status_code == 401, f"Expected 401, got {resp_a.status_code}"
    assert resp_a.status_code != 404, "Must not return 404!"
    assert resp_a.json()["detail"] == "Invalid username or password"
    print("  -> CASE A PASSED: HTTP 401 Unauthorized, 'Invalid username or password', NO 404.")

    # CASE B: NONEXISTENT ACCOUNT
    resp_b = client.post("/auth/login", json={"username": "completely_ghost_account_xyz", "password": "AnyPassword123"})
    print(f"[CASE B - Nonexistent User] Status: {resp_b.status_code}, Response: {resp_b.json()}")
    assert resp_b.status_code == 401, f"Expected 401, got {resp_b.status_code}"
    assert resp_b.status_code != 404, "Must not return 404!"
    assert resp_b.json()["detail"] == "Invalid username or password"
    assert resp_b.json() == resp_a.json(), "Case A and Case B must produce identical responses to prevent enumeration"
    print("  -> CASE B PASSED: HTTP 401 Unauthorized, 'Invalid username or password', NO 404, identical to Case A.")

    # Direct /login alias test
    resp_alias = client.post("/login", json={"username": "teacher_prof", "password": "WrongPassword"})
    assert resp_alias.status_code == 401
    assert resp_alias.status_code != 404
    print("  -> /login alias PASSED: HTTP 401 (never 404).")

    # CASE D: VALID LOGIN
    # Default teacher account: teacher_prof / password123
    resp_d = client.post("/auth/login", json={"username": "teacher_prof", "password": "password123"})
    print(f"[CASE D - Valid Login] Status: {resp_d.status_code}")
    assert resp_d.status_code == 200, f"Expected 200, got {resp_d.status_code}"
    body_d = resp_d.json()
    assert "token" in body_d
    assert body_d["user"]["role"] == "teacher"
    teacher_token = body_d["token"]
    print(f"  -> CASE D PASSED: Login succeeded, role={body_d['user']['role']}, token generated.")

    # CASE E: DIRECT URL & PROTECTED ROUTING
    # Attempting to access protected /teacher/classrooms endpoints unauthenticated
    resp_e_unauth = client.get("/teacher/classrooms")
    print(f"[CASE E - Protected Route Unauthenticated] Status: {resp_e_unauth.status_code}")
    assert resp_e_unauth.status_code == 401, f"Expected 401, got {resp_e_unauth.status_code}"

    # Also test /auth/me without token
    resp_me_unauth = client.get("/auth/me")
    assert resp_me_unauth.status_code == 401

    # Accessing with valid token succeeds
    resp_e_auth = client.get("/auth/me", headers={"Authorization": f"Bearer {teacher_token}"})
    print(f"[CASE E - Protected Route Authenticated] Status: {resp_e_auth.status_code}")
    assert resp_e_auth.status_code == 200
    print("  -> CASE E PASSED: Direct protected endpoints require authentication; valid session succeeds.")

    # CASE F: STUDENT LOGIN WITH USERNAME & PASSWORD
    # Default student account: student_jane / password123
    resp_stu = client.post("/auth/login", json={"username": "student_jane", "password": "password123"})
    assert resp_stu.status_code == 200, f"Expected 200, got {resp_stu.status_code}: {resp_stu.text}"
    stu_body = resp_stu.json()
    assert stu_body["user"]["role"] == "student"
    stu_token = stu_body["token"]
    stu_headers = {"Authorization": f"Bearer {stu_token}"}
    print("  -> CASE F PASSED: Student login with username & password succeeded.")

    # CASE G: TEACHER-STUDENT CONNECTION VIA CONNECTION CODE
    # Get teacher's connection code
    t_code_resp = client.get("/teacher/connection-code", headers={"Authorization": f"Bearer {teacher_token}"})
    assert t_code_resp.status_code == 200
    t_code = t_code_resp.json()["code"]

    # Student connects using the Teacher Connection Code
    conn_resp = client.post("/student/connect", headers=stu_headers, json={"code": t_code})
    assert conn_resp.status_code == 200
    assert conn_resp.json()["success"] is True
    print(f"  -> CASE G PASSED: Student connected to teacher via code {t_code}.")

    # Teacher sees student under My Students
    t_students_resp = client.get("/teacher/students", headers={"Authorization": f"Bearer {teacher_token}"})
    assert t_students_resp.status_code == 200
    student_ids = [s["student_id"] for s in t_students_resp.json()]
    assert stu_body["user"]["id"] in student_ids
    print("  -> CASE H PASSED: Connected student appears in teacher's My Students list.")

    print("\nALL VERIFICATION CHECKS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_checks()
