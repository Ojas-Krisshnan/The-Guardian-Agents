"""
SYNAPSE RUNTIME SERVICE — Orchestration service, per-run locking, cycle management.
Authoritative contract: Contracts.md Sections A.5, A.6, C.1, C.3, D.2, D.5.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from slice import callback, runner
from slice.config import Settings
from slice.records import Question
from slice.store import Store
from synapse.runtime.flow import SYNAPSE_FLOW, SynapseFlow
from synapse.state_machine import RunState


class SubmitAttemptResponse(BaseModel):
    run_id: str
    attempt: Optional[Any] = None
    diagnosis: Optional[Any] = None
    note: Optional[Any] = None
    review: Optional[Any] = None


class RunStatusResponse(BaseModel):
    run_id: str
    state: RunState
    current_cycle: int
    revision_count: int
    model_call_count: int
    error: Optional[str] = None


class RuntimeService:
    """Core runtime service managing Synapse runs, cycle boundaries, and concurrency."""

    def __init__(
        self,
        store: Store | None = None,
        settings: Settings | None = None,
        flow: SynapseFlow | None = None,
    ):
        self._initial_store = store or Store("synapse.db")
        self._main_thread_id = threading.get_ident()
        self.settings = settings or Settings()
        self.flow = flow or SYNAPSE_FLOW
        self._locks: dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()
        self._local = threading.local()

    @property
    def store(self) -> Store:
        if threading.get_ident() == self._main_thread_id:
            return self._initial_store
        if not hasattr(self._local, "store"):
            self._local.store = Store(self._initial_store.path)
        return self._local.store

    @store.setter
    def store(self, value: Store) -> None:
        self._initial_store = value
        self._main_thread_id = threading.get_ident()
        if hasattr(self._local, "store"):
            delattr(self._local, "store")

    def _get_lock(self, run_id: str) -> threading.Lock:
        with self._global_lock:
            if run_id not in self._locks:
                self._locks[run_id] = threading.Lock()
            return self._locks[run_id]

    def _advance_locked(self, run_id: str) -> RunState:
        res = runner.advance(self.store, run_id, self.flow, self.settings)
        if isinstance(res, RunState):
            st = res
        else:
            try:
                st = RunState(res)
            except (ValueError, TypeError):
                st = res
        if st is RunState.COMPLETE:
            meta = self.store.meta(run_id)
            if not meta.get("completed_at"):
                self.store.update_meta(
                    run_id, {"completed_at": datetime.now(timezone.utc).isoformat()}
                )
        return st

    def advance(self, run_id: str) -> RunState:
        """Advance a run to its next terminal or parked state under lock."""
        lock = self._get_lock(run_id)
        with lock:
            return self._advance_locked(run_id)

    def start_teacher_run(
        self,
        markdown: str,
        concept_name: str,
        teacher_id: str,
    ) -> str:
        """Create and begin a teacher-initiated setup run."""
        scope = {
            "concept_name": concept_name,
            "teacher_id": teacher_id,
            "cycle": 1,
        }
        run_id = self.store.create_run(
            domain=self.flow.name,
            meta={"scope": scope},
            initial_state=RunState.TEACHER_SETUP,
        )
        self.store.append(
            run_id,
            "canonical_note",
            {"markdown": markdown, "concept_name": concept_name, "teacher_id": teacher_id},
            produced_by=teacher_id,
        )
        self.advance(run_id)
        return run_id

    def submit_attempt(
        self,
        run_id: str,
        student_id: str,
        test_id: str,
        answers: dict[str, Any] | list[Any],
    ) -> SubmitAttemptResponse:
        """Submit a student's test answers and resume the diagnostic pipeline.

        Precondition: run state must be AWAITING_STUDENT.
        """
        lock = self._get_lock(run_id)
        with lock:
            current_state = self.store.get_state(run_id, state_type=RunState)
            if current_state != RunState.AWAITING_STUDENT:
                raise ValueError(
                    f"Cannot submit attempt: run {run_id} is in state {current_state}, "
                    f"expected {RunState.AWAITING_STUDENT}"
                )

            meta = self.store.meta(run_id)
            scope = dict(meta.get("scope", {}))
            scope["student_id"] = student_id
            self.store.update_meta(run_id, {"scope": scope})

            test_dict = self.store.latest(run_id, "test")
            concept_id = scope.get("concept_id", "")
            score = 0
            total = 1
            if test_dict:
                concept_id = test_dict.get("concept_id", concept_id)
                questions = test_dict.get("questions", [])
                total = max(len(questions), 1)
                ans_map = answers if isinstance(answers, dict) else {
                    a.get("question_id"): a.get("selected_option")
                    for a in answers if isinstance(a, dict)
                }
                for q in questions:
                    qid = q.get("id")
                    if qid in ans_map and ans_map[qid] == q.get("correct_answer"):
                        score += 1
            else:
                ans_map = answers if isinstance(answers, dict) else {}

            self.store.append(
                run_id,
                "attempt",
                {
                    "student_id": student_id,
                    "test_id": test_id,
                    "concept_id": concept_id,
                    "answers": ans_map,
                    "score": score,
                    "total": total,
                    "submitted_at": datetime.now(timezone.utc).isoformat(),
                },
                produced_by=student_id,
            )

            self.store.set_state(run_id, RunState.ATTEMPT_RECEIVED)
            self._advance_locked(run_id)
            return SubmitAttemptResponse(
                run_id=run_id,
                attempt=self.store.latest(run_id, "attempt"),
                diagnosis=self.store.latest(run_id, "diagnosis"),
                note=self.store.latest(run_id, "note_version") or self.store.latest(run_id, "note_candidate"),
                review=self.store.latest(run_id, "review"),
            )

    def start_next_cycle(self, run_id: str) -> RunState:
        """Transition a completed run into the next learning cycle.

        Precondition: run state must be COMPLETE.
        """
        lock = self._get_lock(run_id)
        with lock:
            current_state = self.store.get_state(run_id, state_type=RunState)
            if current_state != RunState.COMPLETE:
                raise ValueError(
                    f"Cannot start next cycle: run {run_id} is in state {current_state}, "
                    f"expected {RunState.COMPLETE}"
                )

            meta = self.store.meta(run_id)
            scope = dict(meta.get("scope", {}))
            scope["cycle"] = int(scope.get("cycle", 1)) + 1
            self.store.set_state(run_id, RunState.AWAITING_STUDENT)
            self.store.update_meta(run_id, {"scope": scope})
            return RunState.AWAITING_STUDENT

    def get_run_status(self, run_id: str) -> RunStatusResponse:
        """Get the current state and metadata for a run."""
        st = self.store.get_state(run_id, state_type=RunState)
        try:
            state_enum = RunState(st)
        except (ValueError, TypeError):
            state_enum = st

        meta = self.store.meta(run_id)
        scope = meta.get("scope", {})
        current_cycle = int(scope.get("cycle", 1))
        rev_count = count_revisions(self.store, run_id, cycle=current_cycle)
        model_call_count = int(meta.get("model_call_count", 0))

        return RunStatusResponse(
            run_id=run_id,
            state=state_enum,
            current_cycle=current_cycle,
            revision_count=rev_count,
            model_call_count=model_call_count,
            error=meta.get("error"),
        )

    def sweep_expired(self) -> list[str]:
        """Sweep and expire unanswered questions across all runs, advancing resumed runs.
        Returns the list of resumed run_id strings.
        """
        expired = callback.sweep(self.store)
        resumed_run_ids: list[str] = []
        for q in expired:
            if q.run_id not in resumed_run_ids:
                resumed_run_ids.append(q.run_id)
        for rid in resumed_run_ids:
            self.advance(rid)
        return resumed_run_ids


# ----------------------------------------------------------------------
# Default Service Instance & Public Function Interface
# ----------------------------------------------------------------------

_default_service: RuntimeService | None = None


def get_service() -> RuntimeService:
    global _default_service
    if _default_service is None:
        _default_service = RuntimeService()
    return _default_service


def set_service(service: RuntimeService) -> None:
    global _default_service
    _default_service = service


def start_teacher_run(markdown: str, concept_name: str, teacher_id: str) -> str:
    return get_service().start_teacher_run(markdown, concept_name, teacher_id)


def submit_attempt(
    run_id: str,
    student_id: str,
    test_id: str,
    answers: dict[str, Any] | list[Any],
) -> SubmitAttemptResponse:
    return get_service().submit_attempt(run_id, student_id, test_id, answers)


def get_run_status(run_id: str) -> RunStatusResponse:
    return get_service().get_run_status(run_id)


def sweep_expired() -> list[str]:
    return get_service().sweep_expired()


def advance(run_id: str) -> RunState:
    return get_service().advance(run_id)


def start_next_cycle(run_id: str) -> RunState:
    return get_service().start_next_cycle(run_id)


def count_revisions(store: Store, run_id: str, cycle: int | None = None) -> int:
    """Derive revisions count from review record history for the cycle."""
    reviews = store.history(run_id, "review")
    if cycle is None:
        run_rec = store.get_run(run_id)
        cycle = run_rec.scope.get("cycle", 1)
    return sum(
        1 for r in reviews
        if r.payload.get("status") == "failed" and r.payload.get("cycle", 1) == cycle
    )
