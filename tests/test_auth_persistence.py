# tests/test_auth_persistence.py
"""
Tests for persistent teacher and student authentication storage in SQLite via slice.store.Store.

Verifies:
1. Teacher registration persists in SQLite and survives Store/process restart.
2. Student registration persists in SQLite and survives Store/process restart.
3. Duplicate registrations (username or email) are rejected with 409 Conflict.
4. Login succeeds with correct credentials and returns JWT token and user profile.
5. Wrong password rejected with 401 Unauthorized.
6. Unknown account rejected with 401 Unauthorized.
7. Role is strictly derived from SQLite user record ('teacher' vs 'student').
8. Password and password_hash are never returned in responses or leaked.
9. Raw passwords are never stored in SQLite (verified via raw DB inspection).
10. Store instance destruction and recreation preserves all accounts.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from api.dependencies import set_store
from api.main import app
from slice.store import Store


@pytest.fixture
def auth_store(tmp_path: Path):
    """Provide an isolated temporary filesystem SQLite database."""
    db_file = tmp_path / "auth_persistence_test.db"
    store = Store(db_file)
    set_store(store)
    yield store, db_file
    store.close()


@pytest.fixture
def client(auth_store):
    return TestClient(app)


# ======================================================================
# Phase 12: Database Restart Persistence Tests (Store Re-creation)
# ======================================================================

def test_teacher_persistence_across_store_restart(tmp_path: Path):
    """Test teacher registration, Store destruction, and login after restart."""
    db_file = tmp_path / "teacher_restart.db"

    # Session 1: Register teacher in Store 1
    s1 = Store(db_file)
    user1 = s1.create_user(
        role="teacher",
        username="prof_noether",
        password="NoetherTheorem2026!",
        name="Emmy Noether",
        email="noether@synapse.edu",
    )
    assert user1["role"] == "teacher"
    assert user1["username"] == "prof_noether"
    assert "password" not in user1
    assert "password_hash" not in user1

    # Verify directly in SQLite filesystem database
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM users WHERE username = 'prof_noether'").fetchone()
    assert row is not None
    assert row["role"] == "teacher"
    assert row["name"] == "Emmy Noether"
    assert row["password_hash"] is not None
    # Verify raw password is NOT stored
    assert "NoetherTheorem2026!" not in row["password_hash"]
    assert "$" in row["password_hash"]  # salt$hash format
    conn.close()

    # Destroy Store 1
    s1.close()
    del s1

    # Session 2: Create a completely NEW Store instance on same DB file (simulating backend restart)
    s2 = Store(db_file)
    # Re-authentication succeeds
    auth_user = s2.authenticate_user("prof_noether", "NoetherTheorem2026!")
    assert auth_user is not None
    assert auth_user["role"] == "teacher"
    assert auth_user["name"] == "Emmy Noether"
    assert "password" not in auth_user
    assert "password_hash" not in auth_user

    # Wrong password fails
    assert s2.authenticate_user("prof_noether", "WrongPassword!") is None
    # Non-existent user fails
    assert s2.authenticate_user("ghost_user", "AnyPassword") is None
    s2.close()


def test_student_persistence_across_store_restart(tmp_path: Path):
    """Test student registration, Store destruction, and login after restart."""
    db_file = tmp_path / "student_restart.db"

    # Session 1: Register student in Store 1
    s1 = Store(db_file)
    student1 = s1.create_user(
        role="student",
        username="learner_ramanujan",
        password="HardyRamanujan1729!",
        name="Srinivasa Ramanujan",
        email="ramanujan@synapse.edu",
    )
    assert student1["role"] == "student"
    assert student1["username"] == "learner_ramanujan"
    assert "password" not in student1
    assert "password_hash" not in student1

    # Verify directly in SQLite filesystem database
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM users WHERE username = 'learner_ramanujan'").fetchone()
    assert row is not None
    assert row["role"] == "student"
    assert row["name"] == "Srinivasa Ramanujan"
    assert "HardyRamanujan1729!" not in row["password_hash"]
    conn.close()

    # Destroy Store 1
    s1.close()
    del s1

    # Session 2: Create NEW Store instance on same DB file
    s2 = Store(db_file)
    auth_student = s2.authenticate_user("learner_ramanujan", "HardyRamanujan1729!")
    assert auth_student is not None
    assert auth_student["role"] == "student"
    assert auth_student["name"] == "Srinivasa Ramanujan"
    assert "password" not in auth_student
    assert "password_hash" not in auth_student

    # Wrong password fails
    assert s2.authenticate_user("learner_ramanujan", "WrongPass") is None
    s2.close()


# ======================================================================
# Phase 13: HTTP Registration and Login Tests (Teacher & Student)
# ======================================================================

def test_teacher_registration_and_login_api(client, auth_store):
    """Verify teacher registration, duplicate rejection, login, and role enforcement."""
    # 1. Registration succeeds (201 Created)
    reg_resp = client.post(
        "/auth/register",
        json={
            "role": "teacher",
            "username": "prof_curie",
            "password": "RadiumPolonium1898!",
            "name": "Marie Curie",
            "email": "curie@synapse.edu",
        },
    )
    assert reg_resp.status_code == 201, reg_resp.text
    reg_data = reg_resp.json()
    assert "token" in reg_data
    assert reg_data["user"]["role"] == "teacher"
    assert reg_data["user"]["username"] == "prof_curie"
    assert reg_data["user"]["name"] == "Marie Curie"
    assert "password" not in reg_data["user"]
    assert "password_hash" not in reg_data["user"]

    # 2. Duplicate registration with same username rejected (409 Conflict)
    dup_resp = client.post(
        "/auth/register",
        json={
            "role": "teacher",
            "username": "prof_curie",
            "password": "AnotherPassword123!",
            "name": "Imposter Curie",
            "email": "imposter@synapse.edu",
        },
    )
    assert dup_resp.status_code == 409
    assert "already registered" in dup_resp.json()["detail"].lower()

    # 3. Duplicate registration with same email rejected (409 Conflict)
    dup_email_resp = client.post(
        "/auth/register",
        json={
            "role": "teacher",
            "username": "curie_alt",
            "password": "AnotherPassword123!",
            "name": "Marie Alt",
            "email": "curie@synapse.edu",
        },
    )
    assert dup_email_resp.status_code == 409

    # 4. Login succeeds with username + password
    login_resp = client.post(
        "/auth/login",
        json={"username": "prof_curie", "password": "RadiumPolonium1898!"},
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert "token" in login_data
    assert login_data["user"]["role"] == "teacher"
    assert login_data["user"]["name"] == "Marie Curie"

    # 5. Login succeeds using email + password
    login_email_resp = client.post(
        "/auth/login",
        json={"username": "curie@synapse.edu", "password": "RadiumPolonium1898!"},
    )
    assert login_email_resp.status_code == 200
    assert login_email_resp.json()["user"]["username"] == "prof_curie"

    # 6. Wrong password rejected (401 Unauthorized)
    wrong_pw_resp = client.post(
        "/auth/login",
        json={"username": "prof_curie", "password": "IncorrectPassword"},
    )
    assert wrong_pw_resp.status_code == 401
    assert "invalid" in wrong_pw_resp.json()["detail"].lower()

    # 7. Unknown username rejected (401 Unauthorized)
    unknown_resp = client.post(
        "/auth/login",
        json={"username": "non_existent_prof", "password": "AnyPassword"},
    )
    assert unknown_resp.status_code == 401

    # 8. Token allows accessing teacher protected route
    token = login_data["token"]
    headers = {"Authorization": f"Bearer {token}"}
    me_resp = client.get("/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["role"] == "teacher"


def test_student_registration_and_login_api(client, auth_store):
    """Verify student registration, duplicate rejection, login, and role enforcement."""
    # 1. Registration succeeds (201 Created)
    reg_resp = client.post(
        "/auth/register",
        json={
            "role": "student",
            "username": "student_feynman",
            "password": "QuantumElectrodynamics1965!",
            "name": "Richard Feynman",
            "email": "feynman@synapse.edu",
        },
    )
    assert reg_resp.status_code == 201
    reg_data = reg_resp.json()
    assert "token" in reg_data
    assert reg_data["user"]["role"] == "student"
    assert reg_data["user"]["name"] == "Richard Feynman"
    assert "password" not in reg_data["user"]
    assert "password_hash" not in reg_data["user"]

    # 2. Duplicate student registration rejected (409 Conflict)
    dup_resp = client.post(
        "/auth/register",
        json={
            "role": "student",
            "username": "student_feynman",
            "password": "NewPassword123!",
            "name": "Another Feynman",
        },
    )
    assert dup_resp.status_code == 409

    # 3. Login succeeds with correct credentials
    login_resp = client.post(
        "/auth/login",
        json={"username": "student_feynman", "password": "QuantumElectrodynamics1965!"},
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert login_data["user"]["role"] == "student"
    assert login_data["user"]["name"] == "Richard Feynman"

    # 4. Wrong password rejected (401 Unauthorized)
    wrong_pw = client.post(
        "/auth/login",
        json={"username": "student_feynman", "password": "BadPassword"},
    )
    assert wrong_pw.status_code == 401

    # 5. Student cannot access teacher routes
    stu_token = login_data["token"]
    stu_headers = {"Authorization": f"Bearer {stu_token}"}
    forbidden = client.post(
        "/teacher/classrooms",
        headers=stu_headers,
        json={"name": "Hacked Class", "subject": "CS"},
    )
    assert forbidden.status_code == 403


def test_login_after_backend_restart_simulation(client, auth_store):
    """Simulate registering via API, destroying Store, reopening, and logging in again."""
    store, db_file = auth_store

    # Register via API
    reg_resp = client.post(
        "/auth/register",
        json={
            "role": "teacher",
            "username": "prof_gauss",
            "password": "DisquisitionesArithmeticae1801!",
            "name": "Carl Friedrich Gauss",
        },
    )
    assert reg_resp.status_code == 201

    # Simulate backend/Store shutdown
    store.close()

    # Simulate backend restart with a new Store instance on the same file
    new_store = Store(db_file)
    set_store(new_store)

    # Login using same credentials after restart
    login_resp = client.post(
        "/auth/login",
        json={"username": "prof_gauss", "password": "DisquisitionesArithmeticae1801!"},
    )
    assert login_resp.status_code == 200
    assert login_resp.json()["user"]["username"] == "prof_gauss"
    assert login_resp.json()["user"]["role"] == "teacher"


def test_registration_validation_and_error_handling(client, auth_store):
    """Verify malformed input, missing fields, invalid role, and endpoint status."""
    # 1. Missing required fields (username, password, name)
    resp = client.post("/auth/register", json={})
    assert resp.status_code == 422
    errs = resp.json()["detail"]
    missing_fields = {e["loc"][-1] for e in errs}
    assert "username" in missing_fields
    assert "password" in missing_fields
    assert "name" in missing_fields

    # 2. Invalid role rejected
    resp = client.post(
        "/auth/register",
        json={"role": "superadmin", "username": "bad_role", "password": "valid_pass_123", "name": "Bad Role"},
    )
    assert resp.status_code == 422

    # 3. Password too short (< 6 characters) rejected
    resp = client.post(
        "/auth/register",
        json={"role": "teacher", "username": "short_pw", "password": "123", "name": "Short Pass"},
    )
    assert resp.status_code == 422

    # 4. Username too short (< 3 characters) rejected
    resp = client.post(
        "/auth/register",
        json={"role": "student", "username": "ab", "password": "valid_pass_123", "name": "Short User"},
    )
    assert resp.status_code == 422

    # 5. Non-existent path returns 404, while /auth/register does NOT return 404
    resp_404 = client.post("/auth/non_existent_endpoint", json={})
    assert resp_404.status_code == 404

    resp_valid = client.post(
        "/auth/register",
        json={"role": "student", "username": "valid_user_99", "password": "valid_password_99", "name": "Valid User"},
    )
    assert resp_valid.status_code == 201


def test_frontend_api_path_parity():
    """Verify frontend client code explicitly targets /auth/register and /auth/login."""
    client_ts_path = Path("frontend/src/api_client/client.ts")
    assert client_ts_path.exists()
    content = client_ts_path.read_text()
    assert "'/auth/register'" in content or '"/auth/register"' in content
    assert "'/auth/login'" in content or '"/auth/login"' in content
    assert "'/auth/me'" in content or '"/auth/me"' in content

    # Also verify vite dev proxy forwards /auth
    vite_cfg = Path("frontend/vite.config.ts").read_text()
    assert "'/auth': 'http://127.0.0.1:8000'" in vite_cfg

