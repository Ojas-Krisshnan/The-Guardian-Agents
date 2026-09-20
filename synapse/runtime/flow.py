"""
SYNAPSE FLOW — Flow assembly and Person 1 runtime handlers.
Authoritative contract: Contracts.md Sections A.5, C.3, D.2, D.5.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from slice.runner import Context
from synapse.state_machine import RunState


# Handler signature: Callable[[Context], RunState]
Handler = Callable[[Context], RunState]


# ----------------------------------------------------------------------
# Person 1 (Runtime) Handlers
# ----------------------------------------------------------------------

def handle_awaiting_student(ctx: Context) -> RunState:
    """Parked waiting state for student test submission.
    Must not advance without an attempt.
    """
    attempt = ctx.latest("attempt")
    if attempt is not None:
        return RunState.ATTEMPT_RECEIVED
    return RunState.AWAITING_STUDENT


def handle_attempt_received(ctx: Context) -> RunState:
    """Invoked when an attempt has been received. Transitions to diagnosing."""
    return RunState.DIAGNOSING


def handle_note_saved(ctx: Context) -> RunState:
    """Invoked after a tailored note candidate is approved or reaches revision limit.
    Promotes note candidate to final NoteVersion and transitions to analysing.
    """
    candidate_dict = ctx.latest(RecordKind.NOTE_CANDIDATE.value)
    diag_dict = ctx.latest(RecordKind.DIAGNOSIS.value)
    review_dict = ctx.latest(RecordKind.REVIEW.value)

    if candidate_dict:
        scope = ctx.store.meta(ctx.run_id).get("scope", {})
        cand_data = dict(candidate_dict)
        if "student_id" not in cand_data:
            cand_data["student_id"] = scope.get("student_id", "student_01")
        if "concept_id" not in cand_data:
            cand_data["concept_id"] = scope.get("concept_id", "default_concept")

        note_ver = NoteVersion.model_validate(cand_data)
        if diag_dict:
            note_ver.diagnosis_id = diag_dict.get("id")
        if review_dict:
            note_ver.review_id = review_dict.get("id")

        ctx.append(
            RecordKind.NOTE_VERSION.value,
            note_ver.model_dump(mode="json"),
            produced_by="runtime:note_saver",
        )

    return RunState.ANALYSING


def handle_complete(ctx: Context) -> RunState:
    """Terminal state for the current cycle's runner.advance() invocation.
    Persists completion metadata and stops. Does NOT auto-transition to awaiting_student.
    """
    try:
        ctx.store.update_meta(ctx.run_id, {"completed_at": datetime.now(timezone.utc).isoformat()})
    except Exception:
        pass
    return RunState.COMPLETE


# ----------------------------------------------------------------------
# Domain Handlers from Person 2 (Agents), Person 3 (Curriculum), Person 4 (Analytics)
# ----------------------------------------------------------------------
from synapse.agents.flow import (
    handle_diagnosing,
    handle_reviewing,
    handle_tailoring,
)
from synapse.analytics.flow import (
    handle_aggregating,
    handle_analysing,
)
from synapse.curriculum.flow import (
    handle_tag_confirmation,
    handle_teacher_setup,
    handle_test_ready,
)
from synapse.schemas import NoteVersion, RecordKind


DEFAULT_HANDLERS: dict[RunState, Handler] = {
    RunState.TEACHER_SETUP: handle_teacher_setup,
    RunState.TAG_CONFIRMATION: handle_tag_confirmation,
    RunState.TEST_READY: handle_test_ready,
    RunState.AWAITING_STUDENT: handle_awaiting_student,
    RunState.ATTEMPT_RECEIVED: handle_attempt_received,
    RunState.DIAGNOSING: handle_diagnosing,
    RunState.TAILORING: handle_tailoring,
    RunState.REVIEWING: handle_reviewing,
    RunState.NOTE_SAVED: handle_note_saved,
    RunState.ANALYSING: handle_analysing,
    RunState.AGGREGATING: handle_aggregating,
    RunState.COMPLETE: handle_complete,
}


class SynapseFlow:
    """Flow implementing the 12-state Synapse domain for slice.runner."""

    name: str = "synapse"
    state_type = RunState

    def __init__(self, handlers: dict[RunState, Handler] | None = None):
        self.handlers = dict(DEFAULT_HANDLERS)
        if handlers:
            self.handlers.update(handlers)

    def register(self, state: RunState, handler: Handler) -> None:
        self.handlers[state] = handler


def build_synapse_flow(handler_overrides: dict[RunState, Handler] | None = None) -> SynapseFlow:
    """Factory creating a SynapseFlow with optional custom/stub handlers."""
    return SynapseFlow(handlers=handler_overrides)


SYNAPSE_FLOW: SynapseFlow = build_synapse_flow()
