"""
Tests for synapse.runtime.service and synapse.runtime.flow.
Verifies cycle boundaries, per-run locking, and state-machine advancement.
"""
import threading
import time
from pathlib import Path

import pytest

from slice.config import Settings
from slice.store import Store
from synapse.runtime.flow import SynapseFlow, build_synapse_flow
from synapse.runtime.service import RuntimeService, count_revisions
from synapse.state_machine import RunState

S = Settings(
    api_key="test",
    model="test-model",
    fallback_model="test-fallback",
    escalation_model="test-esc",
    max_tokens=100,
    max_tokens_per_run=1000,
    max_attempts_per_step=3,
    expert_timeout_minutes=45,
    langfuse_public="",
    langfuse_secret="",
    langfuse_host="",
)


@pytest.fixture
def test_svc(tmp_path):
    store = Store(tmp_path / "test_synapse.db")
    flow = build_synapse_flow()
    return RuntimeService(store=store, settings=S, flow=flow)


def test_start_teacher_run_creates_valid_run_and_status(test_svc):
    # 1. start_teacher_run creates a valid Synapse run
    run_id = test_svc.start_teacher_run(
        markdown="# Photosynthesis",
        concept_name="Photosynthesis",
        teacher_id="t_001",
    )
    assert run_id is not None

    # 2. state is correct: teacher_setup transitions to tag_confirmation (parked)
    status = test_svc.get_run_status(run_id)
    assert status.run_id == run_id
    assert status.state is RunState.TAG_CONFIRMATION
    assert status.current_cycle == 1
    assert status.revision_count == 0


def test_submit_attempt_rejects_non_awaiting_student(test_svc):
    # 4. submit_attempt rejects non-AWAITING_STUDENT runs
    run_id = test_svc.start_teacher_run("md", "c", "t")
    # run is currently at TAG_CONFIRMATION
    with pytest.raises(ValueError, match="is in state"):
        test_svc.submit_attempt(
            run_id=run_id,
            student_id="s_123",
            test_id="test_01",
            answers={"q1": "a"},
        )


def test_submit_attempt_on_awaiting_student_records_and_advances(test_svc):
    # 5. submit_attempt on AWAITING_STUDENT records the attempt and advances
    run_id = test_svc.store.create_run(
        "synapse",
        meta={"scope": {"cycle": 1, "concept_name": "Photosynthesis"}},
        initial_state=RunState.AWAITING_STUDENT,
    )
    resp = test_svc.submit_attempt(
        run_id=run_id,
        student_id="s_123",
        test_id="test_01",
        answers={"q1": "a"},
    )
    assert resp.run_id == run_id
    assert resp.attempt is not None
    assert resp.attempt["student_id"] == "s_123"

    # Default handlers advance attempt_received -> diagnosing -> tailoring -> reviewing -> note_saved -> analysing -> aggregating -> complete
    status = test_svc.get_run_status(run_id)
    assert status.state is RunState.COMPLETE


def test_complete_does_not_automatically_become_awaiting_student(test_svc):
    # 7. COMPLETE does not automatically become AWAITING_STUDENT during runner.advance()
    run_id = test_svc.store.create_run(
        "synapse",
        meta={"scope": {"cycle": 1}},
        initial_state=RunState.COMPLETE,
    )
    adv_state = test_svc.advance(run_id)
    assert adv_state is RunState.COMPLETE
    assert test_svc.store.get_state(run_id, state_type=RunState) is RunState.COMPLETE


def test_start_next_cycle_transitions_and_increments_cycle(test_svc):
    # 8. start_next_cycle changes COMPLETE -> AWAITING_STUDENT
    # 9. start_next_cycle increments cycle exactly once
    run_id = test_svc.store.create_run(
        "synapse",
        meta={"scope": {"cycle": 1}},
        initial_state=RunState.COMPLETE,
    )
    new_state = test_svc.start_next_cycle(run_id)
    assert new_state is RunState.AWAITING_STUDENT
    assert test_svc.store.get_state(run_id, state_type=RunState) is RunState.AWAITING_STUDENT

    status = test_svc.get_run_status(run_id)
    assert status.current_cycle == 2


def test_start_next_cycle_rejects_non_complete(test_svc):
    # 10. start_next_cycle rejects a non-COMPLETE run
    run_id = test_svc.store.create_run(
        "synapse",
        meta={"scope": {"cycle": 1}},
        initial_state=RunState.AWAITING_STUDENT,
    )
    with pytest.raises(ValueError, match="expected"):
        test_svc.start_next_cycle(run_id)


def test_completed_at_persists_across_store_reopen(tmp_path):
    # 11. completed_at persists across Store reopening/restart
    db_path = tmp_path / "synapse_persist.db"
    store1 = Store(db_path)
    flow = build_synapse_flow()
    svc1 = RuntimeService(store=store1, settings=S, flow=flow)

    run_id = store1.create_run(
        "synapse",
        meta={"scope": {"cycle": 1}},
        initial_state=RunState.AGGREGATING,
    )
    state = svc1.advance(run_id)
    assert state is RunState.COMPLETE

    meta1 = store1.meta(run_id)
    assert meta1.get("completed_at") is not None

    # Re-open database with a new Store instance
    store2 = Store(db_path)
    meta2 = store2.meta(run_id)
    assert meta2.get("completed_at") == meta1.get("completed_at")
    assert store2.get_state(run_id, state_type=RunState) is RunState.COMPLETE


def test_per_run_lock_prevents_concurrent_conflicts(test_svc):
    # 6. per-run lock prevents concurrent conflicting advancement
    run_id = test_svc.store.create_run(
        "synapse",
        meta={"scope": {"cycle": 1}},
        initial_state=RunState.NOTE_SAVED,
    )

    lock = test_svc._get_lock(run_id)
    assert not lock.locked()

    # While held by the active run advancement, another thread cannot acquire it concurrently
    acquired = []
    with lock:
        assert lock.locked()
        t = threading.Thread(target=lambda: acquired.append(lock.acquire(blocking=False)))
        t.start()
        t.join()

    assert acquired == [False]

    # After release, advance acquires lock and runs to completion
    assert test_svc.advance(run_id) is RunState.COMPLETE
    assert not lock.locked()


def test_revision_counting_from_history(test_svc):
    # 12. revision counting agrees with the contract's history/DB-counter requirements
    run_id = test_svc.store.create_run(
        "synapse",
        meta={"scope": {"cycle": 1}},
        initial_state=RunState.REVIEWING,
    )
    assert count_revisions(test_svc.store, run_id, cycle=1) == 0

    test_svc.store.append(
        run_id, "review", {"status": "failed", "cycle": 1}, produced_by="reviewer"
    )
    assert count_revisions(test_svc.store, run_id, cycle=1) == 1

    test_svc.store.append(
        run_id, "review", {"status": "failed", "cycle": 1}, produced_by="reviewer"
    )
    assert count_revisions(test_svc.store, run_id, cycle=1) == 2

    test_svc.store.append(
        run_id, "review", {"status": "passed", "cycle": 1}, produced_by="reviewer"
    )
    assert count_revisions(test_svc.store, run_id, cycle=1) == 2

    # Cycle 2 review failure does not count for cycle 1
    test_svc.store.append(
        run_id, "review", {"status": "failed", "cycle": 2}, produced_by="reviewer"
    )
    assert count_revisions(test_svc.store, run_id, cycle=1) == 2
    assert count_revisions(test_svc.store, run_id, cycle=2) == 1


def test_full_flow_with_stubs_and_revision_loop(tmp_path):
    from slice import callback
    from synapse.runtime.stub import build_stubbed_synapse_flow

    store = Store(tmp_path / "stub_test.db")
    flow = build_stubbed_synapse_flow(review_fails=True)
    svc = RuntimeService(store=store, settings=S, flow=flow)

    # 1. Teacher starts run -> teacher_setup -> tag_confirmation (parked)
    run_id = svc.start_teacher_run("Note on Photosynthesis", "Photosynthesis", "t_1")
    assert svc.get_run_status(run_id).state is RunState.TAG_CONFIRMATION

    # 2. Teacher answers confirmation question -> resumes to test_ready -> awaiting_student
    open_qs = callback.pending(store, run_id)
    assert len(open_qs) == 1
    callback.answer(store, open_qs[0].id, "All concepts look great", who="teacher")
    assert svc.advance(run_id) is RunState.AWAITING_STUDENT

    # 3. Student submits attempt -> attempt_received -> diagnosing -> tailoring -> reviewing (fails once, returns to tailoring) -> note_saved -> analysing -> aggregating -> COMPLETE
    resp = svc.submit_attempt(
        run_id=run_id,
        student_id="s_100",
        test_id="test_01",
        answers={"q1": "Thylakoid membrane"},
    )
    assert resp.run_id == run_id
    assert resp.attempt is not None
    assert resp.note is not None
    status = svc.get_run_status(run_id)
    assert status.state is RunState.COMPLETE
    assert status.current_cycle == 1
    assert status.revision_count == 1

    # Check revision history: exactly 1 failed review and 1 passed review recorded
    revs = store.history(run_id, "review")
    assert len(revs) == 2
    assert revs[0].payload["status"] == "failed"
    assert revs[1].payload["status"] == "passed"
    assert count_revisions(store, run_id, cycle=1) == 1

    # 4. Cycle 2 transition: start_next_cycle -> AWAITING_STUDENT
    next_state = svc.start_next_cycle(run_id)
    assert next_state is RunState.AWAITING_STUDENT
    assert svc.get_run_status(run_id).current_cycle == 2


def test_sweep_expired_returns_resumed_run_ids(tmp_path):
    from slice import callback
    S0 = Settings(**{**S.__dict__, "expert_timeout_minutes": 0})
    store = Store(tmp_path / "sweep_test.db")
    flow = build_synapse_flow()
    svc = RuntimeService(store=store, settings=S0, flow=flow)

    run1 = store.create_run(
        "synapse",
        meta={"scope": {"cycle": 1}},
        initial_state=RunState.TEACHER_SETUP,
    )
    callback.ask(
        store, run1, "Question 1",
        {"park_state": RunState.TAG_CONFIRMATION.value, "resume_state": RunState.TEST_READY.value},
        S0, park_state=RunState.TAG_CONFIRMATION, resume_state=RunState.TEST_READY,
    )
    assert store.get_state(run1, state_type=RunState) is RunState.TAG_CONFIRMATION

    resumed = svc.sweep_expired()
    assert isinstance(resumed, list)
    assert all(isinstance(x, str) for x in resumed)
    assert run1 in resumed
    assert store.get_state(run1, state_type=RunState) is RunState.AWAITING_STUDENT


