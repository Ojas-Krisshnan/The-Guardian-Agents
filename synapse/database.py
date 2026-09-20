# synapse/database.py
"""Relational database models and queries for Synapse Cycle classroom platform.

Uses the same SQLite database file as slice.store.Store.
Enforces foreign keys and provides domain operations for:
- Users (Teacher, Student)
- Classrooms & Classroom enrollments
- Student Login Credentials (e.g. STU-X7K29P)
- Assessments, Questions & Answer Keys
- Student Assessment Attempts & Answers
- Teacher AI Teaching Insights
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

DOMAIN_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    role          TEXT NOT NULL, -- 'teacher' or 'student'
    username      TEXT UNIQUE,
    email         TEXT,
    password_hash TEXT,
    name          TEXT NOT NULL,
    created_at    REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

CREATE TABLE IF NOT EXISTS classrooms (
    id            TEXT PRIMARY KEY,
    teacher_id    TEXT NOT NULL REFERENCES users(id),
    name          TEXT NOT NULL,
    subject       TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    academic_year TEXT NOT NULL DEFAULT '',
    created_at    REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_classrooms_teacher ON classrooms(teacher_id);

CREATE TABLE IF NOT EXISTS classroom_students (
    classroom_id  TEXT NOT NULL REFERENCES classrooms(id),
    student_id    TEXT NOT NULL REFERENCES users(id),
    joined_at     REAL NOT NULL,
    PRIMARY KEY (classroom_id, student_id)
);

CREATE TABLE IF NOT EXISTS teacher_student_relationships (
    id            TEXT PRIMARY KEY,
    teacher_id    TEXT NOT NULL REFERENCES users(id),
    student_id    TEXT NOT NULL REFERENCES users(id),
    created_at    REAL NOT NULL,
    status        TEXT NOT NULL DEFAULT 'active',
    UNIQUE(teacher_id, student_id)
);
CREATE INDEX IF NOT EXISTS idx_ts_rel_teacher ON teacher_student_relationships(teacher_id);
CREATE INDEX IF NOT EXISTS idx_ts_rel_student ON teacher_student_relationships(student_id);

CREATE TABLE IF NOT EXISTS teacher_connection_codes (
    code          TEXT PRIMARY KEY,
    teacher_id    TEXT NOT NULL REFERENCES users(id),
    created_at    REAL NOT NULL,
    is_active     INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_tcc_teacher ON teacher_connection_codes(teacher_id);

CREATE TABLE IF NOT EXISTS student_credentials (
    student_id    TEXT PRIMARY KEY REFERENCES users(id),
    login_id      TEXT UNIQUE NOT NULL,
    is_active     INTEGER NOT NULL DEFAULT 0,
    created_at    REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_student_login_id ON student_credentials(login_id);

CREATE TABLE IF NOT EXISTS assessments (
    id              TEXT PRIMARY KEY,
    classroom_id    TEXT NOT NULL REFERENCES classrooms(id),
    title           TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    concept_ids_json TEXT NOT NULL DEFAULT '[]',
    status          TEXT NOT NULL DEFAULT 'draft', -- 'draft', 'validated', 'published', 'closed'
    created_by      TEXT NOT NULL REFERENCES users(id),
    created_at      REAL NOT NULL,
    published_at    REAL
);
CREATE INDEX IF NOT EXISTS idx_assessments_classroom ON assessments(classroom_id);

CREATE TABLE IF NOT EXISTS assessment_questions (
    id              TEXT PRIMARY KEY,
    assessment_id   TEXT NOT NULL REFERENCES assessments(id),
    concept_id      TEXT NOT NULL DEFAULT '',
    question_text   TEXT NOT NULL,
    question_type   TEXT NOT NULL DEFAULT 'multiple_choice',
    options_json    TEXT NOT NULL,
    correct_answer  TEXT NOT NULL,
    explanation     TEXT NOT NULL DEFAULT '',
    order_num       INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_questions_assessment ON assessment_questions(assessment_id);

CREATE TABLE IF NOT EXISTS assessment_attempts (
    id              TEXT PRIMARY KEY,
    assessment_id   TEXT NOT NULL REFERENCES assessments(id),
    student_id      TEXT NOT NULL REFERENCES users(id),
    run_id          TEXT,
    submitted_at    REAL NOT NULL,
    score           INTEGER NOT NULL,
    total           INTEGER NOT NULL,
    percentage      REAL NOT NULL,
    diagnosis_json  TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_attempts_student ON assessment_attempts(student_id);
CREATE INDEX IF NOT EXISTS idx_attempts_assessment ON assessment_attempts(assessment_id);

CREATE TABLE IF NOT EXISTS student_answers (
    id              TEXT PRIMARY KEY,
    attempt_id      TEXT NOT NULL REFERENCES assessment_attempts(id),
    question_id     TEXT NOT NULL REFERENCES assessment_questions(id),
    answer          TEXT NOT NULL,
    is_correct      INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_student_answers_attempt ON student_answers(attempt_id);

CREATE TABLE IF NOT EXISTS teacher_insights (
    id              TEXT PRIMARY KEY,
    classroom_id    TEXT NOT NULL REFERENCES classrooms(id),
    assessment_id   TEXT,
    concept_id      TEXT NOT NULL,
    finding         TEXT NOT NULL,
    evidence        TEXT NOT NULL,
    recommendation  TEXT NOT NULL,
    generated_at    REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_insights_classroom ON teacher_insights(classroom_id);
"""


# ---------------------------------------------------------------------------
# Password Hashing & Security (PBKDF2-HMAC-SHA256)
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with 100,000 iterations and a secure salt."""
    salt = secrets.token_bytes(16)
    pw_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return f"pbkdf2:sha256:100000${salt.hex()}${pw_hash.hex()}"


def verify_password(stored_hash: str, password_to_check: str) -> bool:
    """Verify password against stored PBKDF2-HMAC-SHA256 hash using constant-time comparison."""
    if not stored_hash or not password_to_check:
        return False
    try:
        parts = stored_hash.split("$")
        if len(parts) != 3:
            return False
        algo_part, salt_hex, hash_hex = parts
        salt = bytes.fromhex(salt_hex)
        expected_hash = bytes.fromhex(hash_hex)
        actual_hash = hashlib.pbkdf2_hmac("sha256", password_to_check.encode("utf-8"), salt, 100_000)
        return secrets.compare_digest(expected_hash, actual_hash)
    except Exception:
        return False


def init_domain_tables(db: sqlite3.Connection) -> None:
    """Initialize domain tables in the given SQLite connection."""
    db.executescript(DOMAIN_SCHEMA)
    try:
        db.execute("ALTER TABLE assessment_attempts ADD COLUMN diagnosis_json TEXT NOT NULL DEFAULT '{}'")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# User & Credential Queries
# ---------------------------------------------------------------------------

def create_teacher_user(
    db: sqlite3.Connection,
    username: str,
    password: str,
    name: str,
    email: str = "",
    user_id: Optional[str] = None,
) -> dict[str, Any]:
    uid = user_id or f"tea_{secrets.token_hex(6)}"
    pw_hash = hash_password(password)
    now = time.time()
    db.execute(
        "INSERT INTO users (id, role, username, email, password_hash, name, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (uid, "teacher", username.lower().strip(), email.strip(), pw_hash, name.strip(), now),
    )
    return {"id": uid, "role": "teacher", "username": username, "email": email, "name": name, "created_at": now}


def get_user_by_id(db: sqlite3.Connection, user_id: str) -> Optional[dict[str, Any]]:
    row = db.execute("SELECT id, role, username, email, name, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def get_user_by_username(db: sqlite3.Connection, username: str) -> Optional[dict[str, Any]]:
    row = db.execute("SELECT * FROM users WHERE username = ?", (username.lower().strip(),)).fetchone()
    return dict(row) if row else None


def authenticate_teacher(db: sqlite3.Connection, username: str, password: str) -> Optional[dict[str, Any]]:
    user = get_user_by_username(db, username)
    if not user or user["role"] != "teacher":
        return None
    if not verify_password(user["password_hash"], password):
        return None
    return {"id": user["id"], "role": user["role"], "username": user["username"], "name": user["name"]}


def generate_student_accounts(
    db: sqlite3.Connection,
    classroom_id: str,
    count: int,
) -> list[dict[str, Any]]:
    """Generate cryptographically unique student IDs, users, and enrollments."""
    now = time.time()
    generated: list[dict[str, Any]] = []

    charset = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # unconfusable alphanumeric
    for i in range(count):
        for _ in range(50):
            rand_code = "".join(secrets.choice(charset) for _ in range(6))
            login_id = f"STU-{rand_code}"
            # Check collision
            existing = db.execute("SELECT 1 FROM student_credentials WHERE login_id = ?", (login_id,)).fetchone()
            if not existing:
                break
        else:
            login_id = f"STU-{uuid.uuid4().hex[:6].upper()}"

        student_id = f"stu_{secrets.token_hex(6)}"
        display_name = f"Student {login_id.replace('STU-', '')}"

        # Insert user
        db.execute(
            "INSERT INTO users (id, role, username, email, password_hash, name, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (student_id, "student", login_id.lower(), "", "", display_name, now),
        )

        # Insert credential
        db.execute(
            "INSERT INTO student_credentials (student_id, login_id, is_active, created_at) "
            "VALUES (?, ?, 0, ?)",
            (student_id, login_id, now),
        )

        # Enroll in classroom
        db.execute(
            "INSERT INTO classroom_students (classroom_id, student_id, joined_at) "
            "VALUES (?, ?, ?)",
            (classroom_id, student_id, now),
        )

        generated.append({
            "student_id": student_id,
            "login_id": login_id,
            "name": display_name,
            "is_active": False,
            "created_at": now,
        })

    return generated


def authenticate_student(db: sqlite3.Connection, login_id: str) -> Optional[dict[str, Any]]:
    """Authenticate student via generated login_id (e.g. STU-X7K29P). Activates on first login."""
    clean_id = login_id.strip().upper()
    row = db.execute(
        "SELECT sc.student_id, sc.login_id, sc.is_active, u.name, u.role "
        "FROM student_credentials sc "
        "JOIN users u ON u.id = sc.student_id "
        "WHERE sc.login_id = ?",
        (clean_id,),
    ).fetchone()
    if not row:
        return None

    # Mark active if not already
    if not row["is_active"]:
        db.execute("UPDATE student_credentials SET is_active = 1 WHERE student_id = ?", (row["student_id"],))

    return {
        "id": row["student_id"],
        "role": row["role"],
        "login_id": row["login_id"],
        "name": row["name"],
    }


def list_classroom_students(db: sqlite3.Connection, classroom_id: str) -> list[dict[str, Any]]:
    rows = db.execute(
        "SELECT u.id as student_id, u.name, sc.login_id, sc.is_active, cs.joined_at "
        "FROM classroom_students cs "
        "JOIN users u ON u.id = cs.student_id "
        "LEFT JOIN student_credentials sc ON sc.student_id = u.id "
        "WHERE cs.classroom_id = ? "
        "ORDER BY cs.joined_at DESC",
        (classroom_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Classroom Queries
# ---------------------------------------------------------------------------

def create_classroom(
    db: sqlite3.Connection,
    teacher_id: str,
    name: str,
    subject: str,
    description: str = "",
    academic_year: str = "",
) -> dict[str, Any]:
    cid = f"cls_{secrets.token_hex(6)}"
    now = time.time()
    db.execute(
        "INSERT INTO classrooms (id, teacher_id, name, subject, description, academic_year, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (cid, teacher_id, name.strip(), subject.strip(), description.strip(), academic_year.strip(), now),
    )
    return {
        "id": cid,
        "teacher_id": teacher_id,
        "name": name.strip(),
        "subject": subject.strip(),
        "description": description.strip(),
        "academic_year": academic_year.strip(),
        "created_at": now,
        "student_count": 0,
        "assessment_count": 0,
        "average_mastery": 0.0,
    }


def list_teacher_classrooms(db: sqlite3.Connection, teacher_id: str) -> list[dict[str, Any]]:
    rows = db.execute(
        "SELECT c.*, "
        "(SELECT COUNT(*) FROM classroom_students cs WHERE cs.classroom_id = c.id) as student_count, "
        "(SELECT COUNT(*) FROM assessments a WHERE a.classroom_id = c.id) as assessment_count "
        "FROM classrooms c "
        "WHERE c.teacher_id = ? "
        "ORDER BY c.created_at DESC",
        (teacher_id,),
    ).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d["average_mastery"] = calculate_classroom_average_mastery(db, d["id"])
        results.append(d)
    return results


def get_classroom(db: sqlite3.Connection, classroom_id: str) -> Optional[dict[str, Any]]:
    row = db.execute(
        "SELECT c.*, "
        "(SELECT COUNT(*) FROM classroom_students cs WHERE cs.classroom_id = c.id) as student_count, "
        "(SELECT COUNT(*) FROM assessments a WHERE a.classroom_id = c.id) as assessment_count "
        "FROM classrooms c WHERE c.id = ?",
        (classroom_id,),
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["average_mastery"] = calculate_classroom_average_mastery(db, classroom_id)
    return d


def is_student_in_classroom(db: sqlite3.Connection, classroom_id: str, student_id: str) -> bool:
    row = db.execute(
        "SELECT 1 FROM classroom_students WHERE classroom_id = ? AND student_id = ?",
        (classroom_id, student_id),
    ).fetchone()
    return bool(row)


def list_student_classrooms(db: sqlite3.Connection, student_id: str) -> list[dict[str, Any]]:
    rows = db.execute(
        "SELECT c.*, u.name as teacher_name "
        "FROM classrooms c "
        "JOIN classroom_students cs ON cs.classroom_id = c.id "
        "JOIN users u ON u.id = c.teacher_id "
        "WHERE cs.student_id = ? "
        "ORDER BY cs.joined_at DESC",
        (student_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Assessment & Question Queries
# ---------------------------------------------------------------------------

def create_assessment(
    db: sqlite3.Connection,
    classroom_id: str,
    teacher_id: str,
    title: str,
    description: str = "",
    concept_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    aid = f"asm_{secrets.token_hex(6)}"
    now = time.time()
    c_json = json.dumps(concept_ids or [])
    db.execute(
        "INSERT INTO assessments (id, classroom_id, title, description, concept_ids_json, status, created_by, created_at) "
        "VALUES (?, ?, ?, ?, ?, 'draft', ?, ?)",
        (aid, classroom_id, title.strip(), description.strip(), c_json, teacher_id, now),
    )
    return {
        "id": aid,
        "classroom_id": classroom_id,
        "title": title.strip(),
        "description": description.strip(),
        "concept_ids": concept_ids or [],
        "status": "draft",
        "created_by": teacher_id,
        "created_at": now,
        "published_at": None,
        "question_count": 0,
    }


def get_assessment(db: sqlite3.Connection, assessment_id: str) -> Optional[dict[str, Any]]:
    row = db.execute("SELECT * FROM assessments WHERE id = ?", (assessment_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["concept_ids"] = json.loads(d.get("concept_ids_json") or "[]")
    q_count = db.execute("SELECT COUNT(*) FROM assessment_questions WHERE assessment_id = ?", (assessment_id,)).fetchone()[0]
    d["question_count"] = q_count
    return d


def list_classroom_assessments(
    db: sqlite3.Connection,
    classroom_id: str,
    status_filter: Optional[str] = None,
) -> list[dict[str, Any]]:
    query = "SELECT * FROM assessments WHERE classroom_id = ?"
    params: list[Any] = [classroom_id]
    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)
    query += " ORDER BY created_at DESC"

    rows = db.execute(query, params).fetchall()
    res = []
    for r in rows:
        d = dict(r)
        d["concept_ids"] = json.loads(d.get("concept_ids_json") or "[]")
        d["question_count"] = db.execute("SELECT COUNT(*) FROM assessment_questions WHERE assessment_id = ?", (d["id"],)).fetchone()[0]
        res.append(d)
    return res


def save_assessment_questions(
    db: sqlite3.Connection,
    assessment_id: str,
    questions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Save or replace questions for an assessment."""
    db.execute("DELETE FROM assessment_questions WHERE assessment_id = ?", (assessment_id,))
    saved = []
    for i, q in enumerate(questions):
        qid = q.get("id") or f"q_{secrets.token_hex(5)}"
        opts_json = json.dumps(q.get("options", []))
        concept_id = q.get("concept_id", "")
        db.execute(
            "INSERT INTO assessment_questions (id, assessment_id, concept_id, question_text, question_type, options_json, correct_answer, explanation, order_num) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                qid,
                assessment_id,
                concept_id,
                q["question_text"],
                q.get("question_type", "multiple_choice"),
                opts_json,
                q["correct_answer"],
                q.get("explanation", ""),
                i + 1,
            ),
        )
        saved.append({
            "id": qid,
            "assessment_id": assessment_id,
            "concept_id": concept_id,
            "question_text": q["question_text"],
            "question_type": q.get("question_type", "multiple_choice"),
            "options": q.get("options", []),
            "correct_answer": q["correct_answer"],
            "explanation": q.get("explanation", ""),
            "order_num": i + 1,
        })
    # Update status to validated if questions exist
    if saved:
        db.execute("UPDATE assessments SET status = 'validated' WHERE id = ? AND status = 'draft'", (assessment_id,))
    return saved


def get_assessment_questions(
    db: sqlite3.Connection,
    assessment_id: str,
    include_answers: bool = True,
) -> list[dict[str, Any]]:
    rows = db.execute(
        "SELECT * FROM assessment_questions WHERE assessment_id = ? ORDER BY order_num ASC",
        (assessment_id,),
    ).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d["options"] = json.loads(d.get("options_json") or "[]")
        if not include_answers:
            d.pop("correct_answer", None)
            d.pop("explanation", None)
        results.append(d)
    return results


def update_assessment_status(db: sqlite3.Connection, assessment_id: str, status: str) -> None:
    now = time.time() if status == "published" else None
    if status == "published":
        db.execute("UPDATE assessments SET status = ?, published_at = ? WHERE id = ?", (status, now, assessment_id))
    else:
        db.execute("UPDATE assessments SET status = ? WHERE id = ?", (status, assessment_id))


def map_question_concepts(db: sqlite3.Connection, assessment_id: str, mappings: dict[str, str]) -> None:
    """Update concept_id on each question (question_id -> concept_id)."""
    for qid, cid in mappings.items():
        db.execute(
            "UPDATE assessment_questions SET concept_id = ? WHERE id = ? AND assessment_id = ?",
            (cid, qid, assessment_id),
        )
    # Collect all unique concept_ids and update assessment.concept_ids_json
    cids = [r[0] for r in db.execute("SELECT DISTINCT concept_id FROM assessment_questions WHERE assessment_id = ? AND concept_id != ''", (assessment_id,)).fetchall()]
    db.execute("UPDATE assessments SET concept_ids_json = ? WHERE id = ?", (json.dumps(cids), assessment_id))


# ---------------------------------------------------------------------------
# Attempt & Student Answer Queries
# ---------------------------------------------------------------------------

def save_assessment_attempt(
    db: sqlite3.Connection,
    assessment_id: str,
    student_id: str,
    run_id: str,
    answers: dict[str, str],  # question_id -> student chosen answer
) -> dict[str, Any]:
    """Scores student answers server-side, saves attempt, and records student_answers."""
    questions = get_assessment_questions(db, assessment_id, include_answers=True)
    if not questions:
        raise ValueError(f"No questions found for assessment {assessment_id}")

    score = 0
    total = len(questions)
    detailed_answers = []

    attempt_id = f"att_{secrets.token_hex(6)}"
    now = time.time()

    for q in questions:
        qid = q["id"]
        chosen = answers.get(qid, "")
        correct = q["correct_answer"]
        is_correct = 1 if chosen == correct else 0
        if is_correct:
            score += 1

        ans_id = f"sa_{secrets.token_hex(5)}"
        detailed_answers.append((ans_id, attempt_id, qid, chosen, is_correct))

    percentage = round((score / total) * 100.0, 1) if total > 0 else 0.0

    # Insert attempt
    db.execute(
        "INSERT INTO assessment_attempts (id, assessment_id, student_id, run_id, submitted_at, score, total, percentage) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (attempt_id, assessment_id, student_id, run_id, now, score, total, percentage),
    )

    # Insert answers
    db.executemany(
        "INSERT INTO student_answers (id, attempt_id, question_id, answer, is_correct) "
        "VALUES (?, ?, ?, ?, ?)",
        detailed_answers,
    )

    return {
        "id": attempt_id,
        "assessment_id": assessment_id,
        "student_id": student_id,
        "run_id": run_id,
        "submitted_at": now,
        "score": score,
        "total": total,
        "percentage": percentage,
    }


def get_assessment_attempt(db: sqlite3.Connection, attempt_id: str) -> Optional[dict[str, Any]]:
    row = db.execute("SELECT * FROM assessment_attempts WHERE id = ?", (attempt_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    # Fetch answers with question details
    ans_rows = db.execute(
        "SELECT sa.question_id, sa.answer, sa.is_correct, aq.question_text, aq.options_json, aq.correct_answer, aq.concept_id "
        "FROM student_answers sa "
        "JOIN assessment_questions aq ON aq.id = sa.question_id "
        "WHERE sa.attempt_id = ?",
        (attempt_id,),
    ).fetchall()
    answers = []
    for a in ans_rows:
        ad = dict(a)
        ad["options"] = json.loads(ad.get("options_json") or "[]")
        answers.append(ad)
    d["answers"] = answers
    return d


def save_attempt_diagnosis(db: sqlite3.Connection, attempt_id: str, diagnosis_data: dict[str, Any]) -> None:
    """Persist the authoritative AI diagnosis directly on the attempt record."""
    diag_json = json.dumps(diagnosis_data) if diagnosis_data else "{}"
    try:
        db.execute("UPDATE assessment_attempts SET diagnosis_json = ? WHERE id = ?", (diag_json, attempt_id))
    except sqlite3.OperationalError:
        db.execute("ALTER TABLE assessment_attempts ADD COLUMN diagnosis_json TEXT NOT NULL DEFAULT '{}'")
        db.execute("UPDATE assessment_attempts SET diagnosis_json = ? WHERE id = ?", (diag_json, attempt_id))


def get_attempt_diagnosis(db: sqlite3.Connection, attempt_id: str) -> Optional[dict[str, Any]]:
    """Retrieve the authoritative AI diagnosis for an attempt."""
    try:
        row = db.execute("SELECT diagnosis_json FROM assessment_attempts WHERE id = ?", (attempt_id,)).fetchone()
        if row and row["diagnosis_json"] and row["diagnosis_json"] != "{}":
            return json.loads(row["diagnosis_json"])
    except Exception:
        pass
    return None


def list_student_attempts(db: sqlite3.Connection, student_id: str) -> list[dict[str, Any]]:
    rows = db.execute(
        "SELECT aa.*, a.title as assessment_title, c.name as classroom_name "
        "FROM assessment_attempts aa "
        "JOIN assessments a ON a.id = aa.assessment_id "
        "JOIN classrooms c ON c.id = a.classroom_id "
        "WHERE aa.student_id = ? "
        "ORDER BY aa.submitted_at DESC",
        (student_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Classroom & Student Analytics Calculations
# ---------------------------------------------------------------------------

def calculate_classroom_average_mastery(db: sqlite3.Connection, classroom_id: str) -> float:
    row = db.execute(
        "SELECT AVG(aa.percentage) "
        "FROM assessment_attempts aa "
        "JOIN assessments a ON a.id = aa.assessment_id "
        "WHERE a.classroom_id = ?",
        (classroom_id,),
    ).fetchone()
    if row and row[0] is not None:
        return round(float(row[0]), 1)
    return 0.0


def get_classroom_analytics(db: sqlite3.Connection, classroom_id: str) -> dict[str, Any]:
    """Calculate aggregated classroom-level analytics without leaking private student notes."""
    total_students = db.execute(
        "SELECT COUNT(*) FROM classroom_students WHERE classroom_id = ?", (classroom_id,)
    ).fetchone()[0]

    attempts = db.execute(
        "SELECT aa.percentage, aa.student_id, aa.assessment_id "
        "FROM assessment_attempts aa "
        "JOIN assessments a ON a.id = aa.assessment_id "
        "WHERE a.classroom_id = ?",
        (classroom_id,),
    ).fetchall()

    if not attempts:
        return {
            "classroom_id": classroom_id,
            "total_students": total_students,
            "total_attempts": 0,
            "average_mastery": 0.0,
            "distribution": {"90-100": 0, "80-89": 0, "70-79": 0, "60-69": 0, "below_60": 0},
            "concept_performance": [],
            "mistake_distribution": {},
        }

    percentages = [float(r["percentage"]) for r in attempts]
    avg_mastery = round(sum(percentages) / len(percentages), 1)

    # Score distribution brackets
    dist = {"90-100": 0, "80-89": 0, "70-79": 0, "60-69": 0, "below_60": 0}
    for p in percentages:
        if p >= 90:
            dist["90-100"] += 1
        elif p >= 80:
            dist["80-89"] += 1
        elif p >= 70:
            dist["70-79"] += 1
        elif p >= 60:
            dist["60-69"] += 1
        else:
            dist["below_60"] += 1

    # Concept-level accuracy
    concept_stats = db.execute(
        "SELECT aq.concept_id, "
        "COUNT(sa.id) as total_answers, "
        "SUM(sa.is_correct) as correct_answers "
        "FROM student_answers sa "
        "JOIN assessment_questions aq ON aq.id = sa.question_id "
        "JOIN assessment_attempts aa ON aa.id = sa.attempt_id "
        "JOIN assessments a ON a.id = aa.assessment_id "
        "WHERE a.classroom_id = ? AND aq.concept_id != '' "
        "GROUP BY aq.concept_id",
        (classroom_id,),
    ).fetchall()

    concept_perf = []
    for cs in concept_stats:
        tot = cs["total_answers"]
        cor = cs["correct_answers"] or 0
        pct = round((cor / tot) * 100.0, 1) if tot > 0 else 0.0
        concept_perf.append({
            "concept_id": cs["concept_id"],
            "total_questions": tot,
            "correct_answers": cor,
            "mastery_percentage": pct,
        })
    concept_perf.sort(key=lambda x: x["mastery_percentage"])

    return {
        "classroom_id": classroom_id,
        "total_students": total_students,
        "total_attempts": len(attempts),
        "average_mastery": avg_mastery,
        "distribution": dist,
        "concept_performance": concept_perf,
    }


def get_student_analytics_summary(db: sqlite3.Connection, student_id: str) -> dict[str, Any]:
    """Aggregates overall performance and history across attempts for a student."""
    attempts = db.execute(
        "SELECT aa.*, a.title as assessment_title "
        "FROM assessment_attempts aa "
        "JOIN assessments a ON a.id = aa.assessment_id "
        "WHERE aa.student_id = ? "
        "ORDER BY aa.submitted_at ASC",
        (student_id,),
    ).fetchall()

    if not attempts:
        return {
            "student_id": student_id,
            "total_attempts": 0,
            "overall_mastery": 0.0,
            "history": [],
            "concept_mastery": {},
        }

    percentages = [float(r["percentage"]) for r in attempts]
    overall = round(sum(percentages) / len(percentages), 1)

    history = [
        {
            "assessment_id": r["assessment_id"],
            "title": r["assessment_title"],
            "score": r["score"],
            "total": r["total"],
            "percentage": float(r["percentage"]),
            "submitted_at": r["submitted_at"],
        }
        for r in attempts
    ]

    # Concept breakdown
    c_rows = db.execute(
        "SELECT aq.concept_id, COUNT(sa.id) as total, SUM(sa.is_correct) as correct "
        "FROM student_answers sa "
        "JOIN assessment_questions aq ON aq.id = sa.question_id "
        "JOIN assessment_attempts aa ON aa.id = sa.attempt_id "
        "WHERE aa.student_id = ? AND aq.concept_id != '' "
        "GROUP BY aq.concept_id",
        (student_id,),
    ).fetchall()

    concept_mastery = {}
    for cr in c_rows:
        tot = cr["total"]
        cor = cr["correct"] or 0
        pct = round((cor / tot) * 100.0, 1) if tot > 0 else 0.0
        concept_mastery[cr["concept_id"]] = pct

    return {
        "student_id": student_id,
        "total_attempts": len(attempts),
        "overall_mastery": overall,
        "history": history,
        "concept_mastery": concept_mastery,
    }


# ---------------------------------------------------------------------------
# Teacher Insight Queries
# ---------------------------------------------------------------------------

def save_teacher_insight(
    db: sqlite3.Connection,
    classroom_id: str,
    concept_id: str,
    finding: str,
    evidence: str,
    recommendation: str,
    assessment_id: Optional[str] = None,
) -> dict[str, Any]:
    iid = f"ins_{secrets.token_hex(6)}"
    now = time.time()
    db.execute(
        "INSERT INTO teacher_insights (id, classroom_id, assessment_id, concept_id, finding, evidence, recommendation, generated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (iid, classroom_id, assessment_id, concept_id, finding, evidence, recommendation, now),
    )
    return {
        "id": iid,
        "classroom_id": classroom_id,
        "assessment_id": assessment_id,
        "concept_id": concept_id,
        "finding": finding,
        "evidence": evidence,
        "recommendation": recommendation,
        "generated_at": now,
    }


def list_classroom_insights(db: sqlite3.Connection, classroom_id: str) -> list[dict[str, Any]]:
    rows = db.execute(
        "SELECT * FROM teacher_insights WHERE classroom_id = ? ORDER BY generated_at DESC LIMIT 20",
        (classroom_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Student ↔ Teacher Connection & Performance Analytics
# ---------------------------------------------------------------------------

def get_or_create_teacher_code(db: sqlite3.Connection, teacher_id: str) -> str:
    """Retrieve existing active connection code for teacher, or generate an unconfusable 6-char code."""
    row = db.execute(
        "SELECT code FROM teacher_connection_codes WHERE teacher_id = ? AND is_active = 1",
        (teacher_id,),
    ).fetchone()
    if row:
        return row["code"]

    charset = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    code = "SYN-" + "".join(secrets.choice(charset) for _ in range(6))
    now = time.time()
    db.execute(
        "INSERT OR REPLACE INTO teacher_connection_codes (code, teacher_id, created_at, is_active) VALUES (?, ?, ?, 1)",
        (code, teacher_id, now),
    )
    return code


def connect_student_to_teacher(db: sqlite3.Connection, student_id: str, code: str) -> dict[str, Any]:
    """Connect student to teacher via connection code. Enrolls student into teacher's active classroom."""
    clean_code = code.strip().upper()
    row = db.execute(
        "SELECT teacher_id FROM teacher_connection_codes WHERE code = ? AND is_active = 1",
        (clean_code,),
    ).fetchone()
    if not row:
        raise ValueError("Invalid or inactive connection code.")

    teacher_id = row["teacher_id"]
    teacher = get_user_by_id(db, teacher_id)
    if not teacher or teacher["role"] != "teacher":
        raise ValueError("Teacher account not found.")

    rel_id = f"ts_{secrets.token_hex(6)}"
    now = time.time()
    db.execute(
        "INSERT OR IGNORE INTO teacher_student_relationships (id, teacher_id, student_id, created_at, status) "
        "VALUES (?, ?, ?, ?, 'active')",
        (rel_id, teacher_id, student_id, now),
    )

    # Automatically enroll in teacher's most recently created classroom if available
    class_row = db.execute(
        "SELECT id FROM classrooms WHERE teacher_id = ? ORDER BY created_at DESC LIMIT 1",
        (teacher_id,),
    ).fetchone()
    if class_row:
        db.execute(
            "INSERT OR IGNORE INTO classroom_students (classroom_id, student_id, joined_at) VALUES (?, ?, ?)",
            (class_row["id"], student_id, now),
        )

    return {
        "success": True,
        "message": f"Connected to {teacher['name']}",
        "teacher": {
            "id": teacher["id"],
            "name": teacher["name"],
            "email": teacher.get("email", ""),
            "username": teacher.get("username", ""),
        },
    }


def is_student_connected_to_teacher(db: sqlite3.Connection, teacher_id: str, student_id: str) -> bool:
    """Authoritatively check whether student belongs/is connected to teacher."""
    rel = db.execute(
        "SELECT 1 FROM teacher_student_relationships WHERE teacher_id = ? AND student_id = ? AND status = 'active'",
        (teacher_id, student_id),
    ).fetchone()
    if rel:
        return True

    cls_rel = db.execute(
        "SELECT 1 FROM classroom_students cs "
        "JOIN classrooms c ON c.id = cs.classroom_id "
        "WHERE c.teacher_id = ? AND cs.student_id = ?",
        (teacher_id, student_id),
    ).fetchone()
    return bool(cls_rel)


def list_teacher_connected_students(db: sqlite3.Connection, teacher_id: str) -> list[dict[str, Any]]:
    """List all students connected to this teacher, with live real analytics summary."""
    from synapse.analytics.trends import calculate_trend

    rows = db.execute(
        "SELECT student_id, MIN(joined_at) as joined_at FROM ("
        "  SELECT student_id, created_at as joined_at FROM teacher_student_relationships WHERE teacher_id = ? AND status = 'active' "
        "  UNION "
        "  SELECT cs.student_id, cs.joined_at FROM classroom_students cs JOIN classrooms c ON c.id = cs.classroom_id WHERE c.teacher_id = ? "
        ") GROUP BY student_id ORDER BY joined_at DESC",
        (teacher_id, teacher_id),
    ).fetchall()

    students = []
    for r in rows:
        stu_id = r["student_id"]
        u = db.execute("SELECT id, name, username, email FROM users WHERE id = ?", (stu_id,)).fetchone()
        if not u:
            continue

        sc = db.execute("SELECT login_id FROM student_credentials WHERE student_id = ?", (stu_id,)).fetchone()
        login_id = sc["login_id"] if sc else None

        # Fetch attempt metrics
        attempts = db.execute(
            "SELECT percentage, submitted_at FROM assessment_attempts WHERE student_id = ? ORDER BY submitted_at ASC",
            (stu_id,),
        ).fetchall()

        total_attempts = len(attempts)
        if total_attempts > 0:
            pcts = [float(a["percentage"]) for a in attempts]
            overall_mastery = round(sum(pcts) / total_attempts, 1)
            recent_score = round(pcts[-1], 1)
            history_pairs = [(idx + 1, p / 100.0) for idx, p in enumerate(pcts)]
            trend_label = calculate_trend(pcts[-1] / 100.0, history_pairs[:-1]).value
        else:
            overall_mastery = None
            recent_score = None
            trend_label = "no_data"

        students.append({
            "student_id": stu_id,
            "name": u["name"],
            "username": u["username"] or "",
            "email": u["email"] or "",
            "login_id": login_id,
            "joined_at": float(r["joined_at"]),
            "total_attempts": total_attempts,
            "overall_mastery": overall_mastery,
            "recent_score": recent_score,
            "trend": trend_label,
        })

    return students


def get_connected_student_performance(db: sqlite3.Connection, teacher_id: str, student_id: str) -> Optional[dict[str, Any]]:
    """Authoritatively retrieve a connected student's learning performance.
    
    Returns None if the student does not belong/is not connected to this teacher.
    Strictly excludes private student learning notes to preserve isolation contracts.
    """
    from synapse.analytics.trends import calculate_trend

    if not is_student_connected_to_teacher(db, teacher_id, student_id):
        return None

    u = db.execute("SELECT id, name, username, email, created_at FROM users WHERE id = ?", (student_id,)).fetchone()
    if not u:
        return None

    sc = db.execute("SELECT login_id FROM student_credentials WHERE student_id = ?", (student_id,)).fetchone()
    login_id = sc["login_id"] if sc else None

    # Retrieve all attempts
    attempts = db.execute(
        "SELECT aa.id, aa.assessment_id, aa.run_id, aa.submitted_at, aa.score, aa.total, aa.percentage, a.title as assessment_title "
        "FROM assessment_attempts aa "
        "JOIN assessments a ON a.id = aa.assessment_id "
        "WHERE aa.student_id = ? "
        "ORDER BY aa.submitted_at DESC",
        (student_id,),
    ).fetchall()

    total_attempts = len(attempts)
    if total_attempts > 0:
        pcts_asc = [float(a["percentage"]) for a in reversed(attempts)]
        overall_mastery = round(sum(pcts_asc) / total_attempts, 1)
        average_score = round(sum(a["score"] for a in attempts) / sum(a["total"] for a in attempts) * 100.0, 1) if sum(a["total"] for a in attempts) > 0 else 0.0
        recent_score = round(float(attempts[0]["percentage"]), 1)
        history_pairs = [(idx + 1, p / 100.0) for idx, p in enumerate(pcts_asc)]
        trend_label = calculate_trend(pcts_asc[-1] / 100.0, history_pairs[:-1]).value
    else:
        overall_mastery = None
        average_score = None
        recent_score = None
        trend_label = "no_data"

    recent_attempts = [
        {
            "id": a["id"],
            "assessment_id": a["assessment_id"],
            "title": a["assessment_title"],
            "score": a["score"],
            "total": a["total"],
            "percentage": float(a["percentage"]),
            "submitted_at": float(a["submitted_at"]),
        }
        for a in attempts[:15]
    ]

    # Authoritative AI Diagnosis extraction from the latest attempt
    latest_diagnosis = None
    for a in attempts:
        # 1. Check if diagnosis_json column exists on this attempt
        try:
            row_diag = db.execute("SELECT diagnosis_json FROM assessment_attempts WHERE id = ?", (a["id"],)).fetchone()
            if row_diag and row_diag["diagnosis_json"] and row_diag["diagnosis_json"] != "{}":
                parsed = json.loads(row_diag["diagnosis_json"])
                latest_diagnosis = {
                    "id": parsed.get("id", a["id"]),
                    "student_id": parsed.get("student_id", student_id),
                    "concept_id": parsed.get("concept_id", "Recursion"),
                    "items": [
                        {
                            "question_id": it.get("question_id", ""),
                            "classification": str(it.get("classification", "conceptual_gap")),
                            "reason": str(it.get("reason", "")),
                        }
                        for it in parsed.get("items", [])
                    ],
                    "mastery_estimate": float(parsed.get("mastery_estimate", 0.0)),
                    "trend": str(parsed.get("trend", "new")),
                    "created_at": float(parsed.get("created_at") if isinstance(parsed.get("created_at"), (int, float)) else a["submitted_at"]),
                }
                break
        except Exception:
            pass

        # 2. Check if diagnosis was saved in versions table via run_id
        if a["run_id"]:
            try:
                v_row = db.execute(
                    "SELECT payload_json FROM versions WHERE run_id = ? AND kind = 'diagnosis' ORDER BY seq DESC LIMIT 1",
                    (a["run_id"],),
                ).fetchone()
                if v_row:
                    parsed = json.loads(v_row["payload_json"])
                    latest_diagnosis = {
                        "id": parsed.get("id", a["id"]),
                        "student_id": parsed.get("student_id", student_id),
                        "concept_id": parsed.get("concept_id", "Recursion"),
                        "items": [
                            {
                                "question_id": it.get("question_id", ""),
                                "classification": str(it.get("classification", "conceptual_gap")),
                                "reason": str(it.get("reason", "")),
                            }
                            for it in parsed.get("items", [])
                        ],
                        "mastery_estimate": float(parsed.get("mastery_estimate", 0.0)),
                        "trend": str(parsed.get("trend", "new")),
                        "created_at": float(a["submitted_at"]),
                    }
                    break
            except Exception:
                pass

    # Concept breakdown from student answers
    c_rows = db.execute(
        "SELECT aq.concept_id, COUNT(sa.id) as total, SUM(sa.is_correct) as correct "
        "FROM student_answers sa "
        "JOIN assessment_questions aq ON aq.id = sa.question_id "
        "JOIN assessment_attempts aa ON aa.id = sa.attempt_id "
        "WHERE aa.student_id = ? AND aq.concept_id != '' "
        "GROUP BY aq.concept_id",
        (student_id,),
    ).fetchall()

    concept_mastery = {}
    concepts_studied = []
    concepts_needing_attention = []
    for cr in c_rows:
        cid = cr["concept_id"]
        tot = cr["total"]
        cor = cr["correct"] or 0
        pct = round((cor / tot) * 100.0, 1) if tot > 0 else 0.0
        concept_mastery[cid] = pct
        concepts_studied.append(cid)
        if pct < 70.0:
            concepts_needing_attention.append(cid)

    # Diagnostic answer breakdown
    ans_stats = db.execute(
        "SELECT COUNT(sa.id) as total_answers, SUM(sa.is_correct) as correct_answers "
        "FROM student_answers sa "
        "JOIN assessment_attempts aa ON aa.id = sa.attempt_id "
        "WHERE aa.student_id = ?",
        (student_id,),
    ).fetchone()

    total_ans = ans_stats["total_answers"] or 0
    correct_ans = ans_stats["correct_answers"] or 0
    incorrect_ans = total_ans - correct_ans

    return {
        "student_id": student_id,
        "name": u["name"],
        "username": u["username"] or "",
        "email": u["email"] or "",
        "login_id": login_id,
        "joined_at": float(u["created_at"]),
        "total_attempts": total_attempts,
        "overall_mastery": overall_mastery,
        "average_score": average_score,
        "recent_score": recent_score,
        "trend": trend_label,
        "recent_attempts": recent_attempts,
        "concept_mastery": concept_mastery,
        "concepts_studied": concepts_studied,
        "concepts_needing_attention": concepts_needing_attention,
        "diagnostics_summary": {
            "total_questions_answered": total_ans,
            "correct_answers": correct_ans,
            "incorrect_answers": incorrect_ans,
            "accuracy_percentage": round((correct_ans / total_ans) * 100.0, 1) if total_ans > 0 else 0.0,
        },
        "latest_diagnosis": latest_diagnosis,
    }


def get_student_connected_teachers(db: sqlite3.Connection, student_id: str) -> list[dict[str, Any]]:
    """Retrieve all teachers connected to the authenticated student."""
    rows = db.execute(
        "SELECT DISTINCT u.id, u.name, u.email, u.username FROM users u "
        "JOIN teacher_student_relationships rel ON rel.teacher_id = u.id "
        "WHERE rel.student_id = ? AND rel.status = 'active' "
        "UNION "
        "SELECT DISTINCT u.id, u.name, u.email, u.username FROM users u "
        "JOIN classrooms c ON c.teacher_id = u.id "
        "JOIN classroom_students cs ON cs.classroom_id = c.id "
        "WHERE cs.student_id = ?",
        (student_id, student_id),
    ).fetchall()
    return [dict(r) for r in rows]

