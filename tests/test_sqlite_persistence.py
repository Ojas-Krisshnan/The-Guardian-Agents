# tests/test_sqlite_persistence.py
"""
Explicit SQLite persistence and restart verification for Synapse / slice Store.

Verifies:
1. Store instance recreation and data survival (filesystem DB restart simulation)
2. RunRecord and StepRecord persistence & append-only versions
3. Budget counter persistence across Store recreation
4. Human-in-the-loop callback persistence across Store recreation
5. SQLite engine configuration (WAL journal mode, foreign keys)
6. SQLite append-only trigger enforcement (no update, no delete on versions)
"""
import pytest
from pathlib import Path

from slice.store import Store
from slice.records import RunRecord, StepRecord, RunState
from slice.budget import Budget, BudgetExceeded
from slice.config import Settings
from slice import callback


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Provide a clean temporary filesystem database path (not in-memory)."""
    return tmp_path / "persistence_test.db"


def test_sqlite_engine_pragmas(db_path: Path):
    """Verify SQLite WAL mode and foreign key enforcement."""
    s = Store(db_path)
    
    # 1. Journal mode WAL
    cur = s.db.execute("PRAGMA journal_mode")
    mode = cur.fetchone()[0]
    assert mode.lower() == "wal", f"Expected WAL journal mode, got {mode}"
    
    # 2. Foreign keys enabled
    cur = s.db.execute("PRAGMA foreign_keys")
    fk = cur.fetchone()[0]
    assert fk == 1, "Foreign keys must be enabled"
    
    s.close()


def test_restart_persistence_survives_store_recreation(db_path: Path):
    """
    Simulate full process restart:
    1. Create Store, write run and versions.
    2. Close Store.
    3. Create a NEW Store instance pointing at the same database file.
    4. Verify all records, versions, and states exist intact.
    """
    # Phase 1: Initial Store session
    s1 = Store(db_path)
    run_id = s1.create_run("synapse_cycle", {"topic": "Dynamic Programming"})
    s1.set_state(run_id, RunState.DRAFTING)
    
    seq1 = s1.append(run_id, "thesis", {"version": 1, "text": "Base concept"}, produced_by="agent:author")
    seq2 = s1.append(run_id, "thesis", {"version": 2, "text": "Refined concept"}, produced_by="agent:reviewer")
    s1.close()  # Dispose connection completely
    
    # Phase 2: Fresh Store session on same file
    s2 = Store(db_path)
    assert s2.get_state(run_id) is RunState.DRAFTING
    assert s2.meta(run_id)["topic"] == "Dynamic Programming"
    
    latest_thesis = s2.latest(run_id, "thesis")
    assert latest_thesis is not None
    assert latest_thesis["version"] == 2
    assert latest_thesis["text"] == "Refined concept"
    
    hist = s2.history(run_id, "thesis")
    assert len(hist) == 2
    assert hist[0].seq == seq1
    assert hist[1].seq == seq2
    s2.close()


def test_run_record_and_step_record_persistence(db_path: Path):
    """Verify RunRecord and StepRecord persistence and retrieval across Store recreation."""
    s1 = Store(db_path)
    run = RunRecord(flow="curriculum_flow", state="teacher_setup", scope={"classroom_id": "cls_101"})
    s1.save_run_record(run)
    
    step1 = StepRecord(
        run_id=run.run_id,
        step_name="diagnose_misconceptions",
        input_data={"answers": ["A", "B"]},
        output_data={"gap": "Recursion base case missing"},
        state_before="attempt_received",
        state_after="diagnosing",
    )
    s1.save_step_record(step1)
    s1.close()
    
    # Recreate Store
    s2 = Store(db_path)
    loaded_run = s2.get_run_record(run.run_id)
    assert loaded_run is not None
    assert loaded_run.flow == "curriculum_flow"
    assert loaded_run.state == "teacher_setup"
    assert loaded_run.scope.get("classroom_id") == "cls_101"
    
    loaded_steps = s2.get_step_records(run.run_id)
    assert len(loaded_steps) == 1
    assert loaded_steps[0].step_name == "diagnose_misconceptions"
    assert loaded_steps[0].state_before == "attempt_received"
    assert loaded_steps[0].state_after == "diagnosing"
    assert loaded_steps[0].output_data["gap"] == "Recursion base case missing"
    s2.close()


def test_budget_counters_survive_recreation(db_path: Path):
    """Verify DB-backed budget counters and fences survive Store recreation."""
    s1 = Store(db_path)
    run_id = s1.create_run("budget_test")
    cfg = Settings(
        api_key="mock",
        model="mock-model",
        fallback_model="mock-fallback",
        escalation_model="mock-esc",
        max_tokens=100,
        max_tokens_per_run=5000,
        max_attempts_per_step=3,
        expert_timeout_minutes=45,
        langfuse_public="",
        langfuse_secret="",
        langfuse_host="",
    )
    b1 = Budget(s1, run_id, cfg)
    b1.record_tokens(1500)
    assert b1.attempt("diagnose") == 1
    assert b1.attempt("diagnose") == 2
    s1.close()
    
    # Reopen in new Store instance
    s2 = Store(db_path)
    b2 = Budget(s2, run_id, cfg)
    assert b2.tokens_used() == 1500
    assert b2.tokens_remaining() == 3500
    assert b2.attempts("diagnose") == 2
    
    # Continuing budget tracking
    assert b2.attempt("diagnose") == 3
    with pytest.raises(BudgetExceeded):
        b2.attempt("diagnose")
    s2.close()


def test_callback_persistence_and_recovery(db_path: Path):
    """Verify callback questions/answers survive Store recreation and state machine suspension."""
    cfg = Settings(
        api_key="mock",
        model="mock-model",
        fallback_model="mock-fallback",
        escalation_model="mock-esc",
        max_tokens=100,
        max_tokens_per_run=5000,
        max_attempts_per_step=3,
        expert_timeout_minutes=60,
        langfuse_public="",
        langfuse_secret="",
        langfuse_host="",
    )
    s1 = Store(db_path)
    run_id = s1.create_run("callback_run")
    
    # Ask human expert
    qid = callback.ask(
        s1,
        run_id,
        "Is this prerequisite chain valid?",
        context={"concept": "Trees", "resume_state": "probing"},
        settings=cfg,
    )
    assert s1.get_state(run_id) is RunState.AWAITING_EXPERT
    s1.close()
    
    # Store recreation: process exited and restarts
    s2 = Store(db_path)
    assert s2.get_state(run_id) is RunState.AWAITING_EXPERT
    pending_qs = callback.pending(s2, run_id)
    assert len(pending_qs) == 1
    assert pending_qs[0].id == qid
    assert pending_qs[0].question == "Is this prerequisite chain valid?"
    
    # Answer the question
    resumed_run = callback.answer(s2, qid, "Yes, validated by curriculum team.", who="faculty_lead")
    assert resumed_run == run_id
    assert s2.get_state(run_id) is RunState.PROBING
    assert callback.pending(s2, run_id) == []
    
    latest_answer = s2.latest(run_id, "expert_answer")
    assert latest_answer is not None
    assert latest_answer["answer"] == "Yes, validated by curriculum team."
    assert latest_answer["who"] == "faculty_lead"
    s2.close()


def test_append_only_triggers_enforce_immutability(db_path: Path):
    """Verify SQLite triggers prevent UPDATE and DELETE on the versions table."""
    s = Store(db_path)
    run_id = s.create_run("immutable_test")
    s.append(run_id, "evidence", {"score": 95}, produced_by="grader")
    
    with pytest.raises(Exception, match="append-only"):
        s.db.execute("UPDATE versions SET payload_json='{}' WHERE run_id=?", (run_id,))
        
    with pytest.raises(Exception, match="append-only"):
        s.db.execute("DELETE FROM versions WHERE run_id=?", (run_id,))
        
    s.close()
