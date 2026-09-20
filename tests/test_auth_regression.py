# tests/test_auth_regression.py
"""
Automated regression tests verifying backward compatibility for pre-existing accounts,
legacy 2-part password hashes, email & username lookup, role loading, and 401 responses.
"""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from api.dependencies import set_store
from api.main import app
from slice.store import Store
from synapse.database import verify_password, hash_password


def make_legacy_2part_hash(password: str, salt_hex: str = "4a96e57dfc7bb61c77d5a5704d2d667c") -> str:
    """Recreate legacy 2-part hash format: <salt_hex>$<hash_hex>."""
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_hex.encode("utf-8"), 100_000).hex()
    return f"{salt_hex}${h}"


@pytest.fixture
def auth_store(tmp_path: Path):
    """Provide an isolated temporary filesystem SQLite database."""
    db_file = tmp_path / "auth_regression_test.db"
    store = Store(db_file)
    set_store(store)
    yield store, db_file
    store.close()


@pytest.fixture
def client(auth_store):
    return TestClient(app)


def test_legacy_2part_hash_verification():
    """Verify legacy 2-part hash is correctly verified and matches password."""
    legacy_hash = make_legacy_2part_hash("Secret123!")
    assert verify_password(legacy_hash, "Secret123!") is True
    assert verify_password(legacy_hash, "WrongPassword") is False


def test_modern_3part_hash_verification():
    """Verify modern 3-part hash is correctly verified and matches password."""
    modern_hash = hash_password("Secret123!")
    assert modern_hash.startswith("pbkdf2:sha256:100000$")
    assert verify_password(modern_hash, "Secret123!") is True
    assert verify_password(modern_hash, "WrongPassword") is False


def test_legacy_existing_teacher_can_login(auth_store, client):
    """Pre-insert teacher with legacy 2-part hash into SQLite and verify login."""
    store, db_file = auth_store
    legacy_hash = make_legacy_2part_hash("TeacherPass123!")
    
    # Directly insert into users table simulating pre-existing record
    conn = sqlite3.connect(str(db_file))
    conn.execute(
        "INSERT INTO users (id, role, username, email, password_hash, name, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
        ("tea_legacy_1", "teacher", "prof_legacy", "prof.legacy@synapse.edu", legacy_hash, "Professor Legacy"),
    )
    conn.commit()
    conn.close()

    # Login with username
    resp = client.post("/auth/login", json={"username": "prof_legacy", "password": "TeacherPass123!"})
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert "token" in body
    assert body["user"]["role"] == "teacher"
    assert body["user"]["username"] == "prof_legacy"
    assert body["user"]["name"] == "Professor Legacy"


def test_legacy_existing_student_can_login(auth_store, client):
    """Pre-insert student with legacy 2-part hash into SQLite and verify login."""
    store, db_file = auth_store
    legacy_hash = make_legacy_2part_hash("StudentPass123!")
    
    conn = sqlite3.connect(str(db_file))
    conn.execute(
        "INSERT INTO users (id, role, username, email, password_hash, name, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
        ("stu_legacy_1", "student", "student_legacy", "student.legacy@synapse.edu", legacy_hash, "Student Legacy"),
    )
    conn.commit()
    conn.close()

    # Login with username
    resp = client.post("/auth/login", json={"username": "student_legacy", "password": "StudentPass123!"})
    assert resp.status_code == 200
    body = resp.json()
    assert "token" in body
    assert body["user"]["role"] == "student"
    assert body["user"]["username"] == "student_legacy"


def test_email_login_works_for_existing_user(auth_store, client):
    """Verify existing account can log in using email address instead of username."""
    store, db_file = auth_store
    legacy_hash = make_legacy_2part_hash("Password123!")

    conn = sqlite3.connect(str(db_file))
    conn.execute(
        "INSERT INTO users (id, role, username, email, password_hash, name, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
        ("tea_email_1", "teacher", "prof_email_user", "Prof.Email@Synapse.edu", legacy_hash, "Prof Email"),
    )
    conn.commit()
    conn.close()

    # Login with email (testing case insensitivity as well)
    resp = client.post("/auth/login", json={"username": "prof.email@synapse.edu", "password": "Password123!"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["username"] == "prof_email_user"


def test_wrong_password_returns_401(auth_store, client):
    """Verify wrong password returns 401 and 'Invalid username or password' (never 404)."""
    store, db_file = auth_store
    legacy_hash = make_legacy_2part_hash("CorrectPassword!")

    conn = sqlite3.connect(str(db_file))
    conn.execute(
        "INSERT INTO users (id, role, username, email, password_hash, name, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
        ("stu_wp_1", "student", "user_wp", "user_wp@synapse.edu", legacy_hash, "WP User"),
    )
    conn.commit()
    conn.close()

    resp = client.post("/auth/login", json={"username": "user_wp", "password": "WrongPassword!"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid username or password"


def test_nonexistent_user_returns_401(auth_store, client):
    """Verify unknown user returns 401 and 'Invalid username or password' (never 404)."""
    resp = client.post("/auth/login", json={"username": "does_not_exist_user", "password": "any_password"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid username or password"


def test_protected_route_with_jwt_token(auth_store, client):
    """Verify token from successful login authorizes protected endpoints."""
    store, db_file = auth_store
    store.create_user(role="teacher", username="prof_jwt", password="ProfPass123!", name="Prof JWT")

    resp = client.post("/auth/login", json={"username": "prof_jwt", "password": "ProfPass123!"})
    assert resp.status_code == 200
    token = resp.json()["token"]

    # Call /auth/me
    me_resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == "prof_jwt"
    assert me_resp.json()["role"] == "teacher"


def test_persistence_across_backend_restart(tmp_path: Path):
    """Verify accounts survive backend / Store recreation."""
    db_file = tmp_path / "restart_test.db"

    # Instance 1: Create user with legacy hash
    s1 = Store(db_file)
    legacy_hash = make_legacy_2part_hash("RestartPass123!")
    conn = sqlite3.connect(str(db_file))
    conn.execute(
        "INSERT INTO users (id, role, username, email, password_hash, name, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
        ("tea_restart", "teacher", "prof_restart", "restart@synapse.edu", legacy_hash, "Prof Restart"),
    )
    conn.commit()
    conn.close()
    s1.close()

    # Instance 2: Reopen store in new instance
    s2 = Store(db_file)
    set_store(s2)
    client2 = TestClient(app)

    resp = client2.post("/auth/login", json={"username": "prof_restart", "password": "RestartPass123!"})
    assert resp.status_code == 200
    assert resp.json()["user"]["username"] == "prof_restart"
    s2.close()


def test_registration_still_works_and_logs_in_immediately(auth_store, client):
    """Verify new registrations succeed and can log in immediately."""
    reg_resp = client.post(
        "/auth/register",
        json={
            "role": "student",
            "username": "newly_registered_student",
            "password": "NewStudentPass123!",
            "name": "New Student",
            "email": "new.student@synapse.edu",
        },
    )
    assert reg_resp.status_code in (200, 201)
    reg_body = reg_resp.json()
    assert "token" in reg_body
    assert reg_body["user"]["username"] == "newly_registered_student"

    # Login with new credentials
    login_resp = client.post(
        "/auth/login",
        json={"username": "newly_registered_student", "password": "NewStudentPass123!"},
    )
    assert login_resp.status_code == 200
    assert login_resp.json()["user"]["username"] == "newly_registered_student"
