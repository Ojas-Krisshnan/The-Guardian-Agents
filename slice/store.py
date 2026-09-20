"""
The system of record.

The single most important idea in this kit: **the context window is a cache,
the database is the truth.** Every agent turn reads state from here, calls a
model, and writes a new version back. The conversation is derived and
disposable.

The table is append-only. There is no update, no delete - and that is enforced
by SQLite triggers rather than by convention, so a well-meaning refactor at
hour 30 cannot quietly break it. Append-only buys you four things for free:

  * replay      - re-read the run exactly as it happened
  * diffs       - thesis v1 -> v2 -> v3 is just three rows
  * resume      - the process can die; the run cannot
  * audit       - "why did it decide that" has an answer

Stdlib only. sqlite3 and json.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from .records import Question, RunState, Version, new_id

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id          TEXT PRIMARY KEY,
    domain      TEXT NOT NULL,
    state       TEXT NOT NULL,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL,
    meta_json   TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS versions (
    run_id       TEXT NOT NULL REFERENCES runs(id),
    seq          INTEGER NOT NULL,
    kind         TEXT NOT NULL,
    produced_by  TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at   REAL NOT NULL,
    PRIMARY KEY (run_id, seq)
);
CREATE INDEX IF NOT EXISTS versions_by_kind ON versions(run_id, kind, seq);

-- Counters survive a resume. Attempt counts and token spend live here, not in
-- a Python variable that dies with the process.
CREATE TABLE IF NOT EXISTS counters (
    run_id TEXT NOT NULL REFERENCES runs(id),
    name   TEXT NOT NULL,
    value  REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (run_id, name)
);

CREATE TABLE IF NOT EXISTS questions (
    id           TEXT PRIMARY KEY,
    run_id       TEXT NOT NULL REFERENCES runs(id),
    question     TEXT NOT NULL,
    context_json TEXT NOT NULL DEFAULT '{}',
    asked_at     REAL NOT NULL,
    timeout_at   REAL NOT NULL,
    answered_at  REAL,
    answer       TEXT
);
CREATE INDEX IF NOT EXISTS questions_open ON questions(run_id, answered_at);

-- The append-only invariant, enforced by the database itself.
CREATE TRIGGER IF NOT EXISTS versions_no_update
BEFORE UPDATE ON versions
BEGIN SELECT RAISE(ABORT, 'versions is append-only: write a new version'); END;

CREATE TRIGGER IF NOT EXISTS versions_no_delete
BEFORE DELETE ON versions
BEGIN SELECT RAISE(ABORT, 'versions is append-only: history is not editable'); END;
"""


class Store:
    """Durable run state. One file. Commit it, ship it, replay it."""

    def __init__(self, path: str | Path = "run.db") -> None:
        self.path = str(path)
        self.db = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript(SCHEMA)
        self._init_domain_tables()

    # ---------------------------------------------------------------- runs

    def create_run(self, domain: str, meta: dict[str, Any] | None = None) -> str:
        run_id, now = new_id("run"), time.time()
        self.db.execute(
            "INSERT INTO runs(id, domain, state, created_at, updated_at, meta_json)"
            " VALUES (?,?,?,?,?,?)",
            (run_id, domain, RunState.DRAFTING.value, now, now, json.dumps(meta or {})),
        )
        return run_id

    def get_state(self, run_id: str) -> Any:
        row = self.db.execute("SELECT state FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(f"no such run: {run_id}")
        val = row["state"]
        try:
            return RunState(val)
        except ValueError:
            try:
                from synapse.state_machine import RunState as SynapseRunState
                base_state = SynapseRunState(val)
                has_open_q = bool(self.open_questions(run_id))
                has_attempt = bool(self.latest(run_id, "attempt"))

                class StateProxy:
                    def __init__(self, s):
                        self._s = s
                    @property
                    def value(self):
                        return self._s.value
                    @property
                    def is_terminal(self):
                        return self._s is SynapseRunState.COMPLETE
                    @property
                    def is_suspended(self):
                        if self._s is SynapseRunState.TAG_CONFIRMATION:
                            return has_open_q
                        if self._s is SynapseRunState.AWAITING_STUDENT:
                            return not has_attempt
                        return False
                    def __eq__(self, other):
                        if hasattr(other, "value"):
                            return self.value == other.value
                        return self.value == other or self._s == other
                    def __hash__(self):
                        return hash(self._s)
                    def __str__(self):
                        return str(self.value)
                    def __repr__(self):
                        return repr(self._s)

                return StateProxy(base_state)
            except Exception:
                return val

    def set_state(self, run_id: str, state: Any) -> None:
        val = state.value if hasattr(state, "value") else str(state)
        self.db.execute(
            "UPDATE runs SET state=?, updated_at=? WHERE id=?",
            (val, time.time(), run_id),
        )

    def meta(self, run_id: str) -> dict[str, Any]:
        row = self.db.execute("SELECT meta_json FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(f"no such run: {run_id}")
        return json.loads(row["meta_json"])

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT id, domain, state, created_at, updated_at FROM runs"
            " ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------ versions

    def append(self, run_id: str, kind: str, payload: dict[str, Any], produced_by: str) -> int:
        """Write a new version. Returns its seq. Never overwrites anything."""
        cur = self.db.execute(
            "INSERT INTO versions(run_id, seq, kind, produced_by, payload_json, created_at)"
            " VALUES (?, (SELECT COALESCE(MAX(seq),0)+1 FROM versions WHERE run_id=?), ?,?,?,?)",
            (run_id, run_id, kind, produced_by, json.dumps(payload), time.time()),
        )
        self.db.execute("UPDATE runs SET updated_at=? WHERE id=?", (time.time(), run_id))
        row = self.db.execute(
            "SELECT MAX(seq) AS s FROM versions WHERE run_id=?", (run_id,)
        ).fetchone()
        _ = cur
        return int(row["s"])

    def latest(self, run_id: str, kind: str) -> dict[str, Any] | None:
        """Current state of one kind of record - what an agent reads before acting."""
        row = self.db.execute(
            "SELECT payload_json FROM versions WHERE run_id=? AND kind=?"
            " ORDER BY seq DESC LIMIT 1",
            (run_id, kind),
        ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def history(self, run_id: str, kind: str) -> list[Version]:
        """Every version of one kind, oldest first. This is the diff a judge wants."""
        rows = self.db.execute(
            "SELECT seq, kind, produced_by, payload_json, created_at FROM versions"
            " WHERE run_id=? AND kind=? ORDER BY seq",
            (run_id, kind),
        ).fetchall()
        return [_to_version(r) for r in rows]

    def replay(self, run_id: str) -> list[Version]:
        """The whole run, in order. Backs the `replay` CLI command."""
        rows = self.db.execute(
            "SELECT seq, kind, produced_by, payload_json, created_at FROM versions"
            " WHERE run_id=? ORDER BY seq",
            (run_id,),
        ).fetchall()
        return [_to_version(r) for r in rows]

    # ------------------------------------------------------------ counters

    def bump(self, run_id: str, name: str, by: float = 1) -> float:
        self.db.execute(
            "INSERT INTO counters(run_id, name, value) VALUES (?,?,?)"
            " ON CONFLICT(run_id, name) DO UPDATE SET value = value + excluded.value",
            (run_id, name, by),
        )
        return self.counter(run_id, name)

    def counter(self, run_id: str, name: str) -> float:
        row = self.db.execute(
            "SELECT value FROM counters WHERE run_id=? AND name=?", (run_id, name)
        ).fetchone()
        return float(row["value"]) if row else 0.0

    def reset_counter(self, run_id: str, name: str) -> None:
        self.db.execute("DELETE FROM counters WHERE run_id=? AND name=?", (run_id, name))

    # ----------------------------------------------------------- questions

    def ask(self, run_id: str, question: str, context: dict[str, Any], timeout_minutes: int) -> str:
        qid, now = new_id("q"), time.time()
        self.db.execute(
            "INSERT INTO questions(id, run_id, question, context_json, asked_at, timeout_at)"
            " VALUES (?,?,?,?,?,?)",
            (qid, run_id, question, json.dumps(context), now, now + timeout_minutes * 60),
        )
        return qid

    def answer(self, question_id: str, answer: str) -> None:
        self.db.execute(
            "UPDATE questions SET answer=?, answered_at=? WHERE id=? AND answer IS NULL",
            (answer, time.time(), question_id),
        )

    def get_question(self, question_id: str) -> Question | None:
        row = self.db.execute("SELECT * FROM questions WHERE id=?", (question_id,)).fetchone()
        return _to_question(row) if row else None

    def open_questions(self, run_id: str | None = None) -> list[Question]:
        sql = "SELECT * FROM questions WHERE answered_at IS NULL"
        args: tuple = ()
        if run_id:
            sql += " AND run_id=?"
            args = (run_id,)
        return [_to_question(r) for r in self.db.execute(sql + " ORDER BY asked_at", args)]

    # -------------------------------------------------------- typed records

    def save_run_record(self, record: Any) -> None:
        """Persist a RunRecord to the store."""
        from .records import RunRecord
        if isinstance(record, RunRecord):
            data = record.model_dump(mode="json")
        elif isinstance(record, dict):
            data = record
        else:
            raise TypeError("record must be a RunRecord or dict")
        run_id = data.get("run_id")
        flow = data.get("flow", "default")
        state = data.get("state", "drafting")
        now = time.time()
        c_at = data.get("created_at")
        created_at = c_at if isinstance(c_at, (int, float)) else now
        row = self.db.execute("SELECT id FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            self.db.execute(
                "INSERT INTO runs(id, domain, state, created_at, updated_at, meta_json)"
                " VALUES (?,?,?,?,?,?)",
                (run_id, flow, state, created_at, now, json.dumps(data)),
            )
        else:
            self.db.execute(
                "UPDATE runs SET domain=?, state=?, updated_at=?, meta_json=? WHERE id=?",
                (flow, state, now, json.dumps(data), run_id),
            )

    def get_run_record(self, run_id: str) -> Any:
        """Retrieve a persisted RunRecord."""
        from .records import RunRecord
        row = self.db.execute("SELECT meta_json FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            return None
        meta = json.loads(row["meta_json"])
        try:
            return RunRecord.model_validate(meta)
        except Exception:
            return meta

    def save_step_record(self, record: Any) -> int:
        """Append an immutable StepRecord into versions history."""
        from .records import StepRecord
        if isinstance(record, StepRecord):
            data = record.model_dump(mode="json")
            step_name = record.step_name
            run_id = record.run_id
        elif isinstance(record, dict):
            data = record
            step_name = data.get("step_name", "step")
            run_id = data.get("run_id", "")
        else:
            raise TypeError("record must be a StepRecord or dict")
        return self.append(run_id, "step_record", data, produced_by=step_name)

    def get_step_records(self, run_id: str) -> list[Any]:
        """Retrieve all immutable StepRecords for a run, oldest first."""
        from .records import StepRecord
        versions = self.history(run_id, "step_record")
        records = []
        for v in versions:
            try:
                records.append(StepRecord.model_validate(v.payload))
            except Exception:
                records.append(v.payload)
        return records

    # ---------------------------------------------------------------- users & auth

    def create_user(
        self,
        role: str,
        username: str,
        password: str | None,
        name: str,
        email: str = "",
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Create and persist a user account with hashed password in SQLite.
        
        Raw passwords and password hashes are never returned.
        """
        import secrets
        from synapse.database import hash_password

        clean_role = role.lower().strip()
        if clean_role not in ("teacher", "student"):
            raise ValueError(f"Invalid user role: {role}")

        clean_user = username.lower().strip()
        clean_email = email.strip().lower() if email else ""
        clean_name = name.strip()
        if not clean_name:
            clean_name = clean_user

        prefix = "tea" if clean_role == "teacher" else "stu"
        uid = user_id or f"{prefix}_{secrets.token_hex(6)}"
        pw_hash = hash_password(password) if password else ""
        now = time.time()

        self.db.execute(
            "INSERT INTO users (id, role, username, email, password_hash, name, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (uid, clean_role, clean_user, clean_email, pw_hash, clean_name, now),
        )

        # If direct student registration, also create a student_credentials record so STU- ID login works
        if clean_role == "student":
            login_id = clean_user.upper() if clean_user.upper().startswith("STU-") else f"STU-{secrets.token_hex(3).upper()}"
            self.db.execute(
                "INSERT OR IGNORE INTO student_credentials (student_id, login_id, is_active, created_at) "
                "VALUES (?, ?, 1, ?)",
                (uid, login_id, now),
            )

        return {
            "id": uid,
            "role": clean_role,
            "username": clean_user,
            "email": clean_email,
            "name": clean_name,
            "created_at": now,
        }

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        """Fetch user by ID. Never returns password_hash."""
        row = self.db.execute(
            "SELECT id, role, username, email, name, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        """Fetch user by username or email. Never returns password_hash."""
        norm = username.lower().strip()
        row = self.db.execute(
            "SELECT id, role, username, email, name, created_at FROM users WHERE username = ? OR email = ?",
            (norm, norm),
        ).fetchone()
        return dict(row) if row else None

    def authenticate_user(self, username_or_email: str, password: str) -> dict[str, Any] | None:
        """Authenticate user against SQLite password_hash using constant-time PBKDF2 comparison."""
        from synapse.database import verify_password
        norm = username_or_email.lower().strip()
        row = self.db.execute(
            "SELECT id, role, username, email, password_hash, name FROM users WHERE username = ? OR email = ?",
            (norm, norm),
        ).fetchone()
        if not row:
            return None
        if not row["password_hash"]:
            return None
        if not verify_password(row["password_hash"], password):
            return None
        return {
            "id": row["id"],
            "role": row["role"],
            "username": row["username"],
            "email": row["email"],
            "name": row["name"],
        }

    def authenticate_student_id(self, login_id: str) -> dict[str, Any] | None:
        """Authenticate student via generated login ID (e.g. STU-XXXXXX). Activates credential in SQLite."""
        from synapse.database import authenticate_student
        return authenticate_student(self.db, login_id)

    # ---------------------------------------------------------------- teacher-student connections

    def get_or_create_teacher_code(self, teacher_id: str) -> str:
        """Get or generate persistent 6-char connection code for teacher."""
        from synapse.database import get_or_create_teacher_code
        return get_or_create_teacher_code(self.db, teacher_id)

    def connect_student_to_teacher(self, student_id: str, code: str) -> dict[str, Any]:
        """Connect student to teacher via code."""
        from synapse.database import connect_student_to_teacher
        return connect_student_to_teacher(self.db, student_id, code)

    def is_student_connected_to_teacher(self, teacher_id: str, student_id: str) -> bool:
        """Verify teacher-student relationship."""
        from synapse.database import is_student_connected_to_teacher
        return is_student_connected_to_teacher(self.db, teacher_id, student_id)

    def list_teacher_connected_students(self, teacher_id: str) -> list[dict[str, Any]]:
        """List students connected to teacher with live performance summaries."""
        from synapse.database import list_teacher_connected_students
        return list_teacher_connected_students(self.db, teacher_id)

    def get_connected_student_performance(self, teacher_id: str, student_id: str) -> dict[str, Any] | None:
        """Get student's detailed performance analytics, verifying teacher authorization."""
        from synapse.database import get_connected_student_performance
        return get_connected_student_performance(self.db, teacher_id, student_id)

    def get_student_connected_teachers(self, student_id: str) -> list[dict[str, Any]]:
        """List teachers connected to student."""
        from synapse.database import get_student_connected_teachers
        return get_student_connected_teachers(self.db, student_id)

    def save_attempt_diagnosis(self, attempt_id: str, diagnosis_data: dict[str, Any]) -> None:
        """Persist authoritative diagnosis directly on attempt record."""
        from synapse.database import save_attempt_diagnosis
        save_attempt_diagnosis(self.db, attempt_id, diagnosis_data)

    def get_attempt_diagnosis(self, attempt_id: str) -> dict[str, Any] | None:
        """Retrieve authoritative diagnosis for attempt."""
        from synapse.database import get_attempt_diagnosis
        return get_attempt_diagnosis(self.db, attempt_id)

    def _init_domain_tables(self) -> None:
        """Ensure domain relational tables (users, classrooms, credentials) exist."""
        try:
            from synapse.database import init_domain_tables
            init_domain_tables(self.db)
        except Exception:
            pass

    def close(self) -> None:
        self.db.close()


def _to_version(r: sqlite3.Row) -> Version:
    return Version(
        seq=int(r["seq"]),
        kind=r["kind"],
        produced_by=r["produced_by"],
        payload=json.loads(r["payload_json"]),
        created_at=float(r["created_at"]),
    )


def _to_question(r: sqlite3.Row) -> Question:
    return Question(
        id=r["id"],
        run_id=r["run_id"],
        question=r["question"],
        context=json.loads(r["context_json"]),
        asked_at=float(r["asked_at"]),
        timeout_at=float(r["timeout_at"]),
        answered_at=float(r["answered_at"]) if r["answered_at"] is not None else None,
        answer=r["answer"],
    )
